#!/usr/bin/env python3
"""
snowflake_enrich.py — Build data/snowflake_enrichment.json from TRACKER_ENRICHED.

Reads all of TRACKER_ENRICHED (~2K rows, built by ops-hub/scripts/model_tracker.py)
via the headless service account and produces two output sections:

  articles  — per-article O&O traffic, IAB topic, similarity, median comparison
              keyed by normalized published URL
  authors   — per-author aggregates broken down by publication and IAB topic,
              computed from all articles in TRACKER_ENRICHED for that author

generate_site.py loads this file to power per-author pub breakdowns, topic-stratified
formula analysis, and richer editorial playbooks.

Authentication: RSA key-pair (headless — same auth as model_tracker.py)

Env vars (optional):
    SNOWFLAKE_PRIVATE_KEY_PATH   path to RSA private key (.p8 file)

Usage:
    python3 snowflake_enrich.py [--out FILE]
"""

import argparse
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SF_ACCOUNT  = "wvb49304-mcclatchy_eval"
SF_USER     = "GROWTH_AND_STRATEGY_SERVICE_USER"
SF_KEY_PATH = os.getenv(
    "SNOWFLAKE_PRIVATE_KEY_PATH",
    str(Path.home() / ".credentials" / "growth_strategy_service_rsa_key.p8"),
)

DEFAULT_OUT = "data/snowflake_enrichment.json"

FETCH_SQL = """
SELECT
    LOWER(RTRIM(
        CASE WHEN PUBLISHED_URL LIKE '%://amp.%'
             THEN REPLACE(PUBLISHED_URL, '://amp.', '://www.')
             ELSE PUBLISHED_URL END,
        '/'))                       AS url_norm,
    PUBLISHED_URL,
    AUTHOR,
    HEADLINE,
    article_domain                  AS domain,
    word_count,
    primary_iab_topic               AS iab_topic,
    total_pvs,
    search_pvs,
    social_pvs,
    direct_pvs,
    applenews_pvs,
    smartnews_pvs,
    newsbreak_pvs,
    subscriber_pvs,
    article_vs_co_median,
    is_hit,
    cluster_id,
    cluster_avg_sim_desc,
    cluster_total_pvs,
    cluster_vs_co_median,
    cluster_hit_rate
FROM MCC_PRESENTATION.CONTENT_SCALING_AGENT.TRACKER_ENRICHED
WHERE PUBLISHED_URL IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY url_norm ORDER BY total_pvs DESC NULLS LAST) = 1
"""

COLS = [
    "url_norm", "published_url", "author", "headline", "domain", "word_count",
    "iab_topic", "total_pvs", "search_pvs", "social_pvs", "direct_pvs",
    "applenews_pvs", "smartnews_pvs", "newsbreak_pvs", "subscriber_pvs",
    "article_vs_co_median", "is_hit",
    "cluster_id", "cluster_avg_sim_desc", "cluster_total_pvs",
    "cluster_vs_co_median", "cluster_hit_rate",
]


def get_conn():
    from cryptography.hazmat.primitives.serialization import (
        load_pem_private_key, Encoding, PrivateFormat, NoEncryption,
    )
    import snowflake.connector

    raw = Path(SF_KEY_PATH).read_bytes()
    key = load_pem_private_key(raw, password=None)
    der = key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    return snowflake.connector.connect(
        account=SF_ACCOUNT,
        user=SF_USER,
        private_key=der,
        warehouse="GROWTH_AND_STRATEGY_ROLE_WH",
        role="GROWTH_AND_STRATEGY_ROLE",
    )


def _f(v):
    """Coerce Decimal/None → float or None."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    """Coerce to int or None."""
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def fetch_rows(cur):
    cur.execute(FETCH_SQL)
    rows = cur.fetchall()
    return [dict(zip(COLS, r)) for r in rows]


def build_articles(rows):
    """Per-article enrichment dict keyed by normalized URL."""
    articles = {}
    for r in rows:
        key = r["url_norm"]
        if not key:
            continue
        articles[key] = {
            "author":               r["author"] or "",
            "headline":             r["headline"] or "",
            "domain":               r["domain"] or "",
            "word_count":           _i(r["word_count"]),
            "iab_topic":            r["iab_topic"] or None,
            "total_pvs":            _i(r["total_pvs"]),
            "search_pvs":           _i(r["search_pvs"]),
            "social_pvs":           _i(r["social_pvs"]),
            "direct_pvs":           _i(r["direct_pvs"]),
            "applenews_pvs":        _i(r["applenews_pvs"]),
            "smartnews_pvs":        _i(r["smartnews_pvs"]),
            "newsbreak_pvs":        _i(r["newsbreak_pvs"]),
            "subscriber_pvs":       _i(r["subscriber_pvs"]),
            "article_vs_co_median": _f(r["article_vs_co_median"]),
            "is_hit":               _i(r["is_hit"]),
            "cluster_id":           r["cluster_id"] or None,
            "cluster_avg_sim_desc": _f(r["cluster_avg_sim_desc"]),
            "cluster_total_pvs":    _i(r["cluster_total_pvs"]),
            "cluster_vs_co_median": _f(r["cluster_vs_co_median"]),
            "cluster_hit_rate":     _f(r["cluster_hit_rate"]),
        }
    return articles


def build_authors(rows):
    """
    Per-author aggregates computed from all TRACKER_ENRICHED rows for that author.

    Structure:
        author_name → {
            total_articles, total_pvs, avg_pvs, hit_rate,
            by_pub:   { domain → {articles, total_pvs, avg_pvs, hits, hit_rate} }
            by_topic: { iab_topic → {articles, total_pvs, avg_pvs, hits, hit_rate} }
        }
    """
    # Accumulate raw counts per author → (pub|topic) → bucket
    # bucket = [total_pvs, article_count, hit_count]
    Author = lambda: {
        "pvs":     0,
        "n":       0,
        "hits":    0,
        "by_pub":   defaultdict(lambda: [0, 0, 0]),
        "by_topic": defaultdict(lambda: [0, 0, 0]),
    }
    acc = defaultdict(Author)

    for r in rows:
        author = (r["author"] or "").strip()
        if not author:
            continue
        pvs   = _i(r["total_pvs"]) or 0
        hit   = _i(r["is_hit"])
        pub   = r["domain"] or "unknown"
        topic = r["iab_topic"] or "Unknown"

        a = acc[author]
        a["pvs"]  += pvs
        a["n"]    += 1
        if hit is not None:
            a["hits"] += hit

        a["by_pub"][pub][0]   += pvs
        a["by_pub"][pub][1]   += 1
        if hit is not None:
            a["by_pub"][pub][2] += hit

        a["by_topic"][topic][0]   += pvs
        a["by_topic"][topic][1]   += 1
        if hit is not None:
            a["by_topic"][topic][2] += hit

    def _bucket(raw_dict):
        out = {}
        for key, (pvs, n, hits) in raw_dict.items():
            out[key] = {
                "articles":  n,
                "total_pvs": pvs,
                "avg_pvs":   round(pvs / n) if n else None,
                "hit_rate":  round(hits / n, 3) if n else None,
            }
        return out

    authors = {}
    for author, a in acc.items():
        n = a["n"]
        authors[author] = {
            "total_articles": n,
            "total_pvs":      a["pvs"],
            "avg_pvs":        round(a["pvs"] / n) if n else None,
            "hit_rate":       round(a["hits"] / n, 3) if n else None,
            "by_pub":         _bucket(a["by_pub"]),
            "by_topic":       _bucket(a["by_topic"]),
        }

    return authors


def main():
    parser = argparse.ArgumentParser(description="Build snowflake_enrichment.json")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help=f"Output JSON path (default: {DEFAULT_OUT})")
    args = parser.parse_args()

    print("Connecting to Snowflake…")
    conn = get_conn()
    cur  = conn.cursor()
    print("Connected.")

    print("Fetching TRACKER_ENRICHED…")
    rows = fetch_rows(cur)
    print(f"  {len(rows)} rows fetched.")

    cur.close()
    conn.close()

    print("Building article index…")
    articles = build_articles(rows)
    print(f"  {len(articles)} articles indexed.")

    print("Building author aggregates…")
    authors = build_authors(rows)
    print(f"  {len(authors)} authors indexed.")

    out = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "row_count": len(rows),
        "articles":  articles,
        "authors":   authors,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, default=str))
    size_kb = out_path.stat().st_size // 1024
    print(f"\nWrote {args.out} ({size_kb} KB, {len(articles)} articles, {len(authors)} authors).")


if __name__ == "__main__":
    main()

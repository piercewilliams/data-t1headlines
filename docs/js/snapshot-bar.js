// T1 Headlines — Snapshot version bar
// Renders a row of version buttons at the bottom of the page.
// Clicking a version opens it in a new tab (full re-render) and offers passkey-gated restore.

(function () {
  'use strict';

  // Skip if this page is itself a snapshot (served from the /snapshots/ directory)
  if (window.location.pathname.indexOf('/snapshots/') !== -1) return;

  var SNAP_PK = '8812';
  var _snapIndex = [];
  var _activeSnapId = null;
  var _activeSnapFile = null;
  var _activeSnapLabel = '';

  // Escape HTML special chars before inserting untrusted strings into innerHTML.
  function esc(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Render snapshot bar ──────────────────────────────────────────────────────

  function renderSnapshotBar() {
    var bar = document.getElementById('snapshot-bar');
    if (!bar) return;
    fetch('./snapshots/index.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : Promise.reject('not ok'); })
      .then(function (snaps) {
        if (!snaps.length) { bar.style.display = 'none'; return; }
        _snapIndex = snaps;
        var html = '<span class="snap-bar-label">Page versions</span>';
        snaps.forEach(function (s) {
          html += '<button class="snap-btn" data-snap-id="' + esc(s.id) +
            '" data-snap-file="' + esc(s.filename) + '">' + esc(s.label) + '</button>';
        });
        bar.innerHTML = html;
        bar.querySelectorAll('.snap-btn').forEach(function (btn) {
          btn.addEventListener('click', function () {
            onSnapClick(btn.dataset.snapFile, btn.dataset.snapId, btn.textContent.trim());
          });
        });
      })
      .catch(function () { bar.style.display = 'none'; });
  }

  // ── Handle snapshot button click ─────────────────────────────────────────────

  function onSnapClick(file, id, label) {
    _activeSnapId   = id;
    _activeSnapFile = file;
    _activeSnapLabel = label;
    document.querySelectorAll('.snap-btn').forEach(function (b) {
      b.classList.toggle('active', b.dataset.snapId === id);
    });
    showSnapshotBanner();
  }

  // ── Snapshot banner (appears below nav) ──────────────────────────────────────

  function showSnapshotBanner() {
    var banner = document.getElementById('snapshot-banner');
    if (banner) {
      // Already exists — update label and show
      var lbl = banner.querySelector('#snap-banner-label');
      if (lbl) lbl.textContent = _activeSnapLabel;
      banner.style.display = 'flex';
      return;
    }
    banner = document.createElement('div');
    banner.id = 'snapshot-banner';
    banner.innerHTML =
      '<span>Snapshot: <strong id="snap-banner-label">' + _activeSnapLabel + '</strong></span>' +
      '<span class="snap-banner-actions">' +
        '<button class="snap-banner-btn" id="snap-open-btn">Open full page \u2197</button>' +
        '<button class="snap-banner-btn" id="snap-restore-btn">Restore this version</button>' +
        '<button class="snap-banner-btn snap-banner-exit" id="snap-exit-btn">\u2190 Back to live</button>' +
      '</span>';
    banner.style.display = 'flex';
    // Insert immediately after <nav>
    var nav = document.querySelector('nav');
    if (nav && nav.parentNode) {
      nav.parentNode.insertBefore(banner, nav.nextSibling);
    } else {
      document.body.prepend(banner);
    }
    document.getElementById('snap-open-btn').addEventListener('click', function () {
      window.open('./snapshots/' + _activeSnapFile, '_blank');
    });
    document.getElementById('snap-restore-btn').addEventListener('click', showRestoreModal);
    document.getElementById('snap-exit-btn').addEventListener('click', function () {
      banner.style.display = 'none';
      document.querySelectorAll('.snap-btn').forEach(function (b) { b.classList.remove('active'); });
      _activeSnapId = null;
    });
  }

  // ── Restore modal ────────────────────────────────────────────────────────────

  function showRestoreModal() {
    var modal = document.getElementById('snap-restore-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'snap-restore-modal';
      document.body.appendChild(modal);
      modal.addEventListener('click', function (e) {
        if (e.target === modal) modal.classList.remove('visible');
      });
    }
    modal.innerHTML =
      '<div class="srm-inner">' +
        '<div class="srm-title">Restore this version?</div>' +
        '<div class="srm-body">Downloads the <strong>' + _activeSnapLabel + '</strong> snapshot as <code>index.html</code>. ' +
          'Place it at <code>docs/index.html</code> in the repo and push via GitHub Desktop to restore.</div>' +
        '<input id="srm-passkey" class="srm-input" type="password" placeholder="Passkey" maxlength="10" autocomplete="off">' +
        '<div class="srm-error" id="srm-error"></div>' +
        '<div class="srm-btns">' +
          '<button class="srm-confirm" id="srm-confirm-btn">Download &amp; Restore</button>' +
          '<button class="srm-dismiss" id="srm-dismiss-btn">Cancel</button>' +
        '</div>' +
      '</div>';
    document.getElementById('srm-confirm-btn').addEventListener('click', attemptRestore);
    document.getElementById('srm-dismiss-btn').addEventListener('click', function () {
      modal.classList.remove('visible');
    });
    document.getElementById('srm-passkey').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') attemptRestore();
      if (e.key === 'Escape') modal.classList.remove('visible');
    });
    modal.classList.add('visible');
    setTimeout(function () {
      var i = document.getElementById('srm-passkey');
      if (i) i.focus();
    }, 50);
  }

  // ── Attempt restore ──────────────────────────────────────────────────────────

  function attemptRestore() {
    var input = document.getElementById('srm-passkey');
    var errEl = document.getElementById('srm-error');
    if (!input) return;
    if (input.value !== SNAP_PK) {
      if (errEl) errEl.textContent = 'Incorrect passkey.';
      input.value = '';
      input.classList.add('srm-shake');
      setTimeout(function () { input.classList.remove('srm-shake'); }, 400);
      return;
    }

    function dlFile(content, filename, mime) {
      var blob = new Blob([content], { type: mime });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
    }

    // Download the snapshot HTML as index.html
    fetch('./snapshots/' + _activeSnapFile)
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url; a.download = 'index.html'; a.click();
        URL.revokeObjectURL(url);
      })
      .catch(function (err) {
        var errEl = document.getElementById('srm-error');
        if (errEl) errEl.textContent = 'Download failed: ' + err.message;
      });

    // Download pruned index.json — keep only from restored snapshot onward
    var restoredPos = -1;
    for (var i = 0; i < _snapIndex.length; i++) {
      if (_snapIndex[i].id === _activeSnapId) { restoredPos = i; break; }
    }
    var pruned = restoredPos >= 0 ? _snapIndex.slice(restoredPos) : _snapIndex;
    dlFile(JSON.stringify(pruned, null, 2), 'snapshots-index.json', 'application/json');

    var modal = document.getElementById('snap-restore-modal');
    if (modal) {
      var newer = restoredPos > 0 ? restoredPos : 0;
      modal.querySelector('.srm-inner').innerHTML =
        '<div class="srm-title srm-success">2 files downloaded</div>' +
        '<div class="srm-body">' +
          '\u00b7 <code>index.html</code> \u2192 place at <code>docs/index.html</code><br>' +
          '\u00b7 <code>snapshots-index.json</code> \u2192 place at <code>docs/snapshots/index.json</code><br><br>' +
          (newer > 0 ? 'This removes ' + newer + ' newer version' + (newer !== 1 ? 's' : '') + ' from history. ' : '') +
          'Push via GitHub Desktop to apply.' +
        '</div>' +
        '<div class="srm-btns"><button class="srm-dismiss" id="srm-done-btn">Done</button></div>';
      document.getElementById('srm-done-btn').addEventListener('click', function () {
        modal.classList.remove('visible');
      });
    }
  }

  document.addEventListener('DOMContentLoaded', renderSnapshotBar);
}());

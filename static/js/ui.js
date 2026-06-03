/* ═══════════════════════════════════════════════════════════════════════════
   REMS — UI Interactive Layer
   Features: Toast notifications, Live table search, Table sort,
             Modal confirm dialogs, Auto-format numbers
   No external dependencies.
   ═══════════════════════════════════════════════════════════════════════════ */

'use strict';

/* ── TOAST SYSTEM ─────────────────────────────────────────────────────────── */
const Toast = (() => {
  let region;

  function getRegion() {
    if (!region) {
      region = document.getElementById('toast-region');
      if (!region) {
        region = document.createElement('div');
        region.id = 'toast-region';
        region.className = 'toast-region';
        document.body.appendChild(region);
      }
    }
    return region;
  }

  function show(message, type = 'info', duration = 4000) {
    const r = getRegion();
    const titles = { success: 'Done', error: 'Error', warning: 'Warning', info: 'Notice' };

    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.style.position = 'relative';
    el.innerHTML = `
      <span class="toast-dot"></span>
      <div class="toast-body">
        <div class="toast-title">${titles[type] || 'Notice'}</div>
        <div class="toast-msg">${message}</div>
      </div>
      <button class="toast-close" aria-label="Dismiss">&times;</button>
      <div class="toast-progress"><div class="toast-progress-bar"></div></div>
    `;

    el.querySelector('.toast-close').addEventListener('click', () => dismiss(el));
    r.appendChild(el);

    const timer = setTimeout(() => dismiss(el), duration);
    el._timer = timer;

    // Pause on hover
    el.addEventListener('mouseenter', () => {
      clearTimeout(el._timer);
      const bar = el.querySelector('.toast-progress-bar');
      if (bar) bar.style.animationPlayState = 'paused';
    });
    el.addEventListener('mouseleave', () => {
      el._timer = setTimeout(() => dismiss(el), 1500);
      const bar = el.querySelector('.toast-progress-bar');
      if (bar) bar.style.animationPlayState = 'running';
    });

    return el;
  }

  function dismiss(el) {
    if (!el || el._dismissed) return;
    el._dismissed = true;
    clearTimeout(el._timer);
    el.classList.add('toast-out');
    el.addEventListener('animationend', () => el.remove(), { once: true });
  }

  // Bootstrap from Django messages embedded in the page
  function initFromPage() {
    document.querySelectorAll('[data-toast]').forEach(node => {
      const msg  = node.dataset.toast;
      const type = node.dataset.toastType || 'info';
      show(msg, type);
      node.remove();
    });
  }

  return { show, dismiss, initFromPage };
})();


/* ── LIVE TABLE SEARCH ─────────────────────────────────────────────────────── */
function initLiveSearch() {
  document.querySelectorAll('[data-search-table]').forEach(input => {
    const tableId = input.dataset.searchTable;
    const table   = document.getElementById(tableId);
    if (!table) return;

    const counter = document.querySelector(`[data-search-counter="${tableId}"]`);

    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      let visible = 0;

      table.querySelectorAll('tbody tr').forEach(row => {
        if (row.classList.contains('empty-row')) return;
        const text = row.textContent.toLowerCase();
        const show = !q || text.includes(q);
        row.style.display = show ? '' : 'none';
        if (show) visible++;
      });

      // Show/hide built-in empty row if all filtered out
      const emptyRow = table.querySelector('.empty-row');
      if (emptyRow) {
        emptyRow.style.display = visible === 0 && q ? '' : 'none';
        if (visible === 0 && q) {
          const cell = emptyRow.querySelector('td');
          if (cell) cell.textContent = `No results for "${input.value}"`;
        }
      }

      if (counter) counter.textContent = q ? `${visible} result${visible !== 1 ? 's' : ''}` : '';
    });
  });
}


/* ── TABLE SORT ───────────────────────────────────────────────────────────── */
function initTableSort() {
  document.querySelectorAll('table.rems-table[data-sortable]').forEach(table => {
    const headers = table.querySelectorAll('thead th[data-sort]');

    headers.forEach((th, colIndex) => {
      // Add sort icon
      const icon = document.createElement('span');
      icon.className = 'sort-icon';
      icon.innerHTML = ' ↕';
      th.appendChild(icon);

      th.addEventListener('click', () => {
        const currentAsc = th.classList.contains('sort-asc');
        const dir = currentAsc ? 'desc' : 'asc';

        // Reset all headers
        headers.forEach(h => {
          h.classList.remove('sort-asc', 'sort-desc');
          const i = h.querySelector('.sort-icon');
          if (i) i.innerHTML = ' ↕';
        });

        th.classList.add(`sort-${dir}`);
        th.querySelector('.sort-icon').innerHTML = dir === 'asc' ? ' ↑' : ' ↓';

        sortTable(table, colIndex, dir);
      });
    });
  });
}

function sortTable(table, col, dir) {
  const tbody = table.querySelector('tbody');
  const rows  = Array.from(tbody.querySelectorAll('tr:not(.empty-row)'));

  rows.sort((a, b) => {
    const aText = (a.cells[col]?.textContent || '').trim();
    const bText = (b.cells[col]?.textContent || '').trim();

    // Try numeric comparison first (strip commas and currency)
    const aNum = parseFloat(aText.replace(/[^0-9.-]/g, ''));
    const bNum = parseFloat(bText.replace(/[^0-9.-]/g, ''));

    let cmp;
    if (!isNaN(aNum) && !isNaN(bNum)) {
      cmp = aNum - bNum;
    } else {
      cmp = aText.localeCompare(bText, undefined, { numeric: true, sensitivity: 'base' });
    }
    return dir === 'asc' ? cmp : -cmp;
  });

  rows.forEach(r => tbody.appendChild(r));
}


/* ── MODAL CONFIRM ─────────────────────────────────────────────────────────── */
function initModalConfirm() {
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      const title   = el.dataset.confirmTitle   || 'Are you sure?';
      const message = el.dataset.confirm        || 'This action cannot be undone.';
      const btnText = el.dataset.confirmBtn     || 'Confirm';
      const danger  = el.dataset.confirmDanger !== 'false';
      const href    = el.href;
      const form    = el.closest('form');

      openModal({
        title,
        message,
        btnText,
        danger,
        onConfirm: () => {
          if (form) {
            form.submit();
          } else if (href) {
            window.location.href = href;
          }
        },
      });
    });
  });
}

function openModal({ title, message, btnText, danger, onConfirm }) {
  // Remove any existing modal
  document.getElementById('rems-modal')?.remove();

  const bd = document.createElement('div');
  bd.className = 'modal-backdrop';
  bd.id = 'rems-modal';

  bd.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-icon ${danger ? 'modal-icon-danger' : 'modal-icon-warning'}">
        <i class="fas fa-${danger ? 'trash-alt' : 'exclamation-triangle'}"></i>
      </div>
      <div class="modal-title">${title}</div>
      <div class="modal-body">${message}</div>
      <div class="modal-actions">
        <button class="btn btn-ghost btn-modal-cancel">Cancel</button>
        <button class="btn ${danger ? 'btn-danger' : 'btn-primary'} btn-modal-confirm">${btnText}</button>
      </div>
    </div>
  `;

  document.body.appendChild(bd);
  bd.querySelector('.btn-modal-confirm').focus();

  bd.querySelector('.btn-modal-cancel').addEventListener('click', closeModal);
  bd.querySelector('.btn-modal-confirm').addEventListener('click', () => {
    closeModal();
    onConfirm();
  });

  // Close on backdrop click
  bd.addEventListener('click', e => { if (e.target === bd) closeModal(); });

  // Close on Escape
  const esc = e => { if (e.key === 'Escape') { closeModal(); document.removeEventListener('keydown', esc); } };
  document.addEventListener('keydown', esc);
}

function closeModal() {
  const m = document.getElementById('rems-modal');
  if (m) m.remove();
}


/* ── DELETE BUTTONS → MODAL ──────────────────────────────────────────────── */
function initDeleteButtons() {
  document.querySelectorAll('a.btn-danger, a[data-delete]').forEach(link => {
    if (link.dataset.noConfirm) return;
    link.addEventListener('click', e => {
      e.preventDefault();
      const label = link.dataset.deleteLabel || 'this record';
      openModal({
        title: 'Confirm Delete',
        message: `Are you sure you want to delete <strong>${label}</strong>? This cannot be undone.`,
        btnText: 'Delete',
        danger: true,
        onConfirm: () => { window.location.href = link.href; },
      });
    });
  });
}


/* ── TENANT AUTOCOMPLETE (receipt form) ────────────────────────────────────── */
function initTenantSearch() {
  const input = document.getElementById('id_tenant');
  if (!input || input.tagName !== 'SELECT') return;

  // Wrap select in searchable input
  const wrapper = document.createElement('div');
  wrapper.style.position = 'relative';
  input.parentNode.insertBefore(wrapper, input);
  wrapper.appendChild(input);

  const search = document.createElement('input');
  search.type = 'text';
  search.placeholder = 'Search tenant by name or room...';
  search.className = 'form-control';
  search.style.marginBottom = '6px';

  wrapper.insertBefore(search, input);

  const options = Array.from(input.options).filter(o => o.value);

  search.addEventListener('input', () => {
    const q = search.value.toLowerCase();
    Array.from(input.options).forEach(o => {
      if (!o.value) return;
      o.hidden = q && !o.text.toLowerCase().includes(q);
    });
    // Auto-select if only one remains
    const visible = Array.from(input.options).filter(o => o.value && !o.hidden);
    if (visible.length === 1) input.value = visible[0].value;
  });
}


/* ── AUTO-FORMAT (show UGX abbreviation in KPI cards) ────────────────────── */
function formatMoney(n) {
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (Math.abs(n) >= 1_000)     return (n / 1_000).toFixed(0) + 'K';
  return n.toLocaleString();
}


/* ── ACTIVE NAV (highlight sidebar based on path) ─────────────────────────── */
function initActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(link => {
    const href = link.getAttribute('href');
    if (!href || href === '/') return;
    if (path.startsWith(href)) {
      link.classList.add('active');
    }
  });
}


/* ── DISMISSIBLE INLINE ALERTS ────────────────────────────────────────────── */
function initAlertDismiss() {
  document.querySelectorAll('.alert .alert-close').forEach(btn => {
    btn.addEventListener('click', () => {
      const alert = btn.closest('.alert');
      alert.style.transition = 'opacity .2s, margin .2s, padding .2s, max-height .2s';
      alert.style.opacity = '0';
      alert.style.maxHeight = alert.scrollHeight + 'px';
      requestAnimationFrame(() => {
        alert.style.maxHeight = '0';
        alert.style.padding = '0';
        alert.style.margin = '0';
      });
      setTimeout(() => alert.remove(), 250);
    });
  });
}


/* ── BOOT ─────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  Toast.initFromPage();
  initLiveSearch();
  initTableSort();
  initModalConfirm();
  initDeleteButtons();
  initTenantSearch();
  initAlertDismiss();
});

// Expose globally so templates can call Toast.show() directly if needed
window.REMS = { Toast, openModal, closeModal };

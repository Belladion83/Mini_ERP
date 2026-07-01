(function () {
  if (window.erpAlert && window.erpConfirm && window.erpConfirmSubmit) return;

  function ensureModal() {
    let modal = document.getElementById('global-erp-modal');
    if (modal) return modal;

    modal = document.createElement('div');
    modal.id = 'global-erp-modal';
    modal.className = 'erp-modal-backdrop global-erp-modal-backdrop';
    modal.hidden = true;
    modal.innerHTML = `
      <div class="erp-modal-card global-erp-modal-card" role="dialog" aria-modal="true" aria-labelledby="global-erp-modal-title">
        <div class="erp-modal-header">
          <div>
            <p class="eyebrow" id="global-erp-modal-eyebrow">System Message</p>
            <h2 id="global-erp-modal-title">Message</h2>
          </div>
          <button type="button" class="erp-modal-close" data-erp-modal-close aria-label="Close">×</button>
        </div>
        <div class="erp-modal-body">
          <p id="global-erp-modal-message"></p>
          <div class="erp-modal-summary" id="global-erp-modal-summary" hidden></div>
        </div>
        <div class="erp-modal-actions">
          <button type="button" class="btn-secondary btn-small" id="global-erp-modal-cancel">Cancel</button>
          <button type="button" class="btn-primary btn-small" id="global-erp-modal-ok">OK</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    return modal;
  }

  function normalizeOptions(options) {
    if (typeof options === 'string') return { title: options };
    return options || {};
  }

  function openModal(message, options) {
    options = normalizeOptions(options);
    const modal = ensureModal();
    const title = modal.querySelector('#global-erp-modal-title');
    const eyebrow = modal.querySelector('#global-erp-modal-eyebrow');
    const msg = modal.querySelector('#global-erp-modal-message');
    const summary = modal.querySelector('#global-erp-modal-summary');
    const ok = modal.querySelector('#global-erp-modal-ok');
    const cancel = modal.querySelector('#global-erp-modal-cancel');
    const close = modal.querySelector('[data-erp-modal-close]');

    title.textContent = options.title || 'System Message';
    eyebrow.textContent = options.eyebrow || 'Mini ERP';
    msg.textContent = message || '';
    ok.textContent = options.confirmText || options.okText || 'OK';
    cancel.textContent = options.cancelText || 'Cancel';

    if (options.summaryHtml) {
      summary.hidden = false;
      summary.innerHTML = options.summaryHtml;
    } else {
      summary.hidden = true;
      summary.innerHTML = '';
    }

    modal.dataset.type = options.type || 'info';
    cancel.style.display = options.mode === 'alert' ? 'none' : '';
    modal.hidden = false;
    document.body.classList.add('modal-open');

    return new Promise(resolve => {
      let resolved = false;
      function done(value) {
        if (resolved) return;
        resolved = true;
        modal.hidden = true;
        document.body.classList.remove('modal-open');
        ok.removeEventListener('click', onOk);
        cancel.removeEventListener('click', onCancel);
        close.removeEventListener('click', onCancel);
        modal.removeEventListener('click', onBackdrop);
        document.removeEventListener('keydown', onKey);
        resolve(value);
      }
      function onOk() { done(true); }
      function onCancel() { done(false); }
      function onBackdrop(e) { if (e.target === modal) done(false); }
      function onKey(e) {
        if (e.key === 'Escape') done(false);
        if (e.key === 'Enter' && !e.shiftKey) done(true);
      }
      ok.addEventListener('click', onOk);
      cancel.addEventListener('click', onCancel);
      close.addEventListener('click', onCancel);
      modal.addEventListener('click', onBackdrop);
      document.addEventListener('keydown', onKey);
      setTimeout(() => ok.focus(), 0);
    });
  }

  window.erpAlert = function (message, options) {
    options = normalizeOptions(options);
    options.mode = 'alert';
    options.cancelText = '';
    options.confirmText = options.confirmText || options.okText || 'OK';
    return openModal(message, options);
  };

  window.erpConfirm = function (message, options) {
    options = normalizeOptions(options);
    options.mode = 'confirm';
    options.confirmText = options.confirmText || 'Confirm';
    options.cancelText = options.cancelText || 'Cancel';
    return openModal(message, options);
  };

  window.erpConfirmSubmit = function (form, message, options) {
    if (!form) return false;
    if (form.dataset.erpConfirmed === '1') return true;
    window.erpConfirm(message, Object.assign({
      title: 'Confirm action',
      eyebrow: 'Mini ERP',
      confirmText: 'Confirm',
      cancelText: 'Cancel',
      type: 'warning'
    }, options || {})).then(ok => {
      if (ok) {
        form.dataset.erpConfirmed = '1';
        if (typeof form.requestSubmit === 'function') form.requestSubmit();
        else form.submit();
      }
    });
    return false;
  };

  // Keep old alert() calls visually consistent with the ERP style.
  // confirm() is intentionally not overridden because browser confirm is synchronous;
  // use erpConfirmSubmit() / erpConfirm() for new confirmation workflows.
  const nativeAlert = window.alert;
  window.nativeAlert = nativeAlert;
  window.alert = function (message) {
    window.erpAlert(String(message || ''), { title: 'Notification', type: 'info' });
  };
})();

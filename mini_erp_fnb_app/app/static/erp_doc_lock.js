(function(){
  function lockContainer(container){
    const isLocked = String(container.dataset.docLocked || '').toLowerCase() === 'true';
    if(!isLocked) return;
    container.classList.add('doc-locked');
    container.querySelectorAll('input, select, textarea').forEach(el => {
      if(el.type === 'hidden') return;
      if(el.matches('[data-allow-locked-action]')) return;
      if(el.tagName === 'SELECT' || el.type === 'checkbox' || el.type === 'radio' || el.type === 'file'){
        el.disabled = true;
      }else{
        el.readOnly = true;
      }
    });
    container.querySelectorAll('button.remove-line, button[id^="add-"], button[id*="price"], .locked-hide').forEach(btn => {
      btn.disabled = true;
      btn.style.display = 'none';
    });
    if(window.refreshSearchableSelects) window.refreshSearchableSelects(container);
  }
  function init(){
    document.querySelectorAll('[data-doc-locked="true"]').forEach(lockContainer);
  }
  document.addEventListener('DOMContentLoaded', init);
  window.erpLockReleasedDocuments = init;
})();

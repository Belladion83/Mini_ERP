(function(){
  function optionText(opt){ return (opt.textContent || '').replace(/\s+/g,' ').trim(); }
  function isBlankValue(v){ return v === undefined || v === null || v === '' || v === '0'; }
  function visibleOptions(select){
    return Array.from(select.options).filter(opt => !opt.hidden && !opt.disabled);
  }
  function getCombo(select){
    const next = select.nextElementSibling;
    return next && next.classList && next.classList.contains('searchable-combo') ? next : null;
  }
  function isInLineTable(select){
    return !!select.closest('.entry-lines-table, .line-table-wrap, .purchase-line-table-wrap, #manual-gr-lines-table, #receipt-lines-body');
  }
  function estimatedListHeight(optionCount){
    const count = Math.max(1, Number(optionCount || 0));
    return Math.min(320, Math.max(72, (count * 42) + 14));
  }
  function positionList(select, optionCount){
    const combo = getCombo(select);
    if(!combo) return;
    const input = combo.querySelector('.searchable-input');
    const list = combo.querySelector('.searchable-list');
    if(!input || !list) return;

    const rect = input.getBoundingClientRect();
    const viewportBottom = window.innerHeight || document.documentElement.clientHeight;
    const viewportRight = window.innerWidth || document.documentElement.clientWidth;
    const desiredHeight = estimatedListHeight(optionCount || visibleOptions(select).length);
    const below = viewportBottom - rect.bottom - 8;
    const above = rect.top - 8;

    // Keep dropdown visually attached to the selected input. For line tables,
    // prefer opening downward even inside scroll frames; only open upward when
    // there is very little visible space below. This avoids the dropdown jumping
    // far away from the active row.
    const minUsefulSpace = isInLineTable(select) ? 96 : 140;
    const openUp = below < Math.min(desiredHeight, minUsefulSpace) && above > below;
    const available = Math.max(72, openUp ? above : below);
    const maxHeight = Math.min(desiredHeight, available);

    let left = rect.left;
    const width = Math.max(rect.width, isInLineTable(select) ? 260 : 240);
    if(left + width > viewportRight - 8){
      left = Math.max(8, viewportRight - width - 8);
    }

    let top = openUp ? (rect.top - maxHeight - 6) : (rect.bottom + 6);
    if(!openUp && top + maxHeight > viewportBottom - 8){
      top = Math.max(8, viewportBottom - maxHeight - 8);
    }
    if(openUp && top < 8){
      top = 8;
    }

    list.style.setProperty('--combo-left', `${Math.max(8, left)}px`);
    list.style.setProperty('--combo-top', `${Math.max(8, top)}px`);
    list.style.setProperty('--combo-width', `${width}px`);
    list.style.setProperty('--combo-max-height', `${maxHeight}px`);
  }
  function updateDisplay(select){
    const combo = getCombo(select);
    if(!combo) return;
    const input = combo.querySelector('.searchable-input');
    const selected = select.selectedOptions && select.selectedOptions[0];
    input.value = selected && !isBlankValue(selected.value) ? optionText(selected) : '';
    input.placeholder = select.options[0] ? optionText(select.options[0]) : 'Search...';
    input.disabled = !!select.disabled;
    input.readOnly = !!select.disabled;
    combo.classList.toggle('is-disabled', select.disabled);
  }
  function closeAll(except){
    document.querySelectorAll('.searchable-combo.open').forEach(c => {
      if(c !== except){
        c.classList.remove('open');
        const select = c.previousElementSibling;
        if(select && select.tagName === 'SELECT') updateDisplay(select);
      }
    });
  }
  function render(select){
    const combo = getCombo(select);
    if(!combo) return;
    const input = combo.querySelector('.searchable-input');
    const list = combo.querySelector('.searchable-list');
    const q = (input.value || '').toLowerCase().trim();
    list.innerHTML = '';

    const rows = visibleOptions(select)
      .filter(opt => !q || optionText(opt).toLowerCase().includes(q))
      .slice(0, 120);

    rows.forEach(opt => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'searchable-option';
      item.textContent = optionText(opt);
      item.dataset.value = opt.value;
      if(opt.selected) item.classList.add('selected');
      item.addEventListener('mousedown', e => e.preventDefault());
      item.addEventListener('click', () => {
        select.value = opt.value;
        select.dispatchEvent(new Event('change', {bubbles:true}));
        updateDisplay(select);
        combo.classList.remove('open');
      });
      list.appendChild(item);
    });

    if(!list.children.length){
      const empty = document.createElement('div');
      empty.className = 'searchable-empty';
      empty.textContent = 'No result';
      list.appendChild(empty);
    }
    positionList(select, rows.length || 1);
  }
  function openCombo(select){
    if(!select || select.disabled) return;
    initSelect(select);
    const combo = getCombo(select);
    if(!combo) return;
    const input = combo.querySelector('.searchable-input');

    // Let page scripts refresh dependent options before the list opens.
    select.dispatchEvent(new CustomEvent('searchable:open', {bubbles:true}));

    closeAll(combo);
    combo.classList.add('open');

    // On first click, show all current database options immediately instead of
    // filtering by the selected display text / placeholder.
    input.value = '';
    render(select);
    window.requestAnimationFrame(() => positionList(select, visibleOptions(select).length));
    input.focus({preventScroll:true});
  }
  function ensureObserver(select){
    if(select._searchableObserver) return;
    select._searchableObserver = new MutationObserver(() => {
      updateDisplay(select);
      const combo = getCombo(select);
      if(combo && combo.classList.contains('open')) render(select);
    });
    select._searchableObserver.observe(select, {childList:true, subtree:true, attributes:true, attributeFilter:['hidden','disabled','selected']});
  }
  function initSelect(select){
    if(!select || select.dataset.searchableReady === '1') return;
    select.dataset.searchableReady = '1';
    select.style.display = 'none';

    const combo = document.createElement('div');
    combo.className = 'searchable-combo';
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'searchable-input';
    input.autocomplete = 'off';
    const list = document.createElement('div');
    list.className = 'searchable-list';
    combo.appendChild(input);
    combo.appendChild(list);
    select.insertAdjacentElement('afterend', combo);

    updateDisplay(select);
    ensureObserver(select);

    input.addEventListener('focus', () => openCombo(select));
    input.addEventListener('click', () => openCombo(select));
    input.addEventListener('input', () => { combo.classList.add('open'); render(select); });
    input.addEventListener('keydown', e => {
      if(e.key === 'Escape'){
        combo.classList.remove('open');
        updateDisplay(select);
        input.blur();
      }
      if(e.key === 'Enter'){
        const first = list.querySelector('.searchable-option');
        if(first){ e.preventDefault(); first.click(); }
      }
      if(e.key === 'ArrowDown'){
        const first = list.querySelector('.searchable-option');
        if(first){ e.preventDefault(); first.focus(); }
      }
    });
    select.addEventListener('change', () => {
      updateDisplay(select);
      const combo = getCombo(select);
      if(combo && combo.classList.contains('open')) render(select);
    });
  }
  function targetSelects(root){
    return Array.from((root || document).querySelectorAll('select.searchable-select, .erp-form-grid select, .entry-lines-table select'))
      .filter(sel => !sel.multiple && !sel.classList.contains('multi-select-box') && !sel.dataset.saleChannelSelect);
  }

  window.resetSearchableSelects = function(root){
    (root || document).querySelectorAll('.searchable-combo').forEach(combo => combo.remove());
    targetSelects(root).forEach(sel => {
      sel.dataset.searchableReady = '0';
      sel.style.display = '';
      if(sel._searchableObserver){
        try { sel._searchableObserver.disconnect(); } catch(e) {}
        delete sel._searchableObserver;
      }
    });
  };

  window.initSearchableSelects = function(root){
    targetSelects(root).forEach(initSelect);
  };
  window.refreshSearchableSelects = function(root){
    targetSelects(root).forEach(sel => {
      if(sel.dataset.searchableReady !== '1') initSelect(sel);
      updateDisplay(sel);
      const combo = getCombo(sel);
      if(combo && combo.classList.contains('open')) render(sel);
    });
  };
  window.openSearchableSelect = openCombo;

  function repositionOpen(){
    document.querySelectorAll('.searchable-combo.open').forEach(combo => {
      const sel = combo.previousElementSibling;
      if(sel && sel.tagName === 'SELECT') positionList(sel, visibleOptions(sel).length);
    });
  }
  window.addEventListener('resize', repositionOpen);
  window.addEventListener('scroll', repositionOpen, true);
  document.addEventListener('click', e => {
    if(!e.target.closest('.searchable-combo')) closeAll(null);
  });
  document.addEventListener('DOMContentLoaded', () => window.initSearchableSelects(document));
})();

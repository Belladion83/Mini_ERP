(function(){
  window.__MINI_ERP_TABLE_FILTER_VERSION = 'v96-vn-number-format';
  function normalize(text){
    return (text || '').replace(/\s+/g, ' ').trim();
  }
  function cellText(row, index){
    const cell = row.children[index];
    return normalize(cell ? cell.innerText || cell.textContent : '');
  }
  function parseNumber(value){
    if(window.erpParseNumber) return window.erpParseNumber(value);
    const cleaned = normalize(value)
      .replace(/\./g, '')
      .replace(/,/g, '.')
      .replace(/VND/ig, '')
      .replace(/%/g, '')
      .replace(/[^0-9.\-]/g, '');
    if(!cleaned || cleaned === '-' || cleaned === '.' || cleaned === '-.') return NaN;
    return Number(cleaned);
  }
  function parseDateValue(value){
    const v = normalize(value);
    if(!v) return NaN;
    const iso = /^\d{4}-\d{2}-\d{2}/.test(v) ? Date.parse(v.slice(0, 10)) : NaN;
    if(!Number.isNaN(iso)) return iso;
    const m = v.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/);
    if(m) return new Date(Number(m[3]), Number(m[2])-1, Number(m[1])).getTime();
    return NaN;
  }
  function toDateInputValue(value){
    const v = normalize(value);
    if(/^\d{4}-\d{2}-\d{2}/.test(v)) return v.slice(0, 10);
    const m = v.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/);
    if(m){
      const yyyy = String(m[3]);
      const mm = String(m[2]).padStart(2, '0');
      const dd = String(m[1]).padStart(2, '0');
      return `${yyyy}-${mm}-${dd}`;
    }
    return '';
  }

  function escapeHtml(value){
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
  function displayValueLabel(value){
    const v = normalize(value);
    if(!v || v === '-') return '(Blank / Not assigned)';
    return v;
  }
  function isBlankLikeValue(value){
    const v = normalize(value);
    return !v || v === '-' || v.toLowerCase() === '(blank / not assigned)';
  }
  function parseYmdLocal(value){
    const v = normalize(value);
    const m = v.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if(!m) return null;
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }
  function formatYmd(date){
    const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }
  function addMonths(date, amount){
    return new Date(date.getFullYear(), date.getMonth() + amount, 1);
  }
  function sameYmd(a, b){
    return !!a && !!b && formatYmd(a) === formatYmd(b);
  }
  function dateDisplay(value){
    const d = parseYmdLocal(value);
    if(!d) return '';
    return new Intl.DateTimeFormat('vi-VN', {day:'2-digit', month:'2-digit', year:'numeric'}).format(d);
  }
  function monthDisplay(date){
    const text = new Intl.DateTimeFormat('vi-VN', {month:'long', year:'numeric'}).format(date);
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
  function dateRangeDisplay(from, to){
    if(from && to) return `${dateDisplay(from)} → ${dateDisplay(to)}`;
    if(from) return `Từ ${dateDisplay(from)}`;
    if(to) return `Đến ${dateDisplay(to)}`;
    return 'Chọn khoảng ngày';
  }
  function compareValues(a, b){
    const an = parseNumber(a), bn = parseNumber(b);
    if(!Number.isNaN(an) && !Number.isNaN(bn)) return an - bn;
    const ad = parseDateValue(a), bd = parseDateValue(b);
    if(!Number.isNaN(ad) && !Number.isNaN(bd)) return ad - bd;
    return normalize(a).localeCompare(normalize(b), undefined, {numeric:true, sensitivity:'base'});
  }
  function headerText(th){
    return normalize(th.dataset.headerLabel || th.querySelector('.th-label')?.innerText || th.innerText || th.textContent || '');
  }
  function isActionHeader(text){
    const h = normalize(text).toLowerCase();
    return !h || ['action','actions','thao tác','receive','select',''].includes(h);
  }
  function shouldSkipAdvancedFilter(text){
    const h = normalize(text).toLowerCase();
    return isActionHeader(h);
  }
  function isEnhanceable(table){
    if(!table || table.dataset.erpTableReady === '1') return false;
    if(table.closest('[data-no-table-enhance="true"]')) return false;
    if(table.matches('.entry-lines-table, .bom-lines-table, .no-enhance-table')) return false;
    if(table.closest('.entry-lines-table, .bom-lines-table, .line-table-wrap')) return false;
    const tbody = table.tBodies && table.tBodies[0];
    const thead = table.tHead;
    if(!tbody || !thead || !thead.rows.length) return false;
    if(tbody.querySelector('input[type="text"], input[type="number"], select, textarea')) return false;
    const rows = Array.from(tbody.rows).filter(r => !r.querySelector('.empty-state') && !r.classList.contains('filter-empty-row'));
    return rows.length > 0;
  }
  function getDataRows(table){
    const tbody = table.tBodies[0];
    return Array.from(tbody.rows).filter(r => !r.classList.contains('filter-empty-row') && !r.querySelector('.empty-state'));
  }
  function removeLegacyInlineFilterRows(table){
    const thead = table.tHead;
    if(!thead) return;
    Array.from(thead.rows).forEach((row, idx) => {
      if(idx === 0) return;
      const hasLegacyClass = row.classList.contains('erp-filter-row');
      const controls = row.querySelectorAll('select.erp-column-filter, input.erp-column-filter, .erp-column-filter, select, input');
      const looksLikeFilterRow = controls.length > 0 && Array.from(controls).some(ctrl => {
        const ph = (ctrl.getAttribute('placeholder') || '').toLowerCase();
        const txt = (ctrl.options && ctrl.options.length ? ctrl.options[0].textContent : '').toLowerCase();
        return ph.includes('filter') || txt.includes('filter') || ctrl.classList.contains('erp-column-filter');
      });
      if(hasLegacyClass || looksLikeFilterRow){
        row.remove();
      }
    });
  }
  function makeToolbar(table){
    const wrapper = table.closest('.table-wrap') || table.parentElement;
    if(!wrapper) return null;
    if(wrapper.previousElementSibling?.classList?.contains('erp-table-toolbar')) return wrapper.previousElementSibling;
    const toolbar = document.createElement('div');
    toolbar.className = 'erp-table-toolbar';
    const title = table.dataset.erpTableTitle || table.dataset.tableTitle || '';
    toolbar.innerHTML = [
      '<div class="erp-table-title">' + (title ? title : '') + '</div>',
      '<div class="erp-table-controls">',
      '<div class="erp-table-search-box">',
      '<span class="erp-table-search-icon">🔎</span>',
      '<input type="search" class="erp-table-global-search" placeholder="Search table...">',
      '</div>',
      '<button type="button" class="btn-secondary btn-small erp-table-open-filters">Filter</button>',
      '<button type="button" class="btn-secondary btn-small erp-table-clear">Clear filter</button>',
      '<span class="erp-table-active-filters"></span>',
      '<span class="erp-table-count"></span>',
      '</div>'
    ].join('');
    if(!title) toolbar.querySelector('.erp-table-title')?.classList.add('empty');
    wrapper.insertAdjacentElement('beforebegin', toolbar);
    return toolbar;
  }
  function buildUniqueValues(table, colIndex){
    const values = [];
    getDataRows(table).forEach(row => {
      const value = cellText(row, colIndex);
      if(value && !values.includes(value)) values.push(value);
    });
    return values.sort((a,b)=>compareValues(a,b));
  }
  function detectColumnKind(table, index, header){
    const h = normalize(header).toLowerCase();
    if(h.includes('date') || h.includes('ngày')) return 'date';
    const values = getDataRows(table).map(r => cellText(r, index)).filter(Boolean);
    const sample = values.slice(0, 10);
    if(sample.length && sample.every(v => !Number.isNaN(parseDateValue(v)))) return 'date';
    if(h.includes('qty') || h.includes('quantity') || h.includes('price') || h.includes('amount') || h.includes('total') || h.includes('percent') || h.includes('%')) return 'number';
    if(sample.length && sample.every(v => !Number.isNaN(parseNumber(v)))) return 'number';
    return 'text';
  }
  function ensureSortableHeaders(table){
    const headerRow = table.tHead.rows[0];
    Array.from(headerRow.cells).forEach((th, index) => {
      const label = normalize(th.innerText || th.textContent);
      th.dataset.headerLabel = label;
      if(isActionHeader(label) || th.dataset.sortReady === '1') return;
      th.dataset.sortReady = '1';
      th.classList.add('sortable-th');
      const original = th.innerHTML;
      th.innerHTML = '';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'th-sort-button';
      btn.innerHTML = '<span class="th-label">' + original + '</span><span class="sort-indicator">↕</span>';
      btn.addEventListener('click', () => sortByColumn(table, index));
      th.appendChild(btn);
    });
  }
  function sortByColumn(table, index){
    const tbody = table.tBodies[0];
    const currentIndex = Number(table.dataset.sortCol ?? -1);
    const currentDir = table.dataset.sortDir || '';
    let nextDir = 'asc';
    if(currentIndex === index && currentDir === 'asc') nextDir = 'desc';
    else if(currentIndex === index && currentDir === 'desc') nextDir = '';

    table.dataset.sortCol = nextDir ? String(index) : '';
    table.dataset.sortDir = nextDir;

    Array.from(table.tHead.rows[0].cells).forEach((th, i) => {
      th.classList.remove('sort-asc','sort-desc');
      const ind = th.querySelector('.sort-indicator');
      if(ind) ind.textContent = '↕';
      if(nextDir && i === index){
        th.classList.add(nextDir === 'asc' ? 'sort-asc' : 'sort-desc');
        if(ind) ind.textContent = nextDir === 'asc' ? '↑' : '↓';
      }
    });

    const rows = getDataRows(table);
    if(nextDir){
      rows.sort((ra, rb) => {
        const cmp = compareValues(cellText(ra, index), cellText(rb, index));
        return nextDir === 'asc' ? cmp : -cmp;
      });
    } else {
      rows.sort((ra, rb) => Number(ra.dataset.originalIndex) - Number(rb.dataset.originalIndex));
    }
    rows.forEach(r => tbody.appendChild(r));
    const empty = tbody.querySelector('.filter-empty-row');
    if(empty) tbody.appendChild(empty);
    applyFilters(table);
  }
  function ensureFilterEmptyRow(table){
    let row = table.tBodies[0].querySelector('.filter-empty-row');
    if(row) return row;
    row = document.createElement('tr');
    row.className = 'filter-empty-row';
    row.style.display = 'none';
    const td = document.createElement('td');
    td.className = 'empty-state';
    td.colSpan = table.tHead.rows[0].cells.length;
    td.textContent = 'No matching records.';
    row.appendChild(td);
    table.tBodies[0].appendChild(row);
    return row;
  }
  function findStatusColumn(table){
    let statusIndex = -1;
    Array.from(table.tHead.rows[0].cells).forEach((th, idx) => {
      if(headerText(th).toLowerCase() === 'status') statusIndex = idx;
    });
    return statusIndex;
  }
  function applyDefaultStatusFilter(table){
    const defaultStatus = table.dataset.defaultStatus;
    if(!defaultStatus || table.dataset.defaultStatusApplied === '1') return;
    const statusIndex = findStatusColumn(table);
    if(statusIndex < 0) return;
    table._erpAdvancedFilters = table._erpAdvancedFilters || {};
    table._erpAdvancedFilters[String(statusIndex)] = {kind:'text', selected:[defaultStatus], contains:''};
    table.dataset.defaultStatusApplied = '1';
  }
  function passesAdvancedFilter(row, col, filter){
    if(!filter) return true;
    const value = cellText(row, Number(col));
    if(filter.kind === 'date'){
      const rowYmd = toDateInputValue(value);
      const rowDate = parseYmdLocal(rowYmd);
      if(filter.from){
        const from = parseYmdLocal(filter.from);
        if(!rowDate || !from || rowDate < from) return false;
      }
      if(filter.to){
        const to = parseYmdLocal(filter.to);
        if(!rowDate || !to || rowDate > to) return false;
      }
      return true;
    }
    if(filter.kind === 'number'){
      const n = parseNumber(value);
      if(filter.from !== '' && filter.from !== undefined && filter.from !== null){
        const from = parseNumber(filter.from);
        if(Number.isNaN(n) || Number.isNaN(from) || n < from) return false;
      }
      if(filter.to !== '' && filter.to !== undefined && filter.to !== null){
        const to = parseNumber(filter.to);
        if(Number.isNaN(n) || Number.isNaN(to) || n > to) return false;
      }
      return true;
    }
    const lower = value.toLowerCase();
    const selected = Array.isArray(filter.selected)
      ? filter.selected.filter(v => !isBlankLikeValue(v))
      : [];
    if(filter.contains && !lower.includes(String(filter.contains).toLowerCase())) return false;
    // No selected value = All values, including blank/not assigned rows.
    if(selected.length && !selected.includes(value)) return false;
    return true;
  }
  function advancedFilterCount(table){
    const filters = table._erpAdvancedFilters || {};
    return Object.values(filters).filter(f => {
      if(!f) return false;
      if(f.kind === 'text') return (f.contains && f.contains.trim()) || (f.selected && f.selected.filter(v => !isBlankLikeValue(v)).length);
      return (f.from !== '' && f.from !== undefined && f.from !== null) || (f.to !== '' && f.to !== undefined && f.to !== null);
    }).length;
  }
  function applyFilters(table){
    const toolbar = table._erpToolbar;
    const globalInput = toolbar ? toolbar.querySelector('.erp-table-global-search') : null;
    const globalQ = normalize(globalInput?.value).toLowerCase();
    const adv = table._erpAdvancedFilters || {};

    let visible = 0;
    const rows = getDataRows(table);
    rows.forEach(row => {
      const rowText = normalize(row.innerText || row.textContent).toLowerCase();
      let show = !globalQ || rowText.includes(globalQ);
      if(show){
        for(const [col, filter] of Object.entries(adv)){
          if(!passesAdvancedFilter(row, col, filter)){
            show = false;
            break;
          }
        }
      }
      row.style.display = show ? '' : 'none';
      if(show) visible++;
    });
    const empty = ensureFilterEmptyRow(table);
    empty.style.display = visible === 0 ? '' : 'none';
    const counter = toolbar ? toolbar.querySelector('.erp-table-count') : null;
    if(counter) counter.textContent = visible + ' / ' + rows.length + ' rows';
    const active = toolbar ? toolbar.querySelector('.erp-table-active-filters') : null;
    const cnt = advancedFilterCount(table);
    if(active) active.textContent = cnt ? cnt + ' condition(s)' : '';
  }
  function ensureFilterModal(){
    let modal = document.getElementById('erp-table-filter-modal');
    if(modal) return modal;

    const tpl = document.getElementById('erp-table-filter-template');
    if(tpl && tpl.content && tpl.content.firstElementChild){
      modal = tpl.content.firstElementChild.cloneNode(true);
    } else {
      // Fallback: keep the common filter modal available even when a page does not render base.html.
      modal = document.createElement('div');
      modal.className = 'erp-modal-backdrop erp-table-filter-modal-backdrop';
      modal.id = 'erp-table-filter-modal';
      modal.hidden = true;
      modal.innerHTML = `
        <div class="erp-modal-card erp-table-filter-card" role="dialog" aria-modal="true" aria-labelledby="erp-table-filter-title">
          <div class="erp-modal-header">
            <div><p class="eyebrow">Table Query</p><h2 id="erp-table-filter-title">Filter</h2></div>
            <button type="button" class="erp-modal-close" data-table-filter-close aria-label="Close">×</button>
          </div>
          <div class="erp-modal-body">
            <div class="table-filter-condition-grid" id="erp-table-filter-fields"></div>
          </div>
          <div class="erp-modal-actions">
            <button type="button" class="btn-secondary btn-small" data-table-filter-clear>Clear Conditions</button>
            <button type="button" class="btn-secondary btn-small" data-table-filter-close>Back</button>
            <button type="button" class="btn-primary btn-small" data-table-filter-apply>Apply Filter</button>
          </div>
        </div>`;
    }
    document.body.appendChild(modal);
    modal.addEventListener('click', (ev) => {
      if(ev.target === modal || ev.target.closest('[data-table-filter-close]')) closeFilterModal();
    });
    modal.querySelector('[data-table-filter-apply]')?.addEventListener('click', () => {
      const table = modal._erpTable;
      if(!table) return closeFilterModal();
      const next = {};
      modal.querySelectorAll('[data-filter-col]').forEach(section => {
        const col = section.dataset.filterCol;
        const kind = section.dataset.filterKind;
        if(kind === 'text'){
          // Empty multi-select means All values. The search box only helps find values;
          // it is not a filter condition by itself. This also removes any previous
          // condition for this field when the user leaves it with no selected chips.
          const selected = Array.from(section.querySelectorAll('[data-filter-value]:checked'))
            .map(x => x.value)
            .filter(v => !isBlankLikeValue(v));
          if(selected.length) next[col] = {kind, contains: '', selected};
        }else{
          const from = section.querySelector('[data-filter-from]')?.value || '';
          const to = section.querySelector('[data-filter-to]')?.value || '';
          if(from || to) next[col] = {kind, from, to};
        }
      });
      table._erpAdvancedFilters = next;
      table.dataset.defaultStatusApplied = '1';
      applyFilters(table);
      closeFilterModal();
    });
    modal.querySelector('[data-table-filter-clear]')?.addEventListener('click', () => {
      const table = modal._erpTable;
      if(table){
        table._erpAdvancedFilters = {};
        table.dataset.defaultStatusApplied = '1';
        applyFilters(table);
      }
      closeFilterModal();
    });
    return modal;
  }
  function closeFilterModal(){
    const modal = document.getElementById('erp-table-filter-modal');
    if(!modal) return;
    modal.hidden = true;
    document.body.classList.remove('modal-open');
  }
  function fieldHtmlForColumn(table, index, label){
    const kind = detectColumnKind(table, index, label);
    const current = (table._erpAdvancedFilters || {})[String(index)] || {kind};
    if(kind === 'date'){
      const from = current.from || '';
      const to = current.to || '';
      return `<section class="table-filter-section table-filter-date-section" data-filter-col="${index}" data-filter-kind="date">
        <h3>${escapeHtml(label)}</h3>
        <div class="erp-date-range-picker" data-date-range-picker>
          <input type="hidden" data-filter-from value="${escapeHtml(from)}">
          <input type="hidden" data-filter-to value="${escapeHtml(to)}">
          <button type="button" class="erp-date-range-trigger" data-date-range-toggle>
            <span data-date-range-text>${escapeHtml(dateRangeDisplay(from, to))}</span>
            <span class="erp-date-range-icon" aria-hidden="true">📅</span>
          </button>
          <div class="erp-date-range-panel" data-date-range-panel hidden>
            <div class="erp-date-range-toolbar">
              <button type="button" class="btn-secondary btn-small" data-date-prev aria-label="Previous month">‹</button>
              <div class="erp-date-range-title" data-date-title></div>
              <button type="button" class="btn-secondary btn-small" data-date-next aria-label="Next month">›</button>
            </div>
            <div class="erp-date-range-hint" data-date-hint>Chọn ngày bắt đầu/kết thúc.</div>
            <div class="erp-date-range-months" data-date-months></div>
            <div class="erp-date-range-actions">
              <button type="button" class="btn-secondary btn-small" data-date-clear>Clear date</button>
              <button type="button" class="btn-primary btn-small" data-date-done>Done</button>
            </div>
          </div>
        </div>
      </section>`;
    }
    if(kind === 'number'){
      return `<section class="table-filter-section" data-filter-col="${index}" data-filter-kind="number">
        <h3>${label}</h3>
        <div class="range-filter-row">
          <label>From <input type="text" inputmode="decimal" data-filter-from value="${current.from || ''}" placeholder="1.234,56"></label>
          <label>To <input type="text" inputmode="decimal" data-filter-to value="${current.to || ''}" placeholder="1.234,56"></label>
        </div>
      </section>`;
    }
    const rawValues = buildUniqueValues(table, index);
    // Blank / '-' values are included when the filter is empty because empty means All values.
    // They are not shown as a default option to avoid accidental "blank value + current filter" combinations.
    const values = rawValues.filter(v => !isBlankLikeValue(v));
    const selected = new Set((current.selected || []).filter(v => !isBlankLikeValue(v)));
    const valueHtml = values.slice(0, 250).map(v => {
      const safe = escapeHtml(v);
      const labelSafe = escapeHtml(displayValueLabel(v));
      return `<label class="filter-check erp-multi-option" data-option-label="${labelSafe.toLowerCase()}"><input type="checkbox" data-filter-value value="${safe}" ${selected.has(v) ? 'checked' : ''}> <span>${labelSafe}</span></label>`;
    }).join('');
    return `<section class="table-filter-section" data-filter-col="${index}" data-filter-kind="text">
      <h3>${escapeHtml(label)}</h3>
      <div class="erp-multi-filter" data-multi-filter>
        <div class="erp-multi-filter-control" data-multi-control>
          <div class="erp-multi-filter-chips" data-multi-chips></div>
          <input type="search" data-filter-value-search placeholder="Search & select..." autocomplete="off">
        </div>
        <div class="erp-multi-filter-menu" data-multi-menu hidden>
          <div class="erp-multi-filter-menu-actions">
            <button type="button" class="btn-secondary btn-tiny" data-multi-select-visible>Select shown</button>
            <button type="button" class="btn-secondary btn-tiny" data-multi-clear>Clear</button>
          </div>
          <div class="filter-values-list erp-multi-options">${valueHtml || '<div class="help-text">No specific values. Empty = all values.</div>'}</div>
        </div>
      </div>
    </section>`;
  }
  function buildMonthCalendar(viewDate, fromValue, toValue){
    const monthStart = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
    const firstDay = monthStart.getDay(); // 0 = Sunday
    const daysInMonth = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0).getDate();
    const fromDate = parseYmdLocal(fromValue);
    const toDate = parseYmdLocal(toValue);
    const cells = [];
    const weekLabels = ['CN','T2','T3','T4','T5','T6','T7'];
    weekLabels.forEach(d => cells.push(`<div class="erp-calendar-weekday">${d}</div>`));
    for(let i = 0; i < firstDay; i++) cells.push('<div class="erp-calendar-empty"></div>');
    for(let day = 1; day <= daysInMonth; day++){
      const d = new Date(viewDate.getFullYear(), viewDate.getMonth(), day);
      const ymd = formatYmd(d);
      const isStart = sameYmd(d, fromDate);
      const isEnd = sameYmd(d, toDate);
      const isSingle = isStart && (!toDate || sameYmd(fromDate, toDate));
      const inRange = fromDate && toDate && d > fromDate && d < toDate;
      const classes = ['erp-calendar-day'];
      if(isStart) classes.push('is-start');
      if(isEnd) classes.push('is-end');
      if(isSingle) classes.push('is-single');
      if(inRange) classes.push('is-in-range');
      cells.push(`<button type="button" class="${classes.join(' ')}" data-date-value="${ymd}">${day}</button>`);
    }
    return `<div class="erp-calendar-month"><h4>${monthDisplay(monthStart)}</h4><div class="erp-calendar-grid">${cells.join('')}</div></div>`;
  }
  function closeOtherDateRangePanels(currentPicker){
    document.querySelectorAll('.erp-date-range-picker [data-date-range-panel]:not([hidden])').forEach(panel => {
      const picker = panel.closest('.erp-date-range-picker');
      if(picker !== currentPicker) panel.hidden = true;
    });
  }
  function hydrateDateRangePickers(container){
    container.querySelectorAll('[data-date-range-picker]').forEach(picker => {
      if(picker.dataset.datePickerReady === '1') return;
      picker.dataset.datePickerReady = '1';
      const fromInput = picker.querySelector('[data-filter-from]');
      const toInput = picker.querySelector('[data-filter-to]');
      const trigger = picker.querySelector('[data-date-range-toggle]');
      const text = picker.querySelector('[data-date-range-text]');
      const panel = picker.querySelector('[data-date-range-panel]');
      const title = picker.querySelector('[data-date-title]');
      const months = picker.querySelector('[data-date-months]');
      const hint = picker.querySelector('[data-date-hint]');
      let viewDate = parseYmdLocal(fromInput.value || toInput.value) || new Date();
      viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
      let draftFrom = fromInput.value || '';
      let draftTo = toInput.value || '';
      function updateTrigger(){
        if(text) text.textContent = dateRangeDisplay(fromInput.value, toInput.value);
        trigger?.classList.toggle('has-value', !!(fromInput.value || toInput.value));
      }
      function render(){
        if(title) title.textContent = monthDisplay(viewDate);
        if(hint){
          hint.textContent = draftFrom && !draftTo
            ? 'Chọn ngày kết thúc, sau đó bấm Done.'
            : 'Chọn ngày hoặc khoảng ngày, sau đó bấm Done.';
        }
        months.innerHTML = buildMonthCalendar(viewDate, draftFrom, draftTo);
        updateTrigger();
      }
      trigger?.addEventListener('click', () => {
        closeOtherDateRangePanels(picker);
        panel.hidden = !panel.hidden;
        if(!panel.hidden){
          draftFrom = fromInput.value || '';
          draftTo = toInput.value || '';
          render();
        }
      });
      picker.querySelector('[data-date-prev]')?.addEventListener('click', () => {
        viewDate = addMonths(viewDate, -1);
        render();
      });
      picker.querySelector('[data-date-next]')?.addEventListener('click', () => {
        viewDate = addMonths(viewDate, 1);
        render();
      });
      picker.querySelector('[data-date-clear]')?.addEventListener('click', () => {
        draftFrom = '';
        draftTo = '';
        render();
      });
      picker.querySelector('[data-date-done]')?.addEventListener('click', () => {
        fromInput.value = draftFrom || '';
        toInput.value = draftTo || draftFrom || '';
        panel.hidden = true;
        updateTrigger();
      });
      months?.addEventListener('click', (ev) => {
        const btn = ev.target.closest('[data-date-value]');
        if(!btn) return;
        ev.preventDefault();
        ev.stopPropagation();
        const value = btn.dataset.dateValue;
        const selectedDate = parseYmdLocal(value);
        const currentFrom = parseYmdLocal(draftFrom);
        const currentTo = parseYmdLocal(draftTo);
        if(!currentFrom || currentTo || selectedDate < currentFrom){
          draftFrom = value;
          draftTo = '';
        }else{
          draftTo = value;
        }
        render();
      });
      updateTrigger();
    });
  }

  function hydrateMultiValueFilters(container){
    container.querySelectorAll('[data-multi-filter]').forEach(widget => {
      if(widget.dataset.multiFilterReady === '1') return;
      widget.dataset.multiFilterReady = '1';
      const control = widget.querySelector('[data-multi-control]');
      const input = widget.querySelector('[data-filter-value-search]');
      const menu = widget.querySelector('[data-multi-menu]');
      const chips = widget.querySelector('[data-multi-chips]');
      const options = Array.from(widget.querySelectorAll('.erp-multi-option'));
      const checkboxes = Array.from(widget.querySelectorAll('[data-filter-value]'));

      function checkedBoxes(){
        return checkboxes.filter(cb => cb.checked);
      }
      function renderChips(){
        if(!chips) return;
        const selected = checkedBoxes();
        if(!selected.length){
          chips.innerHTML = '<span class="erp-multi-placeholder">All values (no filter)</span>'; 
          widget.classList.remove('has-selection');
          return;
        }
        widget.classList.add('has-selection');
        const shown = selected.slice(0, 2).map(cb => {
          const label = displayValueLabel(cb.value);
          return `<button type="button" class="erp-multi-chip" data-remove-value="${escapeHtml(cb.value)}" title="Remove ${escapeHtml(label)}">${escapeHtml(label)} <span aria-hidden="true">×</span></button>`;
        }).join('');
        const more = selected.length > 2 ? `<span class="erp-multi-more">+${selected.length - 2}</span>` : '';
        chips.innerHTML = shown + more;
      }
      function filterOptions(){
        const q = normalize(input?.value).toLowerCase();
        let visible = 0;
        options.forEach(option => {
          const text = normalize(option.innerText || option.textContent).toLowerCase();
          const show = !q || text.includes(q);
          option.style.display = show ? '' : 'none';
          if(show) visible++;
        });
        const empty = widget.querySelector('.erp-multi-empty');
        if(empty) empty.remove();
        if(!visible && menu){
          const msg = document.createElement('div');
          msg.className = 'erp-multi-empty help-text';
          msg.textContent = 'No matching value.';
          widget.querySelector('.erp-multi-options')?.appendChild(msg);
        }
      }
      function openMenu(){
        if(menu) menu.hidden = false;
        filterOptions();
      }
      function closeMenu(){
        if(menu) menu.hidden = true;
      }

      renderChips();
      control?.addEventListener('click', () => {
        input?.focus();
        openMenu();
      });
      input?.addEventListener('focus', openMenu);
      input?.addEventListener('input', () => {
        openMenu();
        filterOptions();
      });
      input?.addEventListener('keydown', (ev) => {
        if(ev.key === 'Escape') closeMenu();
      });
      widget.querySelector('[data-multi-clear]')?.addEventListener('click', () => {
        checkboxes.forEach(cb => cb.checked = false);
        if(input) input.value = '';
        filterOptions();
        renderChips();
        input?.focus();
      });
      widget.querySelector('[data-multi-select-visible]')?.addEventListener('click', () => {
        options.forEach(option => {
          if(option.style.display === 'none') return;
          const cb = option.querySelector('[data-filter-value]');
          if(cb) cb.checked = true;
        });
        renderChips();
        input?.focus();
      });
      widget.addEventListener('change', (ev) => {
        if(ev.target.matches('[data-filter-value]')) renderChips();
      });
      chips?.addEventListener('click', (ev) => {
        const btn = ev.target.closest('[data-remove-value]');
        if(!btn) return;
        const value = btn.dataset.removeValue;
        checkboxes.forEach(cb => {
          if(cb.value === value) cb.checked = false;
        });
        renderChips();
        input?.focus();
        openMenu();
      });
      document.addEventListener('click', (ev) => {
        if(widget.contains(ev.target)) return;
        closeMenu();
      });
    });
  }


  function openFilterModal(table){
    const modal = ensureFilterModal();
    const fields = modal.querySelector('#erp-table-filter-fields');
    const title = table.dataset.erpTableTitle || table.dataset.tableTitle || 'Table';
    modal.querySelector('#erp-table-filter-title').textContent = `${title} · Filter`;
    const headerCells = Array.from(table.tHead.rows[0].cells);
    const html = headerCells.map((th, idx) => {
      const label = headerText(th);
      if(shouldSkipAdvancedFilter(label)) return '';
      return fieldHtmlForColumn(table, idx, label);
    }).join('');
    fields.innerHTML = html || '<div class="empty-state">No filterable columns.</div>';
    hydrateDateRangePickers(fields);
    hydrateMultiValueFilters(fields);
    modal._erpTable = table;
    modal.hidden = false;
    document.body.classList.add('modal-open');
  }
  function enhanceTable(table){
    if(!isEnhanceable(table)) return;
    removeLegacyInlineFilterRows(table);
    table.dataset.erpTableReady = '1';
    table.classList.add('erp-enhanced-table');
    getDataRows(table).forEach((row, idx) => row.dataset.originalIndex = String(idx));

    const toolbar = makeToolbar(table);
    table._erpToolbar = toolbar;
    ensureSortableHeaders(table);
    ensureFilterEmptyRow(table);
    applyDefaultStatusFilter(table);

    toolbar?.querySelector('.erp-table-global-search')?.addEventListener('input', () => applyFilters(table));
    toolbar?.querySelector('.erp-table-open-filters')?.addEventListener('click', () => openFilterModal(table));
    toolbar?.querySelector('.erp-table-clear')?.addEventListener('click', () => {
      const global = toolbar.querySelector('.erp-table-global-search');
      if(global) global.value = '';
      table._erpAdvancedFilters = {};
      table.dataset.defaultStatusApplied = '1';
      applyFilters(table);
    });
    applyFilters(table);
  }
  function hasHorizontalScrollWrapper(table){
    return !!table.closest('.table-wrap, .erp-auto-table-wrap, .line-table-wrap, .purchase-line-table-wrap, .item-uom-table-wrap, .bom-table-wrap, .table-responsive');
  }
  function ensureHorizontalScrollWrappers(root){
    const scope = root || document;
    scope.querySelectorAll('table').forEach(table => {
      if(!table || hasHorizontalScrollWrapper(table)) return;
      if(table.closest('[data-no-table-scroll="true"], .no-table-scroll')) return;
      const parent = table.parentNode;
      if(!parent) return;
      const wrapper = document.createElement('div');
      wrapper.className = 'table-wrap erp-auto-table-wrap';
      parent.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    });
  }
  function enhanceTables(root){
    const scope = root || document;
    ensureHorizontalScrollWrappers(scope);
    scope.querySelectorAll('.table-wrap > table, .erp-auto-table-wrap > table, table[data-erp-table="true"]').forEach(enhanceTable);
  }
  window.enhanceErpTables = enhanceTables;
  window.ensureErpTableHorizontalScroll = ensureHorizontalScrollWrappers;
  document.addEventListener('DOMContentLoaded', () => enhanceTables(document));
})();

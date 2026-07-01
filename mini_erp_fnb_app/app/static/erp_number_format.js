(function(){
  const LOCALE = 'vi-VN';

  function cleanNumericText(value){
    return String(value ?? '')
      .replace(/\s+/g, '')
      .replace(/VND/ig, '')
      .replace(/%/g, '')
      .replace(/[^0-9,\.\-]/g, '');
  }

  function normalizeLocaleNumberString(value){
    let s = cleanNumericText(value);
    if(!s || s === '-' || s === ',' || s === '.') return '';
    const negative = /^-/.test(s);
    s = s.replace(/-/g, '');
    const lastComma = s.lastIndexOf(',');
    const lastDot = s.lastIndexOf('.');
    let out = s;

    if(lastComma >= 0 && lastDot >= 0){
      // 1.234,56 => comma is decimal. 1,234.56 => dot is decimal.
      if(lastComma > lastDot){
        out = s.replace(/\./g, '').replace(',', '.');
      }else{
        out = s.replace(/,/g, '');
      }
    }else if(lastComma >= 0){
      // ERP/VN style: comma is decimal separator.
      const parts = s.split(',');
      out = parts.slice(0, -1).join('') + '.' + parts[parts.length - 1];
    }else if(lastDot >= 0){
      const parts = s.split('.');
      if(parts.length > 2){
        // 1.234.567 => thousand groups.
        out = parts.join('');
      }else if(parts.length === 2 && parts[1].length === 3 && parts[0].length >= 1 && parts[0].length <= 3){
        // After fields are converted to ERP/VN input mode, 1.234 means one thousand two hundred thirty-four.
        out = parts.join('');
      }else{
        // Raw backend values in HTML still use dot decimal before JS formats them.
        out = s;
      }
    }
    out = out.replace(/[^0-9.]/g, '');
    if(!out || out === '.') return '';
    return (negative ? '-' : '') + out;
  }

  function parseLocaleNumber(value){
    const normalized = normalizeLocaleNumberString(value);
    if(!normalized) return NaN;
    return Number(normalized);
  }

  function parseBackendNumber(value){
    if(value === null || value === undefined || value === '') return NaN;
    const normalized = String(value).replace(/,/g, '').replace(/[^0-9.\-]/g, '');
    if(!normalized || normalized === '-' || normalized === '.') return NaN;
    return Number(normalized);
  }

  function decimalPlacesFromStep(step){
    const s = String(step || '').trim();
    if(!s || s === 'any') return 4;
    if(!s.includes('.')) return 0;
    return Math.min(8, Math.max(0, s.split('.')[1].length));
  }

  function formatLocaleNumber(value, options){
    const opts = options || {};
    const n = typeof value === 'number' ? value : parseBackendNumber(value);
    if(!Number.isFinite(n)) return value == null ? '' : String(value);
    const max = Number.isInteger(opts.maximumFractionDigits) ? opts.maximumFractionDigits : 4;
    const min = Number.isInteger(opts.minimumFractionDigits) ? opts.minimumFractionDigits : 0;
    return new Intl.NumberFormat(LOCALE, {
      minimumFractionDigits: min,
      maximumFractionDigits: max
    }).format(n);
  }

  function toBackendNumberString(value){
    const normalized = normalizeLocaleNumberString(value);
    if(!normalized) return '';
    return normalized;
  }

  function shouldSkipNumberInput(input){
    const name = (input.name || input.id || '').toLowerCase();
    // Keep year/month fields simple integers, but still mark them as locale-safe for submit.
    return input.type !== 'number' || input.dataset.noLocaleNumber === '1';
  }

  function formatInputValue(input, rawBackendValue){
    if(!input || input.value === '') return;
    const step = input.getAttribute('step');
    const maxFractionDigits = decimalPlacesFromStep(step);
    const n = rawBackendValue === true ? parseBackendNumber(input.value) : parseLocaleNumber(input.value);
    if(Number.isFinite(n)){
      input.value = formatLocaleNumber(n, {maximumFractionDigits: maxFractionDigits});
    }
  }

  function setNumberInputValue(input, value){
    if(!input) return;
    const step = input.getAttribute('step');
    const maxFractionDigits = decimalPlacesFromStep(step);
    input.value = formatLocaleNumber(value, {maximumFractionDigits: maxFractionDigits});
  }

  function prepareNumberInput(input){
    if(!input) return;
    if(input.dataset.erpLocaleNumber === '1' && input.dataset.erpPreparedLocaleNumber === '1') return;
    if(shouldSkipNumberInput(input) && input.dataset.erpLocaleNumber !== '1') return;
    input.dataset.erpLocaleNumber = '1';
    input.dataset.erpPreparedLocaleNumber = '1';
    input.dataset.originalType = input.type;
    input.type = 'text';
    input.inputMode = 'decimal';
    input.autocomplete = input.autocomplete || 'off';
    formatInputValue(input, true);
    input.addEventListener('blur', () => formatInputValue(input, false));
    input.addEventListener('focus', () => {
      // Keep the ERP display separator while editing; users can type comma decimals directly.
      input.select?.();
    });
  }

  function normalizeFormNumbers(form){
    if(!form) return;
    form.querySelectorAll('input[data-erp-locale-number="1"]').forEach(input => {
      const normalized = toBackendNumberString(input.value);
      if(normalized !== '') input.value = normalized;
    });
  }

  function prepareAllNumberInputs(root){
    (root || document).querySelectorAll('input[type="number"], input[data-erp-locale-number="1"]').forEach(prepareNumberInput);
  }

  window.erpParseNumber = parseLocaleNumber;
  window.erpParseLocaleNumber = parseLocaleNumber;
  window.erpNormalizeLocaleNumberString = normalizeLocaleNumberString;
  window.erpToBackendNumberString = toBackendNumberString;
  window.erpFormatNumber = formatLocaleNumber;
  window.erpFormatInputNumber = formatLocaleNumber;
  window.erpSetNumberInput = setNumberInputValue;
  window.erpPrepareNumberInputs = prepareAllNumberInputs;
  window.erpNormalizeFormNumbers = normalizeFormNumbers;

  const nativeSubmit = window.HTMLFormElement && HTMLFormElement.prototype.submit;
  if(nativeSubmit && !HTMLFormElement.prototype.__erpNumberSubmitPatched){
    HTMLFormElement.prototype.submit = function(){
      normalizeFormNumbers(this);
      return nativeSubmit.call(this);
    };
    HTMLFormElement.prototype.__erpNumberSubmitPatched = true;
  }

  document.addEventListener('submit', (event) => {
    if(event.defaultPrevented) return;
    normalizeFormNumbers(event.target);
  });

  document.addEventListener('DOMContentLoaded', () => prepareAllNumberInputs(document));
})();

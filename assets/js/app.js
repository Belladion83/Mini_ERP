(() => {
  const STORAGE_KEY = 'mini_erp_fnb_demo_state_v001';
  const SESSION_KEY = 'mini_erp_fnb_demo_session_v001';
  const LOCK_KEY = 'mini_erp_fnb_demo_login_attempts_v001';

  const seed = {
    meta: { version: '0.01', generatedAt: '2026-07-06', mode: 'static-github-pages' },
    users: [
      { email: 'admin@mini.erp', password: 'admin123', name: 'Admin Demo', role: 'ADMIN' },
      { email: 'buyer@mini.erp', password: 'buyer123', name: 'Buyer Demo', role: 'PURCHASING' }
    ],
    numberRanges: {
      PR: 10000001,
      PO: 45000001,
      GR: 50000001,
      SO: 70000001,
      PRD: 80000001
    },
    bps: [
      { code: 'V10001', name: 'Saigon Fresh Food Co., Ltd', type: 'Vendor', category: 'Enterprise', city: 'TP.HCM', contact: 'procurement@saigonfresh.demo' },
      { code: 'V10002', name: 'Mekong Ingredient Supplier', type: 'Vendor', category: 'Enterprise', city: 'Cần Thơ', contact: 'sales@mekonging.demo' },
      { code: 'C20001', name: 'Jolie Wedding & Event', type: 'Customer', category: 'Enterprise', city: 'TP.HCM', contact: 'event@jolie.demo' },
      { code: 'C20002', name: 'Retail Store Binh Thanh', type: 'Customer', category: 'Enterprise', city: 'TP.HCM', contact: 'store@retail.demo' }
    ],
    items: [
      { code: 'RM-FLOUR', name: 'Bột mì đa dụng', itemType: 'RAW', baseUnit: 'kg', orderUnit: 'bag', conversion: 25, inputTax: 'VAT-IN08', outputTax: '', canBeSold: false, salesPrice: 0, lastCost: 18000, stock: 220, estimateReceiveDays: 2, deliveryDays: 0 },
      { code: 'RM-SUGAR', name: 'Đường cát trắng', itemType: 'RAW', baseUnit: 'kg', orderUnit: 'bag', conversion: 50, inputTax: 'VAT-IN08', outputTax: '', canBeSold: false, salesPrice: 0, lastCost: 21000, stock: 165, estimateReceiveDays: 3, deliveryDays: 0 },
      { code: 'PK-BOX01', name: 'Hộp giấy size M', itemType: 'PACK', baseUnit: 'pcs', orderUnit: 'pcs', conversion: 1, inputTax: 'VAT-IN08', outputTax: '', canBeSold: false, salesPrice: 0, lastCost: 1200, stock: 480, estimateReceiveDays: 4, deliveryDays: 0 },
      { code: 'FG-CAKE01', name: 'Bánh bông lan mini', itemType: 'FINISHED', baseUnit: 'pcs', orderUnit: 'pcs', conversion: 1, inputTax: '', outputTax: 'VAT-OUT08', canBeSold: true, salesPrice: 26000, lastCost: 16000, stock: 96, estimateReceiveDays: 0, deliveryDays: 1 },
      { code: 'FG-TEA01', name: 'Trà đào đóng chai', itemType: 'FINISHED', baseUnit: 'bottle', orderUnit: 'carton', conversion: 24, inputTax: '', outputTax: 'VAT-OUT08', canBeSold: true, salesPrice: 18000, lastCost: 9800, stock: 75, estimateReceiveDays: 0, deliveryDays: 1 }
    ],
    glAccounts: [
      { code: '1519', name: 'Hàng mua đang đi đường', type: 'Balance Sheet', openItem: true },
      { code: '1520', name: 'Nguyên vật liệu', type: 'Balance Sheet', openItem: false },
      { code: '1550', name: 'Thành phẩm', type: 'Balance Sheet', openItem: false },
      { code: '3310', name: 'Phải trả người bán', type: 'Balance Sheet', openItem: true },
      { code: '5110', name: 'Doanh thu bán hàng', type: 'P&L', openItem: false },
      { code: '5210', name: 'Giảm trừ doanh thu', type: 'P&L', openItem: false }
    ],
    taxCodes: [
      { code: 'VAT-IN08', type: 'INPUT', rate: 8, account: '1331' },
      { code: 'VAT-IN10', type: 'INPUT', rate: 10, account: '1331' },
      { code: 'VAT-OUT08', type: 'OUTPUT', rate: 8, account: '3331' },
      { code: 'VAT-OUT10', type: 'OUTPUT', rate: 10, account: '3331' }
    ],
    warehouses: [
      { code: 'WH-RM', name: 'Raw Material Warehouse' },
      { code: 'WH-FG', name: 'Finished Goods Warehouse' },
      { code: 'WH-GIT', name: 'Goods In Transit' }
    ],
    recipes: [
      { code: 'BOM-FG-CAKE01', fg: 'FG-CAKE01', lines: [{ item: 'RM-FLOUR', qty: 0.12 }, { item: 'RM-SUGAR', qty: 0.05 }, { item: 'PK-BOX01', qty: 1 }] },
      { code: 'BOM-FG-TEA01', fg: 'FG-TEA01', lines: [{ item: 'RM-SUGAR', qty: 0.04 }, { item: 'PK-BOX01', qty: 1 }] }
    ],
    prs: [
      { docNo: 'PR10000001', date: '2026-07-06', requestedBy: 'Admin Demo', vendor: 'V10001', status: 'RELEASED', lines: [{ item: 'RM-FLOUR', orderQty: 10, orderUnit: 'bag', baseQty: 250, unitPrice: 18000, taxCode: 'VAT-IN08' }] },
      { docNo: 'PR10000002', date: '2026-07-06', requestedBy: 'Admin Demo', vendor: 'V10002', status: 'DRAFT', lines: [{ item: 'RM-SUGAR', orderQty: 5, orderUnit: 'bag', baseQty: 250, unitPrice: 21000, taxCode: 'VAT-IN08' }] }
    ],
    pos: [],
    grs: [],
    sos: [
      { docNo: 'SO70000001', date: '2026-07-06', customer: 'C20001', status: 'RELEASED', lines: [{ item: 'FG-CAKE01', qty: 50, unitPrice: 26000 }] }
    ],
    productions: []
  };

  let state = loadState();
  let currentUser = readSession();
  let currentPage = 'dashboard';
  let modalContext = null;

  const $ = (id) => document.getElementById(id);
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'master', label: 'Master Data' },
    { id: 'pr', label: 'Purchase Requisition' },
    { id: 'po', label: 'Purchase Order' },
    { id: 'gr', label: 'Goods Receipt' },
    { id: 'sales', label: 'Sales Order' },
    { id: 'production', label: 'Production' },
    { id: 'reports', label: 'Reports' }
  ];

  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function loadState() {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return clone(seed);
    try { return { ...clone(seed), ...JSON.parse(raw) }; }
    catch { return clone(seed); }
  }
  function saveState() { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
  function readSession() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY)); }
    catch { return null; }
  }
  function saveSession(user) {
    currentUser = user;
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(user));
  }
  function clearSession() {
    currentUser = null;
    sessionStorage.removeItem(SESSION_KEY);
  }
  function attempts() {
    try { return JSON.parse(localStorage.getItem(LOCK_KEY)) || {}; }
    catch { return {}; }
  }
  function setAttempts(value) { localStorage.setItem(LOCK_KEY, JSON.stringify(value)); }
  function today() { return new Date().toISOString().slice(0, 10); }
  function fmt(n) { return new Intl.NumberFormat('vi-VN').format(Number(n || 0)); }
  function money(n) { return `${fmt(n)} VND`; }
  function esc(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  }
  function statusBadge(status) { return `<span class="status ${String(status).toLowerCase()}">${esc(status)}</span>`; }
  function item(code) { return state.items.find((x) => x.code === code); }
  function bp(code) { return state.bps.find((x) => x.code === code); }
  function nextNo(prefix) {
    const n = state.numberRanges[prefix];
    state.numberRanges[prefix] += 1;
    return `${prefix}${n}`;
  }
  function lineAmount(line) { return Number(line.baseQty || line.qty || 0) * Number(line.unitPrice || 0); }
  function docAmount(lines) { return (lines || []).reduce((sum, line) => sum + lineAmount(line), 0); }
  function getItemOptions(filterFn = () => true) {
    return state.items.filter(filterFn).map((x) => `<option value="${esc(x.code)}">${esc(x.code)} · ${esc(x.name)}</option>`).join('');
  }
  function getBpOptions(type) {
    return state.bps.filter((x) => x.type === type).map((x) => `<option value="${esc(x.code)}">${esc(x.code)} · ${esc(x.name)}</option>`).join('');
  }
  function notify(message, type = '') {
    const node = document.createElement('div');
    node.className = `notice ${type}`.trim();
    node.textContent = message;
    const view = $('view');
    view.prepend(node);
    setTimeout(() => node.remove(), 4200);
  }

  function init() {
    $('loginForm').addEventListener('submit', onLogin);
    $('logoutBtn').addEventListener('click', () => { clearSession(); showLogin(); });
    $('resetDataBtn').addEventListener('click', resetData);
    $('modalClose').addEventListener('click', closeModal);
    $('modalEdit').addEventListener('click', () => setModalEditMode(true));
    $('modalSave').addEventListener('click', saveModalRecord);
    renderMenu();
    if (currentUser) showMain(); else showLogin();
  }

  function onLogin(event) {
    event.preventDefault();
    const email = $('loginEmail').value.trim().toLowerCase();
    const password = $('loginPassword').value;
    const allAttempts = attempts();
    const count = allAttempts[email] || 0;
    if (count >= 5) {
      $('loginMessage').textContent = 'User đã bị khóa sau 5 lần sai. Hãy reset demo data hoặc liên hệ Admin.';
      return;
    }
    const user = state.users.find((x) => x.email === email && x.password === password);
    if (!user) {
      allAttempts[email] = count + 1;
      setAttempts(allAttempts);
      $('loginMessage').textContent = `Sai thông tin đăng nhập. Số lần sai: ${allAttempts[email]}/5.`;
      return;
    }
    allAttempts[email] = 0;
    setAttempts(allAttempts);
    saveSession({ email: user.email, name: user.name, role: user.role });
    showMain();
  }

  function showLogin() {
    $('mainScreen').classList.add('hidden');
    $('loginScreen').classList.remove('hidden');
  }
  function showMain() {
    $('loginScreen').classList.add('hidden');
    $('mainScreen').classList.remove('hidden');
    $('activeUser').textContent = `${currentUser.name} · ${currentUser.role}`;
    route(currentPage);
  }
  function resetData() {
    if (!confirm('Reset toàn bộ dữ liệu demo trên trình duyệt này?')) return;
    state = clone(seed);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    localStorage.removeItem(LOCK_KEY);
    route('dashboard');
    notify('Đã reset dữ liệu demo.', 'warning');
  }

  function renderMenu() {
    $('menu').innerHTML = menuItems.map((m) => `<button data-page="${m.id}">${m.label}<span>›</span></button>`).join('');
    $('menu').querySelectorAll('button').forEach((btn) => btn.addEventListener('click', () => route(btn.dataset.page)));
  }
  function route(page) {
    currentPage = page;
    $('pageTitle').textContent = menuItems.find((x) => x.id === page)?.label || 'Dashboard';
    $('menu').querySelectorAll('button').forEach((btn) => btn.classList.toggle('active', btn.dataset.page === page));
    const renderer = {
      dashboard: renderDashboard,
      master: renderMaster,
      pr: renderPR,
      po: renderPO,
      gr: renderGR,
      sales: renderSales,
      production: renderProduction,
      reports: renderReports
    }[page];
    renderer();
  }

  function table(headers, rows) {
    if (!rows.length) return $('emptyStateTemplate').innerHTML;
    return `<div class="table-wrap"><table><thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
  }

  function renderDashboard() {
    const openPR = state.prs.filter((x) => x.status === 'DRAFT' || x.status === 'RELEASED').length;
    const releasedPO = state.pos.filter((x) => x.status === 'RELEASED').length;
    const salesDemand = state.sos.reduce((s, so) => s + so.lines.reduce((x, l) => x + Number(l.qty || 0), 0), 0);
    const invValue = state.items.reduce((s, x) => s + Number(x.stock || 0) * Number(x.lastCost || 0), 0);
    $('view').innerHTML = `
      <section class="kpi-grid">
        <div class="kpi"><span>Open PR</span><strong>${fmt(openPR)}</strong></div>
        <div class="kpi"><span>Released PO</span><strong>${fmt(releasedPO)}</strong></div>
        <div class="kpi"><span>Sales Demand</span><strong>${fmt(salesDemand)}</strong></div>
        <div class="kpi"><span>Inventory Value</span><strong>${money(invValue)}</strong></div>
      </section>
      <section class="card">
        <div class="card-head"><div><h3>Mini_ERP F&B Web Demo</h3><p>Bản static mô phỏng các flow chính: Master Data, PR → PO → GR, Sales và Production.</p></div></div>
        <div class="card-body">
          <div class="notice">Bản này không có backend/database server. Mỗi trình duyệt lưu dữ liệu riêng bằng localStorage. Click trực tiếp vào mã master data hoặc document number để mở View mode, sau đó bấm Edit nếu muốn chỉnh các field được phép.</div>
        </div>
      </section>
      <section class="split-grid">
        <div class="card"><div class="card-head"><div><h3>Recent Purchase Requisitions</h3><p>PR status có PO_CREATED để chặn tạo PO lặp.</p></div></div><div class="card-body">${renderPRTable(state.prs.slice(0, 5), false)}</div></div>
        <div class="card"><div class="card-head"><div><h3>Inventory Snapshot</h3><p>Số lượng tồn hiển thị theo base unit.</p></div></div><div class="card-body">${renderInventoryTable()}</div></div>
      </section>`;
    bindDocLinks();
  }

  function renderMaster() {
    $('view').innerHTML = `
      <section class="card"><div class="card-head"><div><h3>Business Partner</h3><p>Customer/Vendor master data.</p></div></div><div class="card-body">${renderMasterTable('bps')}</div></section>
      <section class="card"><div class="card-head"><div><h3>Item Master</h3><p>Purchasing/Sales/Accounting/Manufacturing attributes.</p></div></div><div class="card-body">${renderMasterTable('items')}</div></section>
      <section class="card"><div class="card-head"><div><h3>GL Master</h3><p>Open item and account attributes.</p></div></div><div class="card-body">${renderMasterTable('glAccounts')}</div></section>
      <section class="card"><div class="card-head"><div><h3>Tax Code</h3><p>Input/Output VAT master.</p></div></div><div class="card-body">${renderMasterTable('taxCodes')}</div></section>`;
    bindDocLinks();
  }

  function renderMasterTable(collection) {
    const rows = state[collection].map((x) => {
      if (collection === 'bps') return `<tr><td><button class="doc-link" data-open="master" data-collection="bps" data-key="${esc(x.code)}">${esc(x.code)}</button></td><td>${esc(x.name)}</td><td>${esc(x.type)}</td><td>${esc(x.category)}</td><td>${esc(x.city)}</td><td>${esc(x.contact)}</td></tr>`;
      if (collection === 'items') return `<tr><td><button class="doc-link" data-open="master" data-collection="items" data-key="${esc(x.code)}">${esc(x.code)}</button></td><td>${esc(x.name)}</td><td>${esc(x.itemType)}</td><td>${esc(x.baseUnit)}</td><td>${esc(x.orderUnit)}</td><td>${fmt(x.stock)}</td><td>${money(x.lastCost)}</td><td>${x.canBeSold ? 'Yes' : 'No'}</td></tr>`;
      if (collection === 'glAccounts') return `<tr><td><button class="doc-link" data-open="master" data-collection="glAccounts" data-key="${esc(x.code)}">${esc(x.code)}</button></td><td>${esc(x.name)}</td><td>${esc(x.type)}</td><td>${x.openItem ? 'Yes' : 'No'}</td></tr>`;
      return `<tr><td><button class="doc-link" data-open="master" data-collection="taxCodes" data-key="${esc(x.code)}">${esc(x.code)}</button></td><td>${esc(x.type)}</td><td>${fmt(x.rate)}%</td><td>${esc(x.account)}</td></tr>`;
    });
    const headers = {
      bps: ['Code', 'Name', 'Type', 'Category', 'City', 'Contact'],
      items: ['Code', 'Name', 'Type', 'Base Unit', 'Order Unit', 'Stock', 'Last Cost', 'Can be sold'],
      glAccounts: ['Code', 'Name', 'Type', 'Open Item'],
      taxCodes: ['Code', 'Type', 'Rate', 'VAT Account']
    }[collection];
    return table(headers, rows);
  }

  function renderPR() {
    $('view').innerHTML = `
      <section class="split-grid">
        <div class="card">
          <div class="card-head"><div><h3>Create Purchase Requisition</h3><p>Save/Release xong sẽ giữ nguyên màn hình và clear input.</p></div></div>
          <div class="card-body">
            <form id="prForm" class="form-grid single">
              <label>PR Date<input name="date" type="date" value="${today()}" required></label>
              <label>Vendor<select name="vendor" required>${getBpOptions('Vendor')}</select></label>
              <div class="line-editor" id="prLines">${purchaseLineRow()}</div>
              <button type="button" class="secondary" id="addPrLine">Add line</button>
              <button type="button" class="ghost" id="getPrPrice">Get Price</button>
              <button type="submit" class="primary">Save Draft</button>
              <button type="button" class="primary" id="saveReleasePr">Save & Release</button>
            </form>
          </div>
        </div>
        <div class="card"><div class="card-head"><div><h3>PR List</h3><p>Default list tập trung các PR còn xử lý.</p></div></div><div class="card-body">${renderPRTable(state.prs, true)}</div></div>
      </section>`;
    $('addPrLine').addEventListener('click', () => $('prLines').insertAdjacentHTML('beforeend', purchaseLineRow()));
    $('getPrPrice').addEventListener('click', () => fillPrice('prForm'));
    $('prForm').addEventListener('submit', (e) => savePR(e, 'DRAFT'));
    $('saveReleasePr').addEventListener('click', () => savePR(null, 'RELEASED'));
    bindDocLinks();
  }

  function purchaseLineRow() {
    return `<div class="line-row">
      <label>Item<select name="item">${getItemOptions((x) => x.itemType !== 'FINISHED')}</select></label>
      <label>Order Qty<input name="orderQty" type="number" min="0.01" step="0.01" value="1"></label>
      <label>Unit<input name="orderUnit" value="bag"></label>
      <label>Unit Price<input name="unitPrice" type="number" min="0" step="100" value="0"></label>
      <button type="button" class="danger" onclick="this.closest('.line-row').remove()">Remove</button>
    </div>`;
  }
  function collectPurchaseLines(formId) {
    return [...$(formId).querySelectorAll('.line-row')].map((row) => {
      const code = row.querySelector('[name=item]').value;
      const it = item(code);
      const orderQty = Number(row.querySelector('[name=orderQty]').value || 0);
      const orderUnit = row.querySelector('[name=orderUnit]').value || it.orderUnit;
      const conversion = orderUnit === it.baseUnit ? 1 : Number(it.conversion || 1);
      return { item: code, orderQty, orderUnit, baseQty: orderQty * conversion, unitPrice: Number(row.querySelector('[name=unitPrice]').value || it.lastCost), taxCode: it.inputTax };
    }).filter((x) => x.item && x.orderQty > 0);
  }
  function fillPrice(formId) {
    [...$(formId).querySelectorAll('.line-row')].forEach((row) => {
      const it = item(row.querySelector('[name=item]').value);
      if (!it) return;
      row.querySelector('[name=unitPrice]').value = it.lastCost;
      row.querySelector('[name=orderUnit]').value = it.orderUnit;
    });
    notify('Đã lấy latest unit cost theo Item Master.', 'warning');
  }
  function savePR(event, status) {
    event?.preventDefault();
    const form = $('prForm');
    const lines = collectPurchaseLines('prForm');
    if (!lines.length) return notify('PR cần ít nhất 1 line hợp lệ.', 'danger');
    state.prs.unshift({ docNo: nextNo('PR'), date: form.date.value, requestedBy: currentUser.name, vendor: form.vendor.value, status, lines });
    saveState();
    renderPR();
    notify(`Đã tạo PR trạng thái ${status}.`);
  }
  function renderPRTable(prs, withActions) {
    const rows = prs.map((pr) => `<tr>
      <td><button class="doc-link" data-open="pr" data-key="${esc(pr.docNo)}">${esc(pr.docNo)}</button></td><td>${esc(pr.date)}</td><td>${esc(bp(pr.vendor)?.name || pr.vendor)}</td><td>${esc(pr.requestedBy)}</td><td>${statusBadge(pr.status)}</td><td>${money(docAmount(pr.lines))}</td>
      ${withActions ? `<td><div class="inline-actions">${pr.status === 'DRAFT' ? `<button class="secondary" data-action="release-pr" data-key="${esc(pr.docNo)}">Release</button>` : ''}${pr.status === 'RELEASED' ? `<button class="primary" data-action="create-po" data-key="${esc(pr.docNo)}">Create PO</button>` : ''}</div></td>` : ''}
    </tr>`);
    setTimeout(bindPRActions, 0);
    return table(withActions ? ['PR No', 'Date', 'Vendor', 'Requested By', 'Status', 'Amount', 'Actions'] : ['PR No', 'Date', 'Vendor', 'Requested By', 'Status', 'Amount'], rows);
  }
  function bindPRActions() {
    document.querySelectorAll('[data-action="release-pr"]').forEach((btn) => btn.addEventListener('click', () => {
      const pr = state.prs.find((x) => x.docNo === btn.dataset.key);
      pr.status = 'RELEASED'; saveState(); route('pr'); notify(`${pr.docNo} đã Release.`);
    }));
    document.querySelectorAll('[data-action="create-po"]').forEach((btn) => btn.addEventListener('click', () => createPOFromPR(btn.dataset.key)));
  }
  function createPOFromPR(prNo) {
    const pr = state.prs.find((x) => x.docNo === prNo);
    if (!pr || pr.status !== 'RELEASED') return notify('Chỉ PR RELEASED mới tạo PO được.', 'danger');
    const po = { docNo: nextNo('PO'), date: today(), vendor: pr.vendor, sourcePR: pr.docNo, status: 'DRAFT', lines: clone(pr.lines) };
    state.pos.unshift(po);
    pr.status = 'PO_CREATED';
    saveState();
    route('po');
    notify(`Đã tạo ${po.docNo} từ ${pr.docNo}.`);
  }

  function renderPO() {
    $('view').innerHTML = `
      <section class="card"><div class="card-head"><div><h3>PO List</h3><p>PO từ PR sẽ copy unit price và tax code từ PR. Sau Release, chứng từ bị khóa.</p></div></div><div class="card-body">${renderPOTable()}</div></section>
      <section class="card"><div class="card-head"><div><h3>Create Manual PO</h3><p>Trường hợp không đi từ PR, giá mặc định lấy latest inventory unit cost.</p></div></div><div class="card-body">
        <form id="poForm" class="form-grid">
          <label>PO Date<input name="date" type="date" value="${today()}" required></label>
          <label>Vendor<select name="vendor" required>${getBpOptions('Vendor')}</select></label>
          <div class="line-editor" id="poLines">${purchaseLineRow()}</div>
          <button type="button" class="secondary" id="addPoLine">Add line</button>
          <button type="button" class="ghost" id="getPoPrice">Get Price</button>
          <button type="submit" class="primary">Save Draft</button>
        </form>
      </div></section>`;
    $('addPoLine').addEventListener('click', () => $('poLines').insertAdjacentHTML('beforeend', purchaseLineRow()));
    $('getPoPrice').addEventListener('click', () => fillPrice('poForm'));
    $('poForm').addEventListener('submit', (e) => {
      e.preventDefault();
      const lines = collectPurchaseLines('poForm');
      if (!lines.length) return notify('PO cần ít nhất 1 line hợp lệ.', 'danger');
      state.pos.unshift({ docNo: nextNo('PO'), date: $('poForm').date.value, vendor: $('poForm').vendor.value, sourcePR: '', status: 'DRAFT', lines });
      saveState(); renderPO(); notify('Đã tạo manual PO.');
    });
    bindDocLinks(); bindPOActions();
  }
  function renderPOTable() {
    const rows = state.pos.map((po) => `<tr>
      <td><button class="doc-link" data-open="po" data-key="${esc(po.docNo)}">${esc(po.docNo)}</button></td><td>${esc(po.date)}</td><td>${esc(bp(po.vendor)?.name || po.vendor)}</td><td>${esc(po.sourcePR || 'Manual')}</td><td>${statusBadge(po.status)}</td><td>${po.lines.length}</td><td>${money(docAmount(po.lines))}</td>
      <td><div class="inline-actions">${po.status === 'DRAFT' ? `<button class="secondary" data-action="release-po" data-key="${esc(po.docNo)}">Release</button>` : ''}${po.status === 'RELEASED' ? `<button class="primary" data-action="receive-po" data-key="${esc(po.docNo)}">Create GR</button>` : ''}</div></td>
    </tr>`);
    return table(['PO No', 'Date', 'Vendor', 'Source PR', 'Status', 'Lines', 'Amount', 'Actions'], rows);
  }
  function bindPOActions() {
    document.querySelectorAll('[data-action="release-po"]').forEach((btn) => btn.addEventListener('click', () => {
      const po = state.pos.find((x) => x.docNo === btn.dataset.key); po.status = 'RELEASED'; saveState(); route('po'); notify(`${po.docNo} đã Release.`);
    }));
    document.querySelectorAll('[data-action="receive-po"]').forEach((btn) => btn.addEventListener('click', () => createGRFromPO(btn.dataset.key)));
  }
  function createGRFromPO(poNo) {
    const po = state.pos.find((x) => x.docNo === poNo);
    if (!po || po.status !== 'RELEASED') return notify('Chỉ PO RELEASED mới tạo GR được.', 'danger');
    const gr = { docNo: nextNo('GR'), date: today(), vendor: po.vendor, sourcePO: po.docNo, gitPosting: true, status: 'POSTED', lines: clone(po.lines) };
    gr.lines.forEach((line) => {
      const it = item(line.item);
      if (it) it.stock = Number(it.stock || 0) + Number(line.baseQty || 0);
    });
    po.status = 'RECEIVED';
    state.grs.unshift(gr);
    saveState(); route('gr'); notify(`Đã post ${gr.docNo}. Dr Inventory / Cr 1519 nếu tick GIT posting.`);
  }

  function renderGR() {
    $('view').innerHTML = `<section class="card"><div class="card-head"><div><h3>Goods Receipt List</h3><p>GR cập nhật tồn kho theo base unit. GIT posting demo: Dr Inventory / Cr 1519.</p></div></div><div class="card-body">${renderGRTable()}</div></section>`;
    bindDocLinks();
  }
  function renderGRTable() {
    const rows = state.grs.map((gr) => `<tr><td><button class="doc-link" data-open="gr" data-key="${esc(gr.docNo)}">${esc(gr.docNo)}</button></td><td>${esc(gr.date)}</td><td>${esc(gr.sourcePO)}</td><td>${esc(bp(gr.vendor)?.name || gr.vendor)}</td><td>${gr.gitPosting ? 'Yes' : 'No'}</td><td>${statusBadge(gr.status)}</td><td>${money(docAmount(gr.lines))}</td></tr>`);
    return table(['GR No', 'Date', 'Source PO', 'Vendor', 'GIT Posting', 'Status', 'Amount'], rows);
  }

  function renderSales() {
    $('view').innerHTML = `<section class="split-grid">
      <div class="card"><div class="card-head"><div><h3>Create Sales Order</h3><p>Finished Goods only. Có kiểm tra tồn kho trước khi Release.</p></div></div><div class="card-body">
        <form id="soForm" class="form-grid single">
          <label>SO Date<input name="date" type="date" value="${today()}" required></label>
          <label>Customer<select name="customer" required>${getBpOptions('Customer')}</select></label>
          <div class="line-editor" id="soLines">${salesLineRow()}</div>
          <button type="button" class="secondary" id="addSoLine">Add line</button>
          <button type="button" class="ghost" id="checkAvailability">Check Availability</button>
          <button type="submit" class="primary">Save & Release</button>
        </form>
      </div></div>
      <div class="card"><div class="card-head"><div><h3>SO List</h3><p>Nếu thiếu tồn, hệ thống gợi ý tạo Production Request.</p></div></div><div class="card-body">${renderSOTable()}</div></div>
    </section>`;
    $('addSoLine').addEventListener('click', () => $('soLines').insertAdjacentHTML('beforeend', salesLineRow()));
    $('checkAvailability').addEventListener('click', () => availabilityMessage(collectSalesLines(), true));
    $('soForm').addEventListener('submit', saveSO);
    bindDocLinks(); bindSOActions();
  }
  function salesLineRow() {
    return `<div class="line-row"><label>Finished Good<select name="item">${getItemOptions((x) => x.canBeSold)}</select></label><label>Qty<input name="qty" type="number" min="1" step="1" value="1"></label><label>Unit Price<input name="unitPrice" type="number" min="0" step="100" value="0"></label><span></span><button type="button" class="danger" onclick="this.closest('.line-row').remove()">Remove</button></div>`;
  }
  function collectSalesLines() {
    return [...$('soForm').querySelectorAll('.line-row')].map((row) => {
      const code = row.querySelector('[name=item]').value;
      const it = item(code);
      const qty = Number(row.querySelector('[name=qty]').value || 0);
      const priceInput = Number(row.querySelector('[name=unitPrice]').value || 0);
      return { item: code, qty, unitPrice: priceInput || it.salesPrice };
    }).filter((x) => x.item && x.qty > 0);
  }
  function availabilityMessage(lines, visible) {
    const shortages = lines.map((line) => ({ line, it: item(line.item), shortage: Math.max(0, Number(line.qty) - Number(item(line.item)?.stock || 0)) })).filter((x) => x.shortage > 0);
    if (visible) notify(shortages.length ? `Thiếu tồn: ${shortages.map((x) => `${x.it.code} thiếu ${fmt(x.shortage)}`).join(', ')}` : 'Tồn kho đủ cho SO này.', shortages.length ? 'warning' : '');
    return shortages;
  }
  function saveSO(event) {
    event.preventDefault();
    const lines = collectSalesLines();
    if (!lines.length) return notify('SO cần ít nhất 1 line hợp lệ.', 'danger');
    const shortages = availabilityMessage(lines, false);
    const so = { docNo: nextNo('SO'), date: $('soForm').date.value, customer: $('soForm').customer.value, status: shortages.length ? 'DRAFT' : 'RELEASED', lines };
    state.sos.unshift(so);
    saveState(); renderSales();
    notify(shortages.length ? `${so.docNo} đang DRAFT vì thiếu tồn. Có thể tạo Production Request.` : `${so.docNo} đã Release.`);
  }
  function renderSOTable() {
    const rows = state.sos.map((so) => `<tr><td><button class="doc-link" data-open="so" data-key="${esc(so.docNo)}">${esc(so.docNo)}</button></td><td>${esc(so.date)}</td><td>${esc(bp(so.customer)?.name || so.customer)}</td><td>${statusBadge(so.status)}</td><td>${money(docAmount(so.lines))}</td><td><div class="inline-actions">${so.status === 'DRAFT' ? `<button class="primary" data-action="create-prd" data-key="${esc(so.docNo)}">Create Production Request</button>` : ''}</div></td></tr>`);
    return table(['SO No', 'Date', 'Customer', 'Status', 'Amount', 'Actions'], rows);
  }
  function bindSOActions() {
    document.querySelectorAll('[data-action="create-prd"]').forEach((btn) => btn.addEventListener('click', () => createProductionFromSO(btn.dataset.key)));
  }
  function createProductionFromSO(soNo) {
    const so = state.sos.find((x) => x.docNo === soNo);
    const lines = so.lines.map((l) => ({ fg: l.item, qty: Math.max(0, Number(l.qty) - Number(item(l.item)?.stock || 0)), issueWh: 'WH-RM', receiptWh: 'WH-FG' })).filter((x) => x.qty > 0);
    if (!lines.length) return notify('Không còn thiếu tồn để tạo Production Request.', 'warning');
    const doc = { docNo: nextNo('PRD'), date: today(), sourceSO: so.docNo, status: 'DRAFT', lines };
    state.productions.unshift(doc);
    saveState(); route('production'); notify(`Đã tạo ${doc.docNo} từ ${so.docNo}.`);
  }

  function renderProduction() {
    $('view').innerHTML = `<section class="card"><div class="card-head"><div><h3>Production Requests</h3><p>Issue WH và Receipt WH nằm ở line level.</p></div></div><div class="card-body">${renderProductionTable()}</div></section>`;
    bindDocLinks(); bindProductionActions();
  }
  function renderProductionTable() {
    const rows = state.productions.map((p) => `<tr><td><button class="doc-link" data-open="prd" data-key="${esc(p.docNo)}">${esc(p.docNo)}</button></td><td>${esc(p.date)}</td><td>${esc(p.sourceSO || 'Manual')}</td><td>${statusBadge(p.status)}</td><td>${p.lines.map((l) => `${esc(l.fg)}: ${fmt(l.qty)}`).join('<br>')}</td><td><div class="inline-actions">${p.status === 'DRAFT' ? `<button class="secondary" data-action="release-prd" data-key="${esc(p.docNo)}">Release</button>` : ''}</div></td></tr>`);
    return table(['Production No', 'Date', 'Source SO', 'Status', 'Lines', 'Actions'], rows);
  }
  function bindProductionActions() {
    document.querySelectorAll('[data-action="release-prd"]').forEach((btn) => btn.addEventListener('click', () => {
      const p = state.productions.find((x) => x.docNo === btn.dataset.key);
      p.status = 'RELEASED'; saveState(); route('production'); notify(`${p.docNo} đã Release.`);
    }));
  }

  function renderReports() {
    $('view').innerHTML = `
      <section class="card"><div class="card-head"><div><h3>Inventory Report</h3><p>Base unit quantity and estimated value.</p></div></div><div class="card-body">${renderInventoryTable()}</div></section>
      <section class="card"><div class="card-head"><div><h3>Open Purchasing Documents</h3><p>Click document number để mở chi tiết.</p></div></div><div class="card-body">${renderOpenDocsTable()}</div></section>`;
    bindDocLinks();
  }
  function renderInventoryTable() {
    const rows = state.items.map((x) => `<tr><td><button class="doc-link" data-open="master" data-collection="items" data-key="${esc(x.code)}">${esc(x.code)}</button></td><td>${esc(x.name)}</td><td>${esc(x.itemType)}</td><td>${fmt(x.stock)} ${esc(x.baseUnit)}</td><td>${money(x.lastCost)}</td><td>${money(Number(x.stock || 0) * Number(x.lastCost || 0))}</td></tr>`);
    return table(['Item', 'Name', 'Type', 'Stock', 'Unit Cost', 'Value'], rows);
  }
  function renderOpenDocsTable() {
    const docs = [
      ...state.prs.filter((x) => ['DRAFT', 'RELEASED'].includes(x.status)).map((x) => ({ type: 'PR', no: x.docNo, status: x.status, amount: docAmount(x.lines) })),
      ...state.pos.filter((x) => ['DRAFT', 'RELEASED'].includes(x.status)).map((x) => ({ type: 'PO', no: x.docNo, status: x.status, amount: docAmount(x.lines) }))
    ];
    const rows = docs.map((x) => `<tr><td>${x.type}</td><td><button class="doc-link" data-open="${x.type.toLowerCase()}" data-key="${esc(x.no)}">${esc(x.no)}</button></td><td>${statusBadge(x.status)}</td><td>${money(x.amount)}</td></tr>`);
    return table(['Type', 'Document No', 'Status', 'Amount'], rows);
  }

  function bindDocLinks() {
    document.querySelectorAll('[data-open]').forEach((btn) => btn.addEventListener('click', () => openRecord(btn.dataset.open, btn.dataset.key, btn.dataset.collection)));
  }
  function openRecord(type, key, collection = '') {
    let record;
    let title = key;
    if (type === 'master') { record = state[collection].find((x) => x.code === key); title = `${collection} · ${key}`; }
    if (type === 'pr') record = state.prs.find((x) => x.docNo === key);
    if (type === 'po') record = state.pos.find((x) => x.docNo === key);
    if (type === 'gr') record = state.grs.find((x) => x.docNo === key);
    if (type === 'so') record = state.sos.find((x) => x.docNo === key);
    if (type === 'prd') record = state.productions.find((x) => x.docNo === key);
    if (!record) return;
    modalContext = { type, key, collection, record };
    $('modalTitle').textContent = title;
    $('modal').classList.remove('hidden');
    setModalEditMode(false);
  }
  function closeModal() { $('modal').classList.add('hidden'); modalContext = null; }
  function setModalEditMode(edit) {
    const { record, type } = modalContext;
    $('modalMode').textContent = edit ? 'Edit mode' : 'View mode';
    $('modalEdit').classList.toggle('hidden', edit || immutableDoc(type, record));
    $('modalSave').classList.toggle('hidden', !edit);
    $('modalBody').innerHTML = renderRecordForm(record, edit, type);
  }
  function immutableDoc(type, record) {
    return ['gr'].includes(type) || ['RELEASED', 'PO_CREATED', 'RECEIVED', 'POSTED'].includes(record.status);
  }
  function renderRecordForm(record, edit, type) {
    const primitive = Object.entries(record).filter(([, v]) => !Array.isArray(v) && typeof v !== 'object');
    const fields = primitive.map(([k, v]) => {
      const immutable = ['code', 'docNo', 'status', 'receivedQty', 'issuedQty'].includes(k) || immutableDoc(type, record);
      const ro = immutable || !edit ? 'readonly' : '';
      return `<label>${esc(k)}<input name="${esc(k)}" value="${esc(v)}" ${ro}></label>`;
    }).join('');
    const lines = Array.isArray(record.lines) ? `<div class="notice warning">Lines đang được khóa trong demo để tránh làm sai received/issued quantity/value. Hãy tạo chứng từ mới nếu cần đổi line.</div>${table(['Line data'], record.lines.map((l) => `<tr><td><pre>${esc(JSON.stringify(l, null, 2))}</pre></td></tr>`))}` : '';
    return `<form id="modalForm" class="form-grid">${fields}</form>${lines}`;
  }
  function saveModalRecord() {
    const form = $('modalForm');
    if (!form || !modalContext) return;
    const { record, type } = modalContext;
    if (immutableDoc(type, record)) return notify('Record này đã khóa, không thể chỉnh sửa.', 'danger');
    [...form.elements].forEach((el) => {
      if (!el.name || el.readOnly) return;
      const oldValue = record[el.name];
      record[el.name] = typeof oldValue === 'number' ? Number(el.value || 0) : el.value;
    });
    saveState(); closeModal(); route(currentPage); notify('Đã lưu thay đổi ở các field được phép.');
  }

  init();
})();

(function () {
    const scope = document.querySelector('[data-dirty-guard="true"]');
    if (!scope) return;
    let dirty = false;
    let submitting = false;
    const message = 'Bạn có thay đổi chưa lưu. Bạn có muốn thoát khỏi màn hình mà không lưu không?';
    scope.querySelectorAll('input, select, textarea').forEach(el => {
        el.addEventListener('change', () => { dirty = true; });
        el.addEventListener('input', () => { dirty = true; });
    });
    scope.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', () => { submitting = true; dirty = false; });
    });
    document.querySelectorAll('a').forEach(a => {
        a.addEventListener('click', function (e) {
            if (!dirty || submitting) return;
            const href = this.getAttribute('href') || '';
            if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
            e.preventDefault();
            const proceed = () => { submitting = true; dirty = false; window.location.href = href; };
            if (window.erpConfirm) {
                window.erpConfirm(message, {
                    title: 'Leave without saving?',
                    eyebrow: 'Unsaved changes',
                    confirmText: 'Leave page',
                    cancelText: 'Stay here',
                    type: 'warning'
                }).then(ok => { if (ok) proceed(); });
            } else if (window.confirm(message)) {
                proceed();
            }
        });
    });
    window.addEventListener('beforeunload', function (e) {
        if (!dirty || submitting) return;
        e.preventDefault();
        e.returnValue = '';
    });
})();

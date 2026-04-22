(function () {
    var btn = document.getElementById('logo-btn');
    if (!btn) return;
    btn.addEventListener('click', function () {
        var html = document.documentElement;
        var current = html.getAttribute('data-theme') || 'T4';
        var next = current === 'T4' ? 'T1' : 'T4';
        html.setAttribute('data-theme', next);
        localStorage.setItem('d-tach-theme', next);
    });
})();

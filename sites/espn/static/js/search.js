document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('form[data-path-search="espn"]').forEach(function (form) {
        form.addEventListener('submit', function (event) {
            const input = form.querySelector('input[name="q"]');
            const query = input ? input.value.trim() : '';
            if (!query) return;
            event.preventDefault();
            const params = new URLSearchParams(new FormData(form));
            // Dot segments and leading slashes do not survive browser/router
            // path normalization; keep those literal queries in the fallback.
            if (query === '.' || query === '..' || query.startsWith('/')) {
                window.location.href = '/search/_/q/' + '?' + params.toString();
                return;
            }
            params.delete('q');
            const suffix = params.toString();
            window.location.href = '/search/_/q/' + encodeURIComponent(query) + (suffix ? '?' + suffix : '');
        });
    });

});

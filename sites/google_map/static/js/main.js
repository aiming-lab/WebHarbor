// Google Maps Mirror - main.js

(function () {
    'use strict';

    // Flash auto-dismiss
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.flash').forEach(function (el) {
            setTimeout(function () {
                el.style.transition = 'opacity 300ms ease';
                el.style.opacity = '0';
                setTimeout(function () { el.remove(); }, 300);
            }, 4000);
        });

        // Flash close button
        document.querySelectorAll('.flash-close').forEach(function (btn) {
            btn.addEventListener('click', function () {
                btn.closest('.flash').remove();
            });
        });
    });

    document.querySelectorAll('form[data-path-search="maps"]').forEach(function (form) {
        form.addEventListener('submit', function (event) {
            var input = form.querySelector('input[name="q"]');
            var query = input ? input.value.trim() : '';
            if (!query) return;
            event.preventDefault();
            var params = new URLSearchParams(new FormData(form));
            params.delete('q');
            var suffix = params.toString();
            window.location.href = '/maps/search/' + encodeURIComponent(query) + (suffix ? '?' + suffix : '');
        });
    });

    // Save place toggle
    window.toggleSave = function (placeId, btn) {
        fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ place_id: placeId })
        })
            .then(function (r) {
                if (r.status === 401) {
                    window.location.href = '/login';
                    throw new Error('login required');
                }
                return r.json();
            })
            .then(function (data) {
                if (!data.success) {
                    showToast(data.message || 'Error', 'error');
                    return;
                }
                if (btn) {
                    if (data.saved) {
                        btn.classList.add('saved');
                        var lbl = btn.querySelector('.lbl');
                        if (lbl) lbl.textContent = 'Saved';
                    } else {
                        btn.classList.remove('saved');
                        var lbl2 = btn.querySelector('.lbl');
                        if (lbl2) lbl2.textContent = 'Save';
                    }
                }
                showToast(data.message, 'success');
            })
            .catch(function () { /* swallowed */ });
    };

    // Toast / snackbar
    window.showToast = function (msg, type) {
        type = type || 'info';
        var c = document.querySelector('.flash-container');
        if (!c) {
            c = document.createElement('div');
            c.className = 'flash-container';
            document.body.appendChild(c);
        }
        var f = document.createElement('div');
        f.className = 'flash ' + type;
        f.innerHTML = '<span>' + msg + '</span><button class="flash-close">×</button>';
        f.querySelector('.flash-close').addEventListener('click', function () { f.remove(); });
        c.appendChild(f);
        setTimeout(function () {
            f.style.transition = 'opacity 300ms ease';
            f.style.opacity = '0';
            setTimeout(function () { f.remove(); }, 300);
        }, 4000);
    };

    // Live search suggestions
    var searchInputs = document.querySelectorAll('.search-bar input[name="q"]');
    var debounceTimer = null;
    searchInputs.forEach(function (inp) {
        inp.addEventListener('input', function () {
            var v = inp.value.trim();
            clearTimeout(debounceTimer);
            if (v.length < 2) return;
            debounceTimer = setTimeout(function () {
                // Could enhance with real autocomplete - for now just let submit handle it
            }, 250);
        });
    });
})();

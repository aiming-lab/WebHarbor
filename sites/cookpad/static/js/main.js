/* =====================================================
   ALLRECIPES MIRROR — JavaScript
   ===================================================== */

document.addEventListener('DOMContentLoaded', function() {

    // --- Flash message auto-dismiss ---
    document.querySelectorAll('.flash-msg').forEach(function(msg) {
        setTimeout(function() {
            msg.style.opacity = '0';
            msg.style.transform = 'translateY(-10px)';
            setTimeout(function() { msg.remove(); }, 300);
        }, 4000);
    });
    document.querySelectorAll('.flash-close').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var msg = btn.closest('.flash-msg');
            msg.style.opacity = '0';
            setTimeout(function() { msg.remove(); }, 200);
        });
    });

    // --- Toast notifications ---
    window.showToast = function(message, duration) {
        duration = duration || 3000;
        var existing = document.querySelector('.toast');
        if (existing) existing.remove();
        var toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(function() { toast.classList.add('show'); }, 10);
        setTimeout(function() {
            toast.classList.remove('show');
            setTimeout(function() { toast.remove(); }, 300);
        }, duration);
    };

    // --- Recipe Box toggle ---
    document.querySelectorAll('.recipe-card-save, .recipe-action-btn.save-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            var recipeId = btn.dataset.recipeId;
            if (!recipeId) return;
            fetch('/api/recipe-box/toggle', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({recipe_id: parseInt(recipeId)})
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    showToast(data.message);
                    if (data.saved) {
                        btn.classList.add('saved');
                        btn.innerHTML = btn.dataset.savedIcon || '&#9829;';
                    } else {
                        btn.classList.remove('saved');
                        btn.innerHTML = btn.dataset.unsavedIcon || '&#9825;';
                    }
                    // Update badge
                    var badge = document.querySelector('.recipe-box-badge');
                    if (badge) badge.textContent = data.count;
                } else if (data.message) {
                    window.location.href = '/login';
                }
            })
            .catch(function() {
                window.location.href = '/login';
            });
        });
    });

    // --- Ingredient checkbox toggling ---
    document.querySelectorAll('.ingredients-list li').forEach(function(li) {
        li.addEventListener('click', function() {
            li.classList.toggle('checked');
        });
    });

    // --- Star rating input ---
    var starInputs = document.querySelectorAll('.star-rating-input input');
    starInputs.forEach(function(input) {
        input.addEventListener('change', function() {
            var val = input.value;
            document.getElementById('rating-value-display')
            && (document.getElementById('rating-value-display').textContent = val + ' star' + (val > 1 ? 's' : ''));
        });
    });

    // --- Meal plan add ---
    document.querySelectorAll('.meal-plan-add-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var day = btn.dataset.day;
            var mealType = btn.dataset.meal;
            var select = document.querySelector('#recipe-select-' + day + '-' + mealType);
            if (!select) return;
            var recipeId = select.value;
            if (!recipeId) return;
            fetch('/api/meal-plan/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({recipe_id: parseInt(recipeId), day: day, meal_type: mealType})
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    showToast(data.message);
                    window.location.reload();
                }
            });
        });
    });

    // --- Meal plan remove ---
    document.querySelectorAll('.remove-meal').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var day = btn.dataset.day;
            var mealType = btn.dataset.meal;
            fetch('/api/meal-plan/remove', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({day: day, meal_type: mealType})
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    showToast(data.message);
                    window.location.reload();
                }
            });
        });
    });

    // --- Shopping list item remove ---
    document.querySelectorAll('.remove-item').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var listId = btn.dataset.listId;
            var index = parseInt(btn.dataset.index);
            fetch('/api/shopping-list/' + listId + '/remove', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index: index})
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    btn.closest('li').remove();
                    showToast('Item removed');
                }
            });
        });
    });

    // --- Live search suggestions ---
    var searchInput = document.querySelector('.nav-search input');
    if (searchInput) {
        var timeout = null;
        searchInput.addEventListener('input', function() {
            clearTimeout(timeout);
            var q = searchInput.value.trim();
            var dropdown = document.querySelector('.search-suggestions');
            if (q.length < 2) {
                if (dropdown) dropdown.remove();
                return;
            }
            timeout = setTimeout(function() {
                fetch('/api/search?q=' + encodeURIComponent(q))
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (dropdown) dropdown.remove();
                    if (data.results.length === 0) return;
                    dropdown = document.createElement('div');
                    dropdown.className = 'search-suggestions';
                    dropdown.style.cssText = 'position:absolute;top:100%;left:0;right:0;background:white;border:1px solid #e0e0e0;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.1);z-index:1000;max-height:300px;overflow-y:auto;';
                    data.results.forEach(function(r) {
                        var a = document.createElement('a');
                        a.href = '/recipe/' + r.slug;
                        a.style.cssText = 'display:flex;align-items:center;gap:12px;padding:10px 14px;text-decoration:none;color:#222;font-size:0.9rem;border-bottom:1px solid #f0f0f0;';
                        a.innerHTML = '<span>' + r.title + '</span>';
                        a.addEventListener('mouseenter', function() { a.style.background = '#f7f7f7'; });
                        a.addEventListener('mouseleave', function() { a.style.background = 'white'; });
                        dropdown.appendChild(a);
                    });
                    searchInput.parentElement.appendChild(dropdown);
                });
            }, 300);
        });
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.nav-search')) {
                var dd = document.querySelector('.search-suggestions');
                if (dd) dd.remove();
            }
        });
    }

    // --- Scroll animations ---
    if ('IntersectionObserver' in window) {
        var observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(e) {
                if (e.isIntersecting) {
                    e.target.style.opacity = '1';
                    e.target.style.transform = 'translateY(0)';
                    observer.unobserve(e.target);
                }
            });
        }, { threshold: 0.1 });

        document.querySelectorAll('.recipe-card, .pd-gallery-section, .category-card').forEach(function(el) {
            el.style.opacity = '0';
            el.style.transform = 'translateY(20px)';
            el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            observer.observe(el);
        });
    }
});

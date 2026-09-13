/* ===================================================================
   Apple.com Clone - Main JavaScript
   =================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    initNavbar();
    initFlashMessages();
    initPathSearchForms();
    initScrollAnimations();
});

function initPathSearchForms() {
    document.querySelectorAll('form[data-path-search="apple"]').forEach(form => {
        form.addEventListener('submit', event => {
            const input = form.querySelector('input[name="q"]');
            const query = input ? input.value.trim() : '';
            if (!query) return;
            event.preventDefault();
            const params = new URLSearchParams(new FormData(form));
            params.delete('q');
            const suffix = params.toString();
            window.location.href = '/search/' + encodeURIComponent(query) + (suffix ? '?' + suffix : '');
        });
    });
}

/* --- Navbar scroll effect --- */
function initNavbar() {
    const nav = document.getElementById('globalnav');
    const menuBtn = document.getElementById('gn-menubutton');

    // Scroll effect
    let lastScroll = 0;
    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;
        if (currentScroll > 0) {
            nav.style.background = 'rgba(0, 0, 0, 0.92)';
        } else {
            nav.style.background = 'rgba(0, 0, 0, 0.8)';
        }
        lastScroll = currentScroll;
    });

    // Mobile menu toggle
    if (menuBtn) {
        menuBtn.addEventListener('click', () => {
            const list = document.querySelector('.gn-list');
            list.classList.toggle('gn-mobile-open');
        });
    }
}

/* --- Flash message auto-dismiss --- */
function initFlashMessages() {
    const messages = document.querySelectorAll('.flash-message');
    messages.forEach(msg => {
        setTimeout(() => {
            msg.style.animation = 'slideDown 0.3s ease reverse';
            setTimeout(() => msg.remove(), 300);
        }, 4000);
    });
}

/* --- Scroll animations (fade in on scroll) --- */
function initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

    document.querySelectorAll('.tile, .lineup-card, .feature-card, .product-card').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
}

/* --- Add to Bag --- */
function addToBag(productId, options = {}) {
    const data = {
        product_id: productId,
        quantity: options.quantity || 1,
        color: options.color || '',
        storage: options.storage || ''
    };

    fetch('/api/cart/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(result => {
        if (result.success) {
            // Update bag count
            updateBagCount(result.cart_count);
            // Show notification
            showBagNotification(result.message);
        } else if (result.error) {
            alert(result.error);
        }
    })
    .catch(err => console.error('Add to bag error:', err));
}

/* --- Update bag count in nav --- */
function updateBagCount(count) {
    let badge = document.querySelector('.gn-bag-count');
    if (count > 0) {
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'gn-bag-count';
            document.querySelector('.gn-link-bag').appendChild(badge);
        }
        badge.textContent = count;
    } else if (badge) {
        badge.remove();
    }
}

/* --- Show bag notification --- */
function showBagNotification(message) {
    // Remove existing
    const existing = document.querySelector('.bag-notification');
    if (existing) existing.remove();

    const notif = document.createElement('div');
    notif.className = 'bag-notification show';
    notif.innerHTML = `
        <span class="bag-notification-check">&#10003;</span>
        <span>${message}</span>
    `;
    document.body.appendChild(notif);

    setTimeout(() => {
        notif.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => notif.remove(), 300);
    }, 3000);
}

/* --- Remove from bag --- */
function removeFromBag(itemId) {
    fetch('/api/cart/remove', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ item_id: itemId })
    })
    .then(res => res.json())
    .then(result => {
        if (result.success) {
            location.reload();
        }
    });
}

/* --- Update quantity --- */
function updateQuantity(itemId, delta) {
    const qtyEl = document.querySelector(`#qty-${itemId}`);
    if (!qtyEl) return;

    let newQty = parseInt(qtyEl.textContent) + delta;
    if (newQty < 1) newQty = 1;

    fetch('/api/cart/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ item_id: itemId, quantity: newQty })
    })
    .then(res => res.json())
    .then(result => {
        if (result.success) {
            location.reload();
        }
    });
}

/* --- Product configurator --- */
function selectColor(element, color) {
    document.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('selected'));
    element.classList.add('selected');
    document.getElementById('selected-color').value = color;

    // Update color label
    const label = document.getElementById('color-label');
    if (label) label.textContent = color;
}

function selectStorage(element, storage) {
    document.querySelectorAll('.config-option').forEach(o => o.classList.remove('selected'));
    element.classList.add('selected');
    document.getElementById('selected-storage').value = storage;
}

/* --- CSRF Token --- */
function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

/* --- Search --- */
function initSearch() {
    const input = document.querySelector('.search-input');
    if (!input) return;

    let timeout;
    input.addEventListener('input', () => {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            if (input.value.length >= 2) {
                window.location.href = `/search?q=${encodeURIComponent(input.value)}`;
            }
        }, 800);
    });
}

// BBC News mirror — interactive helpers

function csrfToken() {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
}

function showToast(message, type) {
    type = type || 'info';
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 350);
    }, 2600);
}

function updateHeaderCounts(rlCount, bmCount) {
    const rl = document.getElementById('rl-count');
    if (rl && rlCount !== undefined) rl.textContent = rlCount;
    const bm = document.getElementById('bm-count');
    if (bm && bmCount !== undefined) bm.textContent = bmCount;
}

// --- Reading List ---
function toggleReadingList(articleId, btn) {
    const active = btn.classList.contains('active');
    const url = active ? '/api/reading-list/remove' : '/api/reading-list/add';
    const body = active
        ? { article_id: articleId }
        : { article_id: articleId, folder: 'Read Later' };
    if (active) {
        // Need an item_id to remove — fallback: use add endpoint with a "remove" flag, but API expects item_id.
        // Simpler: add will update if already exists; toggle state through a second call.
        // For detail page we only support "add" (saving). Subsequent clicks just re-save.
    }
    fetch('/api/reading-list/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ article_id: articleId, folder: 'Read Later' }),
    })
        .then((r) => r.json())
        .then((data) => {
            if (data.success) {
                btn.classList.add('active');
                const label = btn.querySelector('.rl-label');
                if (label) label.textContent = 'Saved to list';
                updateHeaderCounts(data.reading_list_count);
                showToast(data.message || 'Added to reading list', 'success');
            } else {
                showToast(data.message || 'Sign in to save stories', 'error');
            }
        })
        .catch(() => {
            window.location.href = '/login';
        });
}

// --- Bookmarks ---
function toggleBookmark(articleId, btn) {
    fetch('/api/bookmark/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ article_id: articleId }),
    })
        .then((r) => {
            if (r.status === 401) {
                window.location.href = '/login';
                return;
            }
            return r.json();
        })
        .then((data) => {
            if (!data) return;
            if (data.success) {
                const label = btn.querySelector('.bm-label');
                if (data.action === 'added') {
                    btn.classList.add('active');
                    if (label) label.textContent = 'Bookmarked';
                    showToast('Added to bookmarks', 'success');
                } else {
                    btn.classList.remove('active');
                    if (label) label.textContent = 'Bookmark';
                    showToast('Removed from bookmarks', 'info');
                }
                updateHeaderCounts(undefined, data.bookmark_count);
            }
        })
        .catch(() => {
            window.location.href = '/login';
        });
}

// --- Comment likes ---
function likeComment(commentId, btn) {
    fetch('/api/comment/like', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment_id: commentId }),
    })
        .then((r) => {
            if (r.status === 401) {
                window.location.href = '/login';
                return;
            }
            return r.json();
        })
        .then((data) => {
            if (data && data.success) {
                const count = btn.querySelector('.like-count');
                if (count) count.textContent = data.like_count;
            }
        })
        .catch(() => {});
}

// --- Share ---
function copyShareUrl(btn) {
    var shareUrl = (btn && btn.getAttribute && btn.getAttribute('data-share-url'))
        || window.BBC_ARTICLE_SHARE_URL;
    if (!shareUrl) {
        showToast('Could not copy link', 'error');
        return;
    }
    if (navigator.clipboard) {
        navigator.clipboard
            .writeText(shareUrl)
            .then(() => showToast('Article link copied', 'success'))
            .catch(() => showToast('Could not copy link', 'error'));
    } else {
        showToast(shareUrl, 'info');
    }
}

// --- Mobile menu toggle ---
function toggleMobileNav() {
    const nav = document.getElementById('mobile-nav');
    if (nav) nav.classList.toggle('open');
}

// --- Fade-in on scroll ---
document.addEventListener('DOMContentLoaded', () => {
    const io = new IntersectionObserver(
        (entries) => {
            entries.forEach((e) => {
                if (e.isIntersecting) {
                    e.target.classList.add('in-view');
                    io.unobserve(e.target);
                }
            });
        },
        { threshold: 0.08 }
    );
    document.querySelectorAll('.fade-up').forEach((el) => io.observe(el));

    // Auto-dismiss flash messages
    setTimeout(() => {
        document.querySelectorAll('.flash-message').forEach((el) => {
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 400);
        });
    }, 4500);
});

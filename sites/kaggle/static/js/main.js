// Kaggle mirror — lightweight interactions (vote / bookmark / follow via fetch).
(function () {
  const csrf = document.querySelector('meta[name="csrf-token"]');
  const token = csrf ? csrf.getAttribute('content') : '';

  function post(url, data) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-CSRFToken': token,
      },
      body: JSON.stringify(data),
    }).then(r => r.json());
  }

  document.addEventListener('click', function (e) {
    const vb = e.target.closest('[data-vote]');
    if (vb) {
      e.preventDefault();
      post('/api/vote', { entity_type: vb.dataset.type, entity_id: vb.dataset.id })
        .then(res => {
          if (res.error) { window.location = '/login'; return; }
          vb.classList.toggle('voted', res.voted);
          const cnt = vb.querySelector('[data-count]');
          if (cnt && res.count != null) cnt.textContent = res.count.toLocaleString();
          const lbl = vb.querySelector('[data-label]');
          if (lbl) lbl.textContent = res.voted ? 'Voted' : 'Upvote';
        })
        .catch(() => { window.location = '/login'; });
      return;
    }
    const bb = e.target.closest('[data-bookmark]');
    if (bb) {
      e.preventDefault();
      post('/api/bookmark', { entity_type: bb.dataset.type, entity_id: bb.dataset.id })
        .then(res => {
          if (res.error) { window.location = '/login'; return; }
          bb.classList.toggle('voted', res.bookmarked);
          const lbl = bb.querySelector('[data-label]');
          if (lbl) lbl.textContent = res.bookmarked ? 'Saved' : 'Save';
        })
        .catch(() => { window.location = '/login'; });
      return;
    }
    const fb = e.target.closest('[data-follow]');
    if (fb) {
      e.preventDefault();
      post('/api/follow', { username: fb.dataset.username })
        .then(res => {
          if (res.error) { window.location = '/login'; return; }
          fb.classList.toggle('voted', res.following);
          fb.textContent = res.following ? 'Following' : 'Follow';
        })
        .catch(() => { window.location = '/login'; });
      return;
    }
  });
})();

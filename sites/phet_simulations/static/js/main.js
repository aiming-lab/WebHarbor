(function () {
  function getCsrfToken(form) {
    var input = form.querySelector('input[name="csrf_token"]');
    return input ? input.value : '';
  }

  document.querySelectorAll('.save-form').forEach(function (form) {
    var status = form.querySelector('.save-status');
    form.querySelectorAll('button[data-action]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var action = btn.getAttribute('data-action');
        var simId = form.getAttribute('data-sim-id');
        var endpoint = action === 'save' ? '/api/save-sim' : '/api/unsave-sim';

        fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(form),
          },
          body: JSON.stringify({ sim_id: simId }),
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (!data.ok) {
              status.textContent = 'Error: ' + (data.error || 'unknown');
              status.style.color = '#c0392b';
              return;
            }
            if (action === 'save') {
              btn.textContent = 'Remove from saved';
              btn.setAttribute('data-action', 'unsave');
              btn.classList.remove('btn-primary');
              btn.classList.add('btn-ghost');
              status.textContent = 'Saved to your account.';
            } else {
              btn.textContent = 'Save to my account';
              btn.setAttribute('data-action', 'save');
              btn.classList.remove('btn-ghost');
              btn.classList.add('btn-primary');
              status.textContent = 'Removed from saved.';
            }
            status.style.color = '#2e7d32';
          })
          .catch(function () {
            status.textContent = 'Network error, please retry.';
            status.style.color = '#c0392b';
          });
      });
    });
  });

  var playBtn = document.querySelector('.sim-detail-play');
  if (playBtn) {
    playBtn.addEventListener('click', function () {
      alert('Mirror snapshot — simulation playback is disabled in benchmark mode.');
    });
  }
})();

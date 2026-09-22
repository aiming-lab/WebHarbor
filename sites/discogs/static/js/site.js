/* Discogs mirror — progressive enhancement for the header, carousels and footer.
   Everything works without JS except dropdown toggling on touch devices. */
(function () {
  'use strict';

  /* Header menus are native <details>; JS only adds "one open at a time" and
     click-outside/Escape dismissal. Without JS they still open and close. */
  function closeAllDropdowns(except) {
    document.querySelectorAll('.hdr-dd[open]').forEach(function (dd) {
      if (dd !== except) dd.open = false;
    });
  }

  document.querySelectorAll('.hdr-secondary .hdr-dd, .hdr-account').forEach(function (dd) {
    dd.addEventListener('toggle', function () {
      if (dd.open) closeAllDropdowns(dd);
    });
  });
  document.addEventListener('click', function (event) {
    if (!event.target.closest('.hdr-dd')) closeAllDropdowns(null);
  });

  /* Mobile drawer. */
  var header = document.querySelector('.site-header');
  var bars = document.querySelector('.hdr-bars');
  var drawer = document.querySelector('.hdr-mobile');
  function setDrawer(open) {
    if (!header || !drawer) return;
    header.classList.toggle('menu-open', open);
    drawer.hidden = !open;
    if (bars) bars.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  if (bars) bars.addEventListener('click', function () { setDrawer(drawer.hidden); });
  document.querySelectorAll('.hdr-mobile-close').forEach(function (b) {
    b.addEventListener('click', function () { setDrawer(false); });
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    closeAllDropdowns(null);
    setDrawer(false);
    var dialog = document.getElementById('shortcuts-dialog');
    if (dialog && dialog.open) dialog.close();
  });

  /* Search category panel: keep "View all results" pointing at the typed query. */
  document.querySelectorAll('.hdr-search').forEach(function (form) {
    var input = form.querySelector('.hdr-query');
    var link = form.querySelector('.hdr-advanced');
    if (!input || !link) return;
    var base = link.getAttribute('href').split('?')[0];
    function sync() {
      var q = input.value.trim();
      link.setAttribute('href', q ? base + '?q=' + encodeURIComponent(q) : base);
    }
    input.addEventListener('input', sync);
    sync();
  });

  /* Release carousels: paged prev/next arrows and bullets, like the live site. */
  document.querySelectorAll('.release-carousel').forEach(function (section) {
    var track = section.querySelector('.rc-track');
    var slides = track ? track.querySelectorAll('.rc-slide') : [];
    var prev = section.querySelector('.rc-prev');
    var next = section.querySelector('.rc-next');
    var pagination = section.querySelector('.rc-pagination');
    if (!track || !slides.length || !prev || !next) return;
    var page = 0;
    var metrics = { perPage: 1, pages: 1, step: 0 };

    function measure() {
      var slide = slides[0];
      var style = getComputedStyle(slide);
      var width = slide.getBoundingClientRect().width + parseFloat(style.marginRight || 0);
      var visible = track.parentElement.getBoundingClientRect().width;
      var perPage = Math.max(1, Math.floor((visible + parseFloat(style.marginRight || 0)) / width));
      metrics = { perPage: perPage, pages: Math.max(1, Math.ceil(slides.length / perPage)), step: width * perPage };
      if (page > metrics.pages - 1) page = metrics.pages - 1;
    }

    function render() {
      track.style.transform = 'translateX(' + (-page * metrics.step) + 'px)';
      prev.disabled = page === 0;
      next.disabled = page >= metrics.pages - 1;
      if (pagination) {
        pagination.innerHTML = '';
        for (var i = 0; i < metrics.pages; i++) {
          var bullet = document.createElement('button');
          bullet.type = 'button';
          bullet.className = 'rc-bullet' + (i === page ? ' active' : '');
          bullet.setAttribute('aria-label', 'Go to slide ' + (i + 1));
          bullet.dataset.page = String(i);
          bullet.addEventListener('click', function (event) {
            page = parseInt(event.currentTarget.dataset.page, 10);
            render();
          });
          pagination.appendChild(bullet);
        }
      }
    }

    prev.addEventListener('click', function () { if (page > 0) { page -= 1; render(); } });
    next.addEventListener('click', function () { if (page < metrics.pages - 1) { page += 1; render(); } });
    window.addEventListener('resize', function () { measure(); render(); });
    measure();
    render();
  });

  /* Footer newsletter: offline mirror, confirm locally without sending anything. */
  document.querySelectorAll('form[data-newsletter]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var success = form.querySelector('.ftr-success');
      var button = form.querySelector('.ftr-signup-btn');
      if (success) success.hidden = false;
      if (button) button.textContent = 'Success!';
    });
  });

  /* Auth forms: show/hide password like the live login page. */
  document.querySelectorAll('[data-toggle-password]').forEach(function (button) {
    button.addEventListener('click', function () {
      var input = document.getElementById(button.dataset.togglePassword);
      if (!input) return;
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      button.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    });
  });

  /* Keyboard shortcuts legend. */
  document.querySelectorAll('[data-dialog="shortcuts"]').forEach(function (trigger) {
    trigger.addEventListener('click', function (event) {
      event.preventDefault();
      var dialog = document.getElementById('shortcuts-dialog');
      if (dialog && typeof dialog.showModal === 'function') dialog.showModal();
    });
  });
  document.querySelectorAll('.shortcuts-dialog-close').forEach(function (b) {
    b.addEventListener('click', function () { b.closest('dialog').close(); });
  });
})();

/* Ryanair mirror — shared interactions (cookie banner, pickers, carousel). */
(function () {
  'use strict';

  // ---- cookie banner -------------------------------------------------
  var banner = document.getElementById('cookie-banner');
  var accepted = localStorage.getItem('ry-cookie') === '1';
  if (banner && !accepted) banner.style.display = 'block';
  function acceptCookies() {
    localStorage.setItem('ry-cookie', '1');
    if (banner) banner.style.display = 'none';
  }
  var acceptBtn = document.getElementById('cookie-accept');
  if (acceptBtn) acceptBtn.addEventListener('click', acceptCookies);
  var prefsBtn = document.getElementById('cookie-prefs');
  if (prefsBtn) prefsBtn.addEventListener('click', function () {
    if (banner) banner.style.display = 'block';
  });
  var settingsBtn = document.getElementById('cookie-settings');
  if (settingsBtn) settingsBtn.addEventListener('click', acceptCookies);

  // ---- generic dropdown toggles --------------------------------------
  document.addEventListener('click', function (e) {
    var toggle = e.target.closest('[data-toggle]');
    if (toggle) {
      var panel = document.getElementById(toggle.getAttribute('data-toggle'));
      if (panel) panel.classList.toggle(toggle.getAttribute('data-toggle-class') || 'hidden');
    } else if (!e.target.closest('.airport-picker, .datepicker, .passengers-selector, [data-picker-trigger]')) {
      document.querySelectorAll('.airport-picker, .datepicker, .passengers-selector')
        .forEach(function (p) { p.classList.add('hidden'); });
    }
  });

  // ---- hero carousel ---------------------------------------------------
  var slides = document.querySelectorAll('.hero__slide');
  if (slides.length > 1) {
    var idx = 0;
    setInterval(function () {
      slides[idx].classList.remove('hero__slide--active');
      var dots = document.querySelectorAll('.hero__dot');
      if (dots[idx]) dots[idx].classList.remove('hero__dot--active');
      idx = (idx + 1) % slides.length;
      slides[idx].classList.add('hero__slide--active');
      if (dots[idx]) dots[idx].classList.add('hero__dot--active');
    }, 6000);
  }

  // ---- horizontal carousels -------------------------------------------
  document.querySelectorAll('[data-carousel]').forEach(function (root) {
    var track = root.querySelector('.carousel__track');
    var left = root.querySelector('.carousel__controls--left');
    var right = root.querySelector('.carousel__controls--right');
    var offset = 0;
    if (!track) return;
    var step = 320;
    function update() {
      track.style.transform = 'translateX(' + offset + 'px)';
      if (left) left.disabled = offset >= 0;
      if (right) right.disabled = offset <= -(track.scrollWidth - root.clientWidth + 40);
    }
    if (left) left.addEventListener('click', function () { offset = Math.min(0, offset + step); update(); });
    if (right) right.addEventListener('click', function () { offset -= step; update(); });
    update();
  });

  // ---- payment method selector -----------------------------------------
  document.querySelectorAll('.payment-method').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.payment-method').forEach(function (b) {
        b.classList.remove('payment-method--selected');
      });
      btn.classList.add('payment-method--selected');
      var input = btn.querySelector('input[type=radio]');
      if (input) input.checked = true;
    });
  });
})();

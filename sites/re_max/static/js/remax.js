/* RE/MAX mirror — filter dropdowns, gallery modal, hero rotation. */
(function () {
  'use strict';

  // Filter dropdown toggles
  document.querySelectorAll('[data-filter]').forEach(function (wrap) {
    var btn = wrap.querySelector('.filter-btn');
    if (!btn) return;
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      document.querySelectorAll('[data-filter]').forEach(function (other) {
        if (other !== wrap) other.classList.remove('open');
      });
      wrap.classList.toggle('open');
    });
  });
  document.addEventListener('click', function () {
    document.querySelectorAll('[data-filter]').forEach(function (w) { w.classList.remove('open'); });
  });
  document.querySelectorAll('.filter-menu').forEach(function (menu) {
    menu.addEventListener('click', function (e) { e.stopPropagation(); });
  });

  // Gallery modal
  var galleryLinks = document.querySelectorAll('[data-gallery]');
  galleryLinks.forEach(function (trigger) {
    trigger.addEventListener('click', function () {
      var photos = [];
      document.querySelectorAll('.ldp-hero img').forEach(function (img) {
        photos.push(img.getAttribute('src'));
      });
      if (!photos.length) return;
      var overlay = document.createElement('div');
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,14,53,0.94);z-index:200;display:flex;align-items:center;justify-content:center;flex-direction:column;';
      var img = document.createElement('img');
      img.src = photos[0];
      img.style.cssText = 'max-width:86vw;max-height:80vh;object-fit:contain;';
      var caption = document.createElement('div');
      caption.style.cssText = 'color:#F5F3EA;font-family:Montserrat,Arial,sans-serif;margin-top:12px;font-size:14px;';
      caption.textContent = 'Photo 1 of ' + photos.length;
      var close = document.createElement('button');
      close.textContent = 'CLOSE';
      close.style.cssText = 'margin-top:14px;background:#0043FF;color:#fff;border:none;padding:10px 22px;font-family:Montserrat,Arial,sans-serif;font-weight:600;cursor:pointer;';
      close.addEventListener('click', function () { document.body.removeChild(overlay); });
      var idx = 0;
      var prev = document.createElement('button');
      prev.textContent = '‹ PREV';
      var next = document.createElement('button');
      next.textContent = 'NEXT ›';
      [prev, next].forEach(function (b) {
        b.style.cssText = 'background:transparent;color:#F5F3EA;border:1px solid #F5F3EA;padding:10px 18px;margin:8px;font-family:Montserrat,Arial,sans-serif;cursor:pointer;';
        b.addEventListener('click', function () {
          idx = (idx + (b === next ? 1 : photos.length - 1)) % photos.length;
          img.src = photos[idx];
          caption.textContent = 'Photo ' + (idx + 1) + ' of ' + photos.length;
        });
      });
      var row = document.createElement('div');
      row.appendChild(prev); row.appendChild(next);
      overlay.appendChild(img); overlay.appendChild(caption); overlay.appendChild(row); overlay.appendChild(close);
      overlay.addEventListener('click', function (e) { if (e.target === overlay) document.body.removeChild(overlay); });
      document.body.appendChild(overlay);
    });
  });

  // Hero carousel rotation — cycles the campaign slides (headline, copy,
  // call-to-action and background) together with the dots, mirroring the
  // upstream homepage carousel. Dots are clickable.
  var slides = document.querySelectorAll('.hero-overlay .hero-slide');
  var backgrounds = document.querySelectorAll('.hero img.hero-bg');
  var dots = document.querySelectorAll('.hero-dots span');
  if (slides.length && backgrounds.length && dots.length) {
    var active = 0;
    var show = function (idx) {
      active = (idx + slides.length) % slides.length;
      slides.forEach(function (s, i) { s.classList.toggle('active', i === active); });
      backgrounds.forEach(function (b, i) { b.classList.toggle('active', i === active); });
      dots.forEach(function (d, i) { d.classList.toggle('active', i === active); });
    };
    dots.forEach(function (d) {
      d.addEventListener('click', function () { show(parseInt(d.getAttribute('data-slide'), 10) || 0); });
    });
    setInterval(function () { show(active + 1); }, 6000);
  }
})();

// Parkers mirror — light progressive enhancement (site works without JS).
(function () {
  'use strict';

  // Cascading selects: any select with data-auto-submit submits its form on change.
  document.querySelectorAll('select[data-auto-submit]').forEach(function (sel) {
    sel.addEventListener('change', function () {
      var form = sel.closest('form');
      if (form) form.submit();
    });
  });

  // Make/model cascade on valuation + specs + insurance hubs.
  document.querySelectorAll('[data-cascade]').forEach(function (pair) {
    var makeSel = pair.querySelector('[data-make-select]');
    var modelSel = pair.querySelector('[data-model-select]');
    if (!makeSel || !modelSel) return;
    makeSel.addEventListener('change', function () {
      modelSel.innerHTML = '<option value="">Select a range</option>';
      modelSel.disabled = true;
      var form = pair.closest('form');
      if (form) form.submit();
    });
  });

  // Gallery thumbs swap hero image.
  document.querySelectorAll('.listing-thumbs img').forEach(function (img) {
    img.addEventListener('click', function () {
      var hero = document.querySelector('.listing-hero img');
      if (hero) hero.src = img.getAttribute('data-full') || img.src;
    });
  });
})();

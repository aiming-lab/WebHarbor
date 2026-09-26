/* SourceForge mirror — minimal interactions: nav dropdowns, sort menus,
   facet "More..." toggles and the off-canvas menu button. */
(function () {
  function ready(fn) {
    if (document.readyState !== 'loading') { fn(); }
    else { document.addEventListener('DOMContentLoaded', fn); }
  }
  ready(function () {
    // Off-canvas menu
    var toggle = document.querySelector('[data-toggle="offCanvas"]');
    var canvas = document.getElementById('offCanvas');
    if (toggle && canvas) {
      toggle.addEventListener('click', function () {
        canvas.classList.toggle('is-open');
      });
    }
    // Resources dropdown
    document.querySelectorAll('.nav-dropdown > a:first-child').forEach(function (a) {
      var li = a.parentElement;
      if (li.querySelector('.nav-dropdown-menu')) {
        a.addEventListener('click', function (e) {
          if (a.getAttribute('href') === '' || a.getAttribute('href') === '#') { e.preventDefault(); }
          document.querySelectorAll('.nav-dropdown.open').forEach(function (o) { if (o !== li) o.classList.remove('open'); });
          li.classList.toggle('open');
        });
      }
    });
    // Reviews "Filter Reviews" dropdown (Foundation dropdown-pane replacement)
    var filterToggle = document.querySelector('.sort-options [data-toggle="filter-rating"] .sort-drop-down > a, [data-toggle="filter-rating"] .sort-drop-down > a');
    var filterPane = document.getElementById('filter-rating');
    if (filterToggle && filterPane) {
      filterToggle.addEventListener('click', function (e) {
        e.preventDefault();
        filterPane.classList.toggle('is-open');
      });
      // close on outside click, like Foundation does
      document.addEventListener('click', function (e) {
        if (filterPane.classList.contains('is-open') &&
            !filterPane.contains(e.target) &&
            !filterToggle.contains(e.target)) {
          filterPane.classList.remove('is-open');
        }
      });
    }
    // Sort-by dropdown: follow data-action links
    document.querySelectorAll('.sort-by .menu a[data-action]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        window.location.href = a.getAttribute('data-action');
      });
    });
    var sortParent = document.querySelector('.sort-by .is-dropdown-submenu-parent > a');
    if (sortParent) {
      sortParent.addEventListener('click', function (e) {
        e.preventDefault();
        sortParent.parentElement.classList.toggle('open');
      });
    }
    // Tickets dropdown on project tabs
    document.querySelectorAll('#top_nav_admin ul.dropdown > li').forEach(function (li) {
      var submenu = li.querySelector('ul');
      if (!submenu) return;
      var trigger = li.querySelector('a');
      trigger.addEventListener('click', function (e) {
        e.preventDefault();
        document.querySelectorAll('#top_nav_admin ul.dropdown > li.show-sub').forEach(function (o) { if (o !== li) o.classList.remove('show-sub'); });
        li.classList.toggle('show-sub');
      });
    });
  });
})();

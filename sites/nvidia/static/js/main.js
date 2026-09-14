// NVIDIA mirror — minimal progressive enhancement
document.addEventListener('DOMContentLoaded', function () {
  // Keep business feedback readable until the next navigation.
  // Escape closes the native details menu and returns focus to its control.
  document.querySelectorAll('.site-menu').forEach(function (menu) {
    menu.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && menu.open) {
        menu.open = false;
        menu.querySelector('summary').focus();
      }
    });
  });

  // A "Scroll horizontally …" hint is only shown while its region really overflows.
  // The region itself stays a focusable labelled region (role=region + tabindex),
  // so keyboard users keep the scroll affordance at every width (audit NVIDIA--7/9/10).
  function syncScrollHints() {
    document.querySelectorAll('.scroll-hint[data-scroll-region]').forEach(function (hint) {
      var region = document.getElementById(hint.dataset.scrollRegion);
      if (!region) return;
      hint.hidden = region.scrollWidth <= region.clientWidth + 1;
    });
  }
  syncScrollHints();
  window.addEventListener('resize', syncScrollHints);
});

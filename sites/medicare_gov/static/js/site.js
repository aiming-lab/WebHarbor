// Medicare.gov mirror — progressive UI enhancements.
// All content works without JS; this adds the gov-banner toggle and
// accordion behavior the upstream site provides.
(function () {
  "use strict";

  // Gov banner "Here's how you know" expander.
  var bannerButton = document.querySelector(".gov-banner__button");
  var bannerDetail = document.getElementById("gov-banner-how");
  if (bannerButton && bannerDetail) {
    bannerButton.addEventListener("click", function () {
      var expanded = bannerButton.getAttribute("aria-expanded") === "true";
      bannerButton.setAttribute("aria-expanded", String(!expanded));
      bannerDetail.hidden = expanded;
    });
  }

  // Accordions (content pages): toggle panels, one open at a time.
  document.querySelectorAll(".accordion__toggle").forEach(function (toggle) {
    toggle.addEventListener("click", function () {
      var expanded = toggle.getAttribute("aria-expanded") === "true";
      var accordion = toggle.closest(".accordion");
      accordion.querySelectorAll(".accordion__toggle").forEach(function (other) {
        other.setAttribute("aria-expanded", "false");
        var panel = document.getElementById(other.getAttribute("aria-controls"));
        if (panel) panel.hidden = true;
      });
      if (!expanded) {
        toggle.setAttribute("aria-expanded", "true");
        var panel = document.getElementById(toggle.getAttribute("aria-controls"));
        if (panel) panel.hidden = false;
      }
    });
  });

  // Smooth-scroll offset for the skip link is handled by CSS; nothing else.
})();

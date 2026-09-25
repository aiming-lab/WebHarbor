/* Ohio.gov mirror — minimal interaction layer.
 * Implements the ODX behaviors the upstream site provides via jQuery:
 * official-site banner dropdown, header search toggle, and collapse
 * accordions (FAQs, outage notifications). */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    // -- "Here's how you know" official-site dropdown -----------------------
    var official = document.getElementById("oficialSite");
    var dropdown = document.getElementById("oficialSiteDropdown");
    function toggleOfficial() {
      if (!official || !dropdown) return;
      var open = official.classList.toggle("opened");
      official.classList.toggle("closed", !open);
      dropdown.classList.toggle("opened", open);
      dropdown.classList.toggle("closed", !open);
      dropdown.style.display = open ? "block" : "none";
      var icons = official.querySelectorAll(".oficialSite__icon");
      icons.forEach(function (i) { i.classList.toggle("hidden"); });
    }
    if (official) {
      official.addEventListener("click", function (e) {
        e.preventDefault();
        toggleOfficial();
      });
    }
    var closeBtn = document.getElementById("js-btn-close-official-site-dropdown");
    if (closeBtn) closeBtn.addEventListener("click", toggleOfficial);

    // -- header search toggle ----------------------------------------------
    var searchBtn = document.getElementById("js-search-button-desktop");
    var searchBox = document.getElementById("js-searchbox");
    function toggleSearch(show) {
      if (!searchBox) return;
      var isHidden = searchBox.classList.contains("hidden");
      var open = typeof show === "boolean" ? show : isHidden;
      searchBox.classList.toggle("hidden", !open);
      if (open) {
        var input = searchBox.querySelector("input");
        if (input) input.focus();
      }
    }
    if (searchBtn) searchBtn.addEventListener("click", function () { toggleSearch(); });
    var cancelBtn = document.getElementById("js-cancel-search-desktop");
    if (cancelBtn) cancelBtn.addEventListener("click", function () { toggleSearch(false); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") toggleSearch(false);
    });

    // -- collapse accordions (bootstrap-3 style: .collapse / .collapse.in) --
    document.querySelectorAll("[data-toggle='collapse']").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        if (btn.tagName === "A") e.preventDefault();
        var target = document.querySelector(btn.getAttribute("data-target"));
        if (!target) return;
        var open = target.classList.toggle("in");
        btn.setAttribute("aria-expanded", open ? "true" : "false");
        var chevron = btn.querySelector(".odx-collapsable__chevron");
        if (chevron) {
          chevron.classList.toggle("turn", open);
          chevron.classList.toggle("return", !open);
        }
      });
    });
  });
})();

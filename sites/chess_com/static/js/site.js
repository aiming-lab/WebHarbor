/* Shared site behaviors: nav dropdowns, mobile toggle, flash dismissal. */
(function () {
  "use strict";
  /* mobile navigation: hamburger toggle + backdrop close (visible <=900px) */
  var toggle = document.querySelector(".nav-toggle");
  var backdrop = document.querySelector(".nav-backdrop");
  function setNav(open) {
    document.body.classList.toggle("nav-open", open);
    if (toggle) {
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.textContent = open ? "✕" : "☰";
    }
  }
  if (toggle) {
    toggle.addEventListener("click", function () {
      setNav(!document.body.classList.contains("nav-open"));
    });
  }
  if (backdrop) {
    backdrop.addEventListener("click", function () { setNav(false); });
  }
  /* touch support: tap to open dropdowns */
  document.querySelectorAll(".sidebar-section > .sidebar-link").forEach(function (link) {
    link.addEventListener("click", function (e) {
      var section = link.parentElement;
      var wasOpen = section.classList.contains("open");
      document.querySelectorAll(".sidebar-section.open").forEach(function (s) {
        s.classList.remove("open");
      });
      if (!wasOpen && section.querySelector(".nav-dropdown")) {
        section.classList.add("open");
        e.preventDefault();
      }
    });
  });
  document.addEventListener("click", function (e) {
    if (!e.target.closest(".sidebar-section")) {
      document.querySelectorAll(".sidebar-section.open").forEach(function (s) {
        s.classList.remove("open");
      });
    }
  });
  /* flash auto-dismiss */
  setTimeout(function () {
    document.querySelectorAll(".flash").forEach(function (f) {
      f.style.transition = "opacity .5s";
      f.style.opacity = "0";
      setTimeout(function () { f.remove(); }, 550);
    });
  }, 5000);
})();

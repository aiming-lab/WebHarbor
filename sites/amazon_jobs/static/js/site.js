/* Amazon Jobs mirror — small UI behaviors (drawer, dropdowns, sort menu). */
(function () {
  "use strict";

  // hamburger drawer
  var hamburger = document.getElementById("hamburger");
  var drawer = document.getElementById("drawer");
  var backdrop = document.getElementById("drawer-backdrop");
  var closeBtn = document.getElementById("drawer-close");

  function openDrawer() {
    if (!drawer) return;
    drawer.hidden = false;
    backdrop.hidden = false;
    hamburger && hamburger.setAttribute("aria-expanded", "true");
  }
  function closeDrawer() {
    if (!drawer) return;
    drawer.hidden = true;
    backdrop.hidden = true;
    hamburger && hamburger.setAttribute("aria-expanded", "false");
  }
  if (hamburger && drawer) {
    hamburger.addEventListener("click", openDrawer);
    if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
    if (backdrop) backdrop.addEventListener("click", closeDrawer);
  }

  // my-career dropdown
  var career = document.getElementById("my-career");
  if (career) {
    var toggle = career.querySelector(".dropdown-toggle");
    if (toggle) {
      toggle.addEventListener("click", function (e) {
        e.stopPropagation();
        var open = career.classList.toggle("open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
      document.addEventListener("click", function () {
        career.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      });
    }
  }

  // sort menu
  var sortBtn = document.getElementById("sort-btn");
  var sortMenu = document.getElementById("sort-menu");
  if (sortBtn && sortMenu) {
    sortBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = !sortMenu.hidden;
      sortMenu.hidden = open;
      sortBtn.setAttribute("aria-expanded", open ? "false" : "true");
    });
    document.addEventListener("click", function () {
      sortMenu.hidden = true;
      sortBtn.setAttribute("aria-expanded", "false");
    });
  }

  // filter group collapse
  document.querySelectorAll(".filter-title").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var group = btn.parentElement;
      var options = group && group.querySelector(".filter-options");
      if (!options) return;
      var open = options.style.display !== "none";
      options.style.display = open ? "none" : "";
      btn.setAttribute("aria-expanded", open ? "false" : "true");
      var arrow = btn.querySelector(".arrow-up");
      if (arrow) {
        arrow.style.transform = open ? "rotate(180deg)" : "";
      }
    });
  });

  // alert bar dismiss
  document.querySelectorAll(".alert-close").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var bar = btn.parentElement;
      if (bar) bar.style.display = "none";
    });
  });

  // copy job link
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = document.querySelector(".share-link");
      if (!input) return;
      input.select();
      try { document.execCommand("copy"); } catch (err) { /* noop */ }
      btn.textContent = "Copied";
      setTimeout(function () { btn.textContent = "Copy link"; }, 1500);
    });
  });
})();

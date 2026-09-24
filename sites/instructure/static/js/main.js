/* Instructure mirror — interactions */
(function () {
  "use strict";

  // FAQ accordions
  document.querySelectorAll(".faq-item .q").forEach(function (btn) {
    btn.addEventListener("click", function () {
      btn.closest(".faq-item").classList.toggle("open");
    });
  });

  // filter group accordions
  document.querySelectorAll(".filter-group .legend-label").forEach(function (lbl) {
    lbl.addEventListener("click", function () {
      lbl.closest(".filter-group").classList.toggle("open");
    });
  });

  // transcript toggles
  document.querySelectorAll("[data-transcript-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var body = document.getElementById(btn.getAttribute("data-transcript-toggle"));
      if (body) body.classList.toggle("open");
    });
  });

  // hero slider
  var slides = Array.prototype.slice.call(document.querySelectorAll(".hero-slide"));
  var navCards = Array.prototype.slice.call(document.querySelectorAll(".hero-nav-card"));
  var dots = Array.prototype.slice.call(document.querySelectorAll(".hero-dots button"));
  var current = 0;
  var timer = null;

  function showSlide(i) {
    current = (i + slides.length) % slides.length;
    slides.forEach(function (s, n) { s.classList.toggle("is-active", n === current); });
    navCards.forEach(function (c, n) { c.classList.toggle("is-active", n === current); });
    dots.forEach(function (d, n) { d.classList.toggle("is-active", n === current); });
  }
  if (slides.length > 1) {
    navCards.forEach(function (card, n) {
      card.addEventListener("click", function () { showSlide(n); restart(); });
      card.addEventListener("mouseenter", function () { showSlide(n); });
    });
    dots.forEach(function (d, n) {
      d.addEventListener("click", function () { showSlide(n); restart(); });
    });
    timer = window.setInterval(function () { showSlide(current + 1); }, 7000);
    function restart() {
      window.clearInterval(timer);
      timer = window.setInterval(function () { showSlide(current + 1); }, 7000);
    }
  }

  // testimonial carousel
  var quotes = Array.prototype.slice.call(document.querySelectorAll(".testimonial-card"));
  var tDots = Array.prototype.slice.call(document.querySelectorAll(".testimonial-dots button"));
  function showQuote(i) {
    quotes.forEach(function (q, n) { q.style.display = n === i ? "block" : "none"; });
    tDots.forEach(function (d, n) { d.classList.toggle("is-active", n === i); });
  }
  if (quotes.length > 1) {
    showQuote(0);
    tDots.forEach(function (d, n) {
      d.addEventListener("click", function () { showQuote(n); });
    });
  }

  // auto-submit filters + search on change
  var filterForm = document.getElementById("hub-filters");
  if (filterForm) {
    filterForm.querySelectorAll("input[type=checkbox]").forEach(function (cb) {
      cb.addEventListener("change", function () { filterForm.submit(); });
    });
    var searchInput = filterForm.querySelector("input[name=hubs_search]");
    if (searchInput) {
      var t = null;
      searchInput.addEventListener("input", function () {
        window.clearTimeout(t);
        t = window.setTimeout(function () { filterForm.submit(); }, 900);
      });
    }
    // open groups that have active options
    filterForm.querySelectorAll(".filter-group").forEach(function (g) {
      if (g.querySelector("input:checked")) g.classList.add("open");
    });
  }

  // careers filter (client side)
  var jobFilters = {
    department: document.querySelector("[data-jobs-filter=department]"),
    location: document.querySelector("[data-jobs-filter=location]"),
    employment: document.querySelector("[data-jobs-filter=employment]"),
  };
  var jobRows = Array.prototype.slice.call(document.querySelectorAll("[data-job-row]"));
  if (jobRows.length && (jobFilters.department || jobFilters.location)) {
    var handler = function () {
      var dep = jobFilters.department ? jobFilters.department.value : "";
      var loc = jobFilters.location ? jobFilters.location.value : "";
      var emp = jobFilters.employment ? jobFilters.employment.value : "";
      var shown = 0;
      jobRows.forEach(function (row) {
        var ok = (!dep || row.dataset.department === dep) &&
                 (!loc || row.dataset.location === loc) &&
                 (!emp || row.dataset.employment === emp);
        row.style.display = ok ? "" : "none";
        if (ok) shown += 1;
      });
      var counter = document.querySelector("[data-jobs-count]");
      if (counter) counter.textContent = "Current Openings (" + shown + ")";
    };
    Object.values(jobFilters).forEach(function (sel) {
      if (sel) sel.addEventListener("change", handler);
    });
    handler();
  }

  // leader modals
  document.querySelectorAll("[data-modal-open]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var modal = document.getElementById(btn.getAttribute("data-modal-open"));
      if (modal) modal.classList.add("open");
    });
  });
  document.querySelectorAll(".modal-overlay").forEach(function (overlay) {
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) overlay.classList.remove("open");
    });
    var close = overlay.querySelector(".close");
    if (close) close.addEventListener("click", function () { overlay.classList.remove("open"); });
  });

  // mobile menu toggle (narrow viewports collapse the main nav behind Menu)
  var menuToggle = document.querySelector(".menu-toggle");
  var mainNav = document.querySelector(".main-nav");
  if (menuToggle && mainNav) {
    menuToggle.addEventListener("click", function () {
      var open = mainNav.classList.toggle("open");
      menuToggle.classList.toggle("open", open);
      menuToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    mainNav.querySelectorAll(".dropdown > button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var wasOpen = btn.parentElement.classList.contains("menu-open");
        mainNav.querySelectorAll(".dropdown.menu-open").forEach(function (d) {
          d.classList.remove("menu-open");
        });
        btn.parentElement.classList.toggle("menu-open", !wasOpen);
      });
    });
    mainNav.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        mainNav.classList.remove("open");
        menuToggle.classList.remove("open");
        menuToggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  // login dropdown toggle (utility bar)
  var loginTrigger = document.getElementById("login-trigger");
  if (loginTrigger) {
    loginTrigger.addEventListener("click", function (e) {
      e.preventDefault();
      loginTrigger.closest(".dropdown").classList.toggle("menu-open");
    });
    document.addEventListener("click", function (e) {
      if (loginTrigger && !loginTrigger.parentElement.contains(e.target)) {
        loginTrigger.closest(".dropdown").classList.remove("menu-open");
      }
    });
  }
})();

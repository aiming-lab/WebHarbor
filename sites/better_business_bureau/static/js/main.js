// Better Business Bureau mirror — small UI behaviors.
(function () {
  "use strict";

  // Dropdown navigation (Consumers / Businesses / Scam Tracker / About).
  document.querySelectorAll(".nav-item").forEach(function (item) {
    var button = item.querySelector(".nav-button");
    if (!button) return;
    button.addEventListener("click", function (event) {
      event.stopPropagation();
      var isOpen = item.classList.contains("open");
      document.querySelectorAll(".nav-item.open").forEach(function (other) {
        other.classList.remove("open");
      });
      if (!isOpen) item.classList.add("open");
    });
    item.addEventListener("mouseenter", function () {
      document.querySelectorAll(".nav-item.open").forEach(function (other) {
        if (other !== item) other.classList.remove("open");
      });
      item.classList.add("open");
    });
    item.addEventListener("mouseleave", function () { item.classList.remove("open"); });
  });
  document.addEventListener("click", function () {
    document.querySelectorAll(".nav-item.open").forEach(function (other) {
      other.classList.remove("open");
    });
  });

  // Cookie banner.
  var banner = document.getElementById("cookieBanner");
  if (banner && !localStorage.getItem("bbbCookiesAccepted")) {
    banner.hidden = false;
    var accept = document.getElementById("cookieAccept");
    if (accept) {
      accept.addEventListener("click", function () {
        localStorage.setItem("bbbCookiesAccepted", "1");
        banner.hidden = true;
      });
    }
  }

  // Hero video pause button.
  var video = document.getElementById("heroVideo");
  var pause = document.getElementById("heroPause");
  if (video && pause) {
    pause.addEventListener("click", function () {
      if (video.paused) { video.play(); pause.innerHTML = "&#10074;&#10074;"; }
      else { video.pause(); pause.innerHTML = "&#9654;"; }
    });
    var dots = document.querySelectorAll(".hero-dots .dot");
    if (dots.length && video) {
      var current = 0;
      var timer = setInterval(function () {
        current = (current + 1) % dots.length;
        dots.forEach(function (d, i) { d.classList.toggle("active", i === current); });
      }, 7000);
      video.addEventListener("pause", function () { clearInterval(timer); });
    }
  }

  // Star picker on the review form.
  var picker = document.getElementById("starPicker");
  if (picker) {
    var input = document.getElementById("ratingInput");
    var stars = picker.querySelectorAll(".st");
    stars.forEach(function (star, index) {
      star.addEventListener("click", function () {
        input.value = index + 1;
        stars.forEach(function (s, i) { s.classList.toggle("on", i <= index); });
      });
    });
  }

  // Complaint wizard on /file-a-complaint.
  var goalForm = document.getElementById("goalForm");
  if (goalForm) {
    goalForm.addEventListener("change", function () {
      var selected = document.querySelector('input[name="goal"]:checked');
      if (selected) goalForm.submit();
    });
  }
})();

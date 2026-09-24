/* LandWatch mirror — client behaviors: search modal, autocomplete, favorites,
   saved searches, sort menu, gallery, carousel scrolling. */
(function () {
  "use strict";

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  /* ---------- flash banner ---------- */
  var flash = $("#lw-flash");
  if (flash && flash.children.length) {
    setTimeout(function () { flash.classList.add("hidden"); }, 5000);
  }

  /* ---------- search modal ---------- */
  var modal = $("#lw-search-modal");
  function openModal() {
    if (!modal) return;
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    var input = $("#lw-modal-input");
    if (input) input.focus();
  }
  function closeModal() {
    if (!modal) return;
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
  }
  $all("[data-close-modal]").forEach(function (el) {
    el.addEventListener("click", closeModal);
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeModal();
  });
  var heroSearch = document.querySelector("[data-qa-searchlocation]");
  if (heroSearch) heroSearch.addEventListener("click", openModal);
  var headerSearchTrigger = document.querySelector("[data-open-search]");
  if (headerSearchTrigger) headerSearchTrigger.addEventListener("click", openModal);

  /* ---------- autocomplete suggestions ---------- */
  function attachSuggest(input, container) {
    if (!input || !container) return;
    var timer = null;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      var q = input.value.trim();
      if (q.length < 2) { container.classList.add("hidden"); return; }
      timer = setTimeout(function () {
        fetch("/api/suggest?q=" + encodeURIComponent(q))
          .then(function (r) { return r.json(); })
          .then(function (data) {
            container.innerHTML = "";
            (data.results || []).forEach(function (item) {
              var a = document.createElement("a");
              a.className = "lw-suggest-item";
              a.href = item.url;
              a.innerHTML = "<span>" + item.label + "</span><span class='lw-suggest-type'>" + item.type + "</span>";
              container.appendChild(a);
            });
            var near = document.createElement("a");
            near.className = "lw-suggest-item";
            near.href = "/land";
            near.innerHTML = "<span class='lw-suggest-near'>LAND FOR SALE NEAR ME</span>";
            container.appendChild(near);
            container.classList.toggle("hidden", (data.results || []).length === 0 && false);
          });
      }, 180);
    });
    input.addEventListener("blur", function () {
      setTimeout(function () { container.classList.add("hidden"); }, 220);
    });
    input.addEventListener("focus", function () {
      if (input.value.trim().length >= 2) container.classList.remove("hidden");
    });
  }
  $all("[data-suggest-input]").forEach(function (input) {
    attachSuggest(input, input.closest(".lw-searchbar-field").querySelector(".lw-suggest"));
  });
  attachSuggest($("#lw-modal-input"), $("#lw-suggest-modal"));

  /* ---------- favorites ---------- */
  $all("[data-favorite-pid]").forEach(function (btn) {
    btn.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      var pid = btn.getAttribute("data-favorite-pid");
      fetch("/favorite/" + pid, { method: "POST" })
        .then(function (r) {
          if (r.status === 401) { window.location = "/log-in?next=" + encodeURIComponent(window.location.pathname); return null; }
          return r.json();
        })
        .then(function (data) {
          if (!data) return;
          btn.classList.toggle("active", data.saved);
          btn.setAttribute("aria-label", data.saved ? "Remove from favorites" : "Save to favorites");
        });
    });
  });

  /* ---------- save search ---------- */
  $all("[data-save-search]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var url = window.location.pathname + window.location.search;
      var name = document.querySelector("h1") ? document.querySelector("h1").innerText.trim() : "Land search";
      fetch("/save-search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url, name: name })
      }).then(function (r) {
        if (r.status === 401) { window.location = "/log-in"; return; }
        return r.json();
      }).then(function (data) {
        if (!data) return;
        if (data.ok) {
          var toast = document.createElement("div");
          toast.className = "lw-flash-item ok";
          toast.textContent = "Search saved to your account.";
          var holder = document.createElement("div");
          holder.style.position = "fixed";
          holder.style.bottom = "22px";
          holder.style.left = "50%";
          holder.style.transform = "translateX(-50%)";
          holder.style.zIndex = "130";
          holder.appendChild(toast);
          document.body.appendChild(holder);
          setTimeout(function () { holder.remove(); }, 3200);
        }
      });
    });
  });

  /* ---------- sort menu ---------- */
  $all("[data-sort-button]").forEach(function (btn) {
    var menu = btn.parentElement.querySelector(".lw-sort-menu");
    if (!menu) return;
    btn.addEventListener("click", function (event) {
      event.stopPropagation();
      menu.classList.toggle("hidden");
    });
    menu.querySelectorAll("button").forEach(function (item) {
      item.addEventListener("click", function () {
        var url = new URL(window.location.href);
        url.searchParams.set("sort", item.getAttribute("data-sort"));
        window.location = url.toString();
      });
    });
  });
  document.addEventListener("click", function () {
    $all(".lw-sort-menu").forEach(function (menu) { menu.classList.add("hidden"); });
  });

  /* ---------- gallery ---------- */
  $all("[data-gallery]").forEach(function (gallery) {
    var photos = JSON.parse(gallery.getAttribute("data-gallery") || "[]");
    if (!photos.length) return;
    var main = gallery.querySelector(".lw-gallery-main img");
    var thumbs = gallery.querySelectorAll(".lw-gallery-thumbs img");
    var index = 0;
    function show(i) {
      index = (i + photos.length) % photos.length;
      main.src = photos[index];
      thumbs.forEach(function (t, ti) {
        t.classList.toggle("active", ti === index % thumbs.length);
      });
    }
    thumbs.forEach(function (thumb, ti) {
      thumb.addEventListener("click", function () { show(ti); });
    });
    var prev = gallery.querySelector("[data-gallery-prev]");
    var next = gallery.querySelector("[data-gallery-next]");
    if (prev) prev.addEventListener("click", function () { show(index - 1); });
    if (next) next.addEventListener("click", function () { show(index + 1); });
  });

  /* ---------- card photo carousel ---------- */
  $all("[data-card-photos]").forEach(function (card) {
    var photos = JSON.parse(card.getAttribute("data-card-photos") || "[]");
    if (photos.length < 2) return;
    var img = card.querySelector("img");
    var index = 0;
    var prev = card.querySelector("[data-card-prev]");
    var next = card.querySelector("[data-card-next]");
    function show(i) {
      index = (i + photos.length) % photos.length;
      img.src = photos[index];
    }
    if (prev) prev.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); show(index - 1); });
    if (next) next.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); show(index + 1); });
  });

  /* ---------- carousel scroll buttons ---------- */
  $all("[data-carousel]").forEach(function (carousel) {
    var wrap = carousel.closest(".lw-section") || carousel.parentElement;
    var prev = wrap.querySelector("[data-carousel-prev]");
    var next = wrap.querySelector("[data-carousel-next]");
    if (prev) prev.addEventListener("click", function () { carousel.scrollBy({ left: -carousel.clientWidth * 0.9, behavior: "smooth" }); });
    if (next) next.addEventListener("click", function () { carousel.scrollBy({ left: carousel.clientWidth * 0.9, behavior: "smooth" }); });
  });

  /* ---------- facet collapse ---------- */
  $all(".lw-facet-card h3").forEach(function (h) {
    h.addEventListener("click", function () {
      var list = h.parentElement.querySelector(".lw-facet-list, .lw-facet-group");
      if (!list) return;
      list.classList.toggle("hidden");
    });
  });
})();

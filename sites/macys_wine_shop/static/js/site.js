/* Macy's Wine Shop mirror — interaction layer.
   Implements the upstream behaviors: the age/state gate, hero rotation,
   "What we're loving" tabs, pack size selection with case contents, the
   quick-view modal, cart AJAX, quantity steppers, and notifications. */

(function () {
  "use strict";

  // ---------- notifications ----------
  window.notify = function (message, kind) {
    var host = document.querySelector(".notify");
    if (!host) {
      host = document.createElement("div");
      host.className = "notify";
      document.body.appendChild(host);
    }
    var note = document.createElement("div");
    note.className = "note " + (kind || "info");
    note.textContent = message;
    host.appendChild(note);
    setTimeout(function () { note.remove(); }, 4200);
  };

  // ---------- age gate ----------
  var gate = document.getElementById("age-gate");
  if (gate) {
    var yesBtn = gate.querySelector("#age-yes");
    var noBtn = gate.querySelector("#age-no");
    var errBox = gate.querySelector(".age-error");
    yesBtn.addEventListener("click", function () {
      var state = gate.querySelector("select").value;
      if (!state) {
        errBox.textContent = "You must select your state to continue.";
        return;
      }
      fetch("/age/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "state=" + encodeURIComponent(state) + "&answer=yes",
      }).then(function (r) { return r.json(); }).then(function (data) {
        if (!data.ok) { errBox.textContent = "Please select your state."; return; }
        gate.remove();
        document.body.style.pointerEvents = "auto";
        var shipSelects = document.querySelectorAll("[data-ship-select]");
        shipSelects.forEach(function (s) { s.value = data.state; });
        window.notify("Welcome! Ship-to state set to " + data.state + ".", "success");
        window.location.reload();
      });
    });
    noBtn.addEventListener("click", function () {
      document.body.innerHTML = "<h1>Sorry, you cannot proceed.</h1>";
    });
  }

  // ---------- header ship-to select ----------
  document.querySelectorAll("[data-ship-select]").forEach(function (sel) {
    sel.addEventListener("change", function () {
      fetch("/ship-state", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "state=" + encodeURIComponent(sel.value),
      });
    });
  });

  // ---------- hero rotation ----------
  var hero = document.querySelector("[data-hero]");
  if (hero && hero.querySelectorAll(".hero-slide").length > 1) {
    var slides = hero.querySelectorAll(".hero-slide");
    var dots = hero.querySelectorAll(".hero-dots button");
    var idx = 0;
    var timer = null;
    function show(i) {
      slides.forEach(function (s, n) { s.style.display = n === i ? "flex" : "none"; });
      dots.forEach(function (d, n) { d.classList.toggle("active", n === i); });
      idx = i;
    }
    function next() { show((idx + 1) % slides.length); }
    dots.forEach(function (d, n) {
      d.addEventListener("click", function () {
        show(n);
        if (timer) { clearInterval(timer); timer = setInterval(next, 6500); }
      });
    });
    show(0);
    timer = setInterval(next, 6500);
  }

  // ---------- featured tabs ----------
  document.querySelectorAll("[data-tab]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var scope = btn.closest("[data-tab-scope]");
      if (!scope) return;
      scope.querySelectorAll("[data-tab]").forEach(function (b) {
        b.classList.toggle("active", b === btn);
      });
      scope.querySelectorAll("[data-tab-panel]").forEach(function (panel) {
        panel.style.display = panel.getAttribute("data-tab-panel") === btn.getAttribute("data-tab") ? "block" : "none";
      });
    });
  });

  // ---------- quantity steppers ----------
  document.querySelectorAll("[data-qty]").forEach(function (wrap) {
    var input = wrap.querySelector("input");
    wrap.querySelector("[data-qty-dec]").addEventListener("click", function () {
      input.value = Math.max(1, parseInt(input.value || "1", 10) - 1);
    });
    wrap.querySelector("[data-qty-inc]").addEventListener("click", function () {
      input.value = Math.min(24, parseInt(input.value || "1", 10) + 1);
    });
  });

  // ---------- announcement bar rotation (upstream two-slide carousel) ----------
  var annSlides = document.querySelectorAll("[data-announcement-slide]");
  if (annSlides.length > 1) {
    var annIdx = 0;
    setInterval(function () {
      annSlides[annIdx].style.display = "none";
      annIdx = (annIdx + 1) % annSlides.length;
      annSlides[annIdx].style.display = "block";
    }, 5000);
  }

  // ---------- cart add (AJAX) ----------
  document.querySelectorAll("[data-add-to-cart]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var variantId = btn.getAttribute("data-variant-id");
      var qtyEl = btn.closest("form") ? btn.closest("form").querySelector("[data-qty-input]") : null;
      var qty = qtyEl ? qtyEl.value : "1";
      btn.disabled = true;
      fetch("/cart/add", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "variant_id=" + encodeURIComponent(variantId) + "&quantity=" + encodeURIComponent(qty),
      }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          btn.disabled = false;
          if (!res.ok) {
            window.notify(res.d.error || "Could not add this item.", "error");
            return;
          }
          window.notify("Added to your cart.", "success");
          var badge = document.querySelector(".cart-badge");
          if (badge) { badge.textContent = res.d.cart_count; }
          window.location.reload();
        });
    });
  });

  // ---------- quick view ----------
  var qvOverlay = document.getElementById("quickview-overlay");
  if (qvOverlay) {
    var qvImg = qvOverlay.querySelector("[data-qv-img]");
    var qvTitle = qvOverlay.querySelector("[data-qv-title]");
    var qvSub = qvOverlay.querySelector("[data-qv-sub]");
    var qvPrice = qvOverlay.querySelector("[data-qv-price]");
    var qvSpecs = qvOverlay.querySelector("[data-qv-specs]");
    var qvAdd = qvOverlay.querySelector("[data-qv-add]");
    var qvQty = qvOverlay.querySelector("[data-qv-qty]");
    qvOverlay.addEventListener("click", function (e) {
      if (e.target === qvOverlay) { qvOverlay.classList.remove("open"); }
    });
    qvOverlay.querySelector(".qv-close").addEventListener("click", function () {
      qvOverlay.classList.remove("open");
    });
    document.querySelectorAll("[data-quickview]").forEach(function (btn) {
      btn.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        fetch("/products/quickview/" + btn.getAttribute("data-quickview"))
          .then(function (r) { return r.json(); })
          .then(function (d) {
            qvImg.src = d.image_url;
            qvImg.alt = d.title;
            qvTitle.textContent = d.title;
            qvSub.textContent = d.subheading || "";
            qvPrice.textContent = d.price + (d.on_sale ? "" : "");
            qvSpecs.innerHTML = "";
            [["Winery", d.winery], ["Varietal", d.varietal], ["Year", d.year],
             ["Type", d.type], ["ABV", d.abv], ["Country", d.country],
             ["Region", d.region]].forEach(function (pair) {
              if (pair[1]) {
                var tr = document.createElement("tr");
                var td1 = document.createElement("td");
                var td2 = document.createElement("td");
                td1.textContent = pair[0];
                td2.textContent = pair[1];
                tr.appendChild(td1); tr.appendChild(td2);
                qvSpecs.appendChild(tr);
              }
            });
            qvAdd.setAttribute("data-variant-id", d.first_available_variant_id);
            if (!d.available) {
              qvAdd.disabled = true;
              qvAdd.textContent = "Item cannot ship to your state";
            } else {
              qvAdd.disabled = false;
              qvAdd.textContent = "Add to Cart";
            }
            qvOverlay.classList.add("open");
          });
      });
    });
  }

  // ---------- single-product variant selection (gift cards etc.) ----------
  var variantSelect = document.querySelector("[data-variant-select]");
  if (variantSelect) {
    variantSelect.addEventListener("change", function () {
      var opt = variantSelect.options[variantSelect.selectedIndex];
      if (!opt) { return; }
      var vid = opt.value;
      var form = document.querySelector("[data-pack-form]");
      if (form) {
        var hidden = form.querySelector("input[name='variant_id']");
        if (hidden) { hidden.value = vid; }
        var addBtn = form.querySelector("[data-add-to-cart]");
        if (addBtn) { addBtn.setAttribute("data-variant-id", vid); }
      }
      var priceNow = document.querySelector(".pdp-price [data-price-now]");
      if (priceNow) { priceNow.textContent = opt.getAttribute("data-price"); }
      var priceCompare = document.querySelector("[data-price-compare]");
      if (priceCompare) { priceCompare.textContent = opt.getAttribute("data-compare") || ""; }
      var priceOff = document.querySelector("[data-price-off]");
      if (priceOff) {
        var off = parseInt(opt.getAttribute("data-off") || "0", 10);
        priceOff.style.display = off > 0 ? "inline-block" : "none";
        priceOff.textContent = off + "% Off";
      }
    });
  }

  // ---------- pack size selection ----------
  var packForm = document.querySelector("[data-pack-form]");
  if (packForm) {
    var options = packForm.querySelectorAll("[data-pack-option]");
    var variantInput = packForm.querySelector("input[name='variant_id']");
    // The price block lives outside the pack form in product_pack.html, so
    // resolve these from the document scope (reviewer finding F4).
    var priceNow = document.querySelector("[data-price-now]");
    var priceCompare = document.querySelector("[data-price-compare]");
    var priceOff = document.querySelector("[data-price-off]");
    var perBottle = document.querySelector("[data-per-bottle]");
    function selectPack(btn) {
      options.forEach(function (o) { o.classList.toggle("selected", o === btn); });
      variantInput.value = btn.getAttribute("data-variant-id");
      // Keep the AJAX add-to-cart button in sync with the selected pack size —
      // the button posts its own data-variant-id (mirroring the single-product
      // variant-select handler below).
      var addBtn = packForm.querySelector("[data-add-to-cart]");
      if (addBtn) { addBtn.setAttribute("data-variant-id", btn.getAttribute("data-variant-id")); }
      if (priceNow) { priceNow.textContent = btn.getAttribute("data-price"); }
      if (priceCompare) { priceCompare.textContent = btn.getAttribute("data-compare"); }
      if (priceOff) {
        var off = btn.getAttribute("data-off");
        priceOff.style.display = off && off !== "0" ? "inline-block" : "none";
        priceOff.textContent = off + "% Off";
      }
      if (perBottle) { perBottle.textContent = btn.getAttribute("data-per-bottle") + " per bottle"; }
      var vid = btn.getAttribute("data-variant-id");
      document.querySelectorAll("[data-case-variant]").forEach(function (block) {
        block.style.display = block.getAttribute("data-case-variant") === vid ? "block" : "none";
      });
    }
    options.forEach(function (btn) {
      btn.addEventListener("click", function () { selectPack(btn); });
    });
    // case thumbnails: switch the visible bottle detail
    document.querySelectorAll("[data-case-block]").forEach(function (block) {
      var thumbs = block.querySelectorAll("[data-bottle-thumb]");
      var details = block.querySelectorAll("[data-bottle-detail]");
      thumbs.forEach(function (thumb) {
        thumb.addEventListener("click", function () {
          thumbs.forEach(function (t) { t.classList.toggle("selected", t === thumb); });
          var num = thumb.getAttribute("data-bottle-thumb");
          details.forEach(function (d) {
            d.style.display = d.getAttribute("data-bottle-detail") === num ? "flex" : "none";
          });
        });
      });
    });
  }

  // ---------- newsletter ----------
  var newsForm = document.querySelector("[data-newsletter]");
  if (newsForm) {
    newsForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var email = newsForm.querySelector("input[name='email']").value;
      fetch("/newsletter/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "email=" + encodeURIComponent(email),
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (d.ok) {
          newsForm.querySelector("input[name='email']").value = "";
          window.notify("Thanks for signing up!", "success");
        } else {
          window.notify(d.error || "Enter a valid email address.", "error");
        }
      });
    });
  }
})();

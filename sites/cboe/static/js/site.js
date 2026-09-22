/* Cboe mirror — symbol typeahead on the quotes pages. */
(function () {
  var input = document.getElementById("symbol-input");
  var box = document.getElementById("symbol-suggest");
  var form = document.querySelector(".symbol-form");
  if (!input || !box || !form) return;
  var timer = null;

  function hide() { box.style.display = "none"; box.innerHTML = ""; }

  input.addEventListener("input", function () {
    var q = input.value.trim();
    if (q.length < 1) { hide(); return; }
    if (timer) clearTimeout(timer);
    timer = setTimeout(function () {
      fetch("/symbol_search?q=" + encodeURIComponent(q))
        .then(function (r) { return r.json(); })
        .then(function (rows) {
          if (!rows.length) { hide(); return; }
          box.innerHTML = rows.map(function (r) {
            return '<div class="sug" data-name="' + r.name + '">' +
              '<span class="mono"><strong>' + r.name + '</strong></span>' +
              '<span class="co">' + r.company + "</span></div>";
          }).join("");
          box.style.display = "block";
          Array.prototype.forEach.call(box.querySelectorAll(".sug"), function (el) {
            el.addEventListener("mousedown", function (ev) {
              ev.preventDefault();
              var name = el.getAttribute("data-name");
              window.location.href = "/delayed_quotes/" + encodeURIComponent(name.toUpperCase());
            });
          });
        })
        .catch(function () { hide(); });
    }, 220);
  });

  document.addEventListener("click", function (ev) {
    if (box.contains(ev.target) || input.contains(ev.target)) return;
    hide();
  });

  window.goSymbol = function (ev) {
    ev.preventDefault();
    var v = input.value.trim().toUpperCase();
    if (v) window.location.href = "/delayed_quotes/" + encodeURIComponent(v);
    return false;
  };
})();

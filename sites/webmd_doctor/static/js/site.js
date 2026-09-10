/* WebMD Care mirror — small progressive enhancements (menus, popovers, typeahead). */
(function () {
  "use strict";

  function closeAll(except) {
    document.querySelectorAll(".menu.open, .popover.open, .typeahead.open").forEach(function (el) {
      if (el !== except) { el.classList.remove("open"); }
    });
  }

  document.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-toggle]");
    if (toggle) {
      event.preventDefault();
      var target = document.getElementById(toggle.getAttribute("data-toggle"));
      if (target) {
        var willOpen = !target.classList.contains("open");
        closeAll(target);
        target.classList.toggle("open", willOpen);
        toggle.setAttribute("aria-expanded", willOpen ? "true" : "false");
      }
      return;
    }
    if (!event.target.closest(".menu, .popover, .typeahead, .search-bar .field")) {
      closeAll(null);
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") { closeAll(null); }
  });

  // Filter bar: submit as soon as a choice changes (checkbox pills, popover radios, selects).
  // Empty / default fields are disabled right before submit so they stay out of the URL.
  function pruneEmptyFields(form) {
    Array.prototype.forEach.call(form.elements, function (field) {
      if (!field.name || field.type === "submit" || field.type === "button") { return; }
      if (field.type === "checkbox" || field.type === "radio") {
        var isDefault = (field.name === "sortby" && field.value === "bestmatch") || (field.name === "gender" && field.value === "all");
        if (!field.checked || field.value === "" || isDefault) { field.disabled = true; }
        return;
      }
      if (field.value === "") { field.disabled = true; }
    });
  }
  document.querySelectorAll("form.filter-form").forEach(function (form) {
    form.addEventListener("submit", function () { pruneEmptyFields(form); });
    form.querySelectorAll("input[type=checkbox], input[type=radio], select").forEach(function (input) {
      input.addEventListener("change", function () {
        if (typeof form.requestSubmit === "function") { form.requestSubmit(); } else { pruneEmptyFields(form); form.submit(); }
      });
    });
  });

  // Booking grid: highlight the checked slot / segment.
  document.querySelectorAll(".slot input, .seg input").forEach(function (input) {
    input.addEventListener("change", function () {
      var group = input.closest(".grid-days, .seg");
      if (group) {
        group.querySelectorAll(".on").forEach(function (el) { el.classList.remove("on"); });
      }
      input.closest("label").classList.add("on");
    });
    if (input.checked) { input.closest("label").classList.add("on"); }
  });

  // Search typeahead over specialties / conditions / practices embedded in the page.
  var dataNode = document.getElementById("typeahead-data");
  if (dataNode) {
    var vocab = JSON.parse(dataNode.textContent);
    document.querySelectorAll("input[data-typeahead]").forEach(function (input) {
      var box = document.getElementById(input.getAttribute("data-typeahead"));
      if (!box) { return; }
      input.addEventListener("input", function () {
        var term = input.value.trim().toLowerCase();
        box.innerHTML = "";
        if (term.length < 2) { box.classList.remove("open"); return; }
        var sections = [["SPECIALTY", vocab.specialty], ["CONDITION", vocab.condition], ["PRACTICE", vocab.practice]];
        var total = 0;
        sections.forEach(function (section) {
          var hits = section[1].filter(function (item) { return item.label.toLowerCase().indexOf(term) === 0; }).slice(0, 5);
          if (!hits.length) { return; }
          var head = document.createElement("div");
          head.className = "ta-section";
          head.textContent = section[0];
          box.appendChild(head);
          hits.forEach(function (item) {
            var link = document.createElement("a");
            link.href = item.href;
            if (section[0] === "SPECIALTY") { link.className = "ta-specialty"; }
            var hit = document.createElement("b");
            hit.textContent = item.label.slice(0, term.length);
            link.appendChild(hit);
            link.appendChild(document.createTextNode(item.label.slice(term.length)));
            box.appendChild(link);
            total += 1;
          });
        });
        box.classList.toggle("open", total > 0);
      });
    });
  }

  // Location typeahead (seeded cities + zips).
  var locNode = document.getElementById("location-data");
  if (locNode) {
    var places = JSON.parse(locNode.textContent);
    document.querySelectorAll("input[data-location]").forEach(function (input) {
      var box = document.getElementById(input.getAttribute("data-location"));
      if (!box) { return; }
      function render() {
        var term = input.value.trim().toLowerCase();
        box.innerHTML = "";
        var hits = places.filter(function (item) { return term.length === 0 || item.label.toLowerCase().indexOf(term) !== -1; }).slice(0, 8);
        hits.forEach(function (item) {
          var link = document.createElement("a");
          link.href = "#";
          link.textContent = item.label;
          link.addEventListener("click", function (event) {
            event.preventDefault();
            input.value = item.label;
            box.classList.remove("open");
          });
          box.appendChild(link);
        });
        box.classList.toggle("open", hits.length > 0);
      }
      input.addEventListener("input", render);
      input.addEventListener("focus", render);
    });
  }

  // Overview "View more".
  document.querySelectorAll("[data-expand]").forEach(function (button) {
    button.addEventListener("click", function (event) {
      event.preventDefault();
      var target = document.getElementById(button.getAttribute("data-expand"));
      if (target) {
        target.classList.toggle("expanded");
        button.textContent = target.classList.contains("expanded") ? "View less" : "View more";
      }
    });
  });
})();

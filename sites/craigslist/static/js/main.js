(function () {
  function setupGallery(root) {
    var frames = Array.prototype.slice.call(root.querySelectorAll(".gallery-frame"));
    if (frames.length <= 1) {
      return;
    }
    var dots = Array.prototype.slice.call(root.querySelectorAll("[data-gallery-index]"));
    var index = 0;

    function show(nextIndex) {
      index = (nextIndex + frames.length) % frames.length;
      frames.forEach(function (frame, frameIndex) {
        frame.classList.toggle("active", frameIndex === index);
      });
      dots.forEach(function (dot, dotIndex) {
        dot.classList.toggle("active", dotIndex === index);
      });
    }

    root.querySelectorAll("[data-gallery-prev]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        show(index - 1);
      });
    });
    root.querySelectorAll("[data-gallery-next]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        show(index + 1);
      });
    });
    dots.forEach(function (dot) {
      dot.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        show(Number(dot.getAttribute("data-gallery-index")) || 0);
      });
    });
  }

  function submitTopSelects(form) {
    form.querySelectorAll("select").forEach(function (select) {
      select.addEventListener("change", function () {
        if (select.name === "area") {
          form.submit();
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-gallery]").forEach(setupGallery);
    document.querySelectorAll(".top-selects").forEach(submitTopSelects);
    var sort = document.querySelector('#sort-order');
    if (sort) sort.addEventListener('change', function () { window.location.assign(sort.value); });
    var filters = document.querySelector('#search-filters');
    var toggle = document.querySelector('.filter-toggle');
    if (toggle) toggle.addEventListener('click', function () {
      filters.hidden = !filters.hidden;
      toggle.setAttribute('aria-expanded', String(!filters.hidden));
    });
    var save = document.querySelector('.cl-save-search');
    if (save) save.addEventListener('click', function () {
      filters.hidden = false;
      toggle.setAttribute('aria-expanded', 'true');
      document.querySelector('#save-search-panel').scrollIntoView({block: 'center'});
      document.querySelector('#save-search-panel input, #save-search-panel a').focus();
    });
  });
}());

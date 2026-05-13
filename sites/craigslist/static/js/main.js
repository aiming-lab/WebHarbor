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
  });
}());

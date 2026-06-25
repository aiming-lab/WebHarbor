// NVIDIA mirror — minimal progressive enhancement
document.addEventListener('DOMContentLoaded', function () {
  // auto-dismiss flash messages after a few seconds
  document.querySelectorAll('.flash').forEach(function (el) {
    setTimeout(function () { el.style.transition = 'opacity .4s'; el.style.opacity = '0'; }, 6000);
  });
});

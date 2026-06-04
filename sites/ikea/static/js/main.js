document.addEventListener("DOMContentLoaded", () => {
  for (const flash of document.querySelectorAll(".flash-card")) {
    setTimeout(() => flash.remove(), 5200);
  }
});

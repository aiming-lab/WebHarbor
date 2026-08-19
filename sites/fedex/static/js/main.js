document.addEventListener("DOMContentLoaded", () => {
  const sampleButtons = document.querySelectorAll("[data-fill-tracking]");
  sampleButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.querySelector(button.dataset.fillTracking);
      if (!target) return;
      target.value = button.dataset.value || "";
      target.focus();
    });
  });
});

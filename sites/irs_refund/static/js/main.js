document.addEventListener("DOMContentLoaded", () => {
  const printButton = document.querySelector("[data-print-summary]");
  if (printButton) {
    printButton.addEventListener("click", () => window.print());
  }
});

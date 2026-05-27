document.querySelectorAll(".preview-toggle").forEach((button) => {
  button.addEventListener("click", () => {
    const targetId = button.getAttribute("data-preview-target");
    const panel = document.getElementById(targetId);
    if (!panel) return;
    panel.classList.toggle("open");
    button.textContent = panel.classList.contains("open") ? "Hide preview" : "Preview mock";
  });
});

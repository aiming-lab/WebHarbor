document.addEventListener("click", (event) => {
  const button = event.target.closest("button, .cta, .ghost, .quiet-btn");
  if (button) {
    button.classList.add("is-pressed");
    window.setTimeout(() => button.classList.remove("is-pressed"), 150);
  }
});

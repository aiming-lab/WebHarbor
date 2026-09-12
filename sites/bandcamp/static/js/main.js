document.querySelectorAll("form select").forEach((select) => {
  select.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
    }
  });
});

document.querySelectorAll("form input, form select, form textarea").forEach((field) => {
  field.addEventListener("invalid", () => {
    if (field.validity.valueMissing) {
      field.setCustomValidity("Please fill out this field.");
    } else if (field.validity.typeMismatch) {
      field.setCustomValidity("Please enter a valid value.");
    } else {
      field.setCustomValidity("");
    }
  });
  field.addEventListener("input", () => field.setCustomValidity(""));
  field.addEventListener("change", () => field.setCustomValidity(""));
});

document.querySelectorAll(".preview-toggle").forEach((button) => {
  button.addEventListener("click", () => {
    const targetId = button.getAttribute("data-preview-target");
    const panel = document.getElementById(targetId);
    if (!panel) return;
    panel.classList.toggle("open");
    button.textContent = panel.classList.contains("open") ? "Hide preview" : "Preview";
  });
});

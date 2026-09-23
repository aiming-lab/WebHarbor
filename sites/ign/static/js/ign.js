document.addEventListener("DOMContentLoaded", () => {
  for (const row of document.querySelectorAll(".check-row")) {
    const checkbox = row.querySelector('input[type="checkbox"]');
    if (!checkbox || checkbox.disabled) continue;
    checkbox.addEventListener("change", () => {
      row.classList.toggle("completed", checkbox.checked);
    });
    row.classList.toggle("completed", checkbox.checked);
  }

  for (const control of document.querySelectorAll("[data-submit-on-change]")) {
    control.addEventListener("change", () => {
      const form = control.form;
      const stateField = control.dataset.stateField;
      if (form && stateField) {
        const hidden = form.querySelector(`input[type="hidden"][name="${stateField}"]`);
        if (hidden) hidden.value = control.checked ? "1" : "0";
      }
      if (form) form.requestSubmit();
    });
  }
});

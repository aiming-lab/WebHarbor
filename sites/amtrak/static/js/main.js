function syncTripForms() {
  document.querySelectorAll("[data-trip-form]").forEach((form) => {
    const typeInputs = form.querySelectorAll("[name='trip_type']");
    const returnField = form.querySelector("[data-return-field]");
    const passengerField = form.querySelector("[name='passengers']");

    const update = () => {
      let selected = "one-way";
      typeInputs.forEach((input) => {
        if (input.checked) {
          selected = input.value;
        }
      });
      if (returnField) {
        returnField.style.display = selected === "round-trip" ? "" : "none";
      }
      if (passengerField) {
        passengerField.min = selected === "multi-city" ? "1" : "1";
      }
    };

    typeInputs.forEach((input) => input.addEventListener("change", update));
    update();
  });
}

function wirePassengerFill() {
  document.querySelectorAll("[data-fill-profile]").forEach((button) => {
    button.addEventListener("click", () => {
      const first = button.getAttribute("data-first-name") || "";
      const last = button.getAttribute("data-last-name") || "";
      const pref = button.getAttribute("data-seat-preference") || "Window";
      const need = button.getAttribute("data-accessibility-need") || "";

      const firstInput = document.querySelector("[name='first_name_0']");
      const lastInput = document.querySelector("[name='last_name_0']");
      const prefInput = document.querySelector("[name='seat_preference_0']");
      const needInput = document.querySelector("[name='accessibility_need_0']");
      if (firstInput) {
        firstInput.value = first;
      }
      if (lastInput) {
        lastInput.value = last;
      }
      if (prefInput) {
        prefInput.value = pref;
      }
      if (needInput) {
        needInput.value = need;
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  syncTripForms();
  wirePassengerFill();
});

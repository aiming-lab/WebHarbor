document.addEventListener("click", (event) => {
  const card = event.target.closest(".plan-card");
  if (!card) return;
  document.querySelectorAll(".plan-card").forEach((el) => el.classList.remove("focused"));
  card.classList.add("focused");
});

// Persist changed selections and render their new total before payment.
const checkout = document.querySelector('#checkout-form');
if (checkout) {
  for (const input of checkout.querySelectorAll('[name="billing_cycle"], [name="seats"]')) {
    input.addEventListener('change', () => {
      if (checkout.reportValidity()) checkout.requestSubmit(document.querySelector('#update-summary'));
    });
  }
}

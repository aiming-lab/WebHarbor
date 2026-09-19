document.addEventListener("click", (event) => {
  const card = event.target.closest(".plan-card");
  if (!card) return;
  document.querySelectorAll(".plan-card").forEach((el) => el.classList.remove("focused"));
  card.classList.add("focused");
});

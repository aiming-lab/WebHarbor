document.addEventListener("DOMContentLoaded", () => {
  for (const flash of document.querySelectorAll(".flash-card")) {
    setTimeout(() => flash.remove(), 5200);
  }

  const storeSelect = document.querySelector("#pickup-store");
  const slotSelect = document.querySelector("#pickup-slot");
  if (storeSelect && slotSelect) {
    storeSelect.addEventListener("change", async () => {
      slotSelect.disabled = true;
      slotSelect.replaceChildren(new Option("Loading pickup times…", ""));
      try {
        const url = new URL(storeSelect.dataset.slotsUrl, window.location.origin);
        url.searchParams.set("store_slug", storeSelect.value);
        const response = await fetch(url);
        if (!response.ok) throw new Error("pickup slots unavailable");
        const payload = await response.json();
        slotSelect.replaceChildren(
          ...payload.slots.map((slot) => new Option(slot.label, String(slot.id))),
        );
      } catch (error) {
        slotSelect.replaceChildren(new Option("Pickup times unavailable", ""));
      } finally {
        slotSelect.disabled = false;
      }
    });
  }
});

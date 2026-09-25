/* Shared interactions: FAQ accordions, read-more, favorites, sailing toggles. */
document.addEventListener("DOMContentLoaded", () => {
  // FAQ accordions
  document.querySelectorAll(".faq-q").forEach(btn => {
    btn.addEventListener("click", () => {
      const item = btn.closest(".faq-item");
      item.classList.toggle("open");
      btn.setAttribute("aria-expanded", item.classList.contains("open"));
    });
  });

  // read-more blocks
  document.querySelectorAll(".read-more-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      const expanded = target.classList.toggle("open");
      btn.textContent = expanded ? "Read Less" : (btn.dataset.more || "Read More");
    });
  });

  // favorite hearts
  document.querySelectorAll(".fav-btn").forEach(btn => {
    btn.addEventListener("click", async (ev) => {
      ev.preventDefault();
      const itinId = btn.dataset.itinerary;
      const body = new URLSearchParams({ itinerary_id: itinId });
      const res = await fetch("/favorites/toggle", {
        method: "POST",
        headers: { "X-Requested-With": "fetch" },
        body,
      });
      if (res.status === 401) {
        window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
        return;
      }
      const data = await res.json();
      if (data.ok) btn.classList.toggle("saved", data.saved);
    });
  });

  // sailing dates toggles on search cards
  document.querySelectorAll(".show-dates-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const panel = document.getElementById(btn.dataset.target);
      if (!panel) return;
      const open = panel.style.display !== "block";
      panel.style.display = open ? "block" : "none";
      btn.textContent = open ? "HIDE DATES" : btn.dataset.label;
    });
  });
});

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

document.querySelectorAll(".cover-play").forEach((button) => {
  button.addEventListener("click", (event) => {
    event.preventDefault();
    const card = button.closest(".release-card, .merch-card");
    if (!card) return;
    card.classList.toggle("playing");
    const badge = button.querySelector(".play-badge");
    if (badge) badge.textContent = card.classList.contains("playing") ? "❚❚" : "▶";
  });
});

function formatClock(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
}

document.querySelectorAll(".player-toggle").forEach((button) => {
  const block = button.closest(".player-block");
  if (!block) return;
  const total = Number(block.getAttribute("data-duration") || 0);
  const timeLabel = block.querySelector(".player-time");
  const fill = block.querySelector(".player-bar span");
  const panel = document.getElementById(button.getAttribute("data-preview-target") || "");
  let elapsed = 0;
  let timer = null;

  const render = () => {
    if (timeLabel) timeLabel.textContent = formatClock(elapsed) + " / " + formatClock(total);
    if (fill) fill.style.width = total > 0 ? Math.min(100, (elapsed / total) * 100).toFixed(2) + "%" : "0%";
  };

  const stop = (reset) => {
    if (timer) { clearInterval(timer); timer = null; }
    block.classList.remove("playing");
    button.textContent = "▶";
    if (reset) { elapsed = 0; render(); }
  };

  button.addEventListener("click", () => {
    if (timer) { stop(false); return; }
    if (total <= 0 || elapsed >= total) elapsed = 0;
    block.classList.add("playing");
    button.textContent = "❚❚";
    if (panel) panel.classList.add("open");
    render();
    timer = setInterval(() => {
      elapsed += 1;
      if (elapsed >= total) { stop(true); if (panel) panel.classList.remove("open"); return; }
      render();
    }, 1000);
  });
});

(function () {
  const strip = document.getElementById("selling-now");
  const toggle = document.getElementById("feed-toggle");
  if (!strip || !toggle) return;
  let timer = null;
  const step = () => {
    const card = strip.querySelector(".sell-card");
    const width = card ? card.getBoundingClientRect().width + 14 : 126;
    if (strip.scrollLeft + strip.clientWidth >= strip.scrollWidth - 4) {
      strip.scrollTo({ left: 0, behavior: "smooth" });
    } else {
      strip.scrollBy({ left: width, behavior: "smooth" });
    }
  };
  const status = document.getElementById("feed-status");
  const stop = () => { if (timer) { clearInterval(timer); timer = null; } toggle.textContent = "unpause"; if (status) status.textContent = "paused"; };
  toggle.addEventListener("click", () => {
    if (timer) { stop(); return; }
    timer = setInterval(step, 4000);
    toggle.textContent = "pause";
    if (status) status.textContent = "";
  });
})();

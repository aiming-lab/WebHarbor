(() => {
  const menus = [...document.querySelectorAll(".nav-menu")];

  for (const menu of menus) {
    menu.addEventListener("toggle", () => {
      if (!menu.open) return;
      for (const sibling of menus) {
        if (sibling !== menu) sibling.removeAttribute("open");
      }
    });
  }

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".nav-menu")) {
      for (const menu of menus) menu.removeAttribute("open");
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      for (const menu of menus) menu.removeAttribute("open");
    }
  });

  const dismissPromo = document.querySelector("[data-dismiss-promo]");
  dismissPromo?.addEventListener("click", () => {
    document.querySelector("[data-promo]")?.remove();
  });
})();

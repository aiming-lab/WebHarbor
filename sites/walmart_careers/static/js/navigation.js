(() => {
  const menus = Array.from(
    document.querySelectorAll(".site-header details.nav-menu, .site-header details.user-menu")
  );

  if (menus.length === 0) return;

  const setExpanded = (menu) => {
    const summary = menu.querySelector(":scope > summary");
    if (summary) summary.setAttribute("aria-expanded", String(menu.open));
  };

  const closeMenus = (except = null) => {
    for (const menu of menus) {
      if (menu !== except && menu.open) {
        menu.open = false;
        setExpanded(menu);
      }
    }
  };

  for (const menu of menus) {
    const summary = menu.querySelector(":scope > summary");
    if (!summary) continue;

    setExpanded(menu);
    summary.addEventListener("click", () => {
      if (!menu.open) closeMenus(menu);
    });
    menu.addEventListener("toggle", () => {
      if (menu.open) closeMenus(menu);
      setExpanded(menu);
    });
  }

  document.addEventListener("pointerdown", (event) => {
    if (!menus.some((menu) => menu.contains(event.target))) closeMenus();
  });

  document.addEventListener("focusin", (event) => {
    if (!menus.some((menu) => menu.contains(event.target))) closeMenus();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;

    const openMenu = menus.find((menu) => menu.open);
    if (!openMenu) return;

    const restoreFocus = openMenu.contains(document.activeElement);
    const summary = openMenu.querySelector(":scope > summary");
    closeMenus();
    if (restoreFocus && summary) summary.focus();
    event.preventDefault();
  });
})();

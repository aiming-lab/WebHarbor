document.addEventListener("DOMContentLoaded", () => {
  const menus = [...document.querySelectorAll(".nav-menu")];
  menus.forEach((menu) => {
    menu.addEventListener("toggle", () => {
      if (menu.open) menus.filter((other) => other !== menu).forEach((other) => { other.open = false; });
    });
  });
  document.addEventListener("click", (event) => {
    menus.filter((menu) => !menu.contains(event.target)).forEach((menu) => { menu.open = false; });
  });
  const menuButton = document.querySelector(".mobile-menu");
  const navigation = document.getElementById("primary-nav");
  menuButton.addEventListener("click", () => {
    const expanded = menuButton.getAttribute("aria-expanded") !== "true";
    menuButton.setAttribute("aria-expanded", String(expanded));
    menuButton.setAttribute("aria-label", expanded ? "Close navigation" : "Open navigation");
    navigation.classList.toggle("is-open", expanded);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const openMenu = menus.find((menu) => menu.open);
    if (openMenu) { openMenu.open = false; openMenu.querySelector("summary").focus(); }
    if (navigation.classList.contains("is-open")) {
      navigation.classList.remove("is-open");
      menuButton.setAttribute("aria-expanded", "false");
      menuButton.setAttribute("aria-label", "Open navigation");
      menuButton.focus();
    }
  });
  const tabs = [...document.querySelectorAll(".home-tabs [role=tab]")];
  const selectTab = (selected) => tabs.forEach((tab) => {
    const active = tab === selected;
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
    document.getElementById(tab.getAttribute("aria-controls")).hidden = !active;
  });
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectTab(tab));
    tab.addEventListener("keydown", (event) => {
      let next;
      if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
      if (event.key === "ArrowLeft") next = (index + tabs.length - 1) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      if (next === undefined) return;
      event.preventDefault();
      selectTab(tabs[next]);
      tabs[next].focus();
    });
  });
  const notice = document.getElementById("offline-notice");
  document.querySelectorAll("[data-notice-title]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      document.getElementById("offline-title").textContent = link.dataset.noticeTitle;
      document.getElementById("offline-description").textContent = link.dataset.noticeDescription;
      notice.showModal();
    });
  });
});

document.documentElement.classList.add("js");

if (window.matchMedia("(max-width: 760px)").matches) {
  document.querySelectorAll(".filter-disclosure[open]").forEach((details) => {
    details.removeAttribute("open");
  });
}

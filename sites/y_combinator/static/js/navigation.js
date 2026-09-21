(() => {
  const toggle = document.querySelector('.nav-toggle');
  const drawer = document.querySelector('.nav-drawer');
  if (!toggle || !drawer) return;
  const setOpen = open => {
    drawer.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  };
  toggle.addEventListener('click', () => setOpen(!drawer.classList.contains('open')));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && drawer.classList.contains('open')) {
      setOpen(false);
      toggle.focus();
    }
  });
  matchMedia('(min-width: 1024px)').addEventListener('change', event => {
    if (event.matches) setOpen(false);
  });
})();

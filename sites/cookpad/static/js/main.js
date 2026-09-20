document.addEventListener('DOMContentLoaded', () => {
  const menu = document.querySelector('.nav-toggle');
  const close = () => { document.body.classList.remove('menu-open'); menu?.setAttribute('aria-expanded', 'false'); };
  menu?.addEventListener('click', () => {
    const expanded = menu.getAttribute('aria-expanded') !== 'true';
    menu.setAttribute('aria-expanded', String(expanded));
    document.body.classList.toggle('menu-open', expanded);
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  document.querySelectorAll('.sidebar a').forEach(a => a.addEventListener('click', close));
});

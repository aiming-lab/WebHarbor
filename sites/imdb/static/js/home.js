document.querySelectorAll('[data-open-dialog]').forEach(button => {
  button.addEventListener('click', () => document.getElementById(button.dataset.openDialog).showModal());
});
const drawer = document.getElementById('nav-drawer');
drawer?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => drawer.close()));
drawer?.addEventListener('click', event => {
  if (event.target === drawer) drawer.close();
});
const searchToggle = document.querySelector('.mobile-search');
searchToggle?.addEventListener('click', () => {
  const expanded = searchToggle.getAttribute('aria-expanded') !== 'true';
  searchToggle.setAttribute('aria-expanded', String(expanded));
  document.querySelector('.topbar').classList.toggle('search-open', expanded);
  if (expanded) document.querySelector('#site-search input').focus();
});
document.querySelector('#site-search')?.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    document.querySelector('.topbar').classList.remove('search-open');
    searchToggle.setAttribute('aria-expanded', 'false');
    searchToggle.focus();
  }
});
document.querySelectorAll('[data-scroll-rail]').forEach(button => {
  button.addEventListener('click', () => {
    const rail = button.parentElement.querySelector('[data-rail]');
    const atEnd = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 2;
    rail.scrollTo({left: atEnd ? 0 : rail.scrollLeft + rail.clientWidth * 0.85,
      behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
  });
});
const slides = [...document.querySelectorAll('[data-slide]')];
document.querySelectorAll('[data-episode-spotlight]').forEach(spotlight => {
  spotlight.querySelectorAll('[data-episode-select]').forEach(button => {
    button.addEventListener('click', () => {
      spotlight.querySelectorAll('[data-episode-select]').forEach(choice => {
        choice.setAttribute('aria-pressed', String(choice === button));
      });
      spotlight.querySelectorAll('[data-episode-panel]').forEach(panel => {
        panel.hidden = panel.dataset.episodePanel !== button.dataset.episodeSelect;
      });
    });
  });
});
let currentSlide = 0;
document.querySelectorAll('[data-hero-step]').forEach(button => {
  button.addEventListener('click', () => {
    if (!slides.length) return;
    slides[currentSlide].hidden = true;
    currentSlide = (currentSlide + Number(button.dataset.heroStep) + slides.length) % slides.length;
    slides[currentSlide].hidden = false;
    document.querySelectorAll('[data-up-next]').forEach(item => {
      const distance = (Number(item.dataset.upNext) - currentSlide + slides.length) % slides.length;
      item.hidden = distance < 1 || distance > 3;
      item.style.order = distance;
    });
    document.getElementById('hero-status').textContent = (currentSlide + 1) + ' of ' + slides.length;
  });
});

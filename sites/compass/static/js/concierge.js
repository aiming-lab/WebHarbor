(() => {
  const page = document.querySelector('#concierge-page');
  if (!page) return;

  const slides = [...page.querySelectorAll('.slide')];
  const status = page.querySelector('[data-story-status]');
  let current = 0;
  const show = index => {
    if (!slides.length) return;
    current = (index + slides.length) % slides.length;
    slides.forEach((slide, position) => {
      slide.hidden = position !== current;
      slide.classList.toggle('slide-active', position === current);
    });
    if (status) status.textContent = `Success story ${current + 1} of ${slides.length}`;
  };
  page.querySelector('.slider-prev')?.addEventListener('click', () => show(current - 1));
  page.querySelector('.slider-next')?.addEventListener('click', () => show(current + 1));
  show(0);

  const chapters = page.querySelector('.concierge-chapters');
  const hero = page.querySelector('#hero');
  const updateChapters = visible => {
    chapters?.classList.toggle('is-visible', visible);
    document.body.classList.toggle('concierge-reading', visible);
  };
  if (chapters && hero && 'IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => updateChapters(!entry.isIntersecting)).observe(hero);
  } else if (chapters && hero) {
    const update = () => updateChapters(hero.getBoundingClientRect().bottom <= 0);
    window.addEventListener('scroll', update, { passive: true });
    update();
  }

  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    page.querySelectorAll('video').forEach(video => video.pause());
  }
})();

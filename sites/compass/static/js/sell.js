(() => {
  const stack = document.querySelector('[data-sell-stack]');
  if (stack) {
    stack.classList.add('is-enhanced');
    const cards = [...stack.querySelectorAll('[data-stack-card]')];
    const status = stack.querySelector('[data-stack-status]');
    let selected = 0;

    function renderStack() {
      cards.forEach((card, index) => {
        const depth = (index - selected + cards.length) % cards.length;
        card.style.zIndex = String(cards.length - depth);
        card.style.transform = `translateX(var(--card-offset-x-${depth})) translateY(var(--card-offset-y-${depth}))`;
        const shade = depth === 1 ? 17 : 67;
        const shadeElement = card.querySelector('.sell-card-shade');
        if (shadeElement) shadeElement.style.background = depth ? `rgba(${shade},${shade},${shade},${depth / 3})` : 'transparent';
        card.setAttribute('aria-hidden', String(depth !== 0));
      });
      if (status && cards[selected]) status.textContent = `${cards[selected].getAttribute('aria-label')}, ${selected + 1} of ${cards.length}`;
    }

    function selectCard(index) {
      selected = index;
      renderStack();
    }

    stack.querySelectorAll('[data-stack-step]').forEach(button => button.addEventListener('click', () => {
      selectCard((selected + Number(button.dataset.stackStep) + cards.length) % cards.length);
    }));
    stack.addEventListener('keydown', event => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        selectCard((selected + (event.key === 'ArrowLeft' ? -1 : 1) + cards.length) % cards.length);
      }
    });
    if (cards.length) renderStack();
  }

  const carousel = document.querySelector('[data-sell-carousel]');
  if (!carousel) return;
  carousel.classList.add('is-enhanced');
  const track = carousel.querySelector('[data-appearance-track]');
  const slides = [...carousel.querySelectorAll('[data-appearance-card]')];
  const status = carousel.querySelector('[data-appearance-status]');
  if (!track || !slides.length) return;
  let slideIndex = 0;

  function renderSlide() {
    const offset = slides[slideIndex].offsetLeft - slides[0].offsetLeft;
    track.style.transform = `translate3d(${-offset}px,0,0)`;
    slides.forEach((slide, index) => {
      slide.setAttribute('role', 'group');
      slide.setAttribute('aria-roledescription', 'slide');
      slide.setAttribute('aria-label', `${index + 1} of ${slides.length}`);
      slide.setAttribute('aria-hidden', String(index !== slideIndex));
      slide.inert = index !== slideIndex;
    });
    if (status) status.textContent = `Listing comparison ${slideIndex + 1} of ${slides.length}`;
  }

  carousel.querySelectorAll('[data-appearance-step]').forEach(button => button.addEventListener('click', () => {
    slideIndex = (slideIndex + Number(button.dataset.appearanceStep) + slides.length) % slides.length;
    renderSlide();
  }));
  carousel.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      slideIndex = (slideIndex + (event.key === 'ArrowLeft' ? -1 : 1) + slides.length) % slides.length;
      renderSlide();
    }
  });
  if ('ResizeObserver' in window) new ResizeObserver(renderSlide).observe(track.parentElement);
  else window.addEventListener('resize', renderSlide);
  renderSlide();
})();

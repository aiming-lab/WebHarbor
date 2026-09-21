/* Progressive enhancement: no automatic carousel movement or navigation. */
(() => {
    'use strict';

    document.querySelectorAll('[data-nav-menu]').forEach((menu) => {
        menu.addEventListener('keydown', (event) => {
            if (event.key !== 'Escape' || !menu.open) return;
            menu.open = false;
            menu.querySelector('summary').focus();
            event.preventDefault();
        });
        document.addEventListener('click', (event) => {
            if (menu.open && !menu.contains(event.target)) menu.open = false;
        });
    });

    document.querySelectorAll('[data-home-carousel]').forEach((carousel) => {
        const slides = Array.from(carousel.querySelectorAll('[data-home-slide]'));
        const controls = carousel.querySelector('[data-home-controls]');
        if (slides.length < 2 || !controls) return;
        const dots = Array.from(carousel.querySelectorAll('[data-home-dot]'));
        const status = carousel.querySelector('[data-home-status]');
        let current = 0;

        const showSlide = (requested) => {
            current = (requested + slides.length) % slides.length;
            slides.forEach((slide, index) => { slide.hidden = index !== current; });
            dots.forEach((dot, index) => {
                if (index === current) dot.setAttribute('aria-current', 'true');
                else dot.removeAttribute('aria-current');
            });
            status.textContent = `Featured story ${current + 1} of ${slides.length}: ${slides[current].querySelector('h2').textContent}`;
        };
        carousel.querySelector('[data-home-previous]').addEventListener('click', () => showSlide(current - 1));
        carousel.querySelector('[data-home-next]').addEventListener('click', () => showSlide(current + 1));
        dots.forEach((dot, index) => dot.addEventListener('click', () => showSlide(index)));
        carousel.addEventListener('keydown', (event) => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            const focusWasOnSlide = slides[current].contains(document.activeElement);
            if (event.key === 'Home') showSlide(0);
            else if (event.key === 'End') showSlide(slides.length - 1);
            else showSlide(current + (event.key === 'ArrowRight' ? 1 : -1));
            if (focusWasOnSlide) slides[current].querySelector('a').focus();
        });
        controls.hidden = false;
    });

    document.querySelectorAll('[data-home-shelf]').forEach((shelf) => {
        const track = shelf.querySelector('[data-home-track]');
        const buttons = Array.from(shelf.querySelectorAll('[data-home-scroll]'));
        const updateButtons = () => {
            const remaining = track.scrollWidth - track.clientWidth;
            buttons.forEach((button) => {
                button.hidden = remaining <= 2;
                button.disabled = Number(button.dataset.homeScroll) < 0
                    ? track.scrollLeft <= 2
                    : track.scrollLeft >= remaining - 2;
            });
        };
        buttons.forEach((button) => button.addEventListener('click', () => {
            const card = track.firstElementChild;
            const gap = parseFloat(getComputedStyle(track).columnGap) || 0;
            const stride = card ? card.getBoundingClientRect().width + gap : track.clientWidth;
            const distance = Math.max(1, Math.floor(track.clientWidth / stride)) * stride;
            track.scrollBy({
                left: distance * Number(button.dataset.homeScroll),
                behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
            });
        }));
        track.addEventListener('scroll', updateButtons, { passive: true });
        if ('ResizeObserver' in window) new ResizeObserver(updateButtons).observe(track);
        else window.addEventListener('resize', updateButtons);
        updateButtons();
    });
})();

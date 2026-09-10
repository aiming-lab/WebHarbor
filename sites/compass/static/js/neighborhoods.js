document.querySelectorAll('[data-region-more]').forEach(button => {
  button.addEventListener('click', () => {
    const expanded = button.getAttribute('aria-expanded') !== 'true';
    button.setAttribute('aria-expanded', String(expanded));
    button.closest('[data-region-links]').classList.toggle('is-expanded', expanded);
    button.textContent = expanded ? 'Show less' : 'Show more';
  });
});

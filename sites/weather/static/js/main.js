document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.weather-search input').forEach((input) => {
    input.setAttribute('autocomplete', 'off');
  });
});

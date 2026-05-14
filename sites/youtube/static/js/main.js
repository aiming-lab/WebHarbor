document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.searchbar input').forEach((input) => {
    input.setAttribute('autocomplete', 'off');
  });
});

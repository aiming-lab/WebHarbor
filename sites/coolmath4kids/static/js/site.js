/* Coolmath4Kids mirror — base page behaviors. */
(function () {
  'use strict';
  // focus the search box on the search page
  var searchInput = document.querySelector('.search-bar input[type="text"]');
  if (searchInput) { searchInput.focus(); }

  // open-fullscreen toggle on game stages
  document.querySelectorAll('.open-fullscreen').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var stage = btn.closest('.game-stage');
      if (stage.requestFullscreen) { stage.requestFullscreen(); }
    });
  });
})();

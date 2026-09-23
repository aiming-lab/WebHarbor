/* Game viewer: replays a real master game's SAN move list with board
   controls (first / prev / next / flip), mirroring the site's game view. */
(function () {
  "use strict";
  var boardEl = document.getElementById("game-board");
  var moveListEl = document.getElementById("game-moves");
  if (!boardEl) return;
  var moves = JSON.parse(boardEl.dataset.moves || "[]");
  var startFen = boardEl.dataset.fen || "rnbqkbnr/pppppppp/8/8/8/8/8/RNBQKBNR w KQkq - 0 1";
  var ply = 0;
  var flipped = false;

  var board = new window.ChessBoard(boardEl, { fen: startFen });

  function sanTable() {
    var html = "";
    for (var i = 0; i < moves.length; i += 2) {
      var no = (i / 2) + 1;
      html += '<span class="move-num">' + no + '.</span>' +
        '<span class="san" data-ply="' + (i + 1) + '">' + moves[i] + '</span> ' +
        (moves[i + 1] ? '<span class="san" data-ply="' + (i + 2) + '">' + moves[i + 1] + '</span> ' : '');
    }
    moveListEl.innerHTML = html;
    moveListEl.querySelectorAll(".san").forEach(function (el) {
      el.addEventListener("click", function () { gotoPly(parseInt(el.dataset.ply, 10)); });
    });
  }

  function gotoPly(n) {
    ply = Math.max(0, Math.min(moves.length, n));
    board.fen = startFen;
    board.replay(moves, ply);
    moveListEl.querySelectorAll(".san").forEach(function (el) {
      el.classList.toggle("active", parseInt(el.dataset.ply, 10) === ply);
    });
    var active = moveListEl.querySelector(".san.active");
    if (active) active.scrollIntoView({ block: "nearest" });
  }

  document.querySelectorAll("[data-board-action]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var action = btn.dataset.boardAction;
      if (action === "first") gotoPly(0);
      else if (action === "prev") gotoPly(ply - 1);
      else if (action === "next") gotoPly(ply + 1);
      else if (action === "last") gotoPly(moves.length);
      else if (action === "flip") {
        flipped = !flipped;
        board.flip = flipped;
        var order = Array.prototype.slice.call(boardEl.children).reverse();
        order.forEach(function (el) { boardEl.appendChild(el); });
        board.draw();
      }
    });
  });
  sanTable();
  gotoPly(0);
})();

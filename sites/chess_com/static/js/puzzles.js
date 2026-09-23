/* Puzzle trainer: fetch real puzzles from the mirror's callback, validate
   the user's moves against the recorded solution, advance the line,
   auto-play the opponent reply, and track the streak. */
(function () {
  "use strict";

  var els = {
    board: document.getElementById("trainer-board"),
    status: document.getElementById("trainer-status"),
    themes: document.getElementById("trainer-themes"),
    goal: document.getElementById("trainer-goal"),
    rating: document.getElementById("trainer-rating"),
    streak: document.getElementById("trainer-streak"),
    solved: document.getElementById("trainer-solved"),
    next: document.getElementById("trainer-next"),
    solutionBox: document.getElementById("trainer-solution"),
    solutionLine: document.getElementById("trainer-solution-line"),
    sideName: document.getElementById("trainer-side"),
  };
  if (!els.board) return;

  var board = new window.ChessBoard(els.board, { interactive: true, onUserMove: onUserMove });
  var puzzle = null;
  var step = 0;
  var streak = 0;
  var busy = false;
  var rated = new URLSearchParams(window.location.search).get("mode") === "rated";
  var loggedIn = document.body.dataset.loggedIn === "1";

  function loadPuzzle() {
    busy = true;
    fetch("/callback/puzzles/next" + (puzzle ? "?after=" + puzzle.id : ""))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        puzzle = data;
        step = 0;
        board.fen = puzzle.fen;
        board.setPosition(puzzle.fen, null);
        els.status.textContent = "Find the best move!";
        els.status.className = "trainer-status";
        els.themes.textContent = (puzzle.themes || []).join(", ") || "Tactics";
        els.goal.textContent = puzzle.goals || "";
        els.rating.textContent = puzzle.rating ? "Rated " + puzzle.rating : "";
        els.solutionLine.textContent = "";
        if (els.solutionBox) els.solutionBox.style.display = "none";
        var whiteToMove = puzzle.fen.split(/\s+/)[1] !== "b";
        if (els.sideName) {
          els.sideName.textContent = whiteToMove
            ? "White to move"
            : "Black to move";
          els.sideName.style.color = whiteToMove ? "#e6e3e1" : "#8f8b88";
        }
        busy = false;
      })
      .catch(function () {
        els.status.textContent = "Could not load the next puzzle.";
      });
  }

  function norm(sq) { return sq ? sq.toLowerCase().replace("square_", "") : sq; }

  function onUserMove(from, to) {
    if (busy || !puzzle) return;
    var expected = puzzle.moves[step];
    if (!expected) return;
    if (norm(from) === norm(expected.from) && norm(to) === norm(expected.to)) {
      board.applyMove(from, to);
      step++;
      if (step >= puzzle.moves.length) {
        streak++;
        els.status.textContent = "Correct! Well played.";
        els.status.className = "trainer-status correct";
        updateStreak();
        recordAttempt(true);
        busy = true;
        return;
      }
      els.status.textContent = "Good! Keep going…";
      els.status.className = "trainer-status";
      /* auto-play the opponent reply after a short pause */
      setTimeout(function () {
        var reply = puzzle.moves[step];
        board.applyMove(norm(reply.from), norm(reply.to));
        step++;
        busy = false;
        if (step >= puzzle.moves.length) {
          streak++;
          els.status.textContent = "Correct! Well played.";
          els.status.className = "trainer-status correct";
          updateStreak();
          recordAttempt(true);
        }
      }, 550);
      busy = true;
      setTimeout(function () { busy = false; }, 560);
    } else {
      streak = 0;
      updateStreak();
      els.status.textContent = "Incorrect — the best line was:";
      els.status.className = "trainer-status incorrect";
      var line = [];
      var st = window.parseFen(puzzle.fen);
      puzzle.moves.forEach(function (mv) {
        line.push("");
      });
      els.solutionLine.textContent = describeSolution();
      if (els.solutionBox) els.solutionBox.style.display = "block";
      recordAttempt(false);
      busy = true;
    }
  }

  function describeSolution() {
    /* replay the solution on a scratch state to render SAN-ish text */
    var parts = [];
    var state = window.parseFen(puzzle.fen);
    var turnNo = 1;
    var sanList = [];
    puzzle.moves.forEach(function (mv) {
      sanList.push(sanOf(state, mv));
    });
    /* pair the moves like a game score */
    var idx = 0;
    var startBlack = state.turn === "b";
    if (startBlack) { parts.push("1… " + sanList[0]); idx = 1; }
    else if (sanList.length) { parts.push("1. " + sanList[0]); idx = 1; }
    var moveNo = startBlack ? 2 : 1;
    while (idx < sanList.length) {
      if (state.turn === "w") {
        parts.push(moveNo + ". " + sanList[idx]);
        idx++;
        if (idx < sanList.length) { parts.push(" " + sanList[idx]); idx++; }
      } else {
        parts.push(moveNo + "… " + sanList[idx]);
        idx++;
      }
      moveNo++;
    }
    return parts.join(" ");
  }

  function sanOf(state, mv) {
    /* minimal SAN for the trainer's solution display */
    var from = norm(mv.from), to = norm(mv.to);
    var piece = state.squares[from];
    if (!piece) return from + "-" + to;
    var type = piece.toUpperCase();
    if (type === "K" && Math.abs(from.charCodeAt(0) - to.charCodeAt(0)) === 2) {
      window.applySan(state, to[0] === "g" ? "O-O" : "O-O-O");
      return to[0] === "g" ? "O-O" : "O-O-O";
    }
    var isCapture = !!state.squares[to] || (type === "P" && from[0] !== to[0]);
    var san = "";
    if (type === "P") {
      san = isCapture ? from[0] + "x" + to : to;
    } else {
      san = type + (isCapture ? "x" : "") + to;
    }
    window.applySan(state, san);
    return san;
  }

  function updateStreak() {
    if (els.streak) els.streak.textContent = streak;
    if (els.solved && loggedIn) {
      fetch("/callback/puzzles/next").then(function () {});
    }
  }

  function recordAttempt(solved) {
    if (!rated || !loggedIn) return;
    fetch("/callback/puzzles/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ puzzle_id: puzzle.id, solved: solved }),
    });
  }

  if (els.next) els.next.addEventListener("click", loadPuzzle);
  loadPuzzle();
})();

/* Chess board renderer + naive SAN replayer + click-to-move.
   Piece images are the site's real Neo set; squares use the live green board. */
(function () {
  "use strict";

  /* FEN piece codes map to the Neo set's file names: P→wp/pp, R→wr/br, … */
  var PIECE_IMG = function (code) {
    var color = code === code.toUpperCase() ? "w" : "b";
    return window.CHESS_STATIC + "/pieces/neo/" + color + code.toLowerCase() + ".png";
  };

  var FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];

  function parseFen(fen) {
    var parts = fen.trim().split(/\s+/);
    var rows = parts[0].split("/");
    var squares = {};
    for (var r = 0; r < 8; r++) {
      var file = 0;
      for (var i = 0; i < rows[r].length; i++) {
        var ch = rows[r][i];
        if (/[1-8]/.test(ch)) { file += parseInt(ch, 10); continue; }
        squares[FILES[file] + (8 - r)] = ch;
        file++;
      }
    }
    return {
      squares: squares,
      turn: parts[1] || "w",
      castling: (parts[2] || "-").replace(/-/g, ""),
      ep: (parts[3] || "-") === "-" ? null : parts[3],
    };
  }

  function stateFromFen(fen) { return parseFen(fen); }

  function otherColor(c) { return c === "w" ? "b" : "w"; }
  function colorOf(piece) { return piece === piece.toUpperCase() ? "w" : "b"; }

  function vectorMoves(state, from, piece) {
    /* pseudo-legal moves for sliding/jumping pieces (enough to locate the
       source square of a recorded SAN move from a real game) */
    var moves = [];
    var f = FILES.indexOf(from[0]);
    var rk = parseInt(from[1], 10);
    var color = colorOf(piece);
    var type = piece.toUpperCase();
    var push = function (df, dr, once) {
      var nf = f + df, nr = rk + dr;
      while (nf >= 0 && nf < 8 && nr >= 1 && nr <= 8) {
        var sq = FILES[nf] + nr;
        var target = state.squares[sq];
        if (target) {
          if (colorOf(target) !== color) moves.push(sq);
          break;
        }
        moves.push(sq);
        if (once) break;
        nf += df; nr += dr;
      }
    };
    if (type === "N") { [[1,2],[2,1],[-1,2],[-2,1],[1,-2],[2,-1],[-1,-2],[-2,-1]].forEach(function (d) { push(d[0], d[1], true); }); }
    else if (type === "B") { [[1,1],[-1,1],[1,-1],[-1,-1]].forEach(function (d) { push(d[0], d[1]); }); }
    else if (type === "R") { [[1,0],[-1,0],[0,1],[0,-1]].forEach(function (d) { push(d[0], d[1]); }); }
    else if (type === "Q") { [[1,0],[-1,0],[0,1],[0,-1],[1,1],[-1,1],[1,-1],[-1,-1]].forEach(function (d) { push(d[0], d[1]); }); }
    else if (type === "K") { [[1,0],[-1,0],[0,1],[0,-1],[1,1],[-1,1],[1,-1],[-1,-1]].forEach(function (d) { push(d[0], d[1], true); }); }
    return moves;
  }

  function applySan(state, san) {
    san = san.replace(/[+#!?]/g, "").trim();
    var squares = state.squares;
    var moveRecord = null;
    if (san === "O-O" || san === "0-0") {
      var rank = state.turn === "w" ? "1" : "8";
      moveRecord = { from: "e" + rank, to: "g" + rank };
      squares["g" + rank] = squares["e" + rank];
      delete squares["e" + rank];
      squares["f" + rank] = squares["h" + rank];
      delete squares["h" + rank];
    } else if (san === "O-O-O" || san === "0-0-0") {
      var rank2 = state.turn === "w" ? "1" : "8";
      moveRecord = { from: "e" + rank2, to: "c" + rank2 };
      squares["c" + rank2] = squares["e" + rank2];
      delete squares["e" + rank2];
      squares["d" + rank2] = squares["a" + rank2];
      delete squares["a" + rank2];
    } else {
      var m = san.match(/^([NBRQK])?([a-h])?([1-8])?(x)?([a-h][1-8])(=?([QRBN]))?/);
      if (!m) return null;
      var type = m[1] || "P";
      var disFile = m[2], disRank = m[3];
      var isCapture = !!m[4];
      var target = m[5];
      var promo = m[7] ? (state.turn === "w" ? m[7] : m[7].toLowerCase()) : null;
      var color = state.turn;
      var from = null;
      if (type === "P") {
        var tf = target[0], tr = parseInt(target[1], 10);
        var dir = color === "w" ? 1 : -1;
        if (isCapture) {
          var cf = FILES.indexOf(tf) - 1;
          from = FILES[cf] + (tr - dir);
          if (!squares[from] || colorOf(squares[from]) !== color) {
            cf = FILES.indexOf(tf) + 1;
            from = FILES[cf] + (tr - dir);
          }
        } else {
          var oneBelow = tf + (tr - dir);
          if (squares[oneBelow] && colorOf(squares[oneBelow]) === color) {
            from = oneBelow;
          } else {
            from = tf + (tr - 2 * dir);
          }
        }
      } else {
        var candidates = [];
        Object.keys(squares).forEach(function (sq) {
          var piece = squares[sq];
          if (piece.toUpperCase() !== type || colorOf(piece) !== color) return;
          if (disFile && sq[0] !== disFile) return;
          if (disRank && sq[1] !== disRank) return;
          if (vectorMoves(state, sq, piece).indexOf(target) === -1) return;
          candidates.push(sq);
        });
        if (candidates.length === 0) return null;
        if (candidates.length > 1) {
          /* disambiguate: pick the only candidate whose move doesn't leave
             own king attacked — simplified: prefer file/rank hints already
             applied; fall back to the first candidate (real-game data is
             unambiguous after hints) */
          candidates.sort();
        }
        from = candidates[0];
      }
      if (!from || !squares[from]) return null;
      var moved = squares[from];
      delete squares[from];
      /* en passant capture: pawn moves diagonally to empty square */
      if (type === "P" && isCapture && !squares[target]) {
        var capSq = target[0] + from[1];
        delete squares[capSq];
      }
      squares[target] = promo || moved;
      moveRecord = { from: from, to: target, capture: isCapture, promotion: promo };
    }
    state.ep = null;
    state.turn = otherColor(state.turn);
    return moveRecord;
  }

  /* ------------------------- rendering ------------------------- */

  function Board(container, options) {
    options = options || {};
    this.container = typeof container === "string" ? document.querySelector(container) : container;
    this.fen = options.fen || "rnbqkbnr/pppppppp/8/8/8/8/8/RNBQKBNR w KQkq - 0 1";
    this.state = stateFromFen(this.fen);
    this.flip = options.flip || false;
    this.lastMove = null;
    this.onUserMove = options.onUserMove || null;
    this.interactive = options.interactive || false;
    this.coords = options.coords !== false;
    this.selected = null;
    this.uciSeq = [];
    this.build();
  }

  Board.prototype.build = function () {
    var self = this;
    this.container.classList.add("board");
    this.squares = {};
    var order = [];
    for (var r = 1; r <= 8; r++) { for (var f = 0; f < 8; f++) { order.push(FILES[f] + r); } }
    if (this.flip) order.reverse();
    order.forEach(function (sq) {
      var el = document.createElement("div");
      var isLight = (FILES.indexOf(sq[0]) + parseInt(sq[1], 10)) % 2 === 0;
      el.className = "sq " + (isLight ? "light" : "dark");
      el.dataset.sq = sq;
      el.addEventListener("click", function () { self.onSquare(sq); });
      self.container.appendChild(el);
      self.squares[sq] = el;
    });
    this.draw();
  };

  Board.prototype.draw = function () {
    var squares = this.state.squares;
    var self = this;
    Object.keys(this.squares).forEach(function (sq) {
      var el = self.squares[sq];
      el.className = el.className.replace(/ ?(last-move|sel|check)/g, "");
      el.innerHTML = "";
      if (self.lastMove && (sq === self.lastMove.from || sq === self.lastMove.to)) {
        el.classList.add("last-move");
      }
      if (self.selected === sq) el.classList.add("sel");
      var piece = squares[sq];
      if (piece) {
        var img = document.createElement("div");
        img.className = "piece" + (self.interactive ? "" : " no-move");
        img.style.backgroundImage = "url(" + PIECE_IMG(piece) + ")";
        if (self.interactive && colorOf(piece) === self.state.turn) {
          img.style.cursor = "pointer";
        }
        el.appendChild(img);
      }
      if (self.coords && sq[0] === (self.flip ? "h" : "a")) {
        var rank = document.createElement("span");
        rank.className = "sq-coord rank";
        rank.textContent = sq[1];
        el.appendChild(rank);
      }
      if (self.coords && sq[1] === (self.flip ? "8" : "1")) {
        var file = document.createElement("span");
        file.className = "sq-coord";
        file.textContent = sq[0];
        el.appendChild(file);
      }
    });
  };

  Board.prototype.onSquare = function (sq) {
    if (!this.interactive || !this.onUserMove) return;
    var piece = this.state.squares[sq];
    if (this.selected && this.selected !== sq) {
      var from = this.selected;
      this.selected = null;
      this.onUserMove(from, sq);
      this.draw();
      return;
    }
    if (piece && colorOf(piece) === this.state.turn) {
      this.selected = (this.selected === sq) ? null : sq;
      this.draw();
    } else {
      this.selected = null;
      this.draw();
    }
  };

  Board.prototype.setPosition = function (fen, lastMove) {
    this.state = stateFromFen(fen);
    this.lastMove = lastMove || null;
    this.selected = null;
    this.draw();
  };

  Board.prototype.applyMove = function (from, to, promo) {
    var piece = this.state.squares[from];
    if (!piece) return;
    if (piece.toUpperCase() === "P" && !this.state.squares[to] &&
        from[0] !== to[0]) {
      delete this.state.squares[to[0] + from[1]];
    }
    if (piece.toUpperCase() === "K" && Math.abs(FILES.indexOf(to[0]) - FILES.indexOf(from[0])) === 2) {
      var rank = from[1];
      if (to[0] === "g") {
        this.state.squares["f" + rank] = this.state.squares["h" + rank];
        delete this.state.squares["h" + rank];
      } else {
        this.state.squares["d" + rank] = this.state.squares["a" + rank];
        delete this.state.squares["a" + rank];
      }
    }
    delete this.state.squares[from];
    this.state.squares[to] = promo || piece;
    if (piece.toUpperCase() === "P" && Math.abs(parseInt(to[1], 10) - parseInt(from[1], 10)) === 2) {
      this.state.ep = from[0] + (parseInt(from[1], 10) + (colorOf(piece) === "w" ? 1 : -1));
    } else {
      this.state.ep = null;
    }
    this.state.turn = otherColor(this.state.turn);
    this.lastMove = { from: from, to: to };
    this.selected = null;
    this.draw();
    return this;
  };

  Board.prototype.replay = function (sanMoves, upto) {
    /* reset to the initial position, then apply sanMoves[0..upto) */
    this.state = stateFromFen(this.fen);
    this.lastMove = null;
    var n = (upto === undefined) ? sanMoves.length : upto;
    for (var i = 0; i < n; i++) {
      var rec = applySan(this.state, sanMoves[i]);
      if (!rec) break;
      this.lastMove = rec;
    }
    this.draw();
  };

  window.ChessBoard = Board;
  window.parseFen = parseFen;
  window.applySan = applySan;
})();

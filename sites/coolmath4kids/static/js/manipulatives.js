/* Coolmath4Kids mirror — interactive manipulatives (Ten Frame, Base Ten
   Blocks, Number Line, Pattern Blocks). Simplified local versions of the
   upstream canvas tools, using the same toolbar concepts and real counter
   artwork. */
(function () {
  'use strict';

  // ---------------- Ten Frame ----------------
  var tfGrid = document.getElementById('tenFrameGrid');
  if (tfGrid) {
    var toolbar = document.getElementById('tenFrameToolbar');
    var status = document.getElementById('tenFrameStatus');
    var frameSize = 10;
    var counter = 'monsters-blue';
    var counters = {
      'monsters-blue': '/static/images/manipulatives/counters/counter-monsters-blue.png',
      'monsters-orange': '/static/images/manipulatives/counters/counter-monsters-orange.png',
      'apples-blue': '/static/images/manipulatives/counters/counter-apple-blue.png',
      'stars-orange': '/static/images/manipulatives/counters/counter-star-orange.png',
      'cats-blue': '/static/images/manipulatives/counters/counter-cat-blue.png',
      'cupcakes-orange': '/static/images/manipulatives/counters/counter-cupcake-orange.png'
    };

    function renderFrame() {
      tfGrid.innerHTML = '';
      var rows = frameSize <= 5 ? 1 : 2;
      var cols = frameSize <= 5 ? 5 : frameSize / rows;
      // minmax(0, 74px) keeps the desktop cell size while letting tracks
      // shrink on narrow screens instead of overflowing the workspace.
      tfGrid.style.gridTemplateColumns = 'repeat(' + cols + ', minmax(0, 74px))';
      for (var i = 0; i < frameSize; i++) {
        var cell = document.createElement('div');
        cell.className = 'tf-cell';
        cell.dataset.index = i;
        var img = document.createElement('img');
        img.src = counters[counter];
        img.alt = 'counter';
        cell.appendChild(img);
        cell.addEventListener('click', function () {
          this.classList.toggle('filled');
          updateStatus();
        });
        tfGrid.appendChild(cell);
      }
      updateStatus();
    }

    function updateStatus() {
      var filled = tfGrid.querySelectorAll('.tf-cell.filled').length;
      status.textContent = filled + ' of ' + frameSize + ' cells filled — click cells to add or remove counters.';
    }

    toolbar.querySelectorAll('[data-frame]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        toolbar.querySelectorAll('[data-frame]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        frameSize = parseInt(btn.getAttribute('data-frame'), 10);
        renderFrame();
      });
    });
    toolbar.querySelectorAll('.counter-pick').forEach(function (btn) {
      btn.addEventListener('click', function () {
        toolbar.querySelectorAll('.counter-pick').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        counter = btn.getAttribute('data-counter');
        renderFrame();
      });
    });
    document.getElementById('startOverBtn').addEventListener('click', renderFrame);
    renderFrame();
  }

  // ---------------- Base Ten Blocks ----------------
  var btGrid = document.getElementById('baseTenGrid');
  if (btGrid) {
    var btToolbar = document.getElementById('baseTenToolbar');
    var btStatus = document.getElementById('baseTenStatus');
    var block = 'units';
    var totalUnits = 0;

    function unitValue() { return block === 'units' ? 1 : block === 'rods' ? 10 : 100; }
    function blockColor() { return block === 'units' ? '#71b8ff' : block === 'rods' ? '#ffbe00' : '#ea6452'; }
    function blockSize() { return block === 'units' ? 18 : block === 'rods' ? [18, 90] : [90, 90]; }

    btToolbar.querySelectorAll('[data-block]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        btToolbar.querySelectorAll('[data-block]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        block = btn.getAttribute('data-block');
        btStatus.textContent = 'Selected: ' + btn.textContent.trim() + ' (worth ' + unitValue() + '). Click the workspace to place it.';
      });
    });

    btGrid.style.position = 'relative';
    btGrid.style.minHeight = '320px';
    btGrid.addEventListener('click', function (e) {
      var rect = btGrid.getBoundingClientRect();
      var piece = document.createElement('div');
      var size = blockSize();
      piece.style.position = 'absolute';
      piece.style.left = (e.clientX - rect.left - size[0] / 2) + 'px';
      piece.style.top = (e.clientY - rect.top - (size[1] / 2)) + 'px';
      piece.style.width = size[0] + 'px';
      piece.style.height = size[1] + 'px';
      piece.style.background = blockColor();
      piece.style.borderRadius = '4px';
      piece.style.opacity = '0.9';
      piece.dataset.value = String(unitValue());
      btGrid.appendChild(piece);
      totalUnits += unitValue();
      btStatus.textContent = 'Total value on the board: ' + totalUnits + '.';
    });

    document.getElementById('startOverBtn').addEventListener('click', function () {
      btGrid.innerHTML = '';
      totalUnits = 0;
      btStatus.textContent = 'Board cleared. Click the workspace to place the selected block.';
    });
  }

  // ---------------- Number Line ----------------
  var nlCanvas = document.getElementById('numberLineCanvas');
  if (nlCanvas) {
    var nlToolbar = document.getElementById('numberLineToolbar');
    var nlStatus = document.getElementById('numberLineStatus');
    var jump = 1;
    var hops = [];
    var position = 0;

    function renderLine() {
      nlCanvas.innerHTML = '';
      var track = document.createElement('div');
      track.style.position = 'relative';
      track.style.height = '70px';
      track.style.borderBottom = '4px solid #2c6792';
      track.style.margin = '60px 10px 30px';
      for (var i = 0; i <= 20; i++) {
        var tick = document.createElement('div');
        tick.style.position = 'absolute';
        tick.style.left = (i * (100 / 20)) + '%';
        tick.style.bottom = '0';
        tick.style.width = '2px';
        tick.style.height = (i % 5 === 0 ? '18px' : '10px');
        tick.style.background = '#2c6792';
        track.appendChild(tick);
        var label = document.createElement('div');
        label.style.position = 'absolute';
        label.style.left = (i * (100 / 20)) + '%';
        label.style.bottom = '-26px';
        label.style.transform = 'translateX(-50%)';
        label.style.fontSize = '13px';
        label.style.fontWeight = '700';
        label.style.color = '#1d324a';
        label.textContent = i;
        track.appendChild(label);
      }
      var marker = document.createElement('div');
      marker.style.position = 'absolute';
      marker.style.left = (position * (100 / 20)) + '%';
      marker.style.bottom = '6px';
      marker.style.transform = 'translateX(-50%)';
      marker.style.width = '20px';
      marker.style.height = '20px';
      marker.style.borderRadius = '50%';
      marker.style.background = '#ff7220';
      marker.style.zIndex = '2';
      track.appendChild(marker);
      hops.forEach(function (hop) {
        var arc = document.createElement('div');
        arc.style.position = 'absolute';
        arc.style.left = (hop.from * (100 / 20)) + '%';
        arc.style.bottom = '10px';
        arc.style.width = (hop.size * (100 / 20)) + '%';
        arc.style.height = (18 + hop.size * 3) + 'px';
        arc.style.borderTop = '3px dashed #24af0e';
        arc.style.borderRadius = '50% 50% 0 0';
        arc.style.opacity = '0.8';
        track.appendChild(arc);
      });
      nlCanvas.appendChild(track);
    }

    nlToolbar.querySelectorAll('[data-jump]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        nlToolbar.querySelectorAll('[data-jump]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        jump = parseInt(btn.getAttribute('data-jump'), 10);
        nlStatus.textContent = 'Jump size: ' + jump + '. Click a number on the line to hop there.';
      });
    });

    nlCanvas.addEventListener('click', function (e) {
      var rect = nlCanvas.getBoundingClientRect();
      var pct = (e.clientX - rect.left - 10) / (rect.width - 20);
      var target = Math.max(0, Math.min(20, Math.round(pct * 20)));
      var from = position;
      var delta = Math.abs(target - from);
      if (delta === 0) return;
      var nHops = Math.ceil(delta / jump);
      hops.push({ from: from, size: target - from });
      position = target;
      renderLine();
      nlStatus.textContent = 'Hopped from ' + from + ' to ' + target + ' (' + nHops + ' jump' + (nHops > 1 ? 's' : '') + ' of ' + jump + '). You are at ' + position + '.';
    });

    document.getElementById('startOverBtn').addEventListener('click', function () {
      hops = [];
      position = 0;
      renderLine();
      nlStatus.textContent = 'Back to 0. Choose a jump size and click the line to hop.';
    });
    renderLine();
  }

  // ---------------- Pattern Blocks ----------------
  var pCanvas = document.getElementById('patternCanvas');
  if (pCanvas) {
    var pToolbar = document.getElementById('patternToolbar');
    var pStatus = document.getElementById('patternStatus');
    var shape = 'triangle';
    var colors = { triangle: '#ea6452', square: '#ffbe00', rhombus: '#2c6792', trapezoid: '#24af0e', hexagon: '#6c3eee' };
    var placed = 0;

    pCanvas.style.position = 'relative';
    pCanvas.style.minHeight = '320px';
    pToolbar.querySelectorAll('[data-shape]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        pToolbar.querySelectorAll('[data-shape]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        shape = btn.getAttribute('data-shape');
        pStatus.textContent = 'Selected shape: ' + shape + '. Click the board to place it.';
      });
    });

    pCanvas.addEventListener('click', function (e) {
      var rect = pCanvas.getBoundingClientRect();
      var piece = document.createElement('div');
      piece.style.position = 'absolute';
      piece.style.left = (e.clientX - rect.left) + 'px';
      piece.style.top = (e.clientY - rect.top) + 'px';
      piece.style.transform = 'translate(-50%, -50%)';
      var size = shape === 'hexagon' ? 84 : shape === 'trapezoid' ? 74 : shape === 'square' ? 52 : 58;
      piece.style.width = size + 'px';
      piece.style.height = (shape === 'square' ? 52 : 58) + 'px';
      piece.style.background = colors[shape];
      piece.style.opacity = '0.85';
      if (shape === 'triangle') {
        piece.style.clipPath = 'polygon(50% 0, 0 100%, 100% 100%)';
      } else if (shape === 'rhombus') {
        piece.style.clipPath = 'polygon(50% 0, 100% 50%, 50% 100%, 0 50%)';
      } else if (shape === 'trapezoid') {
        piece.style.clipPath = 'polygon(25% 0, 75% 0, 100% 100%, 0 100%)';
      } else if (shape === 'hexagon') {
        piece.style.clipPath = 'polygon(25% 0, 75% 0, 100% 50%, 75% 100%, 25% 100%, 0 50%)';
      } else {
        piece.style.borderRadius = '2px';
      }
      pCanvas.appendChild(piece);
      placed += 1;
      pStatus.textContent = placed + ' shape' + (placed > 1 ? 's' : '') + ' placed. Keep going — try tiling hexagons with trapezoids and triangles!';
    });

    document.getElementById('startOverBtn').addEventListener('click', function () {
      pCanvas.innerHTML = '';
      placed = 0;
      pStatus.textContent = 'Board cleared. Choose a shape and click the board to place it.';
    });
  }
})();

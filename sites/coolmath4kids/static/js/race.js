/* Coolmath4Kids mirror — math race game engine.
   Reproduces the Arcademics-style "answer facts to advance your racer" loop
   locally (the upstream games are third-party embeds). 10 facts per race;
   answering correctly advances your racer; opponents advance on a timer. */
(function () {
  'use strict';
  var stage = document.getElementById('raceStage');
  if (!stage) return;

  var operation = stage.getAttribute('data-operation'); // addition/subtraction/multiplication/division/fractions/counting
  var contents = stage.getAttribute('data-contents') || '';
  var overlay = document.getElementById('raceOverlay');
  var overlayTitle = overlay.querySelector('h3');
  var overlaySub = document.getElementById('raceSubtitle');
  var startBtn = document.getElementById('raceStart');
  var questionBox = document.getElementById('raceQuestion');
  var rqText = document.getElementById('rqText');
  var rqAnswer = document.getElementById('rqAnswer');
  var rqSubmit = document.getElementById('rqSubmit');
  var rqFeedback = document.getElementById('rqFeedback');
  var runnerYou = document.getElementById('runnerYou');
  var aiRunners = [
    stage.querySelector('.lane-runner.ai1'),
    stage.querySelector('.lane-runner.ai2'),
    stage.querySelector('.lane-runner.ai3')
  ];
  var TOTAL = 10;
  var facts = [];
  var current = 0;
  var correct = 0;
  var aiProgress = [0, 0, 0];
  var aiTimers = [];
  var raceStart = 0;
  var finished = false;
  var locked = false;

  function contentsMax() {
    var m = /to (\d+)/.exec(contents);
    if (m) { return parseInt(m[1], 10); }
    return 10;
  }

  function randomInt(lo, hi) { return Math.floor(Math.random() * (hi - lo + 1)) + lo; }

  function makeFact() {
    var top = contentsMax();
    if (operation === 'addition') {
      var a = randomInt(0, top), b = randomInt(0, top);
      return { text: a + ' + ' + b, answer: a + b };
    }
    if (operation === 'subtraction') {
      var a2 = randomInt(0, top), b2 = randomInt(0, top);
      if (b2 > a2) { var t = a2; a2 = b2; b2 = t; }
      return { text: a2 + ' − ' + b2, answer: a2 - b2 };
    }
    if (operation === 'multiplication') {
      var a3 = randomInt(1, top), b3 = randomInt(1, top);
      return { text: a3 + ' × ' + b3, answer: a3 * b3 };
    }
    if (operation === 'division') {
      var q = randomInt(1, 10), d = randomInt(1, top);
      return { text: (q * d) + ' ÷ ' + d, answer: q };
    }
    if (operation === 'fractions') {
      // compare fractions: which is bigger?
      var n1 = randomInt(1, 8), d1 = randomInt(2, 9);
      var n2 = randomInt(1, 8), d2 = randomInt(2, 9);
      var v1 = n1 / d1, v2 = n2 / d2;
      var bigger = v1 >= v2 ? 1 : 2;
      return { text: n1 + '/' + d1 + '  or  ' + n2 + '/' + d2 + ' ? (1 or 2)', answer: bigger };
    }
    // counting (123 Tracing): count the dots
    var count = randomInt(1, 12);
    var dots = new Array(count + 1).join('●');
    return { text: 'How many dots?  ' + dots, answer: count };
  }

  function buildFacts() {
    facts = [];
    for (var i = 0; i < TOTAL; i++) { facts.push(makeFact()); }
  }

  function setProgress(el, frac) {
    var track = el.parentElement;
    var pct = Math.max(0, Math.min(1, frac)) * (track.clientWidth - el.offsetWidth);
    el.style.marginLeft = pct + 'px';
  }

  function startRace() {
    buildFacts();
    current = 0;
    correct = 0;
    finished = false;
    raceStart = Date.now();
    overlay.style.display = 'none';
    questionBox.hidden = false;
    setProgress(runnerYou, 0);
    aiProgress = [0, 0, 0];
    aiRunners.forEach(function (r) { setProgress(r, 0); });
    showQuestion();
    startAI();
  }

  function startAI() {
    var speed = 0.008 + Math.random() * 0.004; // progress per tick (100ms)
    aiTimers.forEach(clearInterval);
    aiTimers = aiRunners.map(function (runner, idx) {
      var s = speed * (0.9 + idx * 0.06);
      return setInterval(function () {
        if (finished) return;
        aiProgress[idx] = Math.min(1, aiProgress[idx] + s);
        setProgress(runner, aiProgress[idx]);
      }, 100);
    });
  }

  function showQuestion() {
    locked = false;
    rqFeedback.textContent = '';
    rqFeedback.className = 'rq-feedback';
    rqText.textContent = facts[current].text + ' = ?';
    rqAnswer.value = '';
    rqAnswer.focus();
  }

  function submitAnswer() {
    if (finished || locked) return;
    var fact = facts[current];
    var raw = rqAnswer.value.trim();
    if (raw === '') { rqAnswer.focus(); return; }
    var val = parseInt(raw, 10);
    locked = true;
    if (val === fact.answer) {
      correct += 1;
      rqFeedback.textContent = '✓ Correct!';
      rqFeedback.className = 'rq-feedback right';
      setProgress(runnerYou, (current + 1) / TOTAL);
    } else {
      rqFeedback.textContent = '✗ Oops! The answer was ' + fact.answer + '.';
      rqFeedback.className = 'rq-feedback wrong';
    }
    current += 1;
    if (current >= TOTAL) {
      setTimeout(finishRace, 350);
    } else {
      setTimeout(showQuestion, 650);
    }
  }

  function finishRace() {
    finished = true;
    aiTimers.forEach(clearInterval);
    var duration = Math.round((Date.now() - raceStart) / 1000 * 10) / 10;
    var myProgress = correct / TOTAL;
    var position = 1;
    aiProgress.forEach(function (p) { if (p >= myProgress) position += 1; });
    questionBox.hidden = true;
    overlay.style.display = 'flex';
    overlayTitle.textContent = position === 1 ? 'You Won the Race!' : 'You Finished ' + position + (position === 2 ? 'nd' : position === 3 ? 'rd' : 'th') + '!';
    overlaySub.textContent = 'You answered ' + correct + ' of ' + TOTAL + ' facts correctly in ' + duration + ' seconds.';
    startBtn.textContent = 'Race Again';

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/games/' + stage.getAttribute('data-game') + '/result', true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.send('facts_total=' + TOTAL + '&facts_correct=' + correct + '&position=' + position + '&duration=' + duration);
  }

  startBtn.addEventListener('click', startRace);
  rqSubmit.addEventListener('click', submitAnswer);
  rqAnswer.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); submitAnswer(); }
  });
})();

/* Ticker autocomplete for the header search box.
   Progressive enhancement only: the form posts to /search either way, so an
   agent that never runs JS still has a working search path. */
(function () {
  var input = document.getElementById('gf-q');
  var list = document.getElementById('gf-suggest');
  if (!input || !list) return;

  var timer = null;
  var lastQuery = '';

  function close() {
    list.hidden = true;
    list.innerHTML = '';
    input.setAttribute('aria-expanded', 'false');
  }

  function render(items) {
    if (!items.length) { close(); return; }
    list.innerHTML = items.map(function (it) {
      var chg = it.change_pct === null ? '' :
        '<span class="chg ' + (it.change_pct >= 0 ? 'up' : 'down') + '">' +
        (it.change_pct >= 0 ? '+' : '') + it.change_pct.toFixed(2) + '%</span>';
      return '<li><a href="/quote/' + encodeURI(it.slug) + '">' +
             '<span class="s-tic">' + it.ticker + '</span>' +
             '<span class="s-name">' + it.name + '</span>' + chg + '</a></li>';
    }).join('');
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  }

  input.addEventListener('input', function () {
    var q = input.value.trim();
    if (q === lastQuery) return;
    lastQuery = q;
    clearTimeout(timer);
    if (q.length < 1) { close(); return; }
    timer = setTimeout(function () {
      fetch('/autocomplete?q=' + encodeURIComponent(q))
        .then(function (r) { return r.json(); })
        .then(render)
        .catch(close);
    }, 140);
  });

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') close();
  });

  document.addEventListener('click', function (e) {
    if (!list.contains(e.target) && e.target !== input) close();
  });
})();

/* Chart hover: crosshair, price/volume read-out and a timestamp chip.
   The chart itself is server-rendered SVG; this only adds the pointer layer,
   reading the same series the server used so the two can never disagree. */
(function () {
  var host = document.querySelector('.chart-host');
  if (!host) return;
  var svg = host.querySelector('.price-chart');
  var cross = host.querySelector('.crosshair');
  var readout = host.querySelector('.chart-readout');
  var stamp = host.querySelector('.chart-stamp');
  if (!svg || !cross) return;

  var S;
  try { S = JSON.parse(host.getAttribute('data-series')); } catch (e) { return; }
  if (!S || !S.values || S.values.length < 2) return;

  var vb = svg.viewBox.baseVal;
  var plotW = S.width - S.padL - S.padR;

  function fmtNum(v) {
    return v.toLocaleString('en-US', {minimumFractionDigits: S.digits,
                                      maximumFractionDigits: S.digits});
  }

  function fmtVol(v) {
    if (v >= 1e9) return (v / 1e9).toFixed(2) + 'B';
    if (v >= 1e6) return (v / 1e6).toFixed(2) + 'M';
    if (v >= 1e3) return (v / 1e3).toFixed(2) + 'K';
    return String(v);
  }

  function indexFromEvent(e) {
    var r = svg.getBoundingClientRect();
    var xUser = (e.clientX - r.left) / r.width * vb.width;
    var t = (xUser - S.padL) / plotW;
    var i = Math.round(t * (S.values.length - 1));
    return Math.max(0, Math.min(S.values.length - 1, i));
  }

  function show(e) {
    var i = indexFromEvent(e);
    var v = S.values[i];
    var x = S.padL + i * plotW / (S.values.length - 1);

    // recompute y with the same scale the server used
    var all = S.values.slice();
    if (S.baseline) all.push(S.baseline);
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all);
    var span = (hi - lo) || (Math.abs(hi) * 0.01 || 1);
    lo -= span * 0.10; hi += span * 0.10; span = hi - lo;
    var PRICE_BOT = 194, PLOT_TOP = 10;
    var y = PRICE_BOT - (v - lo) / span * (PRICE_BOT - PLOT_TOP);

    cross.removeAttribute('hidden');
    var line = cross.querySelector('.cross-line');
    line.setAttribute('x1', x); line.setAttribute('x2', x);
    var dot = cross.querySelector('.cross-dot');
    dot.setAttribute('cx', x); dot.setAttribute('cy', y);

    var pct = S.baseline ? ((v - S.baseline) / S.baseline * 100) : null;
    var cls = (pct === null || pct >= 0) ? 'up' : 'down';
    var html = '<span class="k">Price:</span><span class="v ' + cls + '">' +
               S.prefix + fmtNum(v) +
               (pct === null ? '' :
                 ' (' + (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%)') + '</span>';
    if (S.volumes && S.volumes[i] !== undefined) {
      html += '<span class="sep"></span><span class="k">Volume:</span>' +
              '<span class="v">' + fmtVol(S.volumes[i]) + '</span>';
    }
    readout.innerHTML = html;
    readout.removeAttribute('hidden');

    var r = svg.getBoundingClientRect();
    stamp.textContent = (S.dates[i] || '') + ' UTC-4 ' + (S.labels[i] || '');
    stamp.style.left = (x / vb.width * r.width) + 'px';
    stamp.removeAttribute('hidden');
  }

  function hide() {
    cross.setAttribute('hidden', '');
    readout.setAttribute('hidden', '');
    stamp.setAttribute('hidden', '');
  }

  svg.addEventListener('mousemove', show);
  svg.addEventListener('mouseleave', hide);
})();

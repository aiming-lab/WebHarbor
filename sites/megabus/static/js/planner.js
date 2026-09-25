/* Megabus mirror — journey planner widget behaviour:
   origin/destination autocomplete against the mirror's own JSON endpoints,
   passenger stepper, and navigation to the journey results page. */
(function () {
  'use strict';

  var state = { origins: null, dests: {}, originId: null, destId: null };

  function el(id) { return document.getElementById(id); }

  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(null, args); }, ms);
    };
  }

  function fetchJSON(url, cb) {
    fetch(url).then(function (r) { return r.json(); }).then(cb).catch(function () {});
  }

  function loadOrigins(cb) {
    if (state.origins) { cb(state.origins); return; }
    fetchJSON('/journey-planner/api/origin-cities', function (data) {
      state.origins = data.cities || [];
      cb(state.origins);
    });
  }

  function loadDests(originId, cb) {
    if (state.dests[originId]) { cb(state.dests[originId]); return; }
    fetchJSON('/journey-planner/api/destination-cities?originCityId=' + originId,
      function (data) {
        state.dests[originId] = data.cities || [];
        cb(state.dests[originId]);
      });
  }

  function attachAutocomplete(inputId, hiddenId, listGetter, onPick) {
    var input = el(inputId);
    if (!input) return;
    var box = document.createElement('div');
    box.className = 'autocomplete-list';
    box.style.display = 'none';
    input.parentNode.appendChild(box);
    var timer = null;

    function hide() {
      box.innerHTML = '';
      box.style.display = 'none';
    }

    function render(items) {
      box.innerHTML = '';
      if (!items.length) { hide(); return; }
      items.forEach(function (it, idx) {
        var d = document.createElement('div');
        d.className = 'opt' + (idx === 0 ? ' active' : '');
        d.textContent = it.name;
        d.setAttribute('data-id', it.id);
        d.addEventListener('mousedown', function (ev) {
          ev.preventDefault();
          choose(it);
        });
        box.appendChild(d);
      });
      box.style.display = 'block';
    }

    function choose(it) {
      input.value = it.name;
      el(hiddenId).value = it.id;
      hide();
      if (onPick) onPick(it);
    }

    input.addEventListener('input', debounce(function () {
      var q = input.value.trim().toLowerCase();
      el(hiddenId).value = '';
      if (q.length < 2) { hide(); return; }
      listGetter(function (items) {
        var hits = items.filter(function (c) {
          return c.name.toLowerCase().indexOf(q) !== -1;
        }).slice(0, 12);
        render(hits);
      });
    }, 180));

    input.addEventListener('blur', function () {
      setTimeout(hide, 150);
    });
  }

  function initStepper(minusId, plusId, inputId) {
    var minus = el(minusId), plus = el(plusId), input = el(inputId);
    if (!minus || !plus || !input) return;
    minus.addEventListener('click', function () {
      var v = parseInt(input.value || '1', 10);
      input.value = Math.max(1, v - 1);
    });
    plus.addEventListener('click', function () {
      var v = parseInt(input.value || '1', 10);
      input.value = Math.min(9, v + 1);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('journey-planner-form');
    if (form) {
      loadOrigins(function () {});
      attachAutocomplete('startingAt', 'originId', function (cb) {
        loadOrigins(function (items) { cb(items); });
      }, function (it) {
        state.originId = it.id;
        el('goingTo').value = '';
        el('destinationId').value = '';
      });
      attachAutocomplete('goingTo', 'destinationId', function (cb) {
        var oid = el('originId').value;
        if (!oid) { loadOrigins(function (items) { cb(items); }); return; }
        loadDests(oid, function (items) { cb(items); });
      });
      initStepper('totalPassengers_minus', 'totalPassengers_plus', 'totalPassengers');
      form.addEventListener('submit', function (ev) {
        ev.preventDefault();
        var oid = el('originId').value;
        var did = el('destinationId').value;
        var day = el('departureDateInput').value;
        var pax = parseInt(el('totalPassengers').value || '1', 10) || 1;
        if (!oid || !did) {
          var msg = el('planner-error');
          if (msg) {
            msg.textContent = 'Choose a leaving from and going to city from the suggestions.';
            msg.style.display = 'block';
          }
          return;
        }
        var url = '/journey-planner/journeys?originId=' + oid +
          '&destinationId=' + did +
          (day ? '&departureDate=' + day : '') +
          '&totalPassengers=' + pax;
        window.location.href = url;
      });
      var swap = el('swap-stops');
      if (swap) {
        swap.addEventListener('click', function () {
          var o = el('startingAt'), d = el('goingTo');
          var ov = o.value, dv = d.value;
          var oh = el('originId').value, dh = el('destinationId').value;
          o.value = dv; d.value = ov;
          el('originId').value = dh; el('destinationId').value = oh;
        });
      }
    }
  });
})();

/* Ryanair mirror — booking search widget (airport picker, datepicker,
   passenger counters). */
(function () {
  'use strict';
  var AIRPORTS = window.RY_AIRPORTS || [];
  var TODAY = new Date(window.RY_TODAY + 'T00:00:00');

  function el(id) { return document.getElementById(id); }
  function hide(name) { el(name).classList.add('hidden'); }
  function show(name) { el(name).classList.remove('hidden'); }

  // ---------------- airport picker -------------------------------------
  var byCountry = {};
  AIRPORTS.forEach(function (a) {
    (byCountry[a.country] = byCountry[a.country] || []).push(a);
  });
  var countries = Object.keys(byCountry).sort();

  function buildPicker(prefix, inputId, onPick) {
    var countryBox = el(prefix + '-countries');
    var listBox = el(prefix + '-list');
    var searchBox = el(prefix + '-search');
    var selectedCountry = null;

    function renderCountries() {
      countryBox.innerHTML = '';
      countries.forEach(function (c) {
        var div = document.createElement('div');
        div.className = 'country' + (c === selectedCountry ? ' country--selected' : '');
        div.textContent = c;
        div.addEventListener('click', function (e) {
          e.stopPropagation();
          selectedCountry = c;
          renderCountries(); renderList('');
        });
        countryBox.appendChild(div);
      });
    }
    function renderList(query) {
      listBox.innerHTML = '';
      var pool = AIRPORTS.filter(function (a) {
        var text = (a.name + ' ' + a.city + ' ' + a.code).toLowerCase();
        if (query && text.indexOf(query.toLowerCase()) === -1) return false;
        if (selectedCountry && a.country !== selectedCountry) return false;
        return true;
      });
      pool.sort(function (a, b) { return a.name < b.name ? -1 : 1; });
      pool.forEach(function (a) {
        var div = document.createElement('div');
        div.className = 'airport-item';
        div.setAttribute('data-ref', 'airport-item__name');
        div.setAttribute('data-id', a.code);
        div.innerHTML = a.name + '<span class="airport-item__code">' + a.code + '</span>';
        div.addEventListener('click', function () { onPick(a); hide(prefix + '-picker'); });
        listBox.appendChild(div);
      });
    }
    renderCountries(); renderList('');
    if (searchBox) searchBox.addEventListener('input', function () {
      renderList(searchBox.value);
    });
  }

  function pickOrigin(a) {
    el('origin-input').value = a.name;
    el('origin-iata').value = a.code;
  }
  function pickDest(a) {
    el('dest-input').value = a.name;
    el('dest-iata').value = a.code;
  }
  buildPicker('origin', 'origin-input', pickOrigin);
  buildPicker('dest', 'dest-input', pickDest);

  el('origin-input').addEventListener('click', function () { show('origin-picker'); hide('dest-picker'); hide('datepicker'); hide('pax-selector'); });
  el('dest-input').addEventListener('click', function () { show('dest-picker'); hide('origin-picker'); hide('datepicker'); hide('pax-selector'); });

  el('swap').addEventListener('click', function () {
    var oName = el('origin-input').value, oCode = el('origin-iata').value;
    el('origin-input').value = el('dest-input').value;
    el('origin-iata').value = el('dest-iata').value;
    el('dest-input').value = oName;
    el('dest-iata').value = oCode;
  });

  // ---------------- datepicker -------------------------------------------
  var outDate = null, inDate = null;
  var monthOffset = 0;
  var DOW = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
  var MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  function fmt(d) {
    var days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
    var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return days[d.getDay()] + ', ' + d.getDate() + ' ' + months[d.getMonth()];
  }
  function iso(d) { return d.toISOString().slice(0, 10); }

  function renderCalendar() {
    var box = el('datepicker');
    var base = new Date(TODAY.getFullYear(), TODAY.getMonth() + monthOffset, 1);
    var html = '<div class="datepicker__tabs">' +
      '<button type="button" class="datepicker__tab datepicker__tab--active">Exact dates</button>' +
      '<button type="button" class="datepicker__tab">Flexible dates</button></div>' +
      '<div class="datepicker__calendars">';
    for (var m = 0; m < 2; m++) {
      var first = new Date(base.getFullYear(), base.getMonth() + m, 1);
      var monthName = MONTHS[first.getMonth()] + ' ' + first.getFullYear();
      html += '<div class="calendar"><div class="calendar__month-name">';
      if (m === 0) html += '<button type="button" class="calendar__arrow calendar__arrow--left' + (monthOffset === 0 ? ' calendar__arrow--disabled' : '') + '" id="cal-prev">‹</button>';
      html += monthName;
      if (m === 1) html += '<button type="button" class="calendar__arrow calendar__arrow--right" id="cal-next">›</button>';
      html += '</div><div class="calendar-body__row">';
      DOW.forEach(function (d) { html += '<div class="calendar-body__weekday">' + d + '</div>'; });
      html += '</div>';
      var lead = (first.getDay() + 6) % 7;
      var daysInMonth = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
      for (var i = 0; i < lead; i++) html += '<div class="calendar-body__cell calendar-body__cell--disabled"></div>';
      for (var day = 1; day <= daysInMonth; day++) {
        var d = new Date(first.getFullYear(), first.getMonth(), day);
        var classes = 'calendar-body__cell';
        if (d < TODAY) classes += ' calendar-body__cell--disabled';
        if (d.getDay() === 0 || d.getDay() === 6) classes += ' calendar-body__cell--weekend';
        if ((outDate && iso(d) === iso(outDate)) || (inDate && iso(d) === iso(inDate))) classes += ' calendar-body__cell--selected';
        html += '<div class="' + classes + '" data-id="' + iso(d) + '" data-type="day">' + day + '</div>';
      }
      html += '</div>';
    }
    html += '</div>';
    box.innerHTML = html;
    var prev = el('cal-prev');
    if (prev) prev.addEventListener('click', function (e) { e.stopPropagation(); if (monthOffset > 0) { monthOffset--; renderCalendar(); } });
    var next = el('cal-next');
    if (next) next.addEventListener('click', function (e) { e.stopPropagation(); monthOffset++; renderCalendar(); });
    box.querySelectorAll('.calendar-body__cell[data-type="day"]').forEach(function (cell) {
      cell.addEventListener('click', function (e) {
        e.stopPropagation();
        var d = new Date(cell.getAttribute('data-id') + 'T00:00:00');
        if (d < TODAY) return;
        if (!outDate || (inDate && outDate && inDate)) {
          outDate = d; inDate = null;
        } else if (d >= outDate && el('is-return').value !== 'false') {
          inDate = d;
        } else {
          outDate = d; inDate = null;
        }
        syncDates();
        renderCalendar();
        // Upstream behaviour: the calendar closes once the date selection is
        // complete (both legs of a return trip, or the single one-way date).
        if (outDate && (inDate || el('is-return').value === 'false')) hide('datepicker');
      });
    });
  }

  function syncDates() {
    el('date-out').value = outDate ? iso(outDate) : '';
    el('date-in').value = inDate ? iso(inDate) : '';
    var text = outDate ? 'Depart ' + fmt(outDate) : 'Choose date';
    if (inDate) text += ' | Return ' + fmt(inDate);
    el('dates-display').textContent = text;
  }

  el('dates-wrap').addEventListener('click', function () {
    show('datepicker'); hide('origin-picker'); hide('dest-picker'); hide('pax-selector');
    renderCalendar();
  });

  // ---------------- passengers -------------------------------------------
  el('pax-wrap').addEventListener('click', function () {
    show('pax-selector'); hide('origin-picker'); hide('dest-picker'); hide('datepicker');
  });
  document.querySelectorAll('.counter__btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var target = btn.getAttribute('data-target');
      var delta = parseInt(btn.getAttribute('data-delta'), 10);
      var input = document.querySelector('input[name=' + target + ']');
      var value = Math.max(target === 'adults' ? 1 : 0, parseInt(input.value, 10) + delta);
      input.value = value;
      el(target + '-count').textContent = value;
      var total = parseInt(el('adults').value, 10) + parseInt(document.querySelector('input[name=teens]').value, 10) +
                  parseInt(document.querySelector('input[name=children]').value, 10);
      el('pax-display').textContent = total + (total === 1 ? ' Adult' : ' Adults');
    });
  });

  // ---------------- trip type / promo ------------------------------------
  document.querySelectorAll('input[name=tripType]').forEach(function (radio) {
    radio.addEventListener('change', function () {
      el('is-return').value = radio.value === 'return' ? 'true' : 'false';
      if (radio.value !== 'return') { inDate = null; syncDates(); if (outDate) hide('datepicker'); }
    });
  });
  el('promo-toggle').addEventListener('click', function () {
    var row = el('promo-row');
    row.style.display = row.style.display === 'none' ? 'block' : 'none';
  });

  // ---------------- submit guard ------------------------------------------
  el('search-widget').addEventListener('submit', function (e) {
    if (!el('dest-iata').value || !el('date-out').value) {
      e.preventDefault();
      var caption = el('dates-display');
      if (!el('date-out').value) { show('datepicker'); renderCalendar(); }
      if (!el('dest-iata').value) show('dest-picker');
    }
  });

  syncDates();
})();

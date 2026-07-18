document.addEventListener("DOMContentLoaded", () => {
  const createBaseLayer = () => (
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19,
    })
  );

  document.querySelectorAll("[data-dismiss]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.closest(".flash");
      if (target) target.remove();
    });
  });

  document.querySelectorAll("[data-home-tabs]").forEach((tabRoot) => {
    const tabs = tabRoot.querySelectorAll("[data-home-tab]");
    const card = tabRoot.closest(".home-search-card");
    const panels = card?.querySelectorAll("[data-home-panel]") || [];
    const setActiveTab = (tab) => {
      tabs.forEach((item) => item.classList.toggle("is-active", item === tab));
      const key = tab.dataset.homeTab || "all";
      if (card) card.classList.toggle("is-ai-mode", key === "ai");
      panels.forEach((panel) => panel.classList.toggle("is-active", panel.dataset.homePanel === key));
      window.requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
    };
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => setActiveTab(tab));
    });
    const initial = tabRoot.querySelector("[data-home-tab].is-active") || tabs[0];
    if (initial) setActiveTab(initial);
  });

  document.querySelectorAll("[data-example-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      const panel = button.closest("[data-home-panel='ai']");
      const field = panel?.querySelector("textarea[name='q']");
      if (!field) return;
      field.value = button.dataset.examplePrompt || "";
      field.focus();
    });
  });

  document.querySelectorAll("[data-copy-code]").forEach((button) => {
    button.addEventListener("click", async () => {
      const code = button.getAttribute("data-copy-code") || "";
      try {
        await navigator.clipboard.writeText(code);
        button.textContent = "Copied";
        setTimeout(() => { button.textContent = "Copy"; }, 1200);
      } catch (_) {
        button.textContent = "Copy failed";
      }
    });
  });

  document.querySelectorAll("[data-rail]").forEach((rail) => {
    const track = rail.querySelector("[data-rail-track]");
    const prev = rail.querySelector('[data-rail-dir="prev"]');
    const next = rail.querySelector('[data-rail-dir="next"]');
    if (!track || !prev || !next) return;

    const syncRailButtons = () => {
      prev.disabled = track.scrollLeft <= 8;
      next.disabled = track.scrollLeft + track.clientWidth >= track.scrollWidth - 8;
    };
    const jump = () => {
      const firstCard = track.querySelector("[data-rail-card], .rail-card, .card");
      const gap = parseFloat(getComputedStyle(track).gap || 18);
      return firstCard ? firstCard.getBoundingClientRect().width + gap : track.clientWidth * 0.85;
    };

    prev.addEventListener("click", () => track.scrollBy({ left: -jump(), behavior: "smooth" }));
    next.addEventListener("click", () => track.scrollBy({ left: jump(), behavior: "smooth" }));
    track.addEventListener("scroll", syncRailButtons, { passive: true });
    window.addEventListener("resize", syncRailButtons);
    syncRailButtons();
  });

  document.querySelectorAll("[data-review-load-more]").forEach((button) => {
    const list = button.closest(".detail-review-list");
    const row = button.closest("[data-review-load-row]");
    if (!list) return;
    const revealBatch = () => {
      const hiddenCards = Array.from(list.querySelectorAll("[data-review-card].is-hidden-review"));
      hiddenCards.slice(0, 10).forEach((card) => card.classList.remove("is-hidden-review"));
      const remaining = list.querySelectorAll("[data-review-card].is-hidden-review").length;
      if (remaining <= 0) {
        if (row) row.classList.add("is-hidden");
      } else {
        button.textContent = `Show More Reviews (${remaining})`;
      }
    };
    const initialRemaining = list.querySelectorAll("[data-review-card].is-hidden-review").length;
    button.textContent = `Show More Reviews (${initialRemaining})`;
    button.addEventListener("click", revealBatch);
  });

  const updateCallout = (root, source) => {
    const callout = root.querySelector("[data-map-callout]");
    if (!callout || !source) return;
    const setText = (selector, value) => {
      const target = callout.querySelector(selector);
      if (target) target.textContent = value || "";
    };
    setText("[data-callout-label]", source.dataset.mapLabel);
    setText("[data-callout-name]", source.dataset.mapName);
    setText("[data-callout-location]", source.dataset.mapLocation);
    setText("[data-callout-distance]", source.dataset.mapDistance);
    setText("[data-callout-rating]", source.dataset.mapRating);
    setText("[data-callout-reviews]", source.dataset.mapReviews);
    setText("[data-callout-price]", source.dataset.mapPrice);
    const link = callout.querySelector("[data-callout-link]");
    if (link && source.dataset.mapLink) link.setAttribute("href", source.dataset.mapLink);
  };

  const activateMapItem = (root, id, panelKey) => {
    root.querySelectorAll("[data-map-target]").forEach((row) => {
      const match = row.dataset.mapTarget === id && row.dataset.panelKey === panelKey;
      row.classList.toggle("is-active", match);
    });
    let activeSource = null;
    root.querySelectorAll("[data-marker-id]").forEach((marker) => {
      const samePanel = !panelKey || marker.dataset.panelKey === panelKey;
      const match = samePanel && marker.dataset.markerId === id;
      marker.classList.toggle("is-active", match);
      if (match) activeSource = marker;
    });
    if (!activeSource) {
      activeSource = root.querySelector(`[data-map-target="${id}"][data-panel-key="${panelKey}"]`);
    }
    updateCallout(root, activeSource);
  };

  document.querySelectorAll("[data-map-root]").forEach((root) => {
    const tabs = root.querySelectorAll("[data-tab]");
    const panels = root.querySelectorAll("[data-panel]");
    const markers = root.querySelectorAll("[data-marker-id]");
    const setActivePanel = (panelKey) => {
      tabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === panelKey));
      panels.forEach((panel) => panel.classList.toggle("is-active", panel.dataset.panel === panelKey));
      markers.forEach((marker) => marker.classList.toggle("is-hidden", marker.dataset.panelKey !== panelKey));
      const firstVisible = root.querySelector(`[data-marker-id]:not(.is-hidden)`) || root.querySelector(`[data-map-target][data-panel-key="${panelKey}"]`);
      if (firstVisible) {
        const id = firstVisible.dataset.markerId || firstVisible.dataset.mapTarget;
        activateMapItem(root, id, panelKey);
      }
    };

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => setActivePanel(tab.dataset.tab));
    });

    root.querySelectorAll("[data-map-target]").forEach((row) => {
      row.addEventListener("mouseenter", () => activateMapItem(root, row.dataset.mapTarget, row.dataset.panelKey));
      row.addEventListener("focusin", () => activateMapItem(root, row.dataset.mapTarget, row.dataset.panelKey));
    });

    markers.forEach((marker) => {
      marker.addEventListener("click", () => activateMapItem(root, marker.dataset.markerId, marker.dataset.panelKey));
    });

    const firstTab = root.querySelector("[data-tab].is-active");
    if (firstTab) {
      setActivePanel(firstTab.dataset.tab);
    } else {
      const firstMarker = root.querySelector("[data-marker-id]");
      if (firstMarker) activateMapItem(root, firstMarker.dataset.markerId, firstMarker.dataset.panelKey);
    }
  });

  document.querySelectorAll("[data-leaflet-map]").forEach((node) => {
    if (typeof window.L === "undefined") return;
    const centerLat = parseFloat(node.dataset.mapLat || "39.5");
    const centerLng = parseFloat(node.dataset.mapLng || "-98.35");
    let markers = [];
    try {
      markers = JSON.parse(node.dataset.mapMarkers || "[]");
    } catch (_) {
      markers = [];
    }

    const map = L.map(node, { scrollWheelZoom: true }).setView([centerLat, centerLng], 9);
    createBaseLayer().addTo(map);

    const leafletMarkers = [];
    markers.forEach((marker) => {
      const leafletMarker = L.marker([marker.lat, marker.lng]).addTo(map);
      const popup = `
        <strong>${marker.name}</strong><br>
        <span>${marker.location}</span><br>
        <span>${marker.price_display}</span><br>
        <a href="${marker.href}">Open details</a>
      `;
      leafletMarker.bindPopup(popup);
      leafletMarkers.push(leafletMarker);
    });

    if (leafletMarkers.length > 1) {
      const group = L.featureGroup(leafletMarkers);
      map.fitBounds(group.getBounds().pad(0.22));
    } else if (leafletMarkers[0]) {
      leafletMarkers[0].openPopup();
    }
  });

  document.querySelectorAll("[data-booking-calendar]").forEach((calendar) => {
    const form = calendar.closest("form");
    const selectionField = form?.querySelector('select[name="selection"]');
    const startField = form?.querySelector("[data-calendar-start-field]") || form?.querySelector('[name="start_date"]');
    const endField = form?.querySelector("[data-calendar-end-field]") || form?.querySelector('[name="end_date"]');
    const startDisplay = form?.querySelector("[data-calendar-start-display]");
    const windowDisplay = form?.querySelector("[data-calendar-window-display]");
    const status = calendar.querySelector("[data-calendar-status]");
    const buttons = calendar.querySelectorAll("[data-calendar-date]");
    const defaultSpanDays = Math.max(parseInt(calendar.dataset.calendarSpan || "2", 10), 0);

    const parseIsoDate = (value) => {
      const [year, month, day] = (value || "").split("-").map(Number);
      if (!year || !month || !day) return null;
      return new Date(year, month - 1, day);
    };

    const toIsoDate = (value) => {
      const year = value.getFullYear();
      const month = `${value.getMonth() + 1}`.padStart(2, "0");
      const day = `${value.getDate()}`.padStart(2, "0");
      return `${year}-${month}-${day}`;
    };

    const addDays = (value, days) => {
      const next = new Date(value);
      next.setDate(next.getDate() + days);
      return next;
    };

    const diffDays = (startDate, endDate) => {
      const oneDay = 24 * 60 * 60 * 1000;
      return Math.round((endDate - startDate) / oneDay);
    };

    const sameDay = (left, right) => (
      Boolean(left) &&
      Boolean(right) &&
      left.getFullYear() === right.getFullYear() &&
      left.getMonth() === right.getMonth() &&
      left.getDate() === right.getDate()
    );

    const shortFormatter = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" });
    const longFormatter = new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric" });

    const selectedOption = () => selectionField?.selectedOptions?.[0] || null;

    const selectedOptionEndDate = () => {
      const explicitEnd = selectedOption()?.dataset.endDate;
      return explicitEnd ? parseIsoDate(explicitEnd) : null;
    };

    const getSpanDays = () => {
      const optionSpan = parseInt(selectedOption()?.dataset.spanDays || "", 10);
      if (Number.isFinite(optionSpan) && optionSpan >= 0) {
        return optionSpan;
      }
      if (endField?.type === "date" && startField?.value && endField.value) {
        const typedStart = parseIsoDate(startField.value);
        const typedEnd = parseIsoDate(endField.value);
        if (typedStart && typedEnd) {
          const typedSpan = diffDays(typedStart, typedEnd);
          if (typedSpan > 0) return typedSpan;
        }
      }
      return defaultSpanDays;
    };

    const windowLabel = (startDate, endDate) => {
      const spanDays = diffDays(startDate, endDate);
      if (spanDays <= 0) return shortFormatter.format(startDate);
      if (
        startDate.getFullYear() === endDate.getFullYear() &&
        startDate.getMonth() === endDate.getMonth()
      ) {
        return `${shortFormatter.format(startDate)} - ${endDate.getDate()}`;
      }
      return `${shortFormatter.format(startDate)} - ${shortFormatter.format(endDate)}`;
    };

    const updateButtonState = (selectedStart, selectedEnd) => {
      buttons.forEach((item) => {
        const itemDate = parseIsoDate(item.dataset.calendarDate);
        const isSelected = sameDay(itemDate, selectedStart);
        const isRangeEnd = !isSelected && sameDay(itemDate, selectedEnd);
        const isInRange = Boolean(
          itemDate &&
          selectedStart &&
          selectedEnd &&
          itemDate > selectedStart &&
          itemDate < selectedEnd
        );
        item.classList.toggle("is-selected", isSelected);
        item.classList.toggle("is-range-end", isRangeEnd);
        item.classList.toggle("is-in-range", isInRange);
      });
    };

    const applySelection = (selectedStart, selectedEnd, fallbackLabel = "") => {
      if (!selectedStart) return;
      const optionEnd = selectedOptionEndDate();
      const normalizedEnd = optionEnd || (
        selectedEnd && selectedEnd > selectedStart
          ? selectedEnd
          : addDays(selectedStart, Math.max(getSpanDays(), 0))
      );
      updateButtonState(selectedStart, normalizedEnd);
      if (startField) startField.value = toIsoDate(selectedStart);
      if (startDisplay) startDisplay.value = longFormatter.format(selectedStart);
      if (endField) {
        endField.value = toIsoDate(normalizedEnd);
      }
      if (windowDisplay) {
        windowDisplay.value = windowLabel(selectedStart, normalizedEnd);
      }
      if (status) {
        if (diffDays(selectedStart, normalizedEnd) > 0) {
          status.textContent = `${windowLabel(selectedStart, normalizedEnd)} selected`;
        } else {
          status.textContent = `${fallbackLabel || longFormatter.format(selectedStart)} selected`;
        }
      }
    };

    const selectDate = (button) => {
      const selectedStart = parseIsoDate(button.dataset.calendarDate);
      if (!selectedStart) return;
      applySelection(
        selectedStart,
        addDays(selectedStart, getSpanDays()),
        button.dataset.calendarLabel || longFormatter.format(selectedStart),
      );
    };

    const syncFromFields = () => {
      const selectedStart = parseIsoDate(startField?.value);
      if (!selectedStart) return;
      const selectedEnd = endField?.type === "date"
        ? parseIsoDate(endField.value) || addDays(selectedStart, getSpanDays())
        : addDays(selectedStart, getSpanDays());
      applySelection(selectedStart, selectedEnd, longFormatter.format(selectedStart));
    };

    buttons.forEach((button) => {
      button.addEventListener("click", () => selectDate(button));
    });
    if (startField?.type === "date") {
      startField.addEventListener("change", syncFromFields);
    }
    if (endField?.type === "date") {
      endField.addEventListener("change", syncFromFields);
    }
    if (selectionField) {
      selectionField.addEventListener("change", syncFromFields);
    }
    const initial = calendar.querySelector("[data-calendar-date].is-selected");
    if (initial) {
      selectDate(initial);
    } else {
      syncFromFields();
    }
  });

  document.querySelectorAll("[data-layout-shell]").forEach((shell) => {
    const buttons = document.querySelectorAll("[data-layout-mode]");
    const setMode = (mode) => {
      shell.dataset.layout = mode;
      buttons.forEach((button) => button.classList.toggle("is-active", button.dataset.layoutMode === mode));
    };
    buttons.forEach((button) => button.addEventListener("click", () => setMode(button.dataset.layoutMode)));
    setMode(shell.dataset.layout || "split");
  });
});

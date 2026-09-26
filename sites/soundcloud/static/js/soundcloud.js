/* SoundCloud mirror client: playbar state machine + AJAX actions.
   Playback is simulated (progress advances over the track's real duration);
   stream starts are POSTed to /tracks/<id>/played so listening history works. */
(function () {
  "use strict";

  var state = {
    queue: [],      // [{id, title, artist, artwork, duration, url}]
    index: -1,
    playing: false,
    progress: 0,    // ms
    volume: 80,
    timer: null,
  };

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function fmt(ms) {
    var s = Math.max(0, Math.round(ms / 1000));
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    return h > 0 ? h + ":" + pad(m) + ":" + pad(sec) : m + ":" + pad(sec);
    function pad(n) { return (n < 10 ? "0" : "") + n; }
  }

  function current() { return state.queue[state.index] || null; }

  function render() {
    var t = current();
    var art = $("#pb-art"), title = $("#pb-title"), artist = $("#pb-artist");
    var play = $("#pb-play"), fill = $("#pb-fill"), elapsed = $("#pb-elapsed"), total = $("#pb-total");
    if (!play) return;
    if (!t) {
      if (art) art.style.visibility = "hidden";
      if (title) title.textContent = "Nothing playing";
      if (artist) artist.textContent = "";
      if (fill) fill.style.width = "0%";
      if (elapsed) elapsed.textContent = "0:00";
      if (total) total.textContent = "0:00";
      play.textContent = "▶";
      return;
    }
    if (art) { art.style.visibility = "visible"; art.src = t.artwork; }
    if (title) { title.textContent = t.title; title.href = t.url; }
    if (artist) { artist.textContent = t.artist; }
    play.textContent = state.playing ? "❚❚" : "▶";
    var pct = t.duration ? (state.progress / t.duration) * 100 : 0;
    if (fill) fill.style.width = Math.min(100, pct) + "%";
    if (elapsed) elapsed.textContent = fmt(state.progress);
    if (total) total.textContent = fmt(t.duration);
  }

  function stopTimer() {
    if (state.timer) { clearInterval(state.timer); state.timer = null; }
  }

  function tick() {
    var t = current();
    if (!t) return;
    state.progress += 250;
    if (state.progress >= t.duration) {
      // end of track -> auto-advance
      next();
      return;
    }
    render();
  }

  function play() {
    var t = current();
    if (!t) return;
    state.playing = true;
    stopTimer();
    state.timer = setInterval(tick, 250);
    render();
    fetch("/tracks/" + t.id + "/played", { method: "POST", credentials: "same-origin" })
      .catch(function () {});
  }

  function pause() {
    state.playing = false;
    stopTimer();
    render();
  }

  function toggle() {
    var t = current();
    if (!t) return;
    if (state.playing) { pause(); } else { play(); }
  }

  function next() {
    if (!state.queue.length) return;
    state.index = (state.index + 1) % state.queue.length;
    state.progress = 0;
    if (state.playing) { play(); } else { render(); }
  }

  function prev() {
    if (!state.queue.length) return;
    if (state.progress > 3000) { state.progress = 0; render(); return; }
    state.index = (state.index - 1 + state.queue.length) % state.queue.length;
    state.progress = 0;
    if (state.playing) { play(); } else { render(); }
  }

  function startQueue(tracks, index) {
    state.queue = tracks;
    state.index = index;
    state.progress = 0;
    play();
  }

  // ------------------------------------------------------------ data hooks
  window.SC = {
    playTrackFromDOM: function (el) {
      var data = el.getAttribute("data-sc-track");
      if (!data) return;
      try {
        var t = JSON.parse(data);
        startQueue([t], 0);
      } catch (e) { /* noop */ }
    },
    playQueueFromDOM: function (el) {
      var listSel = el.getAttribute("data-sc-queue");
      var startId = el.getAttribute("data-sc-start-id");
      var list = $(listSel);
      if (!list) return;
      var items = $$("[data-sc-track]", list).map(function (n) {
        try { return JSON.parse(n.getAttribute("data-sc-track")); } catch (e) { return null; }
      }).filter(Boolean);
      if (!items.length) return;
      var idx = 0;
      if (startId) {
        for (var i = 0; i < items.length; i++) if (String(items[i].id) === String(startId)) { idx = i; break; }
      }
      startQueue(items, idx);
    },
    seekFraction: function (frac) {
      var t = current();
      if (!t) return;
      state.progress = Math.max(0, Math.min(t.duration, t.duration * frac));
      render();
    },
  };

  // ------------------------------------------------------------ bindings
  document.addEventListener("click", function (ev) {
    var el = ev.target.closest ? ev.target.closest("[data-sc-play]") : null;
    if (el) {
      ev.preventDefault();
      if (el.hasAttribute("data-sc-queue")) { SC.playQueueFromDOM(el); }
      else {
        var carrier = el.hasAttribute("data-sc-track")
          ? el
          : (el.closest("[data-sc-track]") || el);
        SC.playTrackFromDOM(carrier);
      }
      return;
    }
  });

  function bindPlaybar() {
    var play = $("#pb-play"), nextB = $("#pb-next"), prevB = $("#pb-prev");
    var bar = $("#pb-bar");
    if (play) play.addEventListener("click", toggle);
    if (nextB) nextB.addEventListener("click", next);
    if (prevB) prevB.addEventListener("click", prev);
    if (bar) bar.addEventListener("click", function (ev) {
      var rect = bar.getBoundingClientRect();
      SC.seekFraction((ev.clientX - rect.left) / rect.width);
    });
    var vol = $("#pb-vol");
    if (vol) vol.addEventListener("input", function () { state.volume = vol.value; });
  }

  // ------------------------------------------------------------ AJAX actions
  function post(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Requested-With": "fetch" },
      body: JSON.stringify(body || {}),
    }).then(function (r) {
      if (r.status === 401) {
        window.location = "/signin?next_url=" + encodeURIComponent(window.location.pathname);
        throw new Error("auth");
      }
      return r.json();
    });
  }

  function bindActions() {
    $$(".act-like").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-track");
        post("/tracks/" + id + "/like").then(function (d) {
          if (d.ok) {
            btn.classList.toggle("liked", d.liked);
            var n = btn.querySelector(".n");
            if (n) n.textContent = d.likes;
            if (d.liked) { flashToast(btn, d.liked ? "Added to your Likes" : ""); }
          }
        }).catch(function () {});
      });
    });
    $$(".act-repost").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-track");
        post("/tracks/" + id + "/repost").then(function (d) {
          if (d.ok) {
            btn.classList.toggle("reposted", d.reposted);
            var n = btn.querySelector(".n");
            if (n) n.textContent = d.reposts;
          }
        }).catch(function () {});
      });
    });
    $$(".act-follow").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-artist");
        post("/artists/" + id + "/follow").then(function (d) {
          if (d.ok) {
            btn.classList.toggle("following", d.following);
            btn.querySelector("span").textContent = d.following ? "Following" : "Follow";
            $$(".followers-n").forEach(function (n) {
              n.textContent = d.followers.toLocaleString();
            });
          }
        }).catch(function () {});
      });
    });

    var cform = $("#comment-form");
    if (cform) {
      cform.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var input = $("#comment-input");
        var at = $("#comment-at");
        var body = (input.value || "").trim();
        if (!body) return;
        var id = cform.getAttribute("data-track");
        post("/tracks/" + id + "/comment", { body: body, at: at ? at.value : "" })
          .then(function (d) {
            if (d.ok) { window.location.reload(); }
          }).catch(function () {});
      });
    }

    var modal = $("#pl-modal");
    $$(".act-addtopl").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!modal) return;
        var trackId = btn.getAttribute("data-track");
        modal.setAttribute("data-track", trackId);
        // The modal is global (base.html), so the Added/disabled state is
        // computed per clicked track from each playlist's track-id list.
        $$(".pl-add-btn", modal).forEach(function (b) {
          var ids = (b.getAttribute("data-track-ids") || "").split(",");
          var already = ids.indexOf(String(trackId)) !== -1;
          b.disabled = already;
          b.textContent = already ? "Added" : "Add";
        });
        modal.classList.add("open");
      });
    });
    if (modal) {
      $$(".modal-close", modal).forEach(function (b) {
        b.addEventListener("click", function () { modal.classList.remove("open"); });
      });
      modal.addEventListener("click", function (ev) {
        if (ev.target === modal) modal.classList.remove("open");
      });
      var createForm = $("#pl-create-form");
      if (createForm) {
        createForm.addEventListener("submit", function (ev) {
          ev.preventDefault();
          var title = ($("#pl-new-title").value || "").trim();
          if (!title) return;
          post("/playlists/create", { title: title, track_id: modal.getAttribute("data-track") })
            .then(function () { window.location.reload(); }).catch(function () {});
        });
      }
      $$(".pl-add-btn", modal).forEach(function (b) {
        b.addEventListener("click", function () {
          post("/playlists/" + b.getAttribute("data-pl") + "/add",
               { track_id: modal.getAttribute("data-track") })
            .then(function () { window.location.reload(); }).catch(function () {});
        });
      });
    }
    $$(".pl-remove-btn").forEach(function (rm) {
      rm.addEventListener("click", function () {
        post("/playlists/" + rm.getAttribute("data-pl") + "/remove",
             { track_id: rm.getAttribute("data-track") })
          .then(function () { window.location.reload(); }).catch(function () {});
      });
    });
  }

  function flashToast(btn, msg) {
    if (!msg) return;
    var t = document.createElement("div");
    t.textContent = msg;
    t.style.cssText = "position:fixed;bottom:96px;left:50%;transform:translateX(-50%);" +
      "background:#2a2a2a;color:#fff;padding:10px 18px;border-radius:6px;z-index:400;font-size:13px;";
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 2200);
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindPlaybar();
    bindActions();
    render();
  });
})();

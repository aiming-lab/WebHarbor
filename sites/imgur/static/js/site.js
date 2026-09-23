/* Imgur mirror — progressive enhancement only.
   Every action here also works without JS through plain form posts;
   this layer just makes the vote bar, favorite heart, comment votes and
   the search suggest dropdown behave like the live SPA. */
(function () {
    "use strict";

    // ---------------------------------------------------------------- suggest
    var searchbox = document.getElementById("searchbox");
    var suggest = document.getElementById("suggest");
    var timer = null;

    function closeSuggest() {
        if (suggest) suggest.classList.remove("open");
    }

    if (searchbox && suggest) {
        searchbox.addEventListener("input", function () {
            var q = searchbox.value.trim();
            clearTimeout(timer);
            if (q.length < 2) { closeSuggest(); return; }
            timer = setTimeout(function () {
                fetch("/suggest?q=" + encodeURIComponent(q))
                    .then(function (r) { return r.text(); })
                    .then(function (html) {
                        suggest.innerHTML = html;
                        var inner = document.getElementById("suggest-inner");
                        if (inner) suggest.classList.add("open");
                    })
                    .catch(function () { closeSuggest(); });
            }, 160);
        });
        searchbox.addEventListener("keydown", function (event) {
            if (event.key === "Escape") closeSuggest();
        });
        document.addEventListener("click", function (event) {
            if (!suggest.contains(event.target) && event.target !== searchbox) closeSuggest();
        });
    }

    // ------------------------------------------------------------- vote posts
    function post(path, data) {
        var body = new URLSearchParams();
        Object.keys(data).forEach(function (key) { body.append(key, data[key]); });
        return fetch(path, {
            method: "POST",
            headers: { "X-Requested-With": "XMLHttpRequest",
                       "Content-Type": "application/x-www-form-urlencoded" },
            body: body.toString()
        }).then(function (r) {
            if (!r.ok) throw new Error("http " + r.status);
            return r.json();
        });
    }

    function wireVoteButtons() {
        var buttons = document.querySelectorAll(".votebtn[data-post]");
        buttons.forEach(function (button) {
            button.closest("form").addEventListener("submit", function (event) {
                event.preventDefault();
                var value = button.getAttribute("data-value");
                post("/vote/" + button.getAttribute("data-post"), { value: value })
                    .then(function (payload) {
                        var well = button.closest(".votewell");
                        var score = well.querySelector(".votescore");
                        if (score) score.textContent = payload.points;
                        well.querySelectorAll(".votebtn").forEach(function (b) {
                            b.classList.remove("up-active", "down-active");
                        });
                        if (payload.value === 1) button.classList.add("up-active");
                        if (payload.value === -1) button.classList.add("down-active");
                    })
                    .catch(function () { location.href = "/signin"; });
            });
        });
    }

    function wireCommentVotes() {
        document.querySelectorAll(".cup[data-comment], .cdown[data-comment]").forEach(function (button) {
            button.addEventListener("click", function () {
                post("/vote/comment/" + button.getAttribute("data-comment"),
                     { value: button.getAttribute("data-value") })
                    .then(function (payload) {
                        var foot = button.closest(".votes");
                        var score = foot.querySelector(".cscore");
                        if (score) score.textContent = payload.points;
                        foot.querySelectorAll("button").forEach(function (b) {
                            b.classList.remove("up-active", "down-active");
                        });
                        if (payload.value === 1) button.classList.add("up-active");
                        if (payload.value === -1) button.classList.add("down-active");
                    })
                    .catch(function () { location.href = "/signin"; });
            });
        });
    }

    function wireCopyLink() {
        document.querySelectorAll(".copylink-btn").forEach(function (button) {
            button.addEventListener("click", function () {
                var link = button.getAttribute("data-link") || "";
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(location.origin + link).catch(function () {});
                }
            });
        });
    }

    // ------------------------------------------------------------- back to top
    var backtotop = document.getElementById("backtotop");
    if (backtotop) {
        window.addEventListener("scroll", function () {
            if (window.scrollY > 700) backtotop.classList.add("visible");
            else backtotop.classList.remove("visible");
        });
        backtotop.addEventListener("click", function () {
            window.scrollTo({ top: 0, behavior: "smooth" });
        });
    }

    // -------------------------------------------------------------- meme editor
    function wireMemePicker() {
        var labels = document.querySelectorAll(".memolibrary label.tpl");
        var bottomInput = document.getElementById("bottom-text-input");
        var bottomPreview = document.getElementById("bottomtext");
        var hint = document.getElementById("hint");
        var tplSelect = document.getElementById("tpl-select");
        labels.forEach(function (label) {
            label.addEventListener("click", function (event) {
                event.preventDefault();
                labels.forEach(function (other) { other.classList.remove("selected"); });
                label.classList.add("selected");
                var radio = label.querySelector("input");
                if (radio) radio.checked = true;
                if (tplSelect) tplSelect.value = radio.value;
                var img = label.querySelector("img");
                if (hint && img) {
                    hint.innerHTML = "";
                    var preview = document.createElement("img");
                    preview.className = "preview";
                    preview.src = img.src;
                    hint.appendChild(preview);
                }
            });
        });
        if (tplSelect) {
            tplSelect.addEventListener("change", function () {
                var wanted = tplSelect.value;
                labels.forEach(function (label) {
                    var radio = label.querySelector("input");
                    label.classList.toggle("selected", radio && radio.value === wanted);
                    if (radio && radio.value === wanted) {
                        radio.checked = true;
                        var img = label.querySelector("img");
                        if (hint && img) {
                            hint.innerHTML = "";
                            var preview = document.createElement("img");
                            preview.className = "preview";
                            preview.src = img.src;
                            hint.appendChild(preview);
                        }
                    }
                });
            });
        }
        if (bottomInput && bottomPreview) {
            bottomInput.addEventListener("input", function () {
                bottomPreview.textContent = bottomInput.value || "Bottom Text";
            });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            wireVoteButtons();
            wireCommentVotes();
            wireCopyLink();
            wireMemePicker();
        });
    } else {
        wireVoteButtons();
        wireCommentVotes();
        wireCopyLink();
        wireMemePicker();
    }
})();

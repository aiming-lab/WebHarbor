"""Self-checks for the SoundCloud mirror.

Run from sites/soundcloud/:  python3 -m pytest tests/ -q
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import app as sc_app  # noqa: E402
from app import (Artist, Comment, Follow, Like, PlayEvent, Playlist,  # noqa: E402
                 PlaylistTrack, Repost, Subscription, Track, User,
                 UserPlaylist, UserPlaylistTrack, app, db)

app.config["TESTING"] = True


def client():
    return app.test_client()


def test_health():
    with client() as c:
        r = c.get("/_health")
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["tracks"] >= 1000
        assert data["artists"] >= 800
        assert data["playlists"] >= 30
        assert data["comments"] >= 5000
        assert data["users"] == 4


def test_core_pages_render():
    with app.app_context():
        track = Track.query.order_by(Track.plays.desc()).first()
        artist = Artist.query.filter(Artist.followers > 1000).first()
        chart = Playlist.query.filter_by(is_chart=True, chart_country="US").first()
        curated = Playlist.query.filter_by(is_chart=False).first()
    with client() as c:
        for url in ["/", "/discover", "/charts", "/search?q=pop",
                    f"/{artist.permalink}",
                    f"/{track.artist.permalink}/{track.permalink}",
                    f"/{chart.owner.permalink}/sets/{chart.permalink}",
                    f"/{curated.owner.permalink}/sets/{curated.permalink}",
                    "/tags/hip-hop", "/signin", "/signup", "/upgrade"]:
            r = c.get(url)
            assert r.status_code == 200, url
            assert len(r.data) > 2000, url


def test_chart_pages_cover_50_rows():
    with client() as c:
        r = c.get("/music-charts-us/sets/all-music-genres")
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        assert body.count('class="track-row"') == 50
        r = c.get("/music-charts-uk/sets/hip-hop")
        assert r.status_code == 200


def test_scored_search_multword():
    with client() as c:
        r = c.get("/search?q=hip%20hop")
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        assert "track-card" in body
        # strict-AND would break multi-word queries; token overlap must hit
        r = c.get("/search?q=miley%20cyrus")
        body = r.get_data(as_text=True)
        assert "Miley Cyrus" in body


def test_search_tabs():
    with client() as c:
        r = c.get("/search?q=miley&tab=people")
        assert r.status_code == 200
        assert "person-row" in r.get_data(as_text=True)
        r = c.get("/search?q=pop&tab=playlists")
        assert "playlist-card" in r.get_data(as_text=True)


def test_benchmark_users_seeded():
    with app.app_context():
        for email in ["alice.j@test.com", "bob.c@test.com", "carol.d@test.com",
                      "david.k@test.com"]:
            u = User.query.filter_by(email=email).first()
            assert u is not None, email
            assert u.check_password("TestPass123!")
        alice = User.query.filter_by(email="alice.j@test.com").first()
        assert Like.query.filter_by(user_id=alice.id).count() >= 4
        assert Follow.query.filter_by(user_id=alice.id).count() >= 3
        assert UserPlaylist.query.filter_by(user_id=alice.id).count() >= 1
        assert PlayEvent.query.filter_by(user_id=alice.id).count() >= 3
        sub = Subscription.query.filter_by(user_id=alice.id).first()
        assert sub is not None and sub.plan_code == "go-plus"
        bob = User.query.filter_by(email="bob.c@test.com").first()
        sub = Subscription.query.filter_by(user_id=bob.id).first()
        assert sub is not None and sub.plan_code == "next-pro" and sub.cycle == "yearly"


def test_login_flow():
    with client() as c:
        r = c.post("/signin", data={"email": "alice.j@test.com",
                                    "password": "TestPass123!",
                                    "next_url": "/you/likes"},
                   follow_redirects=True)
        assert r.status_code == 200
        assert b"Alice Johnson" in r.data
        r = c.post("/signin", data={"email": "alice.j@test.com",
                                    "password": "wrong"}, follow_redirects=True)
        assert b"doesn&#39;t match" in r.data or b"match" in r.data


def test_like_toggle_and_persistence():
    with client() as c:
        c.post("/signin", data={"email": "david.k@test.com",
                                "password": "TestPass123!"})
        with app.app_context():
            t0 = Track.query.order_by(Track.plays.desc()).first()
            tid, likes0 = t0.id, t0.likes
        r = c.post(f"/tracks/{tid}/like")
        assert r.get_json()["liked"] is True
        with app.app_context():
            t = db.session.get(Track, tid)
            assert t.likes == likes0 + 1
            assert Like.query.filter_by(user_id=4, track_id=tid).count() == 1
        r = c.post(f"/tracks/{tid}/like")
        assert r.get_json()["liked"] is False
        with app.app_context():
            assert db.session.get(Track, tid).likes == likes0


def test_comment_post_and_count():
    with client() as c:
        c.post("/signin", data={"email": "carol.d@test.com",
                                "password": "TestPass123!"})
        with app.app_context():
            t = Track.query.order_by(Track.plays.desc()).first()
            tid, n0 = t.id, t.comment_count
        r = c.post(f"/tracks/{tid}/comment", json={"body": "test comment", "at": "1:23"})
        assert r.get_json()["ok"] is True
        with app.app_context():
            t = db.session.get(Track, tid)
            assert t.comment_count == n0 + 1
            cm = Comment.query.filter_by(track_id=tid).order_by(Comment.id.desc()).first()
            assert cm.body == "test comment"
            assert cm.timestamp_ms == 83_000
            assert cm.author_name == "Carol Davis"


def test_follow_toggle():
    with client() as c:
        c.post("/signin", data={"email": "david.k@test.com",
                                "password": "TestPass123!"})
        with app.app_context():
            a = Artist.query.filter_by(permalink="childish-gambino").first()
            aid, f0 = a.id, a.followers
        r = c.post(f"/artists/{aid}/follow")
        assert r.get_json()["following"] is True
        with app.app_context():
            assert db.session.get(Artist, aid).followers == f0 + 1
        r = c.post(f"/artists/{aid}/follow")
        assert r.get_json()["following"] is False
        with app.app_context():
            assert db.session.get(Artist, aid).followers == f0


def test_user_playlist_crud():
    with client() as c:
        c.post("/signin", data={"email": "bob.c@test.com",
                                "password": "TestPass123!"})
        r = c.post("/playlists/create", json={"title": "Test Rotation"})
        pl = r.get_json()
        assert pl["ok"] and pl["title"] == "Test Rotation"
        with app.app_context():
            t = Track.query.order_by(Track.plays.desc()).first()
            tid = t.id
        r = c.post(f"/playlists/{pl['playlist_id']}/add", json={"track_id": tid})
        assert r.get_json()["count"] == 1
        r = c.post(f"/playlists/{pl['playlist_id']}/add", json={"track_id": tid})
        assert r.get_json().get("already") is True
        r = c.post(f"/playlists/{pl['playlist_id']}/remove", json={"track_id": tid})
        assert r.get_json()["count"] == 0
        with app.app_context():
            up = db.session.get(UserPlaylist, pl["playlist_id"])
            assert up.track_count == 0


def test_play_records_history_for_logged_in():
    with client() as c:
        c.post("/signin", data={"email": "alice.j@test.com",
                                "password": "TestPass123!"})
        with app.app_context():
            t = Track.query.order_by(Track.plays.desc()).first()
            tid, p0 = t.id, t.plays
        r = c.post(f"/tracks/{tid}/played")
        assert r.get_json()["ok"] is True
        with app.app_context():
            assert db.session.get(Track, tid).plays == p0 + 1
            ev = (PlayEvent.query.filter_by(user_id=1, track_id=tid)
                  .order_by(PlayEvent.id.desc()).first())
            assert ev is not None


def test_subscription_switch():
    with client() as c:
        c.post("/signin", data={"email": "david.k@test.com",
                                "password": "TestPass123!"})
        r = c.post("/upgrade/subscribe", data={"plan": "go-plus", "cycle": "monthly",
                                                "card": "4242 4242 4242 4242"},
                   follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            subs = Subscription.query.filter_by(user_id=4).all()
            assert len(subs) == 1
            assert subs[0].plan_code == "go-plus"
            assert subs[0].card_last4 == "4242"


def test_upload_creates_track_and_profile():
    with client() as c:
        c.post("/signin", data={"email": "alice.j@test.com",
                                "password": "TestPass123!"})
        r = c.post("/upload", data={"title": "Pytest Upload", "genre": "Pop",
                                    "minutes": "2", "seconds": "30",
                                    "tags": "pytest", "description": ""},
                   follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            t = Track.query.filter_by(permalink="pytest-upload").first()
            assert t is not None
            assert t.duration == 150_000
            artist = db.session.get(Artist, t.artist_id)
            assert artist.permalink == "alice_j"


def test_waveform_and_artwork_present():
    with app.app_context():
        t = Track.query.filter(Track.artwork != "").order_by(Track.plays.desc()).first()
        samples = t.waveform_samples
        assert len(samples) == 180
        assert t.artwork.startswith("/static/images/tracks/")
        # every seeded (upstream) track has real artwork + waveform; tracks
        # uploaded through the mirror's own upload form by benchmark users are
        # excluded (uploads ship no artwork by design)
        seeded = Track.query.join(Artist).filter(
            Artist.permalink.notin_(["alice_j", "bob_c", "carol_d", "david_k"]))
        missing_art = seeded.filter(Track.artwork == "").count()
        missing_wf = sum(1 for t in seeded.all() if not t.waveform_samples)
        assert missing_art == 0
        assert missing_wf == 0


def test_all_playlists_have_owners_and_art():
    with app.app_context():
        for p in Playlist.query.all():
            assert p.owner is not None
            assert p.artwork.startswith("/static/images/playlists/")
        charts = Playlist.query.filter_by(is_chart=True).count()
        assert charts == 20


def test_404_and_auth_guards():
    with client() as c:
        assert c.get("/no-such-artist").status_code == 404
        assert c.get("/you/likes").status_code == 302
        with app.app_context():
            some_track = Track.query.first()
            tid = some_track.id
        r = c.post(f"/tracks/{tid}/like")
        assert r.status_code == 401


def test_add_to_playlist_modal_on_every_page():
    """The ＋ button on chart rows / artist pages / library must open a real
    modal everywhere (it used to be a dead button outside track pages)."""
    with client() as c:
        # anonymous: modal present with the sign-in prompt, no dead click
        r = c.get("/music-charts-us/sets/all-music-genres")
        body = r.get_data(as_text=True)
        assert 'id="pl-modal"' in body
        assert "Sign in</a> to create playlists" in body
        r = c.get("/")
        assert 'id="pl-modal"' in r.get_data(as_text=True)
        # logged in: modal lists the user's playlists with track-id data for the
        # client-side Added/disabled state
        c.post("/signin", data={"email": "alice.j@test.com",
                                "password": "TestPass123!"})
        r = c.get("/music-charts-us/sets/all-music-genres")
        body = r.get_data(as_text=True)
        assert 'id="pl-modal"' in body
        assert "Late Night Drive" in body
        assert 'class="pl-add-btn"' in body and "data-track-ids=" in body
        # track page still renders the modal exactly once
        with app.app_context():
            t = Track.query.order_by(Track.plays.desc()).first()
            href = f"/{t.artist.permalink}/{t.permalink}"
        body = c.get(href).get_data(as_text=True)
        assert body.count('id="pl-modal"') == 1


def test_landing_hero_matches_upstream_campaign():
    with client() as c:
        body = c.get("/").get_data(as_text=True)
        assert "IT ALL STARTS WITH AN UPLOAD." in body
        assert "Just hit upload" in body
        assert 'href="/upload"' in body and "Explore Artist Pro" in body


def test_t3_fixture_target_not_preliked_by_carol():
    """T3 asks Carol to like the most-played Miley Cyrus track on the US
    'New & Hot' chart; the seed must not pre-like that track for her so the
    action is a clean +1 (the old alice fixture toggled a pre-existing like)."""
    with app.app_context():
        newhot = Playlist.query.filter_by(permalink="new-hot",
                                          chart_country="US").first()
        miley = Artist.query.filter_by(permalink="mileycyrus").first()
        chart_ids = {e.track_id for e in newhot.entries}
        miley_ids = {t.id for t in Track.query.filter_by(artist_id=miley.id)}
        target_id = max(miley_ids & chart_ids,
                        key=lambda i: db.session.get(Track, i).plays)
        target = db.session.get(Track, target_id)
        assert target.title == "Bass Persuades"
        carol = User.query.filter_by(email="carol.d@test.com").first()
        assert Like.query.filter_by(user_id=carol.id,
                                    track_id=target_id).first() is None


def test_tasks_jsonl_schema_and_no_leaks():
    """Every task stays a single goal-style prompt: 7 keys (the two contract
    keys appended by the reviewer — verifier_path + judge_rubric — are
    tracked inline), no answer key, <=100 words. The three texts edited in
    the round-2 fix (T4/T18 profile binding, T19 redesign) must not leak
    their ground-truth answers."""
    import json

    tasks_path = (pathlib.Path(__file__).resolve().parent.parent
                  / "tasks.jsonl")
    rows = [json.loads(l) for l in
            tasks_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 21
    assert [r["id"] for r in rows] == [f"SoundCloud--{i}" for i in range(21)]
    for r in rows:
        assert set(r) == {"web_name", "id", "ques", "web", "upstream_url",
                          "verifier_path", "judge_rubric"}
        assert len(r["ques"].split()) <= 100, r["id"]
        assert "\n" not in r["ques"]

    by_id = {r["id"]: r["ques"] for r in rows}
    # T4/T18: city + follower count must be bound to the profile page
    # (the People-tab search row also shows them — r2 finding #R2).
    assert "shown on his profile" in by_id["SoundCloud--4"]
    assert "shown on the profile" in by_id["SoundCloud--18"]
    # T19: the deep legs that push both step columns >=15 must stay in the
    # text, and no ground-truth token may appear.
    t19 = by_id["SoundCloud--19"]
    for leg in ("Popular-tab", "UK Indie", "profile", "#1"):
        assert leg in t19, leg
    for leaked in ("Lacy", "steevlacy", "oh yeah", "nothing", "Buttons",
                   "doom", "show you me", "Guilty", "Heaney", "377,394",
                   "1,059,416", "211,561", "128,218", "85,000", "33,262",
                   "118", "Safelight"):
        assert leaked.lower() not in t19.lower(), leaked

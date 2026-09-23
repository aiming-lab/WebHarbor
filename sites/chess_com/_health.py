"""Per-site end-to-end health check for the Chess.com mirror.

Run with the site already serving on a port (default 43065). Exercises every
major route family, checks the content is non-empty, and validates the auth
+ stateful flows end-to-end via the test client.
"""
import json
import os
import sys
import urllib.request

BASE = os.environ.get("CHESS_COM_URL", "http://127.0.0.1:43065")


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return r.status, r.read().decode("utf-8", "replace")


def main():
    failures = []

    def expect(path, needles, name=None):
        try:
            status, body = get(path)
            missing = [n for n in needles if n not in body]
            if status != 200 or missing:
                failures.append(f"{path}: status={status} missing={missing[:3]}")
                print(f"[FAIL] {path} status={status} missing={missing[:3]}")
            else:
                print(f"[ok] {path}")
        except Exception as e:
            failures.append(f"{path}: {e!r}")
            print(f"[FAIL] {path}: {e!r}")

    # core pages
    expect("/", ["Play Chess Online", "Chess.com", "Get Started"])
    expect("/_health", ["chess_com"])
    expect("/play", ["Play Bots", "Tournaments"])
    expect("/play/online", ["Bullet", "Blitz", "Rapid"])
    expect("/play/computer", ["rating"])
    expect("/puzzles", ["Puzzles", "trainer-board"])
    expect("/puzzles/themes", ["Puzzle Themes"])
    expect("/puzzles/archive", ["Daily Puzzle Archive"])
    expect("/daily", ["Daily Puzzle"])
    expect("/lessons", ["Lessons", "lessons"])
    expect("/openings", ["Chess Openings"])
    expect("/watch", ["ChessTV Schedule", "Featured Events"])
    expect("/events", ["Events"])
    expect("/leaderboard/live", ["Blitz Leaderboard", "Hikaru"])
    expect("/leaderboard/live/bullet", ["Bullet Leaderboard"])
    expect("/leaderboard/live/rapid", ["Rapid Leaderboard"])
    expect("/leaderboard/tactics", ["Tactics Leaderboard"])
    expect("/leaderboard/daily", ["Daily Leaderboard"])
    expect("/members", ["Members", "Followers"])
    expect("/members/titled-players", ["Titled Players", "GM"])
    expect("/games", ["Chess Games Database"])
    expect("/news", ["News"])
    expect("/clubs", ["Clubs"])
    expect("/today", ["Chess Today"])
    expect("/search?q=hikaru", ["Hikaru"])
    expect("/login", ["Log In"])
    expect("/register", ["Sign Up"])
    expect("/train", ["Train"])
    expect("/other", ["Other"])

    # detail pages: use real slugs from the seed
    status, body = get("/news")
    for slug in ["/news/view/" + s for s in _slugs(body, "/news/view/", 3)]:
        expect(slug, ["News"])
    status, body = get("/openings")
    for slug in ["/openings/" + s for s in _slugs(body, "/openings/", 3)]:
        expect(slug, ["ECO", "Popularity"])
    status, body = get("/lessons")
    for slug in ["/lessons/" + s for s in _slugs(body, "/lessons/", 2)]:
        expect(slug, ["lessons"])
    status, body = get("/clubs")
    for slug in ["/club/" + s for s in _slugs(body, "/club/", 2)]:
        expect(slug, ["members"])
    status, body = get("/games")
    for slug in ["/games/" + s for s in _slugs(body, "/games/", 2)]:
        expect(slug, ["Chess Games"])
    status, body = get("/events")
    for slug in ["/events/info/" + s for s in _slugs(body, "/events/info/", 2)]:
        expect(slug, ["players"])
    status, body = get("/leaderboard/live")
    for slug in ["/stats/live/blitz/" + s for s in _slugs(body, "/stats/live/blitz/", 2)]:
        expect(slug, ["rating"])

    # member profile
    expect("/member/Hikaru", ["followers", "Hikaru"])
    expect("/member/MagnusCarlsen", ["MagnusCarlsen"])

    # puzzle archive -> a real puzzle detail page
    status, body = get("/puzzles/archive")
    for slug in ["/puzzles/problem/" + s for s in _slugs(body, "/puzzles/problem/", 2)]:
        expect(slug, ["Daily Puzzle"])

    # a master game detail page (SAN replay)
    status, body = get("/games/hikaru-nakamura")
    for gid in ["/games/view/" + s for s in _slugs(body, "/games/view/", 2)]:
        expect(gid, ["Result"])

    # JSON callbacks
    status, body = get("/callback/puzzles/next")
    try:
        data = json.loads(body)
        assert data["fen"] and data["moves"], "puzzle payload incomplete"
        print("[ok] /callback/puzzles/next")
    except Exception as e:
        failures.append(f"/callback/puzzles/next: {e!r}")
        print(f"[FAIL] /callback/puzzles/next: {e!r}")

    # auth flow via test client
    try:
        os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from app import app, db, User
        app.config["TESTING"] = True
        with app.test_client() as client:
            r = client.post("/login", data={"username": "alice.j@test.com",
                                            "password": "TestPass123!"},
                            follow_redirects=True)
            assert b"Welcome back" in r.data or b"alice_j" in r.data, "login failed"
            print("[ok] login alice")
            r = client.get("/settings")
            assert b"Settings" in r.data and b"alice_j" in r.data
            print("[ok] settings shows alice_j")
            r = client.post("/settings", data={"action": "profile", "name": "Alice J.",
                                               "location": "Bellevue, WA",
                                               "country_code": "US", "about": "hi"},
                            follow_redirects=True)
            assert b"Profile updated" in r.data or b"Bellevue" in r.data
            print("[ok] settings profile update")
            # toggle from whatever the current state is; both directions must work
            r1 = client.post("/follow/Hikaru", follow_redirects=True)
            state1 = b"Unfollow Hikaru" in r1.data
            r2 = client.post("/follow/Hikaru", follow_redirects=True)
            state2 = b"Unfollow Hikaru" in r2.data
            assert state1 != state2, "follow toggle did not change state"
            print("[ok] follow toggle both directions")
            r1 = client.post("/club/chess-com-community/join", follow_redirects=True)
            s1 = b"Leave Club" in r1.data
            r2 = client.post("/club/chess-com-community/join", follow_redirects=True)
            s2 = b"Leave Club" in r2.data
            assert s1 != s2, "club join/leave toggle did not change state"
            print("[ok] club join/leave toggle")
        print("[ok] stateful flows")
    except Exception as e:
        failures.append(f"stateful flows: {e!r}")
        print(f"[FAIL] stateful flows: {e!r}")

    if failures:
        print(f"\n[health] {len(failures)} FAILURES")
        return 1
    print("\n[health] all checks passed")
    return 0


def _slugs(body, prefix, limit):
    """Real page links only: href="{prefix}<slug>" (asset src URLs excluded)."""
    import re as _re
    out = []
    for m in _re.finditer(_re.escape(prefix) + r'([A-Za-z0-9-]+)', body):
        start = m.start()
        if body[max(0, start - 6):start] != 'href="':
            continue
        slug = m.group(1)
        if slug and not slug.startswith("category") and slug not in out:
            out.append(slug)
        if len(out) >= limit:
            break
    return out


if __name__ == "__main__":
    sys.exit(main())

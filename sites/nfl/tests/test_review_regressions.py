"""Contribution-contract and seed-integrity regression tests for the nfl mirror.

Covers: tasks.jsonl schema (five basic keys only, no ground-truth leaks),
seed determinism (byte-reproducible build), and image-reference integrity
(every served image path exists on disk and no placeholder files ship).
"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys

SITE = pathlib.Path(__file__).resolve().parent.parent

EXPECTED_TASK_KEYS = {"web_name", "id", "ques", "web", "upstream_url"}
# The reviewer pass appends the grading contract (CONTRIBUTING.md "Reviewer
# role"); these two keys are the only permitted additions, and an answer key
# is never allowed.
REVIEWER_TASK_KEYS = {"verifier_path", "judge_rubric"}
DECLARED_PORT = 40115


def test_tasks_jsonl_contract():
    lines = (SITE / "tasks.jsonl").read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) >= 15, "expected at least 15 tasks"
    seen_ids = set()
    for i, line in enumerate(lines):
        row = json.loads(line)
        assert EXPECTED_TASK_KEYS <= set(row.keys()), (
            f"line {i} is missing contributor keys: {EXPECTED_TASK_KEYS - set(row)}"
        )
        assert set(row.keys()) - EXPECTED_TASK_KEYS <= REVIEWER_TASK_KEYS, (
            f"line {i} has unexpected keys: {sorted(set(row) - EXPECTED_TASK_KEYS - REVIEWER_TASK_KEYS)}"
        )
        assert row["web_name"] == "NFL"
        assert row["id"] == f"NFL--{i}", f"line {i} id should be NFL--{i}, got {row['id']}"
        assert row["web"] == f"http://localhost:{DECLARED_PORT}/"
        assert row["upstream_url"] == "https://www.nfl.com/"
        words = len(row["ques"].split())
        assert words <= 100, f"{row['id']} is {words} words"
        assert "answer" not in row, "tasks must not carry answer keys"
        seen_ids.add(row["id"])
    assert len(seen_ids) == len(lines)


def test_tasks_cover_multiple_domains():
    rows = [json.loads(l) for l in (SITE / "tasks.jsonl").read_text().strip().split("\n")]
    text = " ".join(r["ques"] for r in rows).lower()
    domains = {
        "subscription checkout": "nfl+" in text,
        "account management": any(k in text for k in ("sign in", "account", "cancel")),
        "stats": "rusher" in text or "leaders" in text or "stat" in text,
        "standings": "standings" in text or "division" in text or "undefeated" in text,
        "game center": "game" in text or "attendance" in text or "prime time" in text,
        "roster": "roster" in text,
        "injuries": "injur" in text,
        "transactions": "practice squad" in text or "transactions" in text,
        "news": "article" in text or "newsroom" in text,
        "video": "video" in text,
        "search": "search" in text,
    }
    missing = [name for name, ok in domains.items() if not ok]
    assert not missing, f"tasks missing domains: {missing}"


def test_seed_is_byte_reproducible(tmp_path):
    """Rebuilding the seed twice must produce identical bytes."""
    script = (
        "import os, sys, hashlib; os.environ['WEBSYN_SKIP_BOOTSTRAP']='1'; "
        f"sys.path.insert(0, {str(SITE)!r}); "
        f"os.environ['NFL_DB_PATH']='sqlite:///{tmp_path}/s.db'; "
        "from app import app, create_schema; "
        "from seed_data import seed_database, seed_benchmark_users; "
        "app.app_context().__enter__(); create_schema(); "
        "seed_database(); seed_benchmark_users(); "
        f"print(hashlib.sha256(open({str(tmp_path / 's.db')!r},'rb').read()).hexdigest())"
    )
    hashes = []
    for _ in range(2):
        out = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, cwd=SITE
        )
        assert out.returncode == 0, out.stderr[-500:]
        hashes.append(out.stdout.strip().splitlines()[-1])
    assert hashes[0] == hashes[1], "seed is not byte-reproducible"


def test_image_references_resolve():
    """Every image path the templates/app can emit must exist on disk."""
    import app as app_module

    image_roots = {
        "logos": SITE / "static" / "images" / "logos",
        "players": SITE / "static" / "images" / "players",
        "news": SITE / "static" / "images" / "news",
        "videos": SITE / "static" / "images" / "videos",
        "global": SITE / "static" / "images" / "global",
    }
    for root in image_roots.values():
        assert root.exists(), f"missing image dir {root}"

    with app_module.app.app_context():
        from app import Team, Player, NewsArticle, Video

        for team in Team.query.all():
            path = SITE / "static" / "images" / team.logo_file
            assert path.exists(), f"missing logo {team.logo_file}"
        missing_heads = 0
        for player in Player.query.filter_by(has_headshot=True).all():
            path = SITE / "static" / "images" / "players" / f"{player.slug}.png"
            if not path.exists():
                missing_heads += 1
        assert missing_heads == 0, f"{missing_heads} referenced headshots missing"
        for article in NewsArticle.query.filter(NewsArticle.image_id != "").all():
            path = SITE / "static" / "images" / "news" / f"{article.image_id}.jpg"
            assert path.exists(), f"missing news image {article.image_id}"
        for video in Video.query.filter(Video.image_id != "").all():
            path = SITE / "static" / "images" / "videos" / f"{video.image_id}.jpg"
            assert path.exists(), f"missing video thumbnail {video.image_id}"


def test_no_placeholder_images():
    """No zero-byte, tiny, or obviously synthetic files may ship."""
    inventory = json.loads((SITE / "asset_inventory.json").read_text(encoding="utf-8"))
    assert inventory["schema_version"] == 1
    assert inventory["asset_count"] == len(inventory["assets"])
    total = 0
    for asset in inventory["assets"]:
        path = SITE / asset["path"]
        data = path.read_bytes()
        assert len(data) == asset["bytes"], f"size drift at {asset['path']}"
        digest = hashlib.sha256(data).hexdigest()
        assert digest == asset["sha256"], f"hash drift at {asset['path']}"
        assert asset["source_url"].startswith("https://static.www.nfl.com/"), (
            f"non-upstream source for {asset['path']}"
        )
        assert len(data) > 100, f"suspicious tiny file {asset['path']}"
        total += 1
    assert total >= 2500, f"expected the full upstream harvest, got {total}"


def test_inventory_covers_every_shipped_image():
    inventory = json.loads((SITE / "asset_inventory.json").read_text(encoding="utf-8"))
    listed = {a["path"] for a in inventory["assets"]}
    actual = {
        str(p.relative_to(SITE))
        for p in (SITE / "static" / "images").rglob("*")
        if p.is_file() and p.name != ".gitkeep"
    }
    assert actual == listed, (
        f"inventory mismatch: missing={sorted(actual - listed)[:4]} "
        f"extra={sorted(listed - actual)[:4]}"
    )


def test_data_provenance_files_exist():
    for name in ("NOTICE.md", "provenance.json", "asset_inventory.json",
                 "image_manifest.json", ".build-generated-seed"):
        assert (SITE / name).exists(), f"missing provenance artifact {name}"


def test_game_times_render_in_eastern_time(client):
    """Day/date/time must be derived from the Eastern conversion of the UTC
    kickoff, not from the raw UTC calendar day (review finding 2).

    - Prime-time windows land on their badge day in Eastern time: TNF
      Thursday, SNF Sunday, MNF Monday (the feed stores UTC instants whose
      calendar day is one later for >=8pm ET kickoffs).
    - The Week 1 opener (2026-09-10T00:20:00Z) is Wednesday, Sep 9 in ET.
    - Post-DST kickoffs (first Sunday of November onward) use EST (UTC-5),
      not the fixed UTC-4 the original code applied: the Week 14 Raiders
      home game (2026-12-13T21:05:00Z) is 4:05pm ET, not 5:05pm.
    """
    import app as app_module
    with app_module.app.app_context():
        from app import Game

        def probe(slug):
            g = Game.query.filter_by(slug=slug).first()
            assert g is not None, slug
            return g

        tnf = probe("falcons-at-packers-2026-reg-3")
        assert (tnf.day_display, tnf.time_display, tnf.date_display) == (
            "THU", "8:15pm", "SEPTEMBER 24")
        snf = probe("rams-at-broncos-2026-reg-3")
        assert (snf.day_display, snf.time_display) == ("SUN", "8:20pm")
        mnf = probe("eagles-at-bears-2026-reg-3")
        assert (mnf.day_display, mnf.time_display) == ("MON", "8:15pm")
        opener = probe("patriots-at-seahawks-2026-reg-1")
        assert (opener.day_display, opener.time_display) == ("WED", "8:20pm")
        melbourne = probe("49ers-at-rams-2026-reg-1")
        assert (melbourne.day_display, melbourne.time_display) == (
            "INTL THU", "8:35pm")
        est_game = probe("chargers-at-raiders-2026-reg-14")
        assert est_game.time_display == "4:05pm", "EST kickoff runs an hour late"

    tnf_page = client.get("/games/falcons-at-packers-2026-reg-3/").get_data(as_text=True)
    assert re.search(r"WEEK 3\s+·\s+SEPTEMBER 24, 8:15pm ET\s+·\s+TNF", tnf_page)
    scores_w3 = client.get("/scores/2026/REG3/").get_data(as_text=True)
    assert "8:15pm" in scores_w3 and "8:20pm" in scores_w3
    assert "5:05pm" not in scores_w3
    scores_w14 = client.get("/scores/2026/REG14/").get_data(as_text=True)
    assert "4:05pm" in scores_w14, "EST kickoffs must not run an hour late"
    assert "5:05pm" not in scores_w14, "fixed UTC-4 conversion leaked through"
    raiders = client.get("/teams/las-vegas-raiders/schedule/").get_data(as_text=True)
    assert "4:05pm" in raiders
    # The homepage scores ribbon renders day+time in one span.
    home = client.get("/").get_data(as_text=True)
    assert "THU 8:15pm" in home, "ribbon must show the Eastern day for TNF"


def test_search_page_hides_result_counts(client):
    """Search section headers must not carry result-count labels (review
    finding 4): a "PLAYERS (1)" style label hands task answers over without
    any counting work. The rows themselves stay, so counts remain
    derivable by reading the page (see NOTICE.md for the documented
    upstream deviation)."""
    body = client.get("/search?q=Mahomes").get_data(as_text=True)
    for section in ("PLAYERS", "NEWS", "VIDEO"):
        assert f">{section}</h2>" in body, f"{section} header missing"
    for leaked in ("PLAYERS (", "TEAMS (", "NEWS (", "VIDEO ("):
        assert leaked not in body, f"count label leaked: {leaked!r}"
    # The results themselves are still all there to be counted.
    assert body.count("/players/patrick-mahomes/"), "player row missing"
    assert "NFL QB rankings, Week 3" in body, "news row missing"


def _quarter_cells(body: str, team_name: str) -> list[int]:
    """The five per-quarter <td> cells of one SCORE BY QUARTER row."""
    row = re.search(
        rf'<td class="team-cell"><img[^>]*alt=""> {re.escape(team_name)}</td>'
        rf"((?:\s*<td>\d+</td>){{5}})",
        body,
    )
    assert row, f"quarter row for {team_name} not found or not five cells"
    return [int(c) for c in re.findall(r"<td>(\d+)</td>", row.group(1))]


def test_game_center_renders_parsed_quarter_scores(client):
    """r2 review finding F1: the quarter columns are JSON text, so the old
    template's `game.away_quarters[:5]` sliced the STRING and rendered
    characters ("[", "3", ",", " ") instead of per-quarter points. The
    table must render the parsed integers, including the OT column for
    FINAL/OT games (T5's quarter-by-quarter scoring and T17's overtime
    scoring must be answerable from the page)."""
    import app as app_module
    samples = (
        "49ers-at-rams-2026-reg-1",   # played international game (T5)
        "colts-at-chiefs-2026-reg-2",  # FINAL/OT (T17 overtime scoring)
        "saints-at-lions-2026-reg-1",  # second FINAL/OT sample
    )
    with app_module.app.app_context():
        from app import Game

        games = {s: Game.query.filter_by(slug=s).first() for s in samples}
        assert all(g is not None for g in games.values())
        expected = {
            s: (
                g.away.full_name,
                g.home.full_name,
                json.loads(g.away_quarters),
                json.loads(g.home_quarters),
            )
            for s, g in games.items()
        }
    for slug, (away, home, away_q, home_q) in expected.items():
        body = client.get(f"/games/{slug}/").get_data(as_text=True)
        assert "SCORE BY QUARTER" in body, slug
        # ...and no raw JSON column text leaks into the table region.
        table = body[body.index("SCORE BY QUARTER"):]
        table = table[: table.index("</table>")]
        for ch in "[]":
            assert ch not in table, f"{slug}: raw JSON leaked into quarter table"
        # The rendered cells are the parsed quarter points, in order...
        assert _quarter_cells(body, away) == away_q, slug
        assert _quarter_cells(body, home) == home_q, slug
    # The OT column carries the extra-session points on OT games.
    ot = client.get("/games/colts-at-chiefs-2026-reg-2/").get_data(as_text=True)
    assert _quarter_cells(ot, "Kansas City Chiefs")[-1] == 6
    assert _quarter_cells(ot, "Indianapolis Colts")[-1] == 3

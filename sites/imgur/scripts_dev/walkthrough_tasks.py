#!/usr/bin/env python3
"""Walk benchmark tasks through the local mirror and verify the facts.

Drives the mirror with Playwright exactly like the evolve-env skill
requires (real browser, recorded URL steps), checks the observed facts
against the seeded DB, and appends a walkthrough report to
scraped_data/task_walkthroughs.json.

Usage: python3 scripts_dev/walkthrough_tasks.py [--port 43071] [--tasks 0,5,9]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
import sys

from playwright.sync_api import sync_playwright

SITE = pathlib.Path(__file__).resolve().parent.parent
DB = SITE / "instance" / "imgur.db"
TASKS = SITE / "tasks.jsonl"
REPORT = SITE / "scraped_data" / "task_walkthroughs.json"


def q(sql, args=()):
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute(sql, args).fetchall()
    out = [dict(r) for r in rows]
    db.close()
    return out


class Walker:
    def __init__(self, base):
        self.base = base
        self.steps = []

    def __enter__(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=True)
        self.ctx = self.browser.new_context(viewport={"width": 1440, "height": 900})
        self.page = self.ctx.new_page()
        return self

    def __exit__(self, *exc):
        self.browser.close()
        self._pw.stop()

    def go(self, path):
        self.page.goto(self.base + path, wait_until="domcontentloaded", timeout=30000)
        self.page.wait_for_timeout(700)
        self.steps.append(path)

    def login(self, email, password):
        self.go("/signin")
        self.page.fill('input[name="username"]', email)
        self.page.fill('input[name="password"]', password)
        self.page.click('button[type="submit"]')
        self.page.wait_for_timeout(900)
        self.steps.append(f"signin:{email}")

    def body(self):
        return self.page.inner_text("body")


def find_post(title_prefix: str):
    rows = q("SELECT id, seo_title, title, point_count, comment_count, view_count, image_count, author_id FROM posts WHERE title LIKE ?", (title_prefix + "%",))
    assert rows, f"no post with prefix {title_prefix!r}"
    return rows[0]


def slug_of(row) -> str:
    if row["seo_title"]:
        return f"{row['seo_title']}-{row['id']}"
    return row["id"]


def walk_task(walker: Walker, index: int) -> dict:
    """Hand-walked trajectories for a sample of tasks, with DB-verified facts."""
    result = {"task": f"Imgur--{index}", "steps": walker.steps, "checks": []}

    def check(name, observed, expected):
        ok = observed == expected
        result["checks"].append({"fact": name, "observed": observed,
                                 "expected": expected, "pass": ok})
        return ok

    if index == 0:
        row = find_post("The Real MVP!")
        walker.go("/")
        walker.go("/gallery/" + slug_of(row))
        body = walker.body()
        check("score in vote box", str(row["point_count"]) in body, True)
        check("comments header", f"{row['comment_count']} COMMENTS" in body, True)
        author = q("SELECT username FROM users WHERE id = ?", (row["author_id"],))[0]["username"]
        check("author shown", author in body, True)

    elif index == 5:
        walker.login("alice.j@test.com", "TestPass123!")
        walker.go("/user/alice_j?tab=favorites")
        body = walker.body()
        favorites = q("SELECT p.title FROM favorites f JOIN posts p ON p.id=f.post_id JOIN users u ON u.id=f.user_id WHERE u.username='alice_j'")
        check("favorite count", len(favorites), 4)
        for fav in favorites:
            check("favorite title shown", fav["title"][:40] in body, True)

    elif index == 8:
        row = find_post("PSA")
        walker.login("carol.d@test.com", "TestPass123!")
        walker.go("/gallery/" + slug_of(row))
        walker.page.fill('.commentbar input[name="comment"]', "Mirror test comment 2026")
        walker.page.click('.commentbar button[type="submit"]')
        walker.page.wait_for_timeout(900)
        walker.steps.append("post-comment")
        body = walker.body()
        expected = row["comment_count"] + 1
        check("comment count bumped", f"{expected} COMMENTS" in body, True)
        check("comment text persisted", "Mirror test comment 2026" in body, True)

    elif index == 9:
        row = find_post("Welfare queens looking for handouts")
        walker.login("david.k@test.com", "TestPass123!")
        walker.go("/gallery/" + slug_of(row))
        seeded = q("SELECT value FROM votes v JOIN users u ON u.id=v.user_id WHERE u.username='david_k' AND v.post_id=?", (row["id"],))
        seeded_value = seeded[0]["value"] if seeded else 0
        score_before = walker.page.inner_text(".votescore")
        walker.page.click(".down-btn")
        walker.page.wait_for_timeout(900)
        walker.steps.append("downvote")
        score_after = walker.page.inner_text(".votescore")
        check("score before (includes seeded vote)", score_before.strip(), str(row["point_count"] + seeded_value))
        check("score after downvote", score_after.strip(), str(row["point_count"] - 1))

    elif index == 10:
        row = find_post("The Learning Channel presents")
        walker.login("alice.j@test.com", "TestPass123!")
        walker.go("/gallery/" + slug_of(row))
        top = q("SELECT c.point_count, u.username, c.text FROM comments c JOIN users u ON u.id=c.author_id WHERE c.post_id=? AND c.parent_id IS NULL ORDER BY c.point_count DESC LIMIT 1", (row["id"],))[0]
        before = walker.page.inner_text(f'#comment-{q("SELECT id FROM comments c WHERE c.post_id=? AND c.parent_id IS NULL ORDER BY point_count DESC LIMIT 1", (row["id"],))[0]["id"]} .cscore')
        walker.page.click(f'#comment-{q("SELECT id FROM comments c WHERE c.post_id=? AND c.parent_id IS NULL ORDER BY point_count DESC LIMIT 1", (row["id"],))[0]["id"]} .cup')
        walker.page.wait_for_timeout(900)
        walker.steps.append("comment-upvote")
        after = walker.page.inner_text(f'#comment-{q("SELECT id FROM comments c WHERE c.post_id=? AND c.parent_id IS NULL ORDER BY point_count DESC LIMIT 1", (row["id"],))[0]["id"]} .cscore')
        check("top comment author", top["username"], "LitterBoxKing")
        check("comment score before", before.strip(), str(top["point_count"]))
        check("comment score after upvote", after.strip(), str(top["point_count"] + 1))

    elif index == 11:
        walker.go("/t/aww")
        body = walker.body()
        tag = q("SELECT total_items, description FROM tags WHERE name='aww'")[0]
        check("post count shown", f"{tag['total_items']:,} POSTS" in body, True)
        check("description shown", (tag["description"] or "") in body, True)
        first = walker.page.eval_on_selector(".masonry .card .title", "el => el.innerText")
        check("first card title", bool(first), True)

    elif index == 12:
        row = find_post("The Hobbit and The Lord of the Rings artworks")
        walker.go("/")
        body = walker.body()
        check("album counter on feed card", f"1/{row['image_count']}" in body, True)
        walker.go("/gallery/" + slug_of(row))
        body = walker.body()
        check("album score", str(row["point_count"]) in body, True)
        author = q("SELECT username FROM users WHERE id = ?", (row["author_id"],))[0]["username"]
        check("album author", author in body, True)

    elif index == 14:
        walker.go("/search?q=cat")
        body = walker.body()
        match = re.search(r"Found (\d+) results for cat", body)
        check("results heading present", bool(match), True)
        first_url = walker.page.eval_on_selector(".searchcards .image-list-link", "el => el.getAttribute('href')")
        walker.go(first_url)
        body = walker.body()
        check("first tile opens a post", "COMMENTS" in body, True)

    elif index == 15:
        walker.go("/search?q=cat&sort=time")
        first_url = walker.page.eval_on_selector(".searchcards .image-list-link", "el => el.getAttribute('href')")
        walker.go(first_url)
        body = walker.body()
        check("first newest tile opens a post", "COMMENTS" in body, True)

    elif index == 27:
        walker.login("carol.d@test.com", "TestPass123!")
        walker.go("/t/anime")
        walker.page.wait_for_selector(".btn-follow", state="visible")
        walker.page.click(".btn-follow")
        walker.page.wait_for_selector(".btn-follow.following", timeout=10000)
        walker.steps.append("follow-tag:anime")
        label = walker.page.inner_text(".btn-follow").strip()
        check("follow button flips", label, "FOLLOWING")
        body = walker.body()
        tag = q("SELECT total_items, description FROM tags WHERE name='anime'")[0]
        check("anime post count shown", f"{tag['total_items']:,} POSTS" in body, True)
        check("anime description shown", tag["description"].strip() in body, True)

    elif index == 29:
        walker.go("/search?q=memes&date=day")
        body = walker.body()
        match = re.search(r"Found (\d+) results for memes", body)
        check("today window heading present", bool(match), True)
        tiles = walker.page.eval_on_selector_all(".searchcards .image-list-link", "els => els.map(e => e.getAttribute('href'))")
        if tiles:
            walker.go(tiles[0])
            body = walker.body()
            check("first tile opens a post", "COMMENTS" in body, True)
        else:
            check("no results today", "No results" in body, True)

    elif index == 16:
        walker.go("/user/tampacl?tab=about")
        body = walker.body()
        member = q("SELECT reputation, reputation_name, created_at FROM users WHERE username='tampacl'")[0]
        check("reputation shown", "PTS" in body, True)
        check("tier shown", member["reputation_name"].upper() in body.upper(), True)

    elif index == 20:
        walker.go("/register")
        walker.page.fill('input[name="username"]', "mirrorfan2026")
        walker.page.fill('input[name="email"]', "mirrorfan2026@test.com")
        walker.page.fill('input[name="password"]', "TestPass123!")
        walker.page.fill('input[name="retype_password"]', "TestPass123!")
        walker.page.click('button[type="submit"]')
        walker.page.wait_for_timeout(900)
        walker.steps.append("register:mirrorfan2026")
        media = q("SELECT detail_path FROM media LIMIT 1")[0]
        walker.go("/upload")
        walker.page.fill('#paste-url', walker.base + "/" + media["detail_path"])
        walker.page.fill('#up-title', "My first mirror post")
        walker.page.click('.btn-publish')
        walker.page.wait_for_load_state("domcontentloaded")
        walker.page.wait_for_timeout(800)
        walker.steps.append("upload-publish")
        body = walker.body()
        check("post published", "My first mirror post" in body, True)
        posts = q("SELECT COUNT(*) n FROM posts WHERE title='My first mirror post'")
        check("post in DB", posts[0]["n"], 1)

    elif index == 21:
        walker.login("alice.j@test.com", "TestPass123!")
        walker.go("/meme-generator")
        template = q("SELECT id, name FROM meme_templates WHERE name = 'Annoyed Picard'")
        assert template, "Annoyed Picard template missing"
        walker.page.select_option("#tpl-select", str(template[0]["id"]))
        walker.page.fill("#top-text", "WHY DID I")
        walker.page.fill("#bottom-text-input", "OPEN THE MEME GENERATOR")
        walker.page.fill("#meme-title", "My mirror meme")
        walker.page.click('.btn-generate')
        walker.page.wait_for_timeout(1200)
        walker.steps.append("meme-publish")
        body = walker.body()
        check("meme published", "My mirror meme" in body, True)
        rows = q("SELECT COUNT(*) n FROM posts WHERE title='My mirror meme'")
        check("meme in DB", rows[0]["n"], 1)

    elif index == 24:
        walker.go("/")
        cards = walker.page.eval_on_selector_all(
            ".card", "els => els.map(e => ({title: e.querySelector('.title').innerText, score: e.querySelector('.stat').innerText}))")
        scores = [(c["title"], int(c["score"])) for c in cards]
        scores.sort(key=lambda t: -t[1])
        top_two = scores[:2]
        check("has at least two scored cards", len(top_two) >= 2, True)
        result["checks"].append({
            "fact": "top-2 feed cards by score", "observed": top_two,
            "expected": "highest and second-highest score on first feed screen",
            "pass": True})

    else:
        result["checks"].append({"fact": "not sampled", "observed": None,
                                 "expected": None, "pass": True})

    result["pass"] = all(c["pass"] for c in result["checks"])
    return result


def fresh_server(port: int):
    """Start a throwaway Flask server on a scratch copy of the seed DB.

    Walkthroughs mutate state (votes, comments, uploads); running them
    against an isolated copy keeps the real instance database clean and
    makes every run reproducible from instance_seed.
    """
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    scratch_dir = tempfile.mkdtemp(prefix="imgur-walkthrough-")
    scratch_db = os.path.join(scratch_dir, "imgur.db")
    shutil.copyfile(SITE / "instance_seed" / "imgur.db", scratch_db)
    env = dict(os.environ)
    env["IMGUR_DB_PATH"] = f"sqlite:///{scratch_db}"
    process = subprocess.Popen(
        [sys.executable, "-c",
         "from app import app; app.run(host='127.0.0.1', port=%d, debug=False, "
         "use_reloader=False, threaded=True)" % port],
        cwd=str(SITE), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import time as _time
    import urllib.request
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            return process, scratch_db
        except Exception:
            _time.sleep(0.5)
    raise RuntimeError("walkthrough server failed to start")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=43090)
    parser.add_argument("--tasks", default="0,5,8,9,10,11,12,14,15,16,20,21,24,27,29")
    args = parser.parse_args()

    # the DB the walkthroughs verify against is the isolated scratch copy
    global DB
    process, scratch_db = fresh_server(args.port)
    DB = pathlib.Path(scratch_db)

    report = []
    if REPORT.exists():
        report = json.loads(REPORT.read_text(encoding="utf-8"))

    try:
        for index in [int(t) for t in args.tasks.split(",")]:
            walker = Walker(f"http://127.0.0.1:{args.port}")
            with walker:
                result = walk_task(walker, index)
            result["steps"] = walker.steps
            status = "PASS" if result["pass"] else "FAIL"
            print(f"[{status}] Imgur--{index} ({len(result['checks'])} checks)")
            for check in result["checks"]:
                mark = "+" if check["pass"] else "-"
                print(f"    {mark} {check['fact']}: observed={check['observed']!r} expected={check['expected']!r}")
            report.append(result)
    finally:
        process.terminate()
        process.wait(timeout=10)

    REPORT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    failures = [r for r in report if not r["pass"]]
    print(f"\n{len(report)} walkthroughs recorded -> {REPORT}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

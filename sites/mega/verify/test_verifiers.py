#!/usr/bin/env python3
"""No-op / pass / shortcut / wrong-answer matrix for MEGA verifiers.

Uses the locally generated seed (sites/mega/instance_seed/mega.db). No Docker
and no API key: every verifier is invoked with --no_llm true.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
SEED = SITE / "instance_seed" / "mega.db"
BASE = "http://localhost:40028"
TASKS = list(range(18))
READ_ONLY = {0, 1, 9, 10, 11, 13, 15}


def png_bytes(width, height, rgb):
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            row.extend((
                (rgb[0] + x + y) % 256,
                (rgb[1] + x * 3) % 256,
                (rgb[2] + y * 5) % 256,
            ))
        rows.append(b"\x00" + bytes(row))
    raw = b"".join(rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(
            ">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def write_shots(run_dir, count=4):
    shots = run_dir / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    colors = [(220, 30, 40), (20, 90, 180), (16, 132, 90), (240, 180, 40), (30, 30, 30)]
    for i in range(count):
        (shots / f"step_{i:03d}.png").write_bytes(png_bytes(640, 400, colors[i % len(colors)]))


def make_run(run_dir, task_id, paths, answer, params=None, extra_steps=None):
    run_dir = Path(run_dir)
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    write_shots(run_dir)
    steps = []
    urls = [BASE + "/"] + [BASE + p if p.startswith("/") else p for p in paths]
    if urls[-1] != urls[0] and len(urls) == 2:
        pass
    params = params or {}
    for i, url in enumerate(urls):
        last = i == len(urls) - 1
        step = {
            "step": i,
            "url": url,
            "title": "MEGA",
            "thought": "test",
            "action": "done" if last else "click",
            "params": {"text": answer, "success": True, **params} if last else params,
            "screenshot_before": f"step_{min(i, 3):03d}.png",
            "screenshot_after": f"step_{min(i + 1, 3):03d}.png",
        }
        steps.append(step)
    if extra_steps:
        steps.extend(extra_steps)
        steps[-1]["action"] = "done"
        steps[-1]["params"] = {"text": answer, "success": True, **params}
    traj = {
        "task_id": f"MEGA--{task_id}" if isinstance(task_id, int) else task_id,
        "task": "",
        "start_url": BASE + "/",
        "terminated": True,
        "termination_reason": "agent_done",
        "final_answer": answer,
        "success_self_report": True,
        "steps": steps,
        "verifier_path": f"sites/mega/verify/verify_{task_id}.py",
    }
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    return run_dir


def copy_db(src, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def mutate(path, statements):
    con = sqlite3.connect(path)
    try:
        for sql, params in statements:
            con.execute(sql, params)
        con.commit()
    finally:
        con.close()


def scalar(db, sql, params=()):
    con = sqlite3.connect(db)
    try:
        row = con.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def run_verifier(n, run_dir, initial, after):
    script = HERE / f"verify_{n}.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--run_dir", str(run_dir),
         "--initial_db", str(initial), "--after_db", str(after), "--no_llm", "true"],
        capture_output=True, text=True)
    try:
        verdict = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        verdict = {"pass": False, "reason": "unparseable", "evidence": [proc.stdout, proc.stderr]}
    verdict["_returncode"] = proc.returncode
    verdict["_stderr"] = proc.stderr
    return verdict


def expect(label, verdict, should_pass):
    ok = bool(verdict.get("pass"))
    if ok != should_pass:
        raise SystemExit(
            f"{label}: expected pass={should_pass} got pass={ok} reason={verdict.get('reason')!r}\n"
            f"evidence={verdict.get('evidence')}\nstderr={verdict.get('_stderr')}")
    print(f"  OK {label}: pass={ok} reason={verdict.get('reason')!r}")


def pass_paths(n, alice_broll, alice_launch, cmd_id, chrome_id):
    login = ["/login"]
    if n == 0:
        return ["/storage"], "Mobile and desktop access; File and folder links."
    if n == 1:
        return ["/help", "/help/save-your-recovery-key"], "Do not share it with support or teammates."
    if n == 2:
        return login + ["/plans/pro-ii", "/checkout"], "Pro II yearly in checkout."
    if n == 3:
        return login + ["/plans/pro-i", "/checkout", "/orders/MEGA-TEST-ALICE"], "Completed Pro I monthly checkout."
    if n == 4:
        return login + ["/plans/pro-ii", "/plans/business-pro", "/checkout"], "Business Pro includes more users (5)."
    if n == 5:
        return login + ["/cloud", f"/cloud/item/{alice_broll}"], "Shared Atlas b-roll selects.mov."
    if n == 6:
        return login + ["/cloud", f"/cloud/item/{alice_launch}"], "Atlas launch footage.mov is the largest MOV."
    if n == 7:
        return login + ["/cloud", "/cloud?folder=/Projects/Atlas"], "Created Q3 Press Kit and uploaded press-summary.pdf."
    if n == 8:
        return login + ["/vault"], "Saved Atlas staging site vault entry."
    if n == 9:
        return login + ["/vault", "/vault?q=weak"], "Old vendor FTP has no 2FA."
    if n == 10:
        return ["/downloads", f"/downloads/{cmd_id}"], "sha256-megacmdsetup64-exe-webharbor"
    if n == 11:
        return ["/downloads", f"/downloads/{chrome_id}"], "MEGA Pass Chrome extension version 1.12.4"
    if n == 12:
        return login + ["/pricing?category=objectstorage", "/plans/s4-fixed-storage", "/checkout"], "S4 Fixed Storage in checkout."
    if n == 13:
        return ["/business"], "Team dashboard"
    if n == 14:
        return login + ["/contact", "/support/tickets/MEGA-T-TEST"], "Submitted High priority Object storage ticket."
    if n == 15:
        return ["/help", "/help/recover-from-ransomware"], "Disconnect the affected device."
    if n == 16:
        return login + ["/account/edit", "/account"], "Company is Riverlight Studio Labs; 2FA and recovery key enabled."
    if n == 17:
        return login + ["/plans/pro-flexi", "/plans/s4-fixed-storage", "/checkout"], "Pro Flexi yearly in checkout."
    raise AssertionError(n)


def apply_pass_mutation(n, after):
    alice = scalar(after, "SELECT id FROM users WHERE email=?", ("alice.j@test.com",))
    bob = scalar(after, "SELECT id FROM users WHERE email=?", ("bob.c@test.com",))
    pro_i = scalar(after, "SELECT id FROM plans WHERE slug=?", ("pro-i",))
    if n == 3:
        mutate(after, [(
            "INSERT INTO subscription_orders (user_id, plan_id, order_number, billing_cycle, seats, "
            "subtotal, tax, total, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (alice, pro_i, "MEGA-TEST-ALICE", "monthly", 1, 10.99, 0.77, 11.76, "active", "2026-09-14"),
        ), ("UPDATE users SET plan_id=? WHERE id=?", (pro_i, alice))])
    elif n == 5:
        mutate(after, [(
            "UPDATE cloud_items SET shared_with=?, share_link=? WHERE user_id=? AND name=?",
            ("bob.c@test.com, carol.d@test.com", "https://mega.nz/file/BROLL#test",
             alice, "Atlas b-roll selects.mov"),
        )])
    elif n == 6:
        mutate(after, [("UPDATE cloud_items SET favorite=1 WHERE user_id=? AND name=?",
                        (alice, "Atlas launch footage.mov"))])
    elif n == 7:
        mutate(after, [
            ("INSERT INTO cloud_items (user_id, name, slug, item_type, folder, extension, size_mb, "
             "modified_at, sync_status, shared_with, share_link, favorite, backup_source, content_summary) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
             (alice, "Q3 Press Kit", "q3-press-kit-test", "folder", "/Projects/Atlas", "", 0,
              "2026-09-14", "Synced", "", "", 0, "", "User-created folder")),
            ("INSERT INTO cloud_items (user_id, name, slug, item_type, folder, extension, size_mb, "
             "modified_at, sync_status, shared_with, share_link, favorite, backup_source, content_summary) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
             (alice, "press-summary.pdf", "press-summary-test", "file",
              "/Projects/Atlas/Q3 Press Kit", "pdf", 4.2, "2026-09-14", "Synced", "", "", 0, "", "Upload")),
        ])
    elif n == 8:
        mutate(after, [(
            "INSERT INTO vault_items (user_id, title, slug, username, site_url, category, strength, "
            "last_changed, two_factor, notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (alice, "Atlas staging site", "atlas-staging-site-test", "alice_editor",
             "https://staging.atlas.example", "Client", "Strong", "2026-09-14", 1, "new"),
        )])
    elif n == 14:
        mutate(after, [(
            "INSERT INTO support_tickets (user_id, ticket_number, subject, category, priority, status, "
            "message, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (bob, "MEGA-T-TEST", "Need help estimating S4 egress for quarterly archives",
             "Object storage", "High", "Open",
             "Please help estimate S4 egress for quarterly archives.", "2026-09-14"),
        )])
    elif n == 16:
        mutate(after, [("UPDATE users SET company=? WHERE id=?", ("Riverlight Studio Labs", alice))])


def billing_params(n):
    if n in {2, 17}:
        return {"billing_cycle": "yearly"}
    if n == 3:
        return {"billing_cycle": "monthly"}
    return {}


def main():
    if not SEED.exists():
        raise SystemExit(f"missing seed DB {SEED}; generate it by importing sites/mega/app.py")
    alice_broll = scalar(SEED, "SELECT slug FROM cloud_items WHERE name=? AND user_id=("
                         "SELECT id FROM users WHERE email=?)",
                         ("Atlas b-roll selects.mov", "alice.j@test.com"))
    alice_launch = scalar(SEED, "SELECT slug FROM cloud_items WHERE name=? AND user_id=("
                          "SELECT id FROM users WHERE email=?)",
                          ("Atlas launch footage.mov", "alice.j@test.com"))
    cmd_id = scalar(SEED, "SELECT id FROM downloads WHERE package_name=?", ("MEGAcmdSetup64.exe",))
    chrome_id = scalar(SEED, "SELECT id FROM downloads WHERE package_name=?",
                       ("MEGA Pass Chrome extension",))

    failures = 0
    with tempfile.TemporaryDirectory(prefix="mega-verify-") as tmp:
        tmp = Path(tmp)
        for n in TASKS:
            print(f"task {n}")
            initial = copy_db(SEED, tmp / f"t{n}" / "initial.db")
            # --- no-op ---
            after = copy_db(SEED, tmp / f"t{n}" / "noop-after.db")
            run = make_run(tmp / f"t{n}" / "noop", n, [], "")
            expect(f"{n} no-op", run_verifier(n, run, initial, after), False)
            # --- shortcut: right answer, homepage only ---
            paths, answer = pass_paths(n, alice_broll, alice_launch, cmd_id, chrome_id)
            run = make_run(tmp / f"t{n}" / "shortcut", n, [], answer, params=billing_params(n))
            expect(f"{n} shortcut", run_verifier(n, run, initial, copy_db(SEED, tmp / f"t{n}" / "short-after.db")), False)
            # --- wrong answer on the real pages (read-only / comparison) ---
            run = make_run(tmp / f"t{n}" / "wrong", n, paths, "this is not the on-page answer",
                           params=billing_params(n))
            after_wrong = copy_db(SEED, tmp / f"t{n}" / "wrong-after.db")
            apply_pass_mutation(n, after_wrong)
            if n in READ_ONLY or n in {4, 6}:
                expect(f"{n} wrong-answer", run_verifier(n, run, initial, after_wrong), False)
            # --- genuine pass ---
            after_pass = copy_db(SEED, tmp / f"t{n}" / "pass-after.db")
            apply_pass_mutation(n, after_pass)
            run = make_run(tmp / f"t{n}" / "pass", n, paths, answer, params=billing_params(n))
            expect(f"{n} pass", run_verifier(n, run, initial, after_pass), True)
        # stateful: self-report without DB write
        for n in (3, 5, 6, 7, 8, 14, 16):
            paths, answer = pass_paths(n, alice_broll, alice_launch, cmd_id, chrome_id)
            initial = copy_db(SEED, tmp / f"state{n}" / "initial.db")
            after = copy_db(SEED, tmp / f"state{n}" / "after.db")
            run = make_run(tmp / f"state{n}" / "run", n, paths, answer, params=billing_params(n))
            expect(f"{n} state-mismatch", run_verifier(n, run, initial, after), False)
    print("all verifier matrix checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

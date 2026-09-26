"""Deterministic verifier contract tests for the 21 soundcloud tasks.

Covers, per task: the honest trajectory (from the reviewer's live runs, frozen
in fixtures_data.SPECS) MUST PASS; a no-op run (homepage only, empty answer,
clean DB) MUST FAIL; a knowledge-shortcut (correct answer + delta, homepage-only
navigation) MUST FAIL; a wrong answer MUST FAIL; a state-mismatch (success
claim, no DB delta) MUST FAIL for stateful tasks. Read-only tasks MUST FAIL on
a mutated after-DB. Package tampering (task_id mismatch, off-site URL, missing
screenshot, non-done trajectory, undecodable screenshot) MUST fail closed.

Re-review sync (2026-09-26): T18 is stateful since the redesign (Bob reposts
'2021 Vibes'); T3 is a clean single-delta stateful task again (Carol, +1 like —
the old Alice pre-like fixture collision is gone), so it joins the generic
state-mismatch test.

No LLM: snapshots are seed copies mutated through sqlite, trajectories are
written in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, RunBuilder, copy_db, exec_sql, honest_run,  # noqa: E402
                       noop_run, run_verifier, shortcut_run, state_mismatch_run,
                       task_ques, wrong_answer_run, acquire_seed)
from fixtures_data import SPECS  # noqa: E402

STATEFUL = {3, 5, 6, 7, 8, 11, 13, 14, 15, 16, 18, 20}
READ_ONLY = {0, 1, 2, 4, 9, 10, 12, 17, 19}
ALL = sorted(STATEFUL | READ_ONLY)

# plausible but wrong answers per task (contradict frozen ground truth)
WRONG_ANSWERS = {
    0: "US top 3: 'Is Dat Right?' 969,416 plays, 'Backwards' 281,716, 'Cowgirl' "
       "1,453,008. UK top 3: 'Good Girl' 1,294,858, 'Kolter' 938,222, 'On 2nite' "
       "2,399,647. The US #1 has more plays. US #1 shows 41.6K likes; UK #1 "
       "shows 49.9K likes.",
    1: "Top five country tracks posted: 'Last Thing You Need' 7 days ago, "
       "'P.O.S.' 9 days ago, \"That's Just Me\" 2 months ago, 'Think As You "
       "Drunk' 5 months ago, 'Take Me Back' 3 months ago. Atlantic Records has "
       "502,207 followers; Riley Green 31,085. Most plays: 'Take Me Back'.",
    2: "The #9 artist is Lil Baby, not verified, 1,988,726 followers, 235 "
       "tracks. Popular: 'Mrs. Trendsetter' 4,045,616 plays on RCA, 'Dead "
       "Fresh' 2,468,396 on RCA, 'What She Like' 1,468,904, 'Guaranteed' "
       "1,410,636. 'Dead Fresh' is US Hip Hop #5 and UK Hip Hop #2.",
    3: "Miley Cyrus has 1,517,358 followers, 344 tracks, follows 1 person. "
       "Liked 'REDLIGHTS' — comments heading 47, label RCA. It's #4 on the US "
       "Pop chart.",
    4: "Rod Wave is from Tampa with 1,482,903 followers. Popular five: 'Piece "
       "Of Your Love' 1,672,103 plays 3:44, 'Hustle' 1,205,741 2:21, 'Dope "
       "Girl' 803,704 2:10, 'TP' 653,692 2:50, 'Kiss Me Interlude' 572,928 "
       "3:04. Only 'Piece Of Your Love' is over three minutes. Label: Alamo "
       "Records. Newest comment by jaylan at 1:55.",
    5: "Playlist 'Heavy Bag Rounds' has 3 tracks: 'Is Dat Right?', 'Backwards' and "
       "'Dead Fresh'.",
    6: "Unliked 'Cloonee & Prospa - Good Girl' by Cloter and followed them; they have "
       "105,235 followers.",
    7: "Go costs $5.99/month with a 14-day trial; Go+ $12.99 with a 60-day trial. "
       "David pays $99.00 yearly, renews October 26, 2027. Uploaded 'Night Shift "
       "Demo' at /david_k/night-shift-demo-2.",
    8: "Uploaded 'Midnight Sketch' at /alice_j/midnight-sketch-2 — duration 3:55. "
       "Added to 'Late Night Drive'; it now has 5 tracks with 'Midnight Sketch' "
       "at position 2.",
    9: "Rock top five: 'Joseph' 66,993 plays 4:08; 'Benny Boy' 49,856 2:07; 'oh "
       "yeah?' 211,562 0:31; 'It Doesn't Matter' 295,496 3:44; '12 Steps' "
       "218,455 3:10. The Texas artist is Falling In Reverse from Houston with "
       "'Joseph'.",
    10: "Four crossovers: 'Backwards' (#2/#1, 280,717 plays), 'Something I Need' "
         "(#4/#2, 176,446), 'Bass Persuades' (#6/#4, 137,892), 'Last Thing You "
         "Need' (#10/#3, 222,933). Most likes: 'Bass Persuades' — Miley Cyrus "
         "has 1,517,357 followers.",
    11: "Kaskade is from Chicago, US with 498,942 followers. Most-played track "
        "'2021 Vibes' added to 'Sunset Sets'.",
    12: "UK Dance top five: 'Good Girl' 1,294,859 plays, 'Kolter' 938,223, 'On "
        "2nite' 2,399,648, 'Masterplan' 1,077,256, 'Sun is Shining' 460,801. "
        "Most likes: 'Good Girl' — Cloonee from London has 105,235 followers.",
    13: "UK Hip Hop #1 'Dead Fresh' by Lil Baby 2,468,396 plays — after like+repost "
        "64K likes, 331 reposts. #2 'Lil azz-make it out' by dirty mick 463,676 "
        "— 7.63K likes, 32 reposts. The #2 has more plays.",
    14: "Commented 'great mix!' at 1:30 on 'Bass Persuades Remixx' (heading shows "
        "47) and 'so smooth' at 0:45 on \"Tape B x Effin - I'll Never Know\" "
        "(heading 125). The #1 has more plays.",
    15: "In the order played: Different Religion, Bass Persuades, DARK SIDE. Labels: "
        "'DARK SIDE' on 10K Projects, 'Bass Persuades' on RCA, 'Different "
        "Religion' on RCA. Pre-seed history: 'Is Dat Right?', 'Backwards', "
        "'Cowgirl'.",
    16: "Most-played liked track 'Is Dat Right?' with 969,417 plays on Hitmaker "
        "Music Group. Added to 'Late Night Drive'. Removed 'Piece Of Your Love' "
        "(1,672,103 plays, 3:46). Remaining: 'Ghetto Love Story', 'Cowgirl', "
        "'Morgan Wallen - Last Thing You Need'.",
    17: "4 of the top 10 folk tracks are by artists over 100,000 followers: Rod Wave, "
        "Steve Lacy, Alyssa Grace and Malcolm Todd.",
    18: "Found 5 tracks and 3 people. Most-played LUCKI track is 'Luckiest Man Alive' "
         "with 46,393 plays on label EMPIRE. LUCKI is from Detroit with 498,943 "
         "followers. Related: 'Redbone' by Childish Gambino 92,777,387 plays; "
         "'Wrong Place' by Hurricane Wisdom 223,685.",
    19: "Steve Lacy: Rock #4 'oh yeah?' (211,562 plays, label L-M Records/RCA "
        "Records) and Folk #5 'nothing' (85,001 plays, same label). Profile: "
        "377,395 followers, 53 tracks. Popular top three: 'Buttons' 1,059,417; "
        "'oh yeah?' 211,562; 'doom' 128,219. 'nothing' is at UK Indie #4. UK "
        "Indie #1: 'PASSENGER' by Alex Warren — 128,219 plays; his profile has "
        "119 followers.",
    20: "Old plan Go+ at $15.99 monthly; new plan Next Pro at $11.99 monthly; "
        "the difference is $4.00. Renews September 26, 2027. After signing back "
        "in the banner shows Go+.",
}


# ---------------------------------------------------------------- honest PASS
@pytest.mark.parametrize("task_no", ALL)
def test_honest_pass(tmp_path, task_no):
    run = honest_run(tmp_path, task_no)
    verdict = run_verifier(task_no, run, expect_pass=True)
    assert verdict["reason"] == "all checks passed"


# ---------------------------------------------------------------- no-op FAIL
@pytest.mark.parametrize("task_no", ALL)
def test_noop_fail(tmp_path, task_no):
    run = noop_run(tmp_path, task_no)
    verdict = run_verifier(task_no, run, expect_pass=False)
    assert any(f in verdict["reason"] for f in
               ("nonempty_answer", "visited_", "answer", "missing", "terminated"))


# ---------------------------------------------------------------- shortcut FAIL
@pytest.mark.parametrize("task_no", ALL)
def test_shortcut_fail(tmp_path, task_no):
    run = shortcut_run(tmp_path, task_no)
    verdict = run_verifier(task_no, run, expect_pass=False)
    assert "visited_" in verdict["reason"]


# ---------------------------------------------------------------- wrong answer FAIL
@pytest.mark.parametrize("task_no", ALL)
def test_wrong_answer_fail(tmp_path, task_no):
    run = wrong_answer_run(tmp_path, task_no, WRONG_ANSWERS[task_no])
    verdict = run_verifier(task_no, run, expect_pass=False)
    assert verdict["reason"] != "all checks passed"


# ---------------------------------------------------------------- state mismatch FAIL
# T3 is included again: since the fix the seed has no pre-like for Carol on the
# target, so a clean DB with a success claim must FAIL (single legal delta).
@pytest.mark.parametrize("task_no", sorted(STATEFUL))
def test_state_mismatch_fail(tmp_path, task_no):
    run = state_mismatch_run(tmp_path, task_no)
    verdict = run_verifier(task_no, run, expect_pass=False)
    assert verdict["reason"] != "all checks passed"


# ---------------------------------------------------------------- read-only tamper FAIL
@pytest.mark.parametrize("task_no", sorted(READ_ONLY))
def test_readonly_tamper_fail(tmp_path, task_no):
    run = honest_run(tmp_path, task_no)
    db = sqlite3.connect(run / "after.db")
    db.execute("UPDATE tracks SET plays = plays + 1 WHERE id = "
               "(SELECT id FROM tracks ORDER BY id LIMIT 1)")
    db.execute("INSERT INTO likes (user_id, track_id, created_at) "
               "VALUES (1, 2390382459, '2026-09-26 00:00:00.000000')")
    db.commit()
    db.close()
    verdict = run_verifier(task_no, run, expect_pass=False)
    assert "after_rows_unchanged" in verdict["reason"]


# ---------------------------------------------------------------- package tampering
def test_tampered_task_id_fails(tmp_path):
    run = honest_run(tmp_path, 0)
    traj = json.loads((run / "trajectory.json").read_text())
    traj["task_id"] = "SoundCloud--19"
    (run / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(0, run, expect_pass=False)
    assert "task_id_match" in verdict["reason"]


def test_offsite_url_fails(tmp_path):
    run = honest_run(tmp_path, 4)
    traj = json.loads((run / "trajectory.json").read_text())
    traj["steps"][1]["url_after"] = "https://soundcloud.com/childish-gambino/redbone"
    (run / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(4, run, expect_pass=False)
    assert "same_origin_port" in verdict["reason"]


def test_missing_screenshot_fails(tmp_path):
    run = honest_run(tmp_path, 12)
    (run / "screenshots" / "step_002.png").unlink()
    verdict = run_verifier(12, run, expect_pass=False)
    assert "screenshots_decode" in verdict["reason"]


def test_undecodable_screenshot_fails(tmp_path):
    run = honest_run(tmp_path, 12)
    (run / "screenshots" / "step_002.png").write_bytes(b"not a png at all")
    verdict = run_verifier(12, run, expect_pass=False)
    assert "screenshots_decode" in verdict["reason"]


def test_unterminated_trajectory_fails(tmp_path):
    run = honest_run(tmp_path, 18)
    traj = json.loads((run / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    traj["final_answer"] = None
    (run / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(18, run, expect_pass=False)
    assert "terminated_agent_done" in verdict["reason"] or "nonempty_answer" in verdict["reason"]


# ---------------------------------------------------------------- adversarial DB deltas
def test_wrong_like_target_fails(tmp_path):
    """A like on the wrong track must fail T3 even with a matching answer."""
    run = honest_run(tmp_path, 3)
    db = sqlite3.connect(run / "after.db")
    db.execute("DELETE FROM likes WHERE id=24")
    db.execute("UPDATE tracks SET likes = 6770 WHERE id=2393437119")
    db.execute("INSERT INTO likes (id, user_id, track_id, created_at) "
               "VALUES (24, 3, 2398849314, '2026-09-26 00:00:00.000000')")
    db.execute("UPDATE tracks SET likes = likes + 1 WHERE id=2398849314")
    db.commit()
    db.close()
    verdict = run_verifier(3, run, expect_pass=False)
    assert "like_row_is_carol_on_target" in verdict["reason"] or "like_counter_bumped" in verdict["reason"]


def test_t3_preseeded_like_would_fail_closed(tmp_path):
    """The old fixture collision (pre-existing like on the target) must now
    FAIL T3: the only legal delta is exactly +1 like by Carol."""
    run = honest_run(tmp_path, 3)
    db = sqlite3.connect(run / "after.db")
    db.execute("DELETE FROM likes WHERE id=24")          # no like at all
    db.execute("UPDATE tracks SET likes = 6770 WHERE id=2393437119")
    db.commit()
    db.close()
    verdict = run_verifier(3, run, expect_pass=False)
    assert "one_like_added" in verdict["reason"]


def test_extra_playlist_entry_fails(tmp_path):
    """Heavy Bag Rounds with a third track must fail T5."""
    run = honest_run(tmp_path, 5)
    db = sqlite3.connect(run / "after.db")
    db.execute("INSERT INTO user_playlist_tracks (id, playlist_id, track_id, position, added_at) "
               "VALUES (15, 5, 2360196407, 3, '2026-09-26 00:00:00.000000')")
    db.commit()
    db.close()
    verdict = run_verifier(5, run, expect_pass=False)
    assert "entries_are_the_two_tracks" in verdict["reason"] or "two_entries_added" in verdict["reason"]


def test_wrong_subscription_cycle_fails(tmp_path):
    """A monthly Next Pro subscription must fail T7 (yearly required)."""
    run = honest_run(tmp_path, 7)
    db = sqlite3.connect(run / "after.db")
    db.execute("UPDATE subscriptions SET cycle='monthly', amount=1599, "
               "renews_at='2026-10-26 00:00:00.000000' WHERE user_id=4")
    db.commit()
    db.close()
    verdict = run_verifier(7, run, expect_pass=False)
    assert "subscription_row" in verdict["reason"]


def test_t7_upload_missing_fails(tmp_path):
    """The Next Pro switch alone (no 'Night Shift Demo' upload) must fail T7."""
    run = honest_run(tmp_path, 7)
    db = sqlite3.connect(run / "after.db")
    db.execute("DELETE FROM tracks WHERE permalink='night-shift-demo'")
    db.execute("UPDATE artists SET track_count = 0 WHERE permalink='david_k'")
    db.commit()
    db.close()
    verdict = run_verifier(7, run, expect_pass=False)
    assert "one_track_added" in verdict["reason"] or "track_row" in verdict["reason"]


def test_t13_wrong_repost_target_fails(tmp_path):
    """Reposts on the wrong tracks must fail T13 even with a matching answer."""
    run = honest_run(tmp_path, 13)
    db = sqlite3.connect(run / "after.db")
    db.execute("DELETE FROM reposts WHERE id=9")
    db.execute("UPDATE tracks SET reposts = 331 WHERE id=2360196407")
    db.execute("INSERT INTO reposts (id, user_id, track_id, created_at) "
               "VALUES (9, 2, 2390382459, '2026-09-26 00:00:00.000000')")
    db.execute("UPDATE tracks SET reposts = reposts + 1 WHERE id=2390382459")
    db.commit()
    db.close()
    verdict = run_verifier(13, run, expect_pass=False)
    assert "repost_row_t1" in verdict["reason"] or "counters_t1" in verdict["reason"]


def test_t18_missing_repost_fails(tmp_path):
    """The research chain without the repost delta must fail T18."""
    run = honest_run(tmp_path, 18)
    db = sqlite3.connect(run / "after.db")
    db.execute("DELETE FROM reposts WHERE id=9")
    db.execute("UPDATE tracks SET reposts = 1422 WHERE id=1553767969")
    db.commit()
    db.close()
    verdict = run_verifier(18, run, expect_pass=False)
    assert "one_repost_added" in verdict["reason"]


def test_t16_wrong_removed_track_fails(tmp_path):
    """Removing the wrong playlist entry must fail T16."""
    run = honest_run(tmp_path, 16)
    db = sqlite3.connect(run / "after.db")
    db.execute("DELETE FROM user_playlist_tracks WHERE id=2")   # Piece Of Your Love
    db.execute("UPDATE user_playlist_tracks SET position = position - 1 WHERE playlist_id=1 AND id > 2")
    db.commit()
    db.close()
    verdict = run_verifier(16, run, expect_pass=False)
    assert "removed_is_morgan_wallen" in verdict["reason"] or "final_order_three_tracks" in verdict["reason"]


def test_seed_drift_fails_closed(tmp_path):
    """A drifted initial DB (not the frozen seed) must fail read-only tasks."""
    run = honest_run(tmp_path, 12)
    db = sqlite3.connect(run / "initial.db")
    db.execute("UPDATE tracks SET plays = plays + 1 WHERE id = 2328694826")
    db.commit()
    db.close()
    db = sqlite3.connect(run / "after.db")
    db.execute("UPDATE tracks SET plays = plays + 1 WHERE id = 2328694826")
    db.commit()
    db.close()
    verdict = run_verifier(12, run, expect_pass=False)
    assert "initial_is_seed" in verdict["reason"]


# ------------------------------------------------------- T19 re-frozen adversarial
def test_t19_r2_shortcut_replay_fails(tmp_path):
    """The r2 honest-shortest 12-step route (both charts, both track pages,
    the profile, UK Indie — every value it gathers correct) must FAIL the
    re-frozen T19: the new anchors (the Popular tab and its #1/#3 track
    pages, the UK Indie #1 page, the #1 artist's profile) are not on that
    route, so the navigation gates and the new answer anchors both fail.
    Zero false positives against the old shortcut."""
    run = tmp_path / "t19_r2variant"
    run.mkdir(parents=True)
    b = RunBuilder(run, "SoundCloud--19")
    urls = [
        BASE,
        BASE + "/charts",
        BASE + "/music-charts-us/sets/rock",
        BASE + "/charts",
        BASE + "/music-charts-us/sets/folk",
        BASE + "/steevlacy/nothing",
        BASE + "/steevlacy/oh-yeah",
        BASE + "/steevlacy",
        BASE + "/charts",
        BASE + "/music-charts-uk/sets/indie",
    ]
    for i, u in enumerate(urls):
        b.add_step("navigate" if i == 0 else "click", u)
    b.finish("Steve Lacy: US Rock #3 'oh yeah?' \u2014 211,561 plays; US Folk #6 "
             "'nothing' \u2014 85,000 plays; profile: 377,394 followers, 52 tracks "
             "uploaded; 'oh yeah?' is also on the UK Indie chart at #3.")
    (run / "initial.db").write_bytes(acquire_seed().read_bytes())
    (run / "after.db").write_bytes(acquire_seed().read_bytes())
    verdict = run_verifier(19, run, expect_pass=False)
    assert "visited_" in verdict["reason"] or "answer" in verdict["reason"]


def test_t19_partial_new_facts_fails(tmp_path):
    """A trajectory that adds the Popular tab and its #1/#3 pages but never
    opens the UK Indie #1 page or the #1 artist's profile, with the answer
    naming the wrong #1 (values from the chart rows only), must FAIL."""
    run = tmp_path / "t19_partial"
    run.mkdir(parents=True)
    b = RunBuilder(run, "SoundCloud--19")
    spec = SPECS[19]
    for i, u in enumerate(spec["urls"]):
        if u.startswith(BASE + "/sam-heaney"):
            break
        b.add_step("navigate" if i == 0 else "click", u)
    b.add_step("click", BASE + "/music-charts-uk/sets/indie")
    b.finish("Steve Lacy: Rock #3 'oh yeah?' 211,561 plays; Folk #6 'nothing' "
             "85,000 plays; profile 377,394 followers, 52 tracks; popular: "
             "'Buttons' 1,059,416, 'oh yeah?' 211,561, 'doom' 128,218; UK Indie "
             "#1 'Guilty' by Sammi Heaney with 33.3K plays and 118 followers.")
    (run / "initial.db").write_bytes(acquire_seed().read_bytes())
    (run / "after.db").write_bytes(acquire_seed().read_bytes())
    verdict = run_verifier(19, run, expect_pass=False)
    assert "visited_indie1" in verdict["reason"] or "indie1" in verdict["reason"]

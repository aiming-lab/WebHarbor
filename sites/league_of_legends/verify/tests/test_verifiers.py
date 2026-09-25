"""Deterministic verifier contract tests for the 30 League of Legends tasks.

Covers, per task: the honest trajectory MUST PASS (stateful tasks run against a seed
copy mutated with exactly the compliant after-state); a no-op run (homepage only,
empty answer, clean DB) MUST FAIL; a wrong answer MUST FAIL; a shortcut (correct
answer, homepage-only navigation) MUST FAIL for every task (no LOL task is
homepage-surface by design). Read-only tasks MUST FAIL on a mutated after-DB;
stateful tasks MUST FAIL on a state-mismatch (no DB delta) and on a wrong/collateral
state delta. Package tampering (task_id mismatch, off-site URLs, missing screenshots,
non-done trajectory, tampered seed, unavailable DB) MUST fail closed.

No LLM: snapshots are seed copies mutated through sqlite, trajectories are hand-written
in the agent_demo/agent.py shape. The honest answers below were extracted from the
rendered DOM during the live honest runs (wh-lol-review-evidence/runs/) — the same
values the frozen-seed verifiers hardcode as ground truth.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, RunBuilder, _acquire_seed, build_run, copy_db,  # noqa: E402
                      mutate_db, noop_run, run_verifier, tiny_png)


SEED = _acquire_seed()

STATEFUL = {21, 22, 23, 24, 25}
READ_ONLY = sorted(set(range(30)) - STATEFUL)

CH = "/champions/"
NEWS = "/news/"
AATROX = "/champions/aatrox/"
MEL = "/champions/mel/"
AMBESSA = "/champions/ambessa/"
YUNARA = "/champions/yunara/"
SONA = "/champions/sona/"
NAAFIRI = "/champions/naafiri/"
VIEGO = "/champions/viego/"
MILIO = "/champions/milio/"
TRUNDLE = "/champions/trundle/"
HTP = "/how-to-play/"
PATCH_2619 = "/news/game-updates/league-of-legends-patch-26-19-notes/"
PATCH_2618 = "/news/game-updates/league-of-legends-patch-26-18-notes/"
MONK = "/news/dev/dev-modernizing-the-monk/"

# ---------------------------------------------------------------- honest fixtures
# (steps: [(path, action, params), ...], honest answer from the live DOM)
HONEST = {
    0: ([(CH, "goto", {}),
         (CH, "select", {"selector": 'select[name="role"]', "value": "Support"}),
         (CH, "select", {"selector": 'select[name="difficulty"]', "value": "High"}),
         (CH + "?role=Support&difficulty=High", "click",
          {"selector": ".roster-filters button"})],
        "Filtering the roster by the Support role and High difficulty shows 8 champions. "
        "The champions are: Bard, Fiddlesticks, Heimerdinger, Hwei, Renata Glasc, Swain, "
        "Vel'Koz, Xerath."),
    1: ([(CH, "goto", {}),
         (CH, "select", {"selector": 'select[name="role"]', "value": "Marksman"}),
         (CH, "select", {"selector": 'select[name="difficulty"]', "value": "Medium"}),
         (CH + "?role=Marksman&difficulty=Medium", "click",
          {"selector": ".roster-filters button"})],
        "Filtering the roster to Marksman champions with Medium difficulty lists 24 "
        "champions: Ashe, Caitlyn, Corki, Ezreal, Jayce, Jhin, Jinx, Kai'Sa, Kalista, "
        "Kayle, Kindred, Kog'Maw, Lucian, Quinn, Samira, Senna, Sivir, Smolder, Teemo, "
        "Tristana, Twitch, Xayah, Yunara, Zeri."),
    2: ([(CH, "goto", {}),
         (CH, "select", {"selector": 'select[name="difficulty"]', "value": "Low"}),
         (CH + "?difficulty=Low", "click", {"selector": ".roster-filters button"})],
        "Filtering the roster to Low difficulty champions matches 28 in total."),
    3: ([(CH, "goto", {}),
         (CH, "select", {"selector": 'select[name="sort"]', "value": "release"}),
         (CH + "?sort=release", "click", {"selector": ".roster-filters button"})],
        "Sorting the roster by Newest, the first five champions shown are: Naafiri, Hwei, "
        "Zaahen, Milio, Smolder."),
    4: ([(CH, "goto", {}),
         (CH, "fill", {"selector": 'input[name="q"]', "text": "darkin"}),
         (CH + "?q=darkin", "click", {"selector": ".roster-filters button"}),
         (AATROX, "goto", {}), ("/champions/kayn/", "goto", {}),
         (NAAFIRI, "goto", {}), ("/champions/varus/", "goto", {}),
         ("/champions/zaahen/", "goto", {})],
        "Searching for 'darkin' on the Champions page returns 5 champions: Aatrox, Kayn, "
        "Naafiri, Varus, Zaahen. Their roles are — Aatrox: Fighter; Kayn: Fighter / "
        "Assassin; Naafiri: Assassin / Fighter; Varus: Marksman / Mage; Zaahen: Fighter."),
    5: ([(CH, "goto", {}),
         (CH, "fill", {"selector": 'input[name="q"]', "text": "ruined king"}),
         (CH, "click", {"selector": ".roster-filters button"}),
         (VIEGO, "goto", {})],
        "The champion with the epithet 'The Ruined King' is Viego. On their champion page "
        "the role is Fighter / Assassin and the difficulty rating is Medium."),
    6: ([(MEL, "goto", {})],
        "Mel's Available Skins carousel lists 3 skins: Mel, Arcane Councilor Mel, "
        "Prestige Winterblessed Mel."),
    7: ([(AMBESSA, "goto", {})],
        "Ambessa's five abilities in slot order are: Drakehound's Step, Cunning Sweep / "
        "Sundering Slam, Repudiation, Lacerate, Public Execution (Passive, Q, W, E, R)."),
    8: ([(YUNARA, "goto", {}),
         (YUNARA, "click", {"selector": ".ability-slot[data-ability='1']"})],
        "Yunara's Passive ability is 'Vow of the First Lands'. Its full description as "
        "shown on the page: \"Yunara's Critical Strikes deal bonus magic damage.\""),
    9: ([(AATROX, "goto", {}), (NAAFIRI, "goto", {}),
         ("/champions/zaahen/", "goto", {})],
        "Aatrox lists 13 skins, Naafiri lists 5 skins, and Zaahen lists 2 skins. Aatrox "
        "has the most skins of the three."),
    10: ([("/search", "goto", {}),
          ("/search", "fill", {"selector": 'input[name="q"]', "text": "Pulsefire"}),
          ("/search?q=Pulsefire", "click", {"selector": ".search-form button"})],
         "Searching the site for 'Pulsefire' returns 10 champions that own a Pulsefire "
         "skin: Caitlyn, Ekko, Ezreal, Fiora, Lucian, Pantheon, Riven, Shen, Thresh, "
         "Twisted Fate."),
    11: ([("/patch-notes/", "goto", {})],
         "The most recent patch notes article in the list is 'League of Legends Patch "
         "26.19 Notes', published 2026-09-22."),
    12: ([("/patch-notes/", "goto", {}), (PATCH_2619, "goto", {})],
         "In the Patch 26.19 Notes, the Aatrox section changes his W - Infernal Chains. "
         "The new cooldown values listed for it are: 18 / 16.5 / 15 / 13.5 / 12 seconds."),
    13: ([(PATCH_2619, "goto", {}), (PATCH_2618, "goto", {})],
         "Champions that received changes in both Patch 26.19 and Patch 26.18 include "
         "Master Yi and Kassadin. In the 26.18 notes, Kassadin's Q - Null Sphere change "
         "reads: Ability Power Ratio : 70% AP ⇒ 80% AP in standard League."),
    14: ([(NEWS + "dev/", "goto", {})],
         "The Dev category lists 147 articles. The most recent article is 'TL;DW: Team "
         "Voice, Classic & More Dev Update'."),
    15: ([(NEWS + "dev/", "goto", {}), (MONK, "goto", {})],
         "The dev article '/dev: Modernizing the Monk' is authored by The ASU Team. The "
         "article is about Lee Sin's ASU."),
    16: ([(NEWS + "esports/", "goto", {})],
         "The Esports category lists 52 articles. The first card is 'WORLDS 2026 VENUE "
         "EVENT POLICIES'. The cards on this page open as external links (the first card "
         "points to https://lolesports.com/en-us/news/worlds-2026-venue-event-policies)."),
    17: ([(NEWS, "goto", {}), (NEWS + "?page=2", "goto", {})],
         "On page 2 of the News hub, the first article in the grid is 'What would a "
         "\"League Classic Viego\" Look Like?', published 8/6/2026."),
    18: ([(NEWS + "lore/", "goto", {})],
         "The Lore category lists 2 articles: Previously on Star Guardian, The Council "
         "Archives Primer."),
    19: ([("/search", "goto", {}),
          ("/search", "fill", {"selector": 'input[name="q"]', "text": "Vanguard"}),
          ("/search?q=Vanguard", "click", {"selector": ".search-form button"})],
         "Searching the site for 'Vanguard' matches News (3). The most recent matching "
         "article is '/dev: Vanguard x LoL Retrospective' (the three matches are: /dev: "
         "Vanguard x LoL Retrospective; /dev: Vanguard x LoL; TL;DW: Gameplay, Vanguard "
         "& More Dev Update)."),
    20: ([("/login/", "fill", {"selector": 'input[name="username"]',
                              "text": "alice.j@test.com"}),
          ("/login/", "fill", {"selector": 'input[name="password"]', "text": "TestPass123!"}),
          ("/login/", "click", {"selector": "button[type=submit]"}, "/account/"),
          ("/account/favorites", "goto", {}),
          (AATROX, "goto", {}), (MEL, "goto", {}), ("/champions/kayle/", "goto", {}),
          ("/champions/lee-sin/", "goto", {}), (YUNARA, "goto", {})],
         "The demo account has 5 favorite champions: Amumu (15 skins), Draven (15 "
         "skins), Kayle (19 skins), Lee Sin (20 skins), Yunara (3 skins). Lee Sin has the "
         "most skins available."),
    21: ([("/login/", "fill", {"selector": 'input[name="username"]',
                              "text": "bob.c@test.com"}),
          ("/login/", "fill", {"selector": 'input[name="password"]', "text": "TestPass123!"}),
          ("/login/", "click", {"selector": "button[type=submit]"}, "/account/"),
          (MILIO, "goto", {}),
          (MILIO, "click", {"selector": ".champ-action-row button"}),
          ("/account/favorites", "goto", {})],
         "After adding Milio to my favorites from Milio's champion page, the account now "
         "has 6 favorite champions in total."),
    22: ([("/login/", "fill", {"selector": 'input[name="username"]',
                              "text": "carol.d@test.com"}),
          ("/login/", "fill", {"selector": 'input[name="password"]', "text": "TestPass123!"}),
          ("/login/", "click", {"selector": "button[type=submit]"}, "/account/"),
          (TRUNDLE, "goto", {}),
          (TRUNDLE, "click", {"selector": ".champ-action-row button"}),
          ("/account/favorites", "goto", {})],
         "After removing Trundle from the favorites, the champions that remain on the "
         "favorites list are: Jarvan IV, Rell, Udyr, Zac (4 champions)."),
    23: ([("/login/", "fill", {"selector": 'input[name="username"]',
                              "text": "david.k@test.com"}),
          ("/login/", "fill", {"selector": 'input[name="password"]', "text": "TestPass123!"}),
          ("/login/", "click", {"selector": "button[type=submit]"}, "/account/"),
          (PATCH_2619, "goto", {}),
          (PATCH_2619, "click", {"selector": ".article-toolbar button"}),
          ("/account/bookmarks", "goto", {})],
         "After saving the 'League of Legends Patch 26.19 Notes' article to my bookmarks, "
         "the account now has 5 saved articles in total."),
    24: ([("/login/", "fill", {"selector": 'input[name="username"]',
                              "text": "alice.j@test.com"}),
          ("/login/", "fill", {"selector": 'input[name="password"]', "text": "TestPass123!"}),
          ("/login/", "click", {"selector": "button[type=submit]"}, "/account/"),
          ("/account/profile", "goto", {}),
          ("/account/profile", "fill", {"selector": 'input[name="summoner_name"]',
                                        "text": "RadiantViper"}),
          ("/account/profile", "select", {"selector": 'select[name="region"]',
                                          "value": "EUW"}),
          ("/account/profile", "click", {"selector": "button[type=submit]"}, "/account/"),
          ("/account/", "goto", {})],
         "I changed the account's summoner name to 'RadiantViper' and its region to EUW; "
         "the account page now shows summoner name RadiantViper and region EUW."),
    25: ([("/signup/", "fill", {"selector": 'input[name="username"]', "text": "nova_review"}),
          ("/signup/", "fill", {"selector": 'input[name="email"]',
                                "text": "nova.review@test.com"}),
          ("/signup/", "fill", {"selector": 'input[name="display_name"]',
                                "text": "Nova Review"}),
          ("/signup/", "fill", {"selector": 'input[name="password"]',
                                "text": "NovaPass123!"}),
          ("/signup/", "click", {"selector": "button[type=submit]"}, "/account/")],
         "After creating my new account and signing in, the account starts with 0 "
         "favorite champions and 0 saved articles."),
    26: ([(HTP, "goto", {})],
         "In the jungle section of the How To Play page, the site says: \"Killing Baron "
         "grants the slayer's team bonus attack damage, ability power, empowered recall, "
         "and greatly increases the power of nearby minions.\""),
    27: ([(HTP, "goto", {})],
         "The lane described as 'the dynamite of the team' is Bot Lane. The page says: "
         "\"Bot lane champions are the dynamite of the team. As precious cargo, they "
         "need to be protected early on before amassing enough gold and experience to "
         "carry the team to victory.\""),
    28: ([(SONA, "goto", {})],
         "The Sona skins whose names include 'DJ' or 'Pentakill' are: DJ Sona, Pentakill "
         "Sona, Pentakill III: Lost Chapter Sona."),
    29: ([(NAAFIRI, "goto", {}),
          (NAAFIRI, "click", {"selector": ".ability-slot[data-attribute='5']"
                               .replace("data-attribute", "data-ability")})],
         "Naafiri's Ultimate (R) ability is 'Hounds' Pursuit'. Its full description as "
         "shown on the page: \"Naafiri and her packmates dash at a champion, dealing "
         "damage. Naafiri reveals nearby enemies if she scores a takedown and can recast "
         "this Ability once. The second cast grants a shield.\""),
}

# Current task fixtures are synthetic controls, not browser completion evidence.
HONEST.update({int(k): v for k, v in json.loads(
    Path(__file__).with_name("reviewed_fixtures.json").read_text()).items()})

# stateful tasks: SQL that materialises the exactly-compliant after-state from the seed
COMPLIANT_AFTER_SQL = {
    21: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
         "VALUES (2, 84, '2026-09-22')"],
    22: ["DELETE FROM favorite_champions WHERE user_id = 3 AND champion_id = 140"],
    23: ["INSERT INTO bookmark_articles (user_id, article_id, added_date) "
         "VALUES (4, 133, '2026-09-22')"],
    24: ["UPDATE users SET summoner_name = 'RadiantViper', region = 'EUW' WHERE id = 1"],
    25: ["INSERT INTO users (username, email, display_name, summoner_name, region, "
         "password_hash, joined_date) VALUES ('nova_review', 'nova.review@test.com', "
         "'Nova Review', 'Nova Review', 'NA', '4393e74456a378947ee3fc12aad239b62372ee308f7dce631217931775342f3c', '2026-09-22')"],
}
# wrong-delta mutations for the stateful tasks (collateral or wrong row)
WRONG_DELTA_SQL = {
    21: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
         "VALUES (2, 1, '2026-09-22')"],  # adds Aatrox, not Milio
    22: ["DELETE FROM favorite_champions WHERE user_id = 3 AND champion_id = 16"],  # removes Jarvan IV
    23: ["INSERT INTO bookmark_articles (user_id, article_id, added_date) "
         "VALUES (4, 132, '2026-09-22')"],  # bookmarks the wrong article
    24: ["UPDATE users SET display_name = 'Tampered', region = 'EUW' WHERE id = 1"],  # wrong column
    25: ["INSERT INTO users (username, email, display_name, summoner_name, region, "
         "password_hash, joined_date) VALUES ('nova_review', 'nova.review@test.com', "
         "'Nova Review', 'Nova Review', 'NA', '4393e74456a378947ee3fc12aad239b62372ee308f7dce631217931775342f3c', '2026-09-22'), "
         "('nova_two', 'nova.two@test.com', 'Nova Two', 'Nova Two', 'NA', '4393e74456a378947ee3fc12aad239b62372ee308f7dce631217931775342f3c', '2026-09-22')"],
}

WRONG_ANSWERS = {
    0: "Filtering by Support and High shows 12 champions: Blitzcrank, Brand, Braum, "
       "Darius, Dr. Mundo, Evelyn, Fiora, Garen, Illaoi, Jax, Kayle, Leona.",
    1: "There are 18 Marksman champions with Medium difficulty.",
    2: "There are 42 champions with Low difficulty.",
    3: "The first five champions sorted by Newest are: Ahri, Akali, Aatrox, Amumu, Annie.",
    4: "The 'darkin' search returns Aatrox and Rhaast only; both are Fighters.",
    5: "The Ruined King is Kalista, a Marksman with High difficulty.",
    6: "Mel has 5 skins: Mel, Arcane Councilor Mel, Prestige Winterblessed Mel, "
       "Snowday Mel, Winterblessed Mel.",
    7: "Ambessa's abilities are: Deathbringer Stance, The Darkin Blade, Infernal "
       "Chains, Umbral Dash, World Ender.",
    8: "Yunara's Passive is called Hunter's Tide and it restores mana on hit.",
    9: "Aatrox has 9 skins, Naafiri has 7, Zaahen has 4 — Naafiri has the most.",
    10: "The Pulsefire skin owners are Ezreal, Caitlyn, and Thresh.",
    11: "The most recent patch notes are 'League of Legends Patch 26.18 Notes' "
        "published 2026-09-09.",
    12: "Aatrox's E - Umbral Dash was changed; its new cooldown is 20 / 18 / 16 / 14 / 12.",
    13: "Riven and Zed received changes in both patches; Zed's 26.18 change was a "
        "damage buff.",
    14: "The Dev category lists 89 articles and the most recent is 'Champion Roadmap: "
        "October 2023'.",
    15: "The article was written by Riot Jag and is about Yasuo.",
    16: "The Esports page lists 30 cards; the first is 'LCS Championship Tickets', and "
        "they open as articles on this site.",
    17: "The first article on page 2 is 'League of Legends Patch 26.18 Notes'.",
    18: "The Lore category has 5 articles.",
    19: "The Vanguard search matches 7 articles; the most recent is 'TL;DW: Gameplay, "
        "Vanguard & More Dev Update'.",
    20: "Alice has 4 favorites: Amumu, Draven, Kayle and Yunara; Kayle has the most skins.",
    21: "After adding Milio, the account has 7 favorite champions.",
    22: "After removing Trundle, the remaining favorites are Jarvan IV, Rell, Trundle "
        "and Zac.",
    23: "After saving the article, the account has 6 saved articles.",
    24: "The summoner name is now StarlitFox and the region is KR.",
    25: "The new account starts with 2 favorite champions and 1 saved article.",
    26: "Killing Baron grants the slayer's team a shield and movement speed.",
    27: "The mid lane is described as 'the dynamite of the team' and needs farm early.",
    28: "The DJ/Pentakill Sona skins are: DJ Sona and Pentakill Sona.",
    29: "Naafiri's ultimate is 'Duskbringer' and it deals damage in an area.",
}


@pytest.fixture(scope="module")
def tmp(tmp_path_factory):
    return tmp_path_factory.mktemp("lol_verify")


# ---------------------------------------------------------------- honest PASS
@pytest.mark.parametrize("n", range(30))
def test_honest_pass(n, tmp):
    run = tmp / f"honest_{n}"
    steps, answer = HONEST[n]
    build_run(run, f"League of Legends--{n}", steps, answer)
    if n in STATEFUL:
        after = mutate_db(SEED, tmp / f"after_honest_{n}.db", COMPLIANT_AFTER_SQL[n])
    else:
        after = copy_db(SEED, tmp / f"after_honest_{n}.db")
    verdict = run_verifier(n, run, SEED, after)
    assert verdict.get("pass") is True, json.dumps(verdict, indent=1)


# ---------------------------------------------------------------- no-op FAIL
@pytest.mark.parametrize("n", range(30))
def test_noop_fail(n, tmp):
    run = tmp / f"noop_{n}"
    noop_run(run, f"League of Legends--{n}")
    verdict = run_verifier(n, run, SEED, SEED)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)


# ---------------------------------------------------------------- wrong answer FAIL
@pytest.mark.parametrize("n", range(30))
def test_wrong_answer_fail(n, tmp):
    steps, _ = HONEST[n]
    run = tmp / f"wrong_{n}"
    build_run(run, f"League of Legends--{n}", steps, WRONG_ANSWERS[n])
    if n in STATEFUL:
        after = mutate_db(SEED, tmp / f"after_wrong_{n}.db", COMPLIANT_AFTER_SQL[n])
    else:
        after = copy_db(SEED, tmp / f"after_wrong_{n}.db")
    verdict = run_verifier(n, run, SEED, after)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)


# ---------------------------------------------------------------- shortcut FAIL (all tasks)
@pytest.mark.parametrize("n", range(30))
def test_shortcut_fail(n, tmp):
    """Correct answer, homepage-only navigation: every LOL task requires a surface
    beyond the homepage, so the shortcut must FAIL for all 30."""
    _, answer = HONEST[n]
    run = tmp / f"shortcut_{n}"
    build_run(run, f"League of Legends--{n}", [("/", "click", {"selector": "body"})], answer)
    verdict = run_verifier(n, run, SEED, SEED)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)


# ---------------------------------------------------------------- read-only tamper FAIL
@pytest.mark.parametrize("n", READ_ONLY)
def test_read_only_tamper_fail(n, tmp):
    steps, answer = HONEST[n]
    run = tmp / f"tamper_{n}"
    build_run(run, f"League of Legends--{n}", steps, answer)
    after = mutate_db(SEED, tmp / f"after_tamper_{n}.db",
                      ["INSERT INTO users (username, email, display_name, summoner_name, "
                       "region, password_hash, joined_date) VALUES ('tamper', "
                       "'tamper@test.com', 'Tamper', 'Tamper', 'NA', '4393e74456a378947ee3fc12aad239b62372ee308f7dce631217931775342f3c', '2026-09-22')"])
    verdict = run_verifier(n, run, SEED, after)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)


# ---------------------------------------------------------------- stateful mismatch / wrong delta FAIL
@pytest.mark.parametrize("n", sorted(STATEFUL))
def test_stateful_no_delta_fail(n, tmp):
    steps, answer = HONEST[n]
    run = tmp / f"nodelta_{n}"
    build_run(run, f"League of Legends--{n}", steps, answer)
    verdict = run_verifier(n, run, SEED, SEED)  # after == seed: claimed change never happened
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)


@pytest.mark.parametrize("n", sorted(STATEFUL))
def test_stateful_wrong_delta_fail(n, tmp):
    steps, answer = HONEST[n]
    run = tmp / f"wrongdelta_{n}"
    build_run(run, f"League of Legends--{n}", steps, answer)
    after = mutate_db(SEED, tmp / f"after_wrongdelta_{n}.db", WRONG_DELTA_SQL[n])
    verdict = run_verifier(n, run, SEED, after)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)


# ---------------------------------------------------------------- package tampering FAIL
def test_package_wrong_task_id(tmp):
    steps, answer = HONEST[0]
    run = tmp / "pkg_taskid"
    build_run(run, "League of Legends--99", steps, answer)
    verdict = run_verifier(0, run, SEED, copy_db(SEED, tmp / "a_pkg1.db"))
    assert verdict.get("pass") is False


def test_package_offsite_url(tmp):
    run = tmp / "pkg_offsite"
    rb = RunBuilder(run, "League of Legends--6", "/")
    rb.step("/", "navigate", {"url": "https://www.leagueoflegends.com/en-us/champions/mel/"},
            url_after="https://www.leagueoflegends.com/en-us/champions/mel/")
    rb.done(HONEST[6][1])
    verdict = run_verifier(6, run, SEED, copy_db(SEED, tmp / "a_pkg2.db"))
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "all_urls_match_local_origin"


def test_package_missing_screenshot(tmp):
    steps, answer = HONEST[2]
    run = tmp / "pkg_shot"
    build_run(run, "League of Legends--2", steps, answer)
    (run / "screenshots" / "step_001.png").unlink()
    verdict = run_verifier(2, run, SEED, copy_db(SEED, tmp / "a_pkg3.db"))
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "screenshots_decode"


def test_package_not_done(tmp):
    steps, _ = HONEST[5]
    run = tmp / "pkg_notdone"
    rb = RunBuilder(run, "League of Legends--5", "/")
    for path, action, params in steps:
        rb.step(path, action, params)
    # write the trajectory without a done step / final answer
    traj = {"task": "fixture", "task_id": "League of Legends--5",
            "start_url": BASE + "/", "model": "review-fixture", "max_steps": 80,
            "steps": rb.steps, "terminated": False, "termination_reason": "max_steps",
            "final_answer": "", "final_url": BASE + "/",
            "judge_rubric": "", "verifier_path": ""}
    (run / "trajectory.json").write_text(json.dumps(traj, indent=2))
    verdict = run_verifier(5, run, SEED, copy_db(SEED, tmp / "a_pkg4.db"))
    assert verdict.get("pass") is False


def test_package_tampered_seed(tmp):
    steps, answer = HONEST[0]
    run = tmp / "pkg_seed"
    build_run(run, "League of Legends--0", steps, answer)
    bad = mutate_db(SEED, tmp / "bad_seed.db",
                    ["UPDATE champions SET name = 'Tampered' WHERE id = 1"])
    verdict = run_verifier(0, run, bad, copy_db(SEED, tmp / "a_pkg5.db"))
    assert verdict.get("pass") is False
    assert verdict.get("infra_error") is True
    assert verdict.get("reason") == "snapshot_contract_invalid"


def test_package_unavailable_db(tmp):
    steps, answer = HONEST[0]
    run = tmp / "pkg_nodb"
    build_run(run, "League of Legends--0", steps, answer)
    verdict = run_verifier(0, run, tmp / "nonexistent_initial.db",
                           tmp / "nonexistent_after.db")
    assert verdict.get("pass") is False
    assert verdict.get("infra_error") is True


def test_package_screenshot_not_png(tmp):
    steps, answer = HONEST[3]
    run = tmp / "pkg_notpng"
    build_run(run, "League of Legends--3", steps, answer)
    (run / "screenshots" / "step_001.png").write_bytes(b"not a png at all")
    verdict = run_verifier(3, run, SEED, copy_db(SEED, tmp / "a_pkg6.db"))
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "screenshots_decode"


def test_stateful_collateral_writes_fail(tmp):
    """T21 with the compliant favorite row PLUS a collateral bookmark write must FAIL."""
    steps, answer = HONEST[21]
    run = tmp / "stateful_collateral"
    build_run(run, "League of Legends--21", steps, answer)
    after = mutate_db(
        SEED, tmp / "after_collateral.db",
        COMPLIANT_AFTER_SQL[21]
        + ["INSERT INTO bookmark_articles (user_id, article_id, added_date) "
           "VALUES (2, 133, '2026-09-22')"])
    verdict = run_verifier(21, run, SEED, after)
    assert verdict.get("pass") is False
    assert verdict.get("reason") == "no_collateral_writes"

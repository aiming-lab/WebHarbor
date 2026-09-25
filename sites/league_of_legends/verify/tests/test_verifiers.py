"""Deterministic verifier contract tests for the 18 League of Legends deep-chain tasks.

Covers, per task: the honest trajectory MUST PASS (stateful tasks run against a
seed copy mutated with exactly the compliant after-state); a no-op run
(homepage only, empty answer, clean DB) MUST FAIL; a wrong answer MUST FAIL; a
shortcut (correct answer, homepage-only navigation) MUST FAIL for every task.
The read-only baseline (task 17) MUST FAIL on a mutated after-DB; every stateful
task MUST FAIL on a state mismatch (no DB delta), a wrong delta and collateral
writes. Package tampering (task_id mismatch, off-site URLs, missing/invalid
screenshots, non-done trajectory, tampered seed, unavailable DB) MUST fail
closed. No LLM: snapshots are seed copies mutated through sqlite, trajectories
are hand-written in the agent_demo/agent.py shape. The honest answers below are
the values the live DOM walk extracts (wh-lol-depth-upgrade-evidence/runs/);
the verifiers hardcode the same ground truth.

Subject binding (r2 re-review blocking finding): multi-entity comparison facts
swapped between the compared subjects — every token present, each attached to
the wrong entity — MUST FAIL for every task (test_swapped_facts_fail), and the
verify_lib binding helpers carry their own unit tests
(test_bound_* / test_stem_* / test_state_count_segment_*).
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, RunBuilder, VERIFY_DIR, _acquire_seed, build_run,  # noqa: E402
                      copy_db, mutate_db, noop_run, run_verifier)

sys.path.insert(0, str(VERIFY_DIR))
import verify_lib as vl  # noqa: E402


SEED = _acquire_seed()

STATEFUL = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16}
READ_ONLY = sorted(set(range(18)) - STATEFUL)

CH = "/champions/"
CH_SH = "/champions/?q=&role=Support&difficulty=High&sort=name"
CH_MM = "/champions/?q=&role=Marksman&difficulty=Medium&sort=name"
CH_SK = "/champions/?q=&role=&difficulty=&sort=skins"
CH_DK = "/champions/?q=darkin&role=&difficulty=&sort=name"
CH_PF = "/champions/?q=Pulsefire&role=&difficulty=&sort=name"
CH_PF_H = "/champions/?q=Pulsefire&role=&difficulty=High&sort=name"
CH_PF_L = "/champions/?q=Pulsefire&role=&difficulty=Low&sort=name"
CH_M = "/champions/?q=&role=Marksman&difficulty=&sort=name"
HTP = "/how-to-play/"
PATCH_2619 = "/news/game-updates/league-of-legends-patch-26-19-notes/"
PATCH_2618 = "/news/game-updates/league-of-legends-patch-26-18-notes/"
PATCH_2616 = "/news/game-updates/league-of-legends-patch-26-16-notes/"
LORE = "/news/lore/"
LORE_SG = "/news/lore/previously-on-star-guardian/"
LORE_COUNCIL = "/news/lore/the-council-archives-primer/"
MONK = "/news/dev/dev-modernizing-the-monk/"
VANGUARD_A = "/news/dev/dev-vanguard-x-lol/"
VANGUARD_T = "/news/dev/tl-dw-gameplay-vanguard-more-dev-update/"
VANGUARD_R = "/news/dev/dev-vanguard-x-lol-retrospective/"
DEEP_DIVE = "/news/riot_games/ruined-king-gameplay-deep-dive/"
MIDSEASON = "/news/dev/dev-midseason-and-mythics/"

ALICE_LOGIN = [("/login/", "fill", {"selector": "input[name=username]",
                                    "text": "alice.j@test.com"}),
               ("/login/", "fill", {"selector": "input[name=password]",
                                    "text": "TestPass123!"}),
               ("/login/", "click", {"selector": "button[type=submit]"},
                "/account/")]
BOB_LOGIN = [("/login/", "fill", {"selector": "input[name=username]",
                                  "text": "bob.c@test.com"}),
             ("/login/", "fill", {"selector": "input[name=password]",
                                  "text": "TestPass123!"}),
             ("/login/", "click", {"selector": "button[type=submit]"}, "/account/")]
CAROL_LOGIN = [("/login/", "fill", {"selector": "input[name=username]",
                                    "text": "carol.d@test.com"}),
               ("/login/", "fill", {"selector": "input[name=password]",
                                    "text": "TestPass123!"}),
               ("/login/", "click", {"selector": "button[type=submit]"}, "/account/")]
DAVID_LOGIN = [("/login/", "fill", {"selector": "input[name=username]",
                                    "text": "david.k@test.com"}),
               ("/login/", "fill", {"selector": "input[name=password]",
                                    "text": "TestPass123!"}),
               ("/login/", "click", {"selector": "button[type=submit]"}, "/account/")]


def signin_favorite_login(path, email):
    """'Sign in to Favorite' -> login form on the champion page's next URL."""
    return [(path, "click", {"selector": "a:has-text('Sign in to Favorite')"}),
            (path.replace("/champions/", "/login/?next="), "fill",
             {"selector": "input[name=username]", "text": email}),
            (path.replace("/champions/", "/login/?next="), "fill",
             {"selector": "input[name=password]", "text": "TestPass123!"}),
            (path.replace("/champions/", "/login/?next="), "click",
             {"selector": "button[type=submit]"}, path)]


HONEST = {}

HONEST[0] = (
    [("/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Champions')"},
      "/champions/"),
     ("/champions/", "select", {"selector": "select[name=role]", "value": "Support"}),
     ("/champions/", "select", {"selector": "select[name=difficulty]", "value": "High"}),
     ("/champions/", "click", {"selector": ".roster-filters button"}, CH_SH),
     (CH_SH, "click", {"selector": ".champion-card:has-text('Hwei')"}),
     ("/champions/hwei/", "click", {"selector": ".ability-slot[data-ability='3']"}),
     ("/champions/hwei/", "click", {"selector": ".ability-slot[data-ability='5']"}),
     ("/champions/hwei/", "go_back", {}),
     (CH_SH, "click", {"selector": ".champion-card:has-text('Renata Glasc')"}),
     ("/champions/renata/", "click", {"selector": ".ability-slot[data-ability='3']"}),
     ("/champions/renata/", "click", {"selector": ".ability-slot[data-ability='5']"})]
    + signin_favorite_login("/champions/renata/", "alice.j@test.com")
    + [("/champions/renata/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/renata/", "click", {"selector": "a:has-text('My Account')"},
        "/account/")],
    "Filtering the Champions roster by Support role and High difficulty shows 8 "
    "champions; Hwei and Renata Glasc are both eligible. Hwei's W is 'Subject: "
    "Serenity', a menu of utility spells (Fleeting Current, Pool of Reflection, "
    "Stirring Lights), and his R is 'Spiraling Despair', an expanding painting "
    "that slows and damages nearby enemies. Renata Glasc's W is 'Bailout', which "
    "buffs an ally to delay their death, and her R is 'Hostile Takeover', a "
    "chemical wave that makes enemies go Berserk. Hwei has 4 skins and Renata has "
    "6, so Renata Glasc has more skins. I added Renata Glasc to favorites from "
    "her champion page; the account now has 6 favorite champions in total.")

HONEST[1] = (
    [("/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Champions')"},
      "/champions/"),
     ("/champions/", "select", {"selector": "select[name=role]", "value": "Marksman"}),
     ("/champions/", "select", {"selector": "select[name=difficulty]", "value": "Medium"}),
     ("/champions/", "click", {"selector": ".roster-filters button"}, CH_MM),
     (CH_MM, "click", {"selector": ".champion-card:has-text('Lucian')"}),
     ("/champions/lucian/", "click", {"selector": ".ability-slot[data-ability='4']"}),
     ("/champions/lucian/", "go_back", {}),
     (CH_MM, "click", {"selector": ".champion-card:has-text('Ezreal')"}),
     ("/champions/ezreal/", "click", {"selector": ".ability-slot[data-ability='4']"})]
    + signin_favorite_login("/champions/ezreal/", "bob.c@test.com")
    + [("/champions/ezreal/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/ezreal/", "click", {"selector": "a:has-text('My Account')"},
        "/account/")],
    "With the roster filtered to Marksman role and Medium difficulty, both Ezreal "
    "and Lucian qualify. Ezreal's E is 'Arcane Shift', which teleports him to a "
    "target nearby location and fires a homing bolt at the nearest enemy. Lucian's "
    "E is 'Relentless Pursuit', a quick short dash whose cooldown is reduced by "
    "Lightslinger attacks. Ezreal's E is the teleport, so I picked him. Ezreal's "
    "roles are Marksman / Mage and Lucian's are Marksman / Assassin. I added "
    "Ezreal to favorites; the account now has 6 favorite champions.")

HONEST[2] = (
    [("/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Champions')"},
      "/champions/"),
     ("/champions/", "select", {"selector": "select[name=sort]", "value": "skins"}),
     ("/champions/", "click", {"selector": ".roster-filters button"}, CH_SK),
     (CH_SK, "click", {"selector": ".champion-card:has-text('Miss Fortune')"}),
     ("/champions/missfortune/", "click", {"selector": ".ability-slot[data-ability='5']"}),
     ("/champions/missfortune/", "go_back", {}),
     (CH_SK, "click", {"selector": ".champion-card:has-text('Lux')"}),
     ("/champions/lux/", "click", {"selector": ".ability-slot[data-ability='5']"}),
     ("/champions/lux/", "go_back", {}),
     (CH_SK, "click", {"selector": ".champion-card:has-text('Miss Fortune')"})]
    + signin_favorite_login("/champions/missfortune/", "david.k@test.com")
    + [("/champions/missfortune/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/missfortune/", "click", {"selector": "a:has-text('My Account')"},
        "/account/")],
    "Sorting the roster by Most skins, the first five champions are: Miss Fortune, "
    "Lux, Ahri, Akali, Ezreal. Miss Fortune's ultimate is 'Bullet Time' and she has "
    "24 skins including the base appearance; one non-base skin is 'Cowgirl Miss "
    "Fortune'. Lux's ultimate is 'Final Spark' and she has 23 skins including the "
    "base appearance; one non-base skin is 'Sorceress Lux'. Miss Fortune has the "
    "most skins, so I added her to favorites; the account now has 6 favorite "
    "champions.")

HONEST[3] = (
    [("/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Champions')"},
      "/champions/"),
     ("/champions/", "fill", {"selector": "input[name=q]", "text": "darkin"}),
     ("/champions/", "click", {"selector": ".roster-filters button"}, CH_DK)]
    + [pair for name in ["Aatrox", "Kayn", "Naafiri", "Varus", "Zaahen"]
       for pair in [(CH_DK, "click", {"selector": f".champion-card:has-text('{name}')"}),
                    ("/champions/" + {"Aatrox": "aatrox", "Kayn": "kayn", "Naafiri": "naafiri",
                                      "Varus": "varus", "Zaahen": "zaahen"}[name] + "/",
                     "go_back", {})]]
    + [(CH_DK, "click", {"selector": ".champion-card:has-text('Aatrox')"})]
    + signin_favorite_login("/champions/aatrox/", "carol.d@test.com")
    + [("/champions/aatrox/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/aatrox/", "click", {"selector": "a:has-text('My Account')"},
        "/account/")],
    "Searching the Champions roster for 'darkin' returns 5 champions. Aatrox — "
    "'the Darkin Blade', Fighter, Medium difficulty. Kayn — 'the Shadow Reaper', "
    "Fighter / Assassin, High. Naafiri — 'the Hound of a Hundred Bites', Assassin / "
    "Fighter, Low. Varus — 'the Arrow of Retribution', Marksman / Mage, Low. Zaahen "
    "— 'The Unsundered', Fighter, Low. The champion titled 'the Darkin Blade' is "
    "Aatrox, a Fighter rated Medium difficulty. I added Aatrox to favorites from "
    "his champion page; the account now has 6 favorite champions.")

HONEST[4] = (
    [("/", "click", {"selector": ".riotbar-icon.riotbar-search"}, "/search"),
     ("/search", "fill", {"selector": "input[name=q]", "text": "Ruined King"}),
     ("/search", "click", {"selector": ".search-form button"}, "/search?q=Ruined+King"),
     ("/search?q=Ruined+King", "click",
      {"selector": ".champion-grid .champion-card:first-child"}, "/champions/viego/"),
     ("/champions/viego/", "click", {"selector": ".ability-slot[data-ability='4']"}),
     ("/champions/viego/", "go_back", {}),
     ("/search?q=Ruined+King", "click",
      {"selector": ".news-grid .article-card:first-child"}, DEEP_DIVE),
     (DEEP_DIVE, "go_back", {}),
     ("/search?q=Ruined+King", "click",
      {"selector": ".champion-grid .champion-card:first-child"}, "/champions/viego/")]
    + signin_favorite_login("/champions/viego/", "alice.j@test.com")
    + [("/champions/viego/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/viego/", "click", {"selector": "a:has-text('My Account')"},
        "/account/")],
    "The site search for 'Ruined King' returns 60 champion cards and 29 news "
    "results. The first champion result is Viego, and his champion page confirms "
    "the epithet 'The Ruined King'. The highest-ranked news result is 'Ruined "
    "King: Gameplay Deep Dive', published 2020-12-11. Viego's passive 'Sovereign's "
    "Domination' turns enemies who fall before him into wraiths; attacking a "
    "wraith seizes the dead enemy's body, healing him and gaining their basic "
    "abilities and items, with his own ultimate replacing theirs. His E 'Harrowed "
    "Path' haunts a piece of terrain with the Black Mist, giving camouflage, Move "
    "Speed, and Attack Speed. I added Viego to favorites from his champion page; "
    "the account now has 6 favorite champions.")

HONEST[5] = (
    [("/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Champions')"},
      "/champions/"),
     ("/champions/", "fill", {"selector": "input[name=q]", "text": "Pulsefire"}),
     ("/champions/", "click", {"selector": ".roster-filters button"}, CH_PF),
     (CH_PF, "select", {"selector": "select[name=difficulty]", "value": "High"}),
     (CH_PF, "click", {"selector": ".roster-filters button"}, CH_PF_H),
     (CH_PF_H, "click", {"selector": ".champion-card:has-text('Ekko')"}),
     ("/champions/ekko/", "go_back", {}),
     (CH_PF_H, "select", {"selector": "select[name=difficulty]", "value": "Low"}),
     (CH_PF_H, "click", {"selector": ".roster-filters button"}, CH_PF_L),
     (CH_PF_L, "click", {"selector": ".champion-card:has-text('Fiora')"}),
     ("/champions/fiora/", "click", {"selector": ".skin-thumb"})]
    + signin_favorite_login("/champions/fiora/", "carol.d@test.com")
    + [("/champions/fiora/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/fiora/", "click", {"selector": "a:has-text('My Account')"},
        "/account/")],
    "Searching the Champions roster for 'Pulsefire' returns 10 champion cards: "
    "Caitlyn, Ekko, Ezreal, Fiora, Lucian, Pantheon, Riven, Shen, Thresh, and "
    "Twisted Fate. With the High difficulty filter the Pulsefire holders are "
    "Ekko, Riven, and Twisted Fate; Ekko's champion page confirms the High "
    "difficulty rating. With the Low difficulty filter, only Fiora remains. "
    "Fiora's Available Skins include 'Pulsefire Fiora'. I added Fiora to favorites "
    "from her champion page; the account now has 6 favorite champions.")

HONEST[6] = (
    [("/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Patch Notes')"},
      "/patch-notes/"),
     ("/patch-notes/", "click", {"selector": ".article-card:first-child"}, PATCH_2619),
     (PATCH_2619, "go_back", {}),
     ("/patch-notes/", "click", {"selector": ".article-card:nth-child(2)"}, PATCH_2618),
     (PATCH_2618, "go_back", {}),
     ("/patch-notes/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Champions')"},
      "/champions/"),
     ("/champions/", "fill", {"selector": "input[name=q]", "text": "Aatrox"}),
     ("/champions/", "click", {"selector": ".roster-filters button"}),
     ("/champions/?q=Aatrox", "click", {"selector": ".champion-card:has-text('Aatrox')"}),
     ("/champions/aatrox/", "click", {"selector": ".ability-slot[data-ability='3']"}),
     ("/champions/aatrox/", "click", {"selector": ".ability-slot[data-ability='4']"})]
    + signin_favorite_login("/champions/aatrox/", "david.k@test.com")
    + [("/champions/aatrox/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/aatrox/", "click", {"selector": "a:has-text('My Account')"},
        "/account/")],
    "The two most recent patch notes articles are 'League of Legends Patch 26.19 "
    "Notes' (published 2026-09-22) and 'League of Legends Patch 26.18 Notes' "
    "(published 2026-09-09). In 26.19, Aatrox's W change reads: W - Infernal "
    "Chains Cooldown: 20 / 18 / 16 / 14 / 12 seconds => 18 / 16.5 / 15 / 13.5 / 12 "
    "seconds. On Aatrox's champion page his W is 'Infernal Chains' and his E is "
    "'Umbral Dash', a dash that lets him heal. I added Aatrox to favorites from his "
    "champion page; the account now has 6 favorite champions.")

HONEST[7] = (
    [("/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Patch Notes')"},
      "/patch-notes/"),
     ("/patch-notes/", "click", {"selector": ".article-card:first-child"}, PATCH_2619),
     (PATCH_2619, "go_back", {}),
     ("/patch-notes/", "click", {"selector": ".article-card:nth-child(4)"}, PATCH_2616),
     (PATCH_2616, "go_back", {}),
     ("/patch-notes/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Champions')"},
      "/champions/"),
     ("/champions/", "fill", {"selector": "input[name=q]", "text": "Poppy"}),
     ("/champions/", "click", {"selector": ".roster-filters button"}),
     ("/champions/?q=Poppy", "click", {"selector": ".champion-card:has-text('Poppy')"}),
     ("/champions/poppy/", "go_back", {}),
     ("/champions/?q=Poppy", "fill", {"selector": "input[name=q]", "text": "Nasus"}),
     ("/champions/?q=Poppy", "click", {"selector": ".roster-filters button"}),
     ("/champions/?q=Nasus", "click", {"selector": ".champion-card:has-text('Nasus')"}),
     ]
    + signin_favorite_login("/champions/nasus/", "bob.c@test.com")
    + [("/champions/nasus/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/nasus/", "click", {"selector": "a:has-text('My Account')"},
        "/account/")],
    "The champions adjusted in both Patch 26.19 and Patch 26.16 are Nasus and "
    "Poppy. Nasus is a Fighter / Tank rated Medium difficulty; Poppy is a Tank / "
    "Fighter, also Medium. Nasus's Q change in Patch 26.16 (Siphoning Strike) "
    "reads: 'Stacks: 3, increased to 12 on champions / large minions / monsters "
    "=> 4, increased to 10 on champions / large minions / monsters.' I added "
    "Nasus to favorites from his champion page; the account now has 6 favorite "
    "champions. Nasus's roles are Fighter / Tank.")

HONEST[8] = (
    [("/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('News')"}, "/news/"),
     ("/news/", "click", {"selector": "a:has-text('Older »')"}, "/news/?page=2"),
     ("/news/?page=2", "click", {"selector": ".filter-chip:has-text('Lore')"}, LORE),
     (LORE, "click", {"selector": ".article-card:has-text('Previously on Star Guardian')"},
      LORE_SG),
     (LORE_SG, "go_back", {}),
     (LORE, "click", {"selector": ".article-card:has-text('The Council Archives Primer')"},
      LORE_COUNCIL),
     (LORE_COUNCIL, "go_back", {}),
     (LORE, "click", {"selector": ".article-card:has-text('Previously on Star Guardian')"},
      LORE_SG)]
    + [(LORE_SG, "click", {"selector": "a:has-text('Sign in to Save')"}),
       (LORE_SG.replace("/news/", "/login/?next="), "fill",
        {"selector": "input[name=username]", "text": "david.k@test.com"}),
       (LORE_SG.replace("/news/", "/login/?next="), "fill",
        {"selector": "input[name=password]", "text": "TestPass123!"}),
       (LORE_SG.replace("/news/", "/login/?next="), "click",
        {"selector": "button[type=submit]"}, LORE_SG),
       (LORE_SG, "click", {"selector": ".article-toolbar button"}),
       (LORE_SG, "click", {"selector": "a:has-text('My Account')"}, "/account/"),
       ("/account/", "click", {"selector": "a:has-text('Saved Articles')"},
        "/account/bookmarks")],
    "On page 2 of the News hub, the first article is 'What would a “League "
    "Classic Viego” Look Like?', published 2026-08-06. The Lore category lists 2 "
    "articles: 'Previously on Star Guardian' (2022-07-09), the story so far of "
    "the Star Guardian universe, and 'The Council Archives Primer' (2021-11-08), "
    "an invitation to wander the stacks of the Council Archives and explore the "
    "history of Piltover and beyond. I saved 'Previously on Star Guardian' to my "
    "bookmarks; the account now has 5 saved articles.")

HONEST[9] = (
    [("/", "click", {"selector": ".riotbar-icon.riotbar-search"}, "/search"),
     ("/search", "fill", {"selector": "input[name=q]", "text": "Modernizing the Monk"}),
     ("/search", "click", {"selector": ".search-form button"},
      "/search?q=Modernizing+the+Monk"),
     ("/search?q=Modernizing+the+Monk", "click",
      {"selector": ".news-grid .article-card:first-child"}, MONK),
     (MONK, "click", {"selector": ".riotbar-nav .nav-item a:has-text('Champions')"},
      "/champions/"),
     ("/champions/", "fill", {"selector": "input[name=q]", "text": "Lee Sin"}),
     ("/champions/", "click", {"selector": ".roster-filters button"}),
     ("/champions/?q=Lee+Sin", "click", {"selector": ".champion-card:has-text('Lee Sin')"}),
     ("/champions/leesin/", "click", {"selector": ".ability-slot[data-ability='3']"}),
     ("/champions/leesin/", "click", {"selector": ".ability-slot[data-ability='5']"})]
    + signin_favorite_login("/champions/leesin/", "bob.c@test.com")
    + [("/champions/leesin/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/leesin/", "click", {"selector": ".riotbar-icon.riotbar-search"},
        "/search"),
       ("/search", "fill", {"selector": "input[name=q]", "text": "Modernizing the Monk"}),
       ("/search", "click", {"selector": ".search-form button"},
        "/search?q=Modernizing+the+Monk"),
       ("/search?q=Modernizing+the+Monk", "click",
        {"selector": ".news-grid .article-card:first-child"}, MONK),
       (MONK, "click", {"selector": ".article-toolbar button"}),
       (MONK, "click", {"selector": "a:has-text('My Account')"}, "/account/")],
    "'/dev: Modernizing the Monk' was written by The ASU Team. ASU stands for Art "
    "and Sustainability Update. Searching the site for 'Modernizing the Monk' "
    "matches 2 champion cards (Lee Sin and Wukong); the updated champion is Lee "
    "Sin. His W is 'Safeguard / Iron Will' — he rushes to an ally and shields "
    "himself, then Iron Will grants Omnivamp — and his R is 'Dragon's Rage', a "
    "roundhouse kick that launches the target back and damages enemies they "
    "collide with. I added Lee Sin to favorites and saved the article to my "
    "bookmarks; the account now has 6 favorite champions and 5 saved articles.")

HONEST[10] = (
    [("/", "click", {"selector": ".riotbar-play"}, "/signup/"),
     ("/signup/", "click", {"selector": "a:has-text('Sign In')"}, "/login/")]
    + ALICE_LOGIN
    + [("/account/", "click", {"selector": ".riotbar-icon.riotbar-search"}, "/search"),
       ("/search", "fill", {"selector": "input[name=q]", "text": "Vanguard"}),
       ("/search", "click", {"selector": ".search-form button"}, "/search?q=Vanguard"),
       ("/search?q=Vanguard", "click",
        {"selector": ".news-grid .article-card:first-child"}, VANGUARD_T),
       (VANGUARD_T, "go_back", {}),
       ("/search?q=Vanguard", "click",
        {"selector": ".news-grid .article-card:nth-child(2)"}, VANGUARD_A),
       (VANGUARD_A, "go_back", {}),
       ("/search?q=Vanguard", "click",
        {"selector": ".news-grid .article-card:nth-child(3)"}, VANGUARD_R),
       (VANGUARD_R, "click", {"selector": ".article-toolbar button"}),
       (VANGUARD_R, "click", {"selector": "a:has-text('My Account')"}, "/account/")],
    "Searching the site for 'Vanguard' returns 3 news results and a single "
    "champion card: Garen. The three articles are: 'TL;DW: Gameplay, Vanguard & "
    "More Dev Update' (published 2024-02-29), '/dev: Vanguard x LoL' "
    "(2024-04-11), and '/dev: Vanguard x LoL Retrospective' (2024-08-22). The "
    "retrospective reports that over 175,000 accounts were banned for cheating "
    "and that the Ranked scripting rate fell below 1% for the first time in "
    "nearly four years. I saved the retrospective to my bookmarks from the "
    "article page; the account now has 5 saved articles.")

HONEST[11] = (
    [("/", "click", {"selector": ".riotbar-play"}, "/signup/"),
     ("/signup/", "fill", {"selector": "input[name=username]", "text": "nova_harbor"}),
     ("/signup/", "fill", {"selector": "input[name=email]",
                           "text": "nova.harbor@test.com"}),
     ("/signup/", "fill", {"selector": "input[name=display_name]", "text": "Nova Harbor"}),
     ("/signup/", "fill", {"selector": "input[name=password]", "text": "NovaPass123!"}),
     ("/signup/", "click", {"selector": "button[type=submit]"}, "/account/"),
     ("/account/", "click", {"selector": "a:has-text('Edit Profile')"},
      "/account/profile"),
     ("/account/profile", "fill", {"selector": "input[name=summoner_name]",
                                    "text": "HarborRookie"}),
     ("/account/profile", "select", {"selector": "select[name=region]", "value": "EUW"}),
     ("/account/profile", "click", {"selector": "button[type=submit]"}, "/account/"),
     ("/account/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Champions')"},
      "/champions/"),
     ("/champions/", "fill", {"selector": "input[name=q]", "text": "Milio"}),
     ("/champions/", "click", {"selector": ".roster-filters button"}),
     ("/champions/?q=Milio", "click", {"selector": ".champion-card:has-text('Milio')"}),
     ("/champions/milio/", "click", {"selector": ".champ-action-row button"}),
     ("/champions/milio/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Patch Notes')"},
      "/patch-notes/"),
     ("/patch-notes/", "click", {"selector": ".article-card:first-child"}, PATCH_2619),
     (PATCH_2619, "click", {"selector": ".article-toolbar button"}),
     (PATCH_2619, "click", {"selector": "a:has-text('My Account')"}, "/account/"),
     ("/account/", "click", {"selector": "button:has-text('Sign Out')"}, "/"),
     ("/", "click", {"selector": ".riotbar-play"}, "/signup/"),
     ("/signup/", "click", {"selector": "a:has-text('Sign In')"}, "/login/"),
     ("/login/", "fill", {"selector": "input[name=username]",
                          "text": "nova.harbor@test.com"}),
     ("/login/", "fill", {"selector": "input[name=password]", "text": "NovaPass123!"}),
     ("/login/", "click", {"selector": "button[type=submit]"}, "/account/")],
    "I created the account, edited the profile so the summoner name is "
    "'HarborRookie' and the region is EUW, added Milio to favorites from his "
    "champion page, and saved 'League of Legends Patch 26.19 Notes' to my "
    "bookmarks. After signing out and signing back in, the account page still "
    "shows summoner name HarborRookie and region EUW, with 1 favorite champion "
    "and 1 saved article.")

HONEST[12] = (
    [("/", "click", {"selector": ".riotbar-play"}, "/signup/"),
     ("/signup/", "click", {"selector": "a:has-text('Sign In')"}, "/login/")]
    + CAROL_LOGIN
    + [("/account/", "click", {"selector": "a:has-text('Favorite Champions')"},
        "/account/favorites"),
       ("/account/favorites", "click", {"selector": ".champion-card:has-text('Trundle')"}),
       ("/champions/trundle/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/trundle/", "click", {"selector": "a:has-text('My Account')"},
        "/account/"),
       ("/account/", "click", {"selector": "a:has-text('Favorite Champions')"},
        "/account/favorites"),
       ("/account/favorites", "click", {"selector": ".champion-card:has-text('Zac')"}),
       ("/champions/zac/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/zac/", "click", {"selector": "a:has-text('My Account')"},
        "/account/"),
       ("/account/", "click", {"selector": "a:has-text('Favorite Champions')"},
        "/account/favorites")],
    "After removing Trundle from the account's favorite champions, the favorites "
    "page showed 4 remaining: Jarvan IV, Rell, Udyr, and Zac. After removing Zac "
    "as well, the account has 3 favorite champions left: Jarvan IV, Rell, and "
    "Udyr.")

HONEST[13] = (
    [("/", "click", {"selector": ".riotbar-play"}, "/signup/"),
     ("/signup/", "click", {"selector": "a:has-text('Sign In')"}, "/login/")]
    + ALICE_LOGIN
    + [("/account/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Champions')"},
        "/champions/"),
       ("/champions/", "fill", {"selector": "input[name=q]", "text": "Yone"}),
       ("/champions/", "click", {"selector": ".roster-filters button"}),
       ("/champions/?q=Yone", "click", {"selector": ".champion-card:has-text('Yone')"}),
       ("/champions/yone/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/yone/", "click", {"selector": "a:has-text('My Account')"},
        "/account/"),
       ("/account/", "click", {"selector": "button:has-text('Sign Out')"}, "/"),
       ("/", "click", {"selector": ".riotbar-play"}, "/signup/"),
       ("/signup/", "click", {"selector": "a:has-text('Sign In')"}, "/login/")]
    + BOB_LOGIN
    + [("/account/", "click", {"selector": "a:has-text('Favorite Champions')"},
        "/account/favorites"),
       ("/account/favorites", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Champions')"},
        "/champions/"),
       ("/champions/", "fill", {"selector": "input[name=q]", "text": "Milio"}),
       ("/champions/", "click", {"selector": ".roster-filters button"}),
       ("/champions/?q=Milio", "click", {"selector": ".champion-card:has-text('Milio')"}),
       ("/champions/milio/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/milio/", "click", {"selector": "a:has-text('My Account')"},
        "/account/")],
    "After adding Yone to alice's favorites, alice's account shows 6 favorite "
    "champions. Bob's account was not affected: it still shows 5 favorites — "
    "Anivia, Annie, Cho'Gath, Renata Glasc, and Viego — and Yone is not among "
    "them. After adding Milio from his champion page, bob's account now has 6 "
    "favorite champions.")

HONEST[14] = (
    [("/", "click", {"selector": ".riotbar-play"}, "/signup/"),
     ("/signup/", "click", {"selector": "a:has-text('Sign In')"}, "/login/")]
    + DAVID_LOGIN
    + [("/account/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Patch Notes')"},
        "/patch-notes/"),
       ("/patch-notes/", "click", {"selector": ".article-card:first-child"}, PATCH_2619),
       (PATCH_2619, "click", {"selector": ".article-toolbar button"}),
       (PATCH_2619, "click", {"selector": "a:has-text('My Account')"}, "/account/"),
       ("/account/", "click", {"selector": "a:has-text('Saved Articles')"},
        "/account/bookmarks"),
       ("/account/bookmarks", "click",
        {"selector": ".article-card:has-text('Midseason and Mythics')"}, MIDSEASON),
       (MIDSEASON, "click", {"selector": ".article-toolbar button"}),
       (MIDSEASON, "click", {"selector": "a:has-text('My Account')"}, "/account/"),
       ("/account/", "click", {"selector": "a:has-text('Saved Articles')"},
        "/account/bookmarks")],
    "After saving 'League of Legends Patch 26.19 Notes' to my bookmarks, the "
    "Saved Articles page shows 5 saved articles. The oldest of the four "
    "previously bookmarked articles is '/dev: Midseason and Mythics'; after "
    "removing it, the account has 4 saved articles.")

HONEST[15] = (
    [("/", "click", {"selector": ".riotbar-play"}, "/signup/"),
     ("/signup/", "click", {"selector": "a:has-text('Sign In')"}, "/login/")]
    + ALICE_LOGIN
    + [("/account/", "click", {"selector": "a:has-text('Edit Profile')"},
        "/account/profile"),
       ("/account/profile", "fill", {"selector": "input[name=summoner_name]",
                                      "text": "RadiantViper"}),
       ("/account/profile", "select", {"selector": "select[name=region]",
                                        "value": "EUW"}),
       ("/account/profile", "click", {"selector": "button[type=submit]"}, "/account/"),
       ("/account/", "click", {"selector": "button:has-text('Sign Out')"}, "/"),
       ("/", "click", {"selector": ".riotbar-play"}, "/signup/"),
       ("/signup/", "click", {"selector": "a:has-text('Sign In')"}, "/login/")]
    + ALICE_LOGIN
    + [("/account/", "click", {"selector": "a:has-text('Edit Profile')"},
        "/account/profile"),
       ("/account/profile", "select", {"selector": "select[name=region]",
                                        "value": "NA"}),
       ("/account/profile", "click", {"selector": "button[type=submit]"}, "/account/"),
       ("/account/", "click", {"selector": "a:has-text('Edit Profile')"},
        "/account/profile"),
       ("/account/profile", "click", {"selector": "a:has-text('My Account')"},
        "/account/")],
    "After changing the summoner name to 'RadiantViper' and the region to EUW, "
    "the account page showed summoner name RadiantViper and region EUW. After "
    "signing out and signing in again, the account page still showed "
    "RadiantViper and EUW, so the changes persisted. After switching the region "
    "back to NA, the final account page shows summoner name RadiantViper and "
    "region NA.")

HONEST[16] = (
    [("/", "click", {"selector": ".riotbar-nav .nav-item a:has-text('Game Overview')"},
      HTP),
     (HTP, "click", {"selector": ".riotbar-nav .nav-item a:has-text('Champions')"},
      "/champions/"),
     ("/champions/", "select", {"selector": "select[name=role]", "value": "Marksman"}),
     ("/champions/", "click", {"selector": ".roster-filters button"}, CH_M),
     (CH_M, "click", {"selector": ".champion-card:has-text('Ashe')"}),
     ("/champions/ashe/", "click", {"selector": ".ability-slot[data-ability='5']"}),
     ("/champions/ashe/", "go_back", {}),
     (CH_M, "click", {"selector": ".champion-card:has-text('Miss Fortune')"}),
     ("/champions/missfortune/", "click", {"selector": ".ability-slot[data-ability='5']"})]
    + signin_favorite_login("/champions/missfortune/", "carol.d@test.com")
    + [("/champions/missfortune/", "click", {"selector": ".champ-action-row button"}),
       ("/champions/missfortune/", "click", {"selector": "a:has-text('My Account')"},
        "/account/")],
    "How To Play says killing Baron Nashor grants the slayer's team bonus attack "
    "damage, ability power, empowered recall, and greatly increases the power of "
    "nearby minions. Bot-lane champions are called 'the dynamite of the team': "
    "as precious cargo, they need to be protected early on before amassing "
    "enough gold and experience to carry the team to victory. Filtering the "
    "roster by Marksman role shows Miss Fortune and Ashe. Miss Fortune's "
    "ultimate is 'Bullet Time' and she has 24 skins; Ashe's ultimate is "
    "'Enchanted Crystal Arrow' and she has 21 skins. Miss Fortune has more "
    "skins, so I added her to favorites; the account now has 6 favorite "
    "champions.")

HONEST[17] = (
    [("/", "click", {"selector": ".riotbar-play"}, "/signup/"),
     ("/signup/", "click", {"selector": "a:has-text('Sign In')"}, "/login/")]
    + ALICE_LOGIN
    + [("/account/", "click", {"selector": "a:has-text('Favorite Champions')"},
        "/account/favorites")]
    + [pair for name in ["Amumu", "Draven", "Kayle", "Lee Sin", "Yunara"]
       for pair in [("/account/favorites", "click",
                     {"selector": f".champion-card:has-text('{name}')"}),
                    ("/champions/" + {"Amumu": "amumu", "Draven": "draven", "Kayle": "kayle",
                                      "Lee Sin": "leesin", "Yunara": "yunara"}[name] + "/",
                     "go_back", {})]],
    "The account has 5 favorite champions: Amumu (15 skins), Draven (15 skins), "
    "Kayle (19 skins), Lee Sin (20 skins), and Yunara (3 skins). Lee Sin has the "
    "most skins available.")

NEW_USER_SQL = (
    "INSERT INTO users (username, email, display_name, summoner_name, region, "
    "password_hash, joined_date) VALUES ('nova_harbor', 'nova.harbor@test.com', "
    "'Nova Harbor', 'HarborRookie', 'EUW', "
    "'7c58dd13f4172ec9e3d4f1a4b1c5f9e3c6e22b6bf38f76ca75c93e08a52e6c19', '2026-09-22')")

# stateful tasks: SQL that materialises the exactly-compliant after-state from the seed
COMPLIANT_AFTER_SQL = {
    0: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (1, 109, '2026-09-22')"],
    1: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (2, 33, '2026-09-22')"],
    2: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (4, 85, '2026-09-22')"],
    3: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (3, 1, '2026-09-22')"],
    4: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (1, 152, '2026-09-22')"],
    5: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (3, 35, '2026-09-22')"],
    6: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (4, 1, '2026-09-22')"],
    7: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (2, 90, '2026-09-22')"],
    8: ["INSERT INTO bookmark_articles (user_id, article_id, added_date) "
        "VALUES (4, 183, '2026-09-22')"],
    9: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (2, 71, '2026-09-22')",
        "INSERT INTO bookmark_articles (user_id, article_id, added_date) "
        "VALUES (2, 82, '2026-09-22')"],
    10: ["INSERT INTO bookmark_articles (user_id, article_id, added_date) "
         "VALUES (1, 108, '2026-09-22')"],
    11: [NEW_USER_SQL,
         "INSERT INTO favorite_champions (user_id, champion_id, added_date) "
         "VALUES (5, 84, '2026-09-22')",
         "INSERT INTO bookmark_articles (user_id, article_id, added_date) "
         "VALUES (5, 133, '2026-09-22')"],
    12: ["DELETE FROM favorite_champions WHERE user_id = 3 AND champion_id = 140",
         "DELETE FROM favorite_champions WHERE user_id = 3 AND champion_id = 167"],
    13: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
         "VALUES (1, 162, '2026-09-22')",
         "INSERT INTO favorite_champions (user_id, champion_id, added_date) "
         "VALUES (2, 84, '2026-09-22')"],
    14: ["INSERT INTO bookmark_articles (user_id, article_id, added_date) "
         "VALUES (4, 133, '2026-09-22')",
         "DELETE FROM bookmark_articles WHERE user_id = 4 AND article_id = 80"],
    15: ["UPDATE users SET summoner_name = 'RadiantViper' WHERE id = 1"],
    16: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
         "VALUES (3, 85, '2026-09-22')"],
}

# wrong-delta mutations for the stateful tasks (collateral or wrong row)
WRONG_DELTA_SQL = {
    0: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (1, 46, '2026-09-22')"],                      # Hwei added, not Renata
    1: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (2, 1, '2026-09-22')"],                       # Aatrox added, not Ezreal
    2: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (4, 78, '2026-09-22')"],                      # Lux added, not Miss Fortune
    3: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (3, 64, '2026-09-22')"],                      # Kayn added, not Aatrox
    4: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (1, 39, '2026-09-22')"],                      # Garen added, not Viego
    5: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (3, 30, '2026-09-22')"],                      # Ekko added, not Fiora
    6: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (4, 90, '2026-09-22')"],                      # Nasus added, not Aatrox
    7: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (2, 101, '2026-09-22')"],                     # Poppy added, not Nasus
    8: ["INSERT INTO bookmark_articles (user_id, article_id, added_date) "
        "VALUES (4, 225, '2026-09-22')"],                     # Council saved, not Star Guardian
    9: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (2, 162, '2026-09-22')",
        "INSERT INTO bookmark_articles (user_id, article_id, added_date) "
        "VALUES (2, 82, '2026-09-22')"],                      # Yone added, not Lee Sin
    10: ["INSERT INTO bookmark_articles (user_id, article_id, added_date) "
         "VALUES (1, 107, '2026-09-22')"],                    # announcement saved, not retrospective
    11: [NEW_USER_SQL.replace("'HarborRookie'", "'WrongRookie'")],  # wrong summoner name
    12: ["DELETE FROM favorite_champions WHERE user_id = 3 AND champion_id = 140"],
    13: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
        "VALUES (1, 162, '2026-09-22')"],                     # alice's row only, bob's missing
    14: ["INSERT INTO bookmark_articles (user_id, article_id, added_date) "
         "VALUES (4, 133, '2026-09-22')"],                    # added but not removed
    15: ["UPDATE users SET summoner_name = 'RadiantViper', region = 'EUW' WHERE id = 1"],
    16: ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
         "VALUES (3, 11, '2026-09-22')"],                     # Ashe added, not Miss Fortune
}

WRONG_ANSWERS = {
    0: "Hwei and Renata both qualify; I added Hwei to favorites because he has 6 skins "
       "versus Renata's 4, and the account now has 7 favorites. Hwei's W is Bailout and "
       "his R is Hostile Takeover; Renata's W is Subject: Serenity.",
    1: "Both qualify; Lucian's E 'Relentless Pursuit' is the teleport, so I added "
       "Lucian; the account now has 6 favorites. Ezreal's roles are Marksman / Assassin.",
    2: "The first five by skins are Lux, Miss Fortune, Ahri, Akali, Ezreal. Lux's "
       "ultimate is Bullet Time with 24 skins; I added Lux, leaving 7 favorites.",
    3: "The darkin search returns four champions: Aatrox, Kayn, Naafiri and Varus. "
       "The Darkin Blade is Kayn, a Fighter rated High; I added him, so the account "
       "has 6 favorites.",
    4: "The search returns 63 champion cards and 25 news results. The first champion "
       "is Draven with epithet 'the Glorious Executioner'. The top news result is "
       "'Ruined King: Gameplay Deep Dive' from 2019. I added Viego; the account has "
       "7 favorites.",
    5: "Nine champions hold Pulsefire skins. The High-difficulty holders are Ekko and "
       "Riven; the Low holder is Lucian with 'Pulsefire Lucian'. I added Lucian and "
       "the account now has 6 favorites.",
    6: "The newest patches are 26.18 (2026-09-09) and 26.17 (2026-08-25). Aatrox's W "
       "cooldown went from 18/16/14/12/10 to 20/18/16/14/12. His W is World Ender and "
       "his E is Infernal Chains; I added him, so david has 6 favorites.",
    7: "The two champions adjusted in both patches are Master Yi and Kassadin. Nasus's "
       "Q change in 26.16 reads stacks 2 to 8 => 3 to 9. I added Poppy to favorites; "
       "the account now has 6 favorites.",
    8: "Page 2 of News starts with 'League of Legends Patch 26.15 Notes' (2026-07-28). "
       "The Lore category has 3 articles; I saved 'The Council Archives Primer' and "
       "the account now has 6 saved articles.",
    9: "The article was written by Riot Jag; ASU means Art and Sound Update. The search "
       "matches 3 champion cards; the updated champion is Wukong, whose W is Alpha "
       "Strike and R is Crescent Sweep. I added Wukong; the account has 6 favorites "
       "and 6 saved articles.",
    10: "The Vanguard search returns 4 news results and 2 champion cards, including "
        "Darius. The retrospective says over 150,000 accounts were banned and the "
        "scripting rate fell below 2%. I saved the announcement; the account now has "
        "5 saved articles.",
    11: "I created the account with summoner name 'HarborVeteran' and region NA, added "
        "Milio and saved the patch article; the account shows 2 favorite champions and "
        "1 saved article.",
    12: "After removing Trundle the account had 4 favorites: Jarvan IV, Rell, Trundle "
        "and Zac. After removing Zac it has 4 favorites: Jarvan IV, Rell, Udyr and Zac.",
    13: "Alice's account shows 7 favorites after adding Yone. Bob's account shows 4 "
        "favorites including Yone; after adding Milio bob has 5 favorites.",
    14: "After saving the patch article the account has 6 saved articles. I removed "
        "'Zaahen Abilities Rundown', the newest bookmark, leaving 3 saved articles.",
    15: "After the first change the account showed summoner name StarlitFox and region "
        "EUW. The final page shows RadiantViper and region KR.",
    16: "Killing Baron grants a shield and movement speed to the slayer's team. "
        "Mid-laners are the dynamite of the team. Miss Fortune's ultimate is Make It "
        "Rain with 21 skins; Ashe's is Volley with 24. I added Ashe; the account has "
        "6 favorites.",
    17: "The account has 4 favorite champions: Amumu, Draven, Kayle and Yunara. Kayle "
        "has the most skins with 19.",
}


@pytest.fixture(scope="module")
def tmp(tmp_path_factory):
    return tmp_path_factory.mktemp("lol_verify")


# ---------------------------------------------------------------- honest PASS
@pytest.mark.parametrize("n", range(18))
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
@pytest.mark.parametrize("n", range(18))
def test_noop_fail(n, tmp):
    run = tmp / f"noop_{n}"
    noop_run(run, f"League of Legends--{n}")
    verdict = run_verifier(n, run, SEED, SEED)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)


# ---------------------------------------------------------------- wrong answer FAIL
@pytest.mark.parametrize("n", range(18))
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
@pytest.mark.parametrize("n", range(18))
def test_shortcut_fail(n, tmp):
    """Correct answer, homepage-only navigation: every task requires on-site
    surfaces beyond the homepage, so the shortcut must FAIL for all 18."""
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
                       "'tamper@test.com', 'Tamper', 'Tamper', 'NA', "
                       "'7c58dd13f4172ec9e3d4f1a4b1c5f9e3c6e22b6bf38f76ca75c93e08a52e6c19', '2026-09-22')"])
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
    for entry in steps:
        rb.step(entry[0], entry[1], entry[2])
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
    """Task 9 with the compliant favorite + bookmark rows PLUS a collateral
    favorite write for another user must FAIL."""
    steps, answer = HONEST[9]
    run = tmp / "stateful_collateral"
    build_run(run, "League of Legends--9", steps, answer)
    after = mutate_db(
        SEED, tmp / "after_collateral.db",
        COMPLIANT_AFTER_SQL[9]
        + ["INSERT INTO favorite_champions (user_id, champion_id, added_date) "
           "VALUES (3, 1, '2026-09-22')"])
    verdict = run_verifier(9, run, SEED, after)
    assert verdict.get("pass") is False


# ------------------------------------------------------- subject binding (r2 fix)
# The r2 re-review blocking finding: answers that swap the compared subjects'
# facts (every token present, each bound to the wrong entity) were accepted by
# global token-in-answer checks. The reworked verifiers bind every multi-entity
# comparison fact to its subject; these tests lock that contract in place.

def test_bound_phrase_binds_fact_to_owner():
    ok = "Hwei's W is 'Subject: Serenity' and Renata's W is 'Bailout'."
    assert vl.bound_phrase(ok, "Subject Serenity", "Hwei", ["Renata"], mode="after")
    swapped = "Hwei's W is 'Bailout' and Renata's W is 'Subject: Serenity'."
    assert not vl.bound_phrase(swapped, "Subject Serenity", "Hwei", ["Renata"],
                               mode="after")
    # mode='near' binds by proximity in either direction
    assert vl.bound_count("Hwei has 4 skins and Renata has 6.", 4, "Hwei", ["Renata"])
    assert not vl.bound_count("Hwei has 6 skins and Renata has 4.", 4, "Hwei",
                              ["Renata"])


def test_bound_phrase_absent_fact_and_optional_owner():
    assert not vl.bound_phrase("Hwei's W is a mystery.", "Subject Serenity",
                               "Hwei", ["Renata"])
    # only_if_present: an answer that never characterises the fact is not penalised
    assert vl.bound_phrase("Hwei's W is a mystery.", "Subject Serenity", "Hwei",
                           ["Renata"], only_if_present=True)
    # optional_owner: with no owner label to bind to, presence alone is enough
    assert vl.bound_phrase("The profile shows EUW.", "EUW", "region", ["summoner"],
                           optional_owner=True)


def test_bound_date_binds_to_subject():
    ok = ("'Patch 26.19 Notes' (2026-09-22) and 'Patch 26.18 Notes' (2026-09-09).")
    assert vl.bound_date(ok, "2026-09-22", "26.19", ["26.18"], mode="after")
    swapped = ("'Patch 26.19 Notes' (2026-09-09) and 'Patch 26.18 Notes' (2026-09-22).")
    assert not vl.bound_date(swapped, "2026-09-22", "26.19", ["26.18"], mode="after")
    # any accepted date form binds the same way
    assert vl.bound_date("The retrospective (August 22, 2024) reported it.",
                         "2024-08-22", "retrospective", ["announcement"], mode="after")


def test_stem_matching_accepts_natural_word_forms():
    # r2 finding 1: whole-word gates false-negatived natural honest forms
    assert vl.contains_stem("delays an ally's death", "delay")
    assert vl.contains_stem("delaying their death", "delay")
    assert vl.contains_stem("Aatrox heals himself", "heal")
    assert vl.contains_stem("both values persisted", "persist")
    assert not vl.contains_stem("unrelated text", "delay")
    assert vl.bound_stem("Her W 'Bailout' delays an ally's death.", "delay",
                         "Bailout", ["Hostile Takeover"], mode="after")
    assert not vl.bound_stem("Her R 'Hostile Takeover' delays an ally's death.",
                             "delay", "Bailout", ["Hostile Takeover"], mode="after")


def test_bound_phrase_any_and_phrase_exclusion():
    skins = ["Cowgirl Miss Fortune", "Waterloo Miss Fortune"]
    ok = ("Miss Fortune's ultimate is 'Bullet Time'; one non-base skin is "
          "'Cowgirl Miss Fortune'.")
    assert vl.bound_phrase_any(ok, skins, "Bullet Time", ["Final Spark"], mode="after")
    swapped = "Lux's ultimate is 'Final Spark'; one non-base skin is 'Cowgirl Miss Fortune'."
    assert not vl.bound_phrase_any(swapped, skins, "Bullet Time", ["Final Spark"],
                                    mode="after")
    # negative half: a fact owned by rivals must never be attributed to the owner
    ok = ("Fiora is the Low-difficulty holder; Ekko, Riven and Twisted Fate are High.")
    assert vl.phrase_excluded_from(ok, "High", "Fiora", ["Ekko", "Riven",
                                   "Twisted Fate"])
    assert not vl.phrase_excluded_from("Fiora is a High-difficulty holder.", "High",
                                       "Fiora", ["Ekko", "Riven", "Twisted Fate"])


def test_state_count_segment_binds_lists_to_states():
    ok = ("After removing Trundle the page showed 4 remaining: Jarvan IV, Rell, "
          "Udyr, and Zac. After removing Zac, 3 left: Jarvan IV, Rell, Udyr.")
    assert vl.state_count_segment(ok, 4, "Trundle", ["Zac"], must_contain=["Zac"],
                                  mode="after")
    assert vl.state_count_segment(ok, 3, "Zac", ["Trundle"], forbid_after=["Zac"],
                                  mode="after")
    swapped = ("After removing Trundle the page showed 3 remaining: Jarvan IV, "
               "Rell, Udyr. After removing Zac, 4 left: Jarvan IV, Rell, Udyr, and Zac.")
    assert not vl.state_count_segment(swapped, 4, "Trundle", ["Zac"],
                                      must_contain=["Zac"], mode="after")
    assert not vl.state_count_segment(swapped, 3, "Zac", ["Trundle"],
                                      forbid_after=["Zac"], mode="after")


def test_name_spans_join_tolerant():
    assert vl.bound_count("Miss  Fortune has 24 skins.", 24, "Miss Fortune")
    assert vl.bound_count("LeeSin has 20 skins.", 20, "Lee Sin")
    # punctuation-tolerant titled subject: the year binds to the full title
    assert vl.bound_count("The Ruined King: Gameplay Deep Dive (2020-12-11).",
                          2020, "Ruined King Gameplay Deep Dive", mode="after")


def _swap_simultaneous(text, pairs):
    """Swap every a <-> b pair simultaneously (placeholder-safe): each a
    occurrence becomes b and each b occurrence becomes a, so every token stays
    present and only the subject binding flips (the r2 false-positive shape)."""
    for i, (a, b) in enumerate(pairs):
        assert a in text, f"swap source missing: {a!r}"
        text = text.replace(a, f"\x00{i}A\x00")
    for i, (a, b) in enumerate(pairs):
        assert b in text, f"swap target missing: {b!r}"
        text = text.replace(b, f"\x00{i}B\x00")
    for i, (a, b) in enumerate(pairs):
        text = text.replace(f"\x00{i}A\x00", b)
        text = text.replace(f"\x00{i}B\x00", a)
    return text


# per-task swapped-fact answers: simultaneous a<->b swaps (simple cases) or
# ordered (old -> new) replacements (complex clause rewrites), applied to the
# HONEST answer. Every one of these was a false positive against the old
# global token checks (r2 adversarial replay) and MUST now FAIL.
SWAP_SIMULTANEOUS = {
    0: [("Subject: Serenity", "Bailout"), ("Spiraling Despair", "Hostile Takeover")],
    1: [("Arcane Shift", "Relentless Pursuit")],
    2: [("Bullet Time", "Final Spark"), ("24 skins", "23 skins")],
    3: [("Fighter, Medium difficulty", "Fighter / Assassin, High")],
    6: [("2026-09-22", "2026-09-09")],
    9: [("Safeguard / Iron Will", "Dragon's Rage")],
    10: [("2024-02-29", "2024-04-11")],
    11: [("HarborRookie", "EUW")],
    13: [("Yone", "Milio")],
    14: [("5 saved articles", "4 saved articles")],
    15: [("RadiantViper", "EUW")],
    16: [("Bullet Time", "Enchanted Crystal Arrow"), ("24 skins", "21 skins")],
    17: [("19 skins", "20 skins")],
}
SWAP_REPLACEMENTS = {
    4: [("60 champion cards and 29 news results",
         "29 champion cards and 60 news results")],
    5: [("With the High difficulty filter the Pulsefire holders are Ekko, Riven,"
         " and Twisted Fate; Ekko's champion page confirms the High difficulty"
         " rating. With the Low difficulty filter, only Fiora remains.",
         "With the High difficulty filter, only Fiora remains. With the Low"
         " difficulty filter the Pulsefire holders are Ekko, Riven, and Twisted"
         " Fate; Ekko's champion page confirms the High difficulty rating.")],
    7: [("'Stacks: 3, increased to 12 on champions / large minions / monsters =>"
         " 4, increased to 10 on champions / large minions / monsters.'",
         "'Stacks: 4, increased to 10 on champions / large minions / monsters =>"
         " 3, increased to 12 on champions / large minions / monsters.'")],
    8: [("'Previously on Star Guardian' (2022-07-09), the story so far of the Star"
         " Guardian universe, and 'The Council Archives Primer' (2021-11-08), an"
         " invitation to wander the stacks of the Council Archives and explore"
         " the history of Piltover and beyond.",
         "'Previously on Star Guardian' (2022-07-09), a primer on the Council"
         " Archives, and 'The Council Archives Primer' (2021-11-08), a Star"
         " Guardian story recap.")],
    12: [("the favorites page showed 4 remaining: Jarvan IV, Rell, Udyr, and Zac."
          " After removing Zac as well, the account has 3 favorite champions"
          " left: Jarvan IV, Rell, and Udyr.",
          "the favorites page showed 3 remaining: Jarvan IV, Rell, and Udyr."
          " After removing Zac as well, the account has 4 favorite champions"
          " left: Jarvan IV, Rell, Udyr, and Zac.")],
}


def _swapped_answer(n):
    answer = HONEST[n][1]
    for old, new in SWAP_REPLACEMENTS.get(n, []):
        assert old in answer, f"T{n}: replacement source missing: {old!r}"
        answer = answer.replace(old, new)
    return _swap_simultaneous(answer, SWAP_SIMULTANEOUS.get(n, []))


@pytest.mark.parametrize("n", range(18))
def test_swapped_facts_fail(n, tmp):
    """Honest trajectory + compliant after-DB + the two subjects' facts swapped
    in the answer MUST FAIL (r2 blocking finding regression gate)."""
    steps, _ = HONEST[n]
    run = tmp / f"swapped_{n}"
    build_run(run, f"League of Legends--{n}", steps, _swapped_answer(n))
    if n in STATEFUL:
        after = mutate_db(SEED, tmp / f"after_swapped_{n}.db", COMPLIANT_AFTER_SQL[n])
    else:
        after = copy_db(SEED, tmp / f"after_swapped_{n}.db")
    verdict = run_verifier(n, run, SEED, after)
    assert verdict.get("pass") is False, json.dumps(verdict, indent=1)

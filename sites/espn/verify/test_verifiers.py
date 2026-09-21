#!/usr/bin/env python3
"""Positive and adversarial regression tests for every ESPN verifier.

These are SYNTHETIC GRADING CONTROLS, not independent browser attempts: each
positive case pins the exact trajectory shape and the ground-truth answer the
served mirror pages yield (recorded during the reviewer's real-Chromium audit
of the running container), and the adversarial cases prove the verifiers
reject no-op runs, recall shortcuts, wrong answers, DB writes, foreign task
ids, and broken run packages.

Every control runs the real CLI contract end-to-end:
    python verify_<n>.py --run_dir RUN --initial_db DB --after_db DB
exactly the way agent_demo/eval_judge.py invokes the verifier.

The seed DB fixture is fetched from the site container (docker cp) because the
repository tracks no instance assets; set WH_CONTAINER to point at the site's
container when it is not the default wh-ver-espn. When docker is unavailable
the suite falls back to a synthetic DB with the benchmark schema.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
SITE_DIR = VERIFY_DIR.parent
sys.path.insert(0, str(VERIFY_DIR))

import verify_lib

ORIGIN = "http://127.0.0.1:41014"
TASKS = list(range(44))

PNG = bytes.fromhex("89504e470d0a1a0a") + b"review-evidence" * 8

# task -> (navigation paths a compliant trajectory must contain, model answer)
POSITIVE = {
    0: (["/nba/standings"],
        "The NBA Eastern Conference standings (as of April 10, 2024): Atlantic — Boston Celtics 64-18, "
        "New York Knicks 50-32, Philadelphia 76ers 47-35, Toronto Raptors 25-57, Brooklyn Nets 32-50; "
        "Central — Cleveland Cavaliers 48-34, Indiana Pacers 47-35, Milwaukee Bucks 49-33, Chicago Bulls "
        "39-43, Detroit Pistons 14-68; Southeast — Miami Heat 46-36, Orlando Magic 47-35, Atlanta Hawks "
        "36-46, Washington Wizards 15-67, Charlotte Hornets 21-61. The Celtics lead the East at 64-18."),
    1: (["/nba/", "/nba/news", "/nba/transactions"],
        "No NBA trades occurred within the past 2 days (April 8-10, 2024). The most recent trade on ESPN's "
        "transactions page is James Harden traded from the Philadelphia 76ers to the LA Clippers (Oct 31, "
        "2023). Recent player movements in the window: Caleb Martin signed a 4-year contract extension with "
        "the Heat (Apr 9) and Aaron Gordon signed a $130M extension with the Nuggets (Apr 9); the Lakers' "
        "LeBron James also met the front office about a contract extension (Apr 8)."),
    2: (["/team/nba/milwaukee-bucks", "/game/17"],
        "The Bucks game within the last 2 days was played on April 9, 2024: Milwaukee Bucks 119, Indiana "
        "Pacers 114 (Final, Fiserv Forum). Main highlight: Giannis Antetokounmpo dominated with 35 points "
        "and 12 rebounds as the Bucks held off the Pacers in a tight contest."),
    3: (["/nba/scoreboard", "/game/17"],
        "The most recent NBA game broadcast on ESPN was played on April 9, 2024: the Indiana Pacers lost to "
        "the Milwaukee Bucks 114-119 (Final) at Fiserv Forum, broadcast on ESPN."),
    4: (["/nba/scoreboard"],
        "Yesterday's (April 9, 2024) NBA final scores: Indiana Pacers 114 - Milwaukee Bucks 119; Golden "
        "State Warriors 109 - Denver Nuggets 121; New York Knicks 102 - Miami Heat 108; Dallas Mavericks "
        "110 - Phoenix Suns 128; Philadelphia 76ers 110 - Boston Celtics 118; Minnesota Timberwolves 115 "
        "- Oklahoma City Thunder 121; Atlanta Hawks 118 - Cleveland Cavaliers 125; Sacramento Kings 108 "
        "- New Orleans Pelicans 116."),
    5: (["/nba/scoreboard", "/game/17", "/player/nba/giannis-antetokounmpo"],
        "From the latest completed game (April 9, 2024, Pacers @ Bucks), the top scorer was Giannis "
        "Antetokounmpo with 35 points, playing for the Milwaukee Bucks at power forward (PF)."),
    6: (["/team/nba/boston-celtics/schedule", "/game/36"],
        "The latest Lakers-Celtics game was played on February 1, 2024: Los Angeles Lakers 114, Boston "
        "Celtics 105 (Final at Crypto.com Arena). Top scorer from the match: LeBron James with 33 points."),
    7: (["/team/nba/los-angeles-lakers/schedule", "/game/19"],
        "The Lakers' latest game was on April 8, 2024: LA Clippers 111, Los Angeles Lakers 106 (Final at "
        "Crypto.com Arena). Summary: James Harden scored 30 points to lead the Clippers over the Lakers, "
        "while LeBron James led the Lakers with 29 points."),
    8: (["/nba/stats/leaders?stat=points"],
        "The top three scoring leaders in the NBA for 2023-24: Joel Embiid (Philadelphia 76ers) at 34.7 "
        "PPG, Luka Doncic (Dallas Mavericks) at 33.9 PPG, and Giannis Antetokounmpo (Milwaukee Bucks) at "
        "30.4 PPG."),
    9: (["/search?q=Los%20Angeles"],
        "8 teams have 'Los Angeles' in their name: the Los Angeles Lakers (NBA), Los Angeles Chargers "
        "(NFL), Los Angeles Rams (NFL), Los Angeles Kings (NHL), Los Angeles Angels (MLB), Los Angeles "
        "Dodgers (MLB), Los Angeles LA Galaxy (Soccer), and Los Angeles LAFC (Soccer). Only 1 of them is "
        "an NBA team: the Lakers."),
    10: (["/college-football/scoreboard", "/game/23"],
         "The latest college football championship game was played on January 8, 2024: the Michigan "
         "Wolverines defeated the Washington Huskies 34-13 in the College Football Playoff National "
         "Championship at Michigan Stadium — Michigan's first national championship in decades."),
    11: (["/nba/teams"],
         "There are 30 NBA teams. The teams with 'New' in their name: the New York Knicks and the New "
         "Orleans Pelicans."),
    12: (["/"],
         "The first three Top Headlines on the ESPN home page are: 1) a Soccer story (Champions League "
         "quarter-final preview: Real Madrid vs Manchester City), 2) an NHL story (NHL playoff picture "
         "comes into focus in the East), and 3) an NBA story (NBA Top Headlines: Celtics, LeBron, Embiid "
         "dominate news). So the leagues are Soccer, NHL, and NBA."),
    13: (["/nba/", "/story/nba-top-headlines-april-2024"],
         "Today's top headline in the Basketball section is 'NBA Top Headlines: Celtics, LeBron, Embiid "
         "dominate news' (April 9, 2024). Main points: the Boston Celtics clinched the league's best "
         "record (64-18); LeBron James broke the all-time scoring record with 39,000+ career points; Joel "
         "Embiid was ruled out indefinitely with a knee injury; and the playoff picture is taking shape "
         "across both conferences."),
    14: (["/nba/transactions"],
         "The most recent trade deal on ESPN's NBA transactions page: James Harden was traded from the "
         "Philadelphia 76ers to the Los Angeles Clippers (Oct 31, 2023). The most recent player "
         "acquisitions: Caleb Martin signed a 4-year extension with the Heat (Apr 9) and Aaron Gordon "
         "signed a $130M extension with the Nuggets (Apr 9)."),
    15: (["/nba/scoreboard?date=20231225"],
         "The NBA games played on December 25, 2023: Boston Celtics 117 - Los Angeles Lakers 120; Boston "
         "Celtics 122 - Golden State Warriors 115; New York Knicks 101 - Milwaukee Bucks 108; Golden "
         "State Warriors 114 - Denver Nuggets 127; Miami Heat 102 - Philadelphia 76ers 110."),
    16: (["/nba/scoreboard?date=20231225", "/nba/standings"],
         "The marquee NBA game on December 25, 2023 was Boston Celtics @ Los Angeles Lakers. Their "
         "current standings: the Celtics are 64-18 (.780), first in the Eastern Conference; the Lakers "
         "are 47-35 (.573) in the Western Conference."),
    17: (["/nba/bpi"],
         "In the NBA Basketball Power Index 2023-24, the Boston Celtics are in first place with a BPI of "
         "10.5, and the San Antonio Spurs are in last place (30th) with a BPI of 0.9."),
    18: (["/"],
         "You can choose from 12 sports/leagues on the ESPN home page: NFL, NBA, MLB, NHL, Soccer, "
         "College Football, Men's College Basketball, Women's College Basketball, Tennis, Golf, MMA, and "
         "Fantasy."),
    19: (["/team/nba/boston-celtics/roster"],
         "Kristaps Porzingis has the highest salary on the Boston Celtics 2023-24 roster: $36,000,000 "
         "(ahead of Jayson Tatum's $32,600,000)."),
    20: (["/nba/stats/leaders?stat=rebounds&conference=West",
          "/nba/stats/leaders?stat=assists&conference=West"],
         "In the NBA Western Conference, the rebounds leader is Domantas Sabonis (Sacramento Kings) with "
         "13.6 rebounds per game, and the assists leader is Luka Doncic (Dallas Mavericks) with 9.8 "
         "assists per game."),
    21: (["/team/nba/denver-nuggets/schedule", "/game/18"],
         "The Nuggets game within the last 3 days was on April 9, 2024: Denver Nuggets 121, Golden State "
         "Warriors 109 (Final at Ball Arena). Main highlight: Nikola Jokic posted 29 points and a "
         "triple-double as the Nuggets cruised past Golden State to clinch home court advantage."),
    22: (["/nba/transactions"],
         "Latest NBA transactions within the past week (April 3-10, 2024): Tobias Harris listed "
         "day-to-day with right ankle soreness (Apr 9); Caleb Martin signed a 4-year Heat extension "
         "(Apr 9); Aaron Gordon signed a $130M Nuggets extension (Apr 9); Joel Embiid ruled out "
         "indefinitely with a left knee injury (Apr 8); OG Anunoby reached an extension agreement with "
         "the Knicks (Apr 8); Ben Simmons waived by the Nets (Apr 7); Bobby Portis re-signed by the Bucks "
         "(Apr 7)."),
    23: (["/team/nba/miami-heat/schedule", "/game/25"],
         "The latest Heat-Knicks game was played on April 9, 2024: Miami Heat 108, New York Knicks 102 "
         "(Final at Kaseya Center). Top rebounder from the match: Bam Adebayo with 11 rebounds."),
    24: (["/nfl/scoreboard", "/game/83"],
         "The most recent NFL game broadcast on ESPN was played on January 21, 2024: the San Francisco "
         "49ers defeated the Green Bay Packers 24-21 (Final) at Levi's Stadium."),
    25: (["/nba/scoreboard", "/game/17", "/player/nba/tyrese-haliburton"],
         "From the latest NBA game (April 9, 2024, Pacers @ Bucks), the player with the most assists was "
         "Tyrese Haliburton with 11 assists, playing for the Indiana Pacers at point guard (PG)."),
    26: (["/nba/scoreboard", "/game/25"],
         "Yesterday's (April 9, 2024) NBA matchups: the only game in which the loser's high scorer "
         "outscored the winner's high scorer was Knicks @ Heat — the losing Knicks' Jalen Brunson scored "
         "36 points while the winning Heat's Jimmy Butler had 27. In every other game the winner's high "
         "scorer outscored the loser's."),
    27: (["/search?q=Golden"],
         "2 teams have 'Golden' in their name: the Golden State Warriors (NBA) and the Vegas Golden "
         "Knights (NHL). 1 of them is in the NHL — the Vegas Golden Knights."),
    28: (["/mlb/teams"],
         "There are 30 MLB teams. The only MLB team with 'City' in its name is the Kansas City Royals."),
    29: (["/soccer/", "/story/champions-league-quarter-final-preview"],
         "Today's top headline in the Soccer section is 'Champions League quarter-final preview: Real "
         "Madrid vs Manchester City headlines second leg' (April 9, 2024). Main points: Real Madrid host "
         "Manchester City in the second leg with the tie level on aggregate at the Bernabeu; Ancelotti is "
         "expected to start Vinicius Junior and Jude Bellingham while Guardiola considers a midfield "
         "reshuffle; the Bayern Munich vs Arsenal tie sits at 2-2 with Harry Kane in his most prolific "
         "European campaign."),
    30: (["/nhl/standings"],
         "NHL Standings 2023-24: in the Eastern Conference, the Boston Bruins top the Atlantic Division "
         "(47-20-15) and the Carolina Hurricanes top the Metropolitan Division (52-23-7), while the "
         "Ottawa Senators sit bottom of the Atlantic and the Washington Capitals bottom of the "
         "Metropolitan. In the Western Conference, the Dallas Stars lead the Central Division (52-21-9) "
         "and the Vegas Golden Knights lead the Pacific (45-29-8), with the Chicago Blackhawks last in "
         "the Central and the Anaheim Ducks last in the Pacific."),
    31: (["/team/mlb/new-york-yankees/roster"],
         "Anthony Rizzo (1B) is the heaviest infielder on the New York Yankees 2023-24 roster at 240 lbs."),
    32: (["/nhl/scoreboard"],
         "Yesterday's (April 9, 2024) NHL results: New York Rangers 2-4 Boston Bruins; Edmonton Oilers "
         "2-3 Vegas Golden Knights; Florida Panthers 1-3 Toronto Maple Leafs; Edmonton Oilers 4-5 "
         "Colorado Avalanche; Nashville Predators 2-4 Dallas Stars; New Jersey Devils 2-3 Carolina "
         "Hurricanes."),
    33: (["/nfl/news"],
         "The latest ESPN articles discussing potential 2023 NFL MVP candidates: 'Lamar Jackson's "
         "MVP-caliber season' (January 10, 2024) — Baltimore's quarterback stacks the resume; earlier "
         "pieces cover Patrick Mahomes' 2023 MVP candidacy (Dec 14, 2023), Josh Allen's MVP profile "
         "(Nov 22, 2023), and Jalen Hurts' MVP candidacy (Nov 12, 2023)."),
    34: (["/team/nba/philadelphia-76ers/injuries"],
         "The 76ers' latest injuries: Joel Embiid (C) is OUT with a left knee injury; Tobias Harris (PF) "
         "is DAY-TO-DAY with right ankle soreness; Robert Covington (SF) is OUT after left knee surgery; "
         "Mo Bamba (C) is day-to-day with right knee soreness; Kelly Oubre Jr. (SF) is questionable with "
         "a left hand contusion."),
    35: (["/team/nba/los-angeles-lakers/schedule", "/tickets/135"],
         "The Lakers' next game starts on April 13, 2024 at 8:00 PM ET — @ Portland Trail Blazers (TNT). "
         "From ESPN's ticket purchasing page for that game, the cheapest ticket available is the Upper "
         "Level (300-Level) at $55.00."),
    36: (["/search?q=Messi", "/player/soccer/lionel-messi/gamelog"],
         "Lionel Messi plays for Inter Miami CF. His last 5 games: April 9 @ Real Madrid — L 2-3; April 6 "
         "vs Paris Saint-Germain — W 1-0; April 3 @ Barcelona — W 4-2; March 30 vs Barcelona — D 2-2; "
         "March 23 @ Paris Saint-Germain — W 3-2. That is 3 wins, 1 draw, and 1 loss."),
    37: (["/player/nba/lebron-james"],
         "Per LeBron James' ESPN career stats, he has played 1,492 games in his career so far (with "
         "39,800 career points)."),
    38: (["/team/nba/los-angeles-lakers/stats"],
         "Anthony Davis played 76 games in 2023-24 — a games-played (GP) percentage of 92.7% (76 of 82). "
         "Yes, other Lakers players have the same games played percentage: Austin Reaves (76) and "
         "D'Angelo Russell (76)."),
    39: (["/team/nfl/new-york-jets/depth-chart"],
         "The players listed as injured in the 2ND position on the Jets depth chart: Zach Wilson (QB, "
         "Injured - Out), Connor McGovern (C, day-to-day - hip), Will McDonald IV (DE, day-to-day - "
         "ankle), Wes Schweitzer (LG, day-to-day - back), Olu Fashanu (LT, out - ankle sprain), Mike "
         "Williams (WR, day-to-day - knee), and Carter Warren (RT, out - knee)."),
    40: (["/espnplus"],
         "ESPN+ Tools is a suite of analytics, projections, and trade calculators that helps fans "
         "research matchups, build fantasy lineups, and dig into advanced stats — bundling the Trade "
         "Machine, Player Rater, Mock Draft, Bracket Predictor, and FPI / BPI projection dashboards in "
         "one subscriber-only workspace."),
    41: (["/nfl/teams"],
         "The NFC North contains four teams: the Chicago Bears, the Detroit Lions, the Green Bay "
         "Packers, and the Minnesota Vikings."),
    42: (["/mens-college-basketball/standings"],
         "In the America East Conference standings, the teams with equal wins and losses are Binghamton "
         "(9-9), UMass Lowell (10-10), and Maine (10-10). (UMBC and Albany are also tied at 11-7.)"),
    43: (["/womens-college-basketball/recruiting"],
         "The top three NCAAW recruits are committed to: No. 1 Paige Bueckers — UConn; No. 2 Aaliyah "
         "Edwards — Stanford; No. 3 Olivia Miles — USC."),
}

# wrong-answer negatives: same navigation as the positive, fabricated content
WRONG = {
    0: "The Eastern Conference is led by the Miami Heat with a 58-24 record.",
    1: "The Lakers traded Anthony Davis to the Heat for Tyler Herro two days ago.",
    2: "The Bucks lost 98-101 to the Bulls two days ago; Bobby Portis scored 40.",
    3: "The most recent NBA game on ESPN was the Warriors beating the Lakers 130-120 on May 1, 2024.",
    4: "Yesterday the Knicks beat the Celtics 150-90 and the Suns beat the Bucks 140-100.",
    5: "The top scorer in the latest game was Tyrese Haliburton with 22 points for the Pacers at center.",
    6: "The Lakers beat the Celtics 120-117 with Jayson Tatum scoring 32 as the game's top scorer.",
    7: "The Lakers won their latest game 115-100 behind a 40-point night from Anthony Davis.",
    8: "The top three scorers are Stephen Curry, Ja Morant, and Trae Young of the Hawks.",
    9: "5 teams have Los Angeles in their name and 3 of them are NBA teams.",
    10: "Alabama beat Georgia 45-42 in the latest college football championship game.",
    11: "There are 32 NBA teams; the 'New' teams are the New York Knicks and the New Jersey Nets.",
    12: "The first three headlines are from the NFL, MLB, and MLS.",
    13: "The top Basketball story is about the Warriors trading for a new center.",
    14: "The Sixers acquired a new point guard from the Nuggets in a trade yesterday.",
    15: "On December 25 the Bucks beat the Knicks 150-100 and the Heat beat the Lakers 99-90.",
    16: "The Christmas game was Knicks @ Heat; the Knicks stand 50-32 and the Heat 60-22.",
    17: "The Nuggets are first in the BPI at 12.3 and the Pistons are last at 1.1.",
    18: "ESPN's home page offers 6 leagues: NFL, NBA, MLB, NHL, MLS, and NCAA.",
    19: "Jayson Tatum has the highest salary on the Celtics roster at $37.1 million.",
    20: "The Western Conference rebounds leader is Anthony Davis at 12.6 and assists leader is Trae Young at 10.8.",
    21: "The Nuggets lost 98-120 to the Spurs three days ago; Victor Wembanyama scored 40.",
    22: "Within the past week the Celtics traded Jaylen Brown and signed a new center from Europe.",
    23: "The Heat beat the Knicks 110-99 with Jimmy Butler grabbing 15 rebounds as the top rebounder.",
    24: "The most recent NFL game on ESPN was the Bills beating the Dolphins 30-27 on January 15, 2024.",
    25: "Giannis Antetokounmpo had the most assists in the latest game with 14 for the Bucks at center.",
    26: "The qualifying matchup was the Bucks-Pacers game, where Haliburton's 22 outscored Giannis's 35.",
    27: "4 teams have 'Golden' in their name and 2 are in the NHL.",
    28: "There are 32 MLB teams and the 'City' teams are Kansas City and New York City Mets.",
    29: "The top soccer story is Messi's move to Al-Hilal, summarizing his new contract.",
    30: "The Rangers top the East and the Kings top the West; the divisions are North and South.",
    31: "Giancarlo Stanton is the heaviest infielder on the Yankees at 245 pounds.",
    32: "Yesterday the Rangers beat the Oilers 8-2 and the Maple Leafs beat the Panthers 6-0.",
    33: "The latest NFL MVP article is about Brock Purdy's 2024 MVP case.",
    34: "The 76ers are fully healthy with Embiid probable with a wrist sprain.",
    35: "The Lakers next play tomorrow at 7:00 PM ET vs the Warriors; the cheapest ticket is $220.",
    36: "Messi played for Real Madrid and PSG; he won all of his last five games 5-0.",
    37: "LeBron James has played 1,620 career games.",
    38: "Davis played 60 games (73%); no other Laker has the same percentage.",
    39: "Only Aaron Rodgers is injured on the Jets depth chart in the 2ND position.",
    40: "ESPN+ Tools is a streaming add-on used to watch live games and buy merchandise.",
    41: "The NFC North contains the Bears, Lions, Cowboys, and Eagles.",
    42: "Vermont is the only team with equal wins and losses at 14-14.",
    43: "The top three recruits are committed to UConn, Duke, and Kentucky.",
}


_RUN_SEQ = [0]


def make_run(root: Path, task: int, paths, answer, *, task_id=None, origin=ORIGIN,
            drop_trajectory=False, break_screenshot=False, db_task_id=None):
    _RUN_SEQ[0] += 1
    run = root / f"run_{task}_{_RUN_SEQ[0]:04d}"
    shots = run / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    paths = list(paths)
    steps = []
    for index, path in enumerate(paths):
        shot = f"step_{index:03d}.png"
        (shots / shot).write_bytes(PNG)
        steps.append({"step": index, "url": origin + path, "action": "click",
                      "action_result": {"success": True}, "screenshot_after": shot})
    final_shot = f"step_{len(paths):03d}.png"
    if not break_screenshot:
        (shots / final_shot).write_bytes(PNG)
    steps.append({"step": len(paths), "url": origin + (paths[-1] if paths else "/"),
                  "action": "done", "action_result": {"success": True},
                  "screenshot_after": final_shot})
    trajectory = {
        "task_id": db_task_id or f"ESPN--{task}",
        "task": "fixture",
        "start_url": origin + "/",
        "terminated": True,
        "termination_reason": "agent_done",
        "final_answer": answer,
        "steps": steps,
    }
    if not drop_trajectory:
        (run / "trajectory.json").write_text(json.dumps(trajectory))
    return run


def run_verifier(verifier: Path, run_dir: Path, initial_db: Path, after_db: Path):
    cmd = [sys.executable, str(verifier), "--run_dir", str(run_dir),
           "--initial_db", str(initial_db), "--after_db", str(after_db)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(VERIFY_DIR))
    try:
        verdict = json.loads(r.stdout)
    except Exception:
        verdict = {"pass": False, "reason": f"verifier crashed: {r.stderr[:300]}"}
    return r.returncode, verdict


def fetch_seed_db(tmp: Path) -> Path:
    """Real instance_seed from the container when possible, else synthetic schema."""
    container = os.environ.get("WH_CONTAINER", "wh-ver-espn")
    out = tmp / "espn_seed.db"
    r = subprocess.run(["docker", "cp", f"{container}:/opt/WebSyn/espn/instance_seed/espn.db", str(out)],
                       capture_output=True, text=True)
    if r.returncode == 0 and out.exists():
        return out
    con = sqlite3.connect(out)
    for t in verify_lib.TABLES:
        con.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY, x TEXT)")
    con.execute("INSERT INTO teams VALUES (1, 'lakers')")
    con.commit(); con.close()
    return out


class TestEspnVerifiers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="espn-verify-tests-"))
        cls.seed = fetch_seed_db(cls.tmp)
        cls.after = cls.tmp / "espn_after.db"
        shutil.copy(cls.seed, cls.after)
        cls.dirty = cls.tmp / "espn_dirty.db"
        shutil.copy(cls.seed, cls.dirty)
        con = sqlite3.connect(cls.dirty)
        try:
            try:
                # real schema: bump one team's wins (content fingerprint changes)
                con.execute("UPDATE teams SET wins = wins + 1 WHERE id = (SELECT MIN(id) FROM teams)")
            except sqlite3.OperationalError:
                # synthetic fallback schema: add a row instead (fingerprint changes)
                con.execute("INSERT INTO teams (id, x) VALUES (424242, 'dirty')")
            con.commit()
        finally:
            con.close()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def grade(self, task, run):
        v = VERIFY_DIR / f"verify_{task}.py"
        return run_verifier(v, run, self.seed, self.after)

    # ---------------------------------------------------------------- contract
    def test_tasks_jsonl_contract(self):
        lines = (SITE_DIR / "tasks.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 44)
        for line in lines:
            row = json.loads(line)
            self.assertEqual(list(row.keys()),
                             ["web_name", "id", "ques", "web", "upstream_url",
                              "verifier_path", "judge_rubric"])
            self.assertNotIn("answer", row)
            self.assertTrue(row["judge_rubric"].startswith("FACT CHECKPOINTS."))
            self.assertIn("FAIL", row["judge_rubric"])
            vp = (SITE_DIR.parent.parent) / row["verifier_path"]
            self.assertTrue(vp.exists(), f"missing verifier {vp}")

    # ---------------------------------------------------------------- per-task
    def _positive(self, task):
        paths, answer = POSITIVE[task]
        run = make_run(self.tmp, task, paths, answer)
        rc, verdict = self.grade(task, run)
        self.assertEqual(rc, 0, f"positive for {task} should PASS: {verdict}")
        self.assertTrue(verdict["pass"], verdict)

    def _noop(self, task):
        run = make_run(self.tmp, task, ["/"], "")
        rc, verdict = self.grade(task, run)
        self.assertNotEqual(rc, 0, f"no-op for {task} must FAIL")
        self.assertFalse(verdict["pass"])

    def _shortcut(self, task):
        paths, answer = POSITIVE[task]
        if task in (12, 18):
            # These two tasks legitimately require ONLY the mirror homepage, so
            # the shortcut simulation is a run that never opened the mirror at
            # all (off-site origin) while still producing the right answer.
            run = make_run(self.tmp, task, ["/"], answer, origin="http://example.com")
        else:
            run = make_run(self.tmp, task, ["/"], answer)  # homepage only
        rc, verdict = self.grade(task, run)
        self.assertNotEqual(rc, 0, f"shortcut for {task} must FAIL")
        self.assertFalse(verdict["pass"])
        self.assertTrue(verdict["reason"].startswith("nav_"),
                        f"shortcut for {task} should fail on navigation, got {verdict['reason']}")

    def _wrong(self, task):
        paths = POSITIVE[task][0]
        run = make_run(self.tmp, task, paths, WRONG[task])
        rc, verdict = self.grade(task, run)
        self.assertNotEqual(rc, 0, f"wrong-answer for {task} must FAIL")
        self.assertFalse(verdict["pass"])

    def _state_mismatch(self, task):
        paths, answer = POSITIVE[task]
        run = make_run(self.tmp, task, paths, answer)
        v = VERIFY_DIR / f"verify_{task}.py"
        rc, verdict = run_verifier(v, run, self.seed, self.dirty)
        self.assertNotEqual(rc, 0, f"state-mismatch for {task} must FAIL")
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["reason"], "db_state_readonly", verdict)

    def _broken_package(self, task):
        # missing screenshots
        paths, answer = POSITIVE[task]
        run = make_run(self.tmp, task, paths, answer, break_screenshot=True)
        rc, verdict = self.grade(task, run)
        self.assertFalse(verdict["pass"], f"broken screenshots for {task} must FAIL")
        # missing trajectory
        run = make_run(self.tmp, task, paths, answer, drop_trajectory=True)
        rc, verdict = self.grade(task, run)
        self.assertFalse(verdict["pass"], f"missing trajectory for {task} must FAIL")
        self.assertEqual(verdict["reason"], "run_package_valid")
        # foreign task id
        run = make_run(self.tmp, task, paths, answer, db_task_id="ESPN--999")
        rc, verdict = self.grade(task, run)
        self.assertFalse(verdict["pass"], f"foreign task id for {task} must FAIL")
        self.assertEqual(verdict["reason"], "run_package_valid")


def _add_task_tests():
    for task in TASKS:
        def positive(self, t=task):
            self._positive(t)
        def noop(self, t=task):
            self._noop(t)
        def shortcut(self, t=task):
            self._shortcut(t)
        def wrong(self, t=task):
            self._wrong(t)
        def state(self, t=task):
            self._state_mismatch(t)
        def broken(self, t=task):
            self._broken_package(t)
        setattr(TestEspnVerifiers, f"test_positive_{task:02d}", positive)
        setattr(TestEspnVerifiers, f"test_noop_{task:02d}", noop)
        setattr(TestEspnVerifiers, f"test_shortcut_{task:02d}", shortcut)
        setattr(TestEspnVerifiers, f"test_wrong_answer_{task:02d}", wrong)
        setattr(TestEspnVerifiers, f"test_state_mismatch_{task:02d}", state)
        setattr(TestEspnVerifiers, f"test_broken_package_{task:02d}", broken)


def _add_rework_tests():
    """Acceptor-rework regression controls (items B and C of ACCEPT.md §7).

    B (verify_35): the task asks only for the next game's start and the
    cheapest ticket, so an answer WITHOUT the opponent named must still PASS
    when date/time/ticket/navigation are right, while a wrong ticket price or
    wrong date still FAILs.
    C (verify_33): an honest answer anchored on the LATER MVP meta-articles
    (which discuss MVP cases/voting without naming candidates) must PASS
    with its own on-page facts; a fabricated subject still FAILs (covered by
    the standard wrong-answer case).
    """
    def v35_no_opponent_pass(self):
        run = make_run(self.tmp, 35,
                       ["/team/nba/los-angeles-lakers/schedule", "/tickets/135"],
                       "The Lakers' next game starts on April 13, 2024 at 8:00 PM ET. "
                       "From ESPN's ticket purchasing page for that game, the cheapest "
                       "ticket available is the Upper Level (300-Level) at $55.00.")
        rc, verdict = self.grade(35, run)
        self.assertEqual(rc, 0, f"no-opponent honest answer must PASS: {verdict}")
        self.assertTrue(verdict["pass"], verdict)

    def v35_wrong_ticket_fail(self):
        run = make_run(self.tmp, 35,
                       ["/team/nba/los-angeles-lakers/schedule", "/tickets/135"],
                       "The Lakers' next game starts on April 13, 2024 at 8:00 PM ET. "
                       "From ESPN's ticket purchasing page for that game, the cheapest "
                       "ticket available is the Courtside (Floor) at $575.00.")
        rc, verdict = self.grade(35, run)
        self.assertNotEqual(rc, 0, "a wrong cheapest-ticket claim must FAIL")
        self.assertEqual(verdict["reason"], "answer_cheapest_ticket")

    def v35_wrong_date_fail(self):
        run = make_run(self.tmp, 35,
                       ["/team/nba/los-angeles-lakers/schedule", "/tickets/135"],
                       "The Lakers' next game starts on April 16, 2024 at 7:30 PM ET, and "
                       "the cheapest ticket on the ticket page is $55.")
        rc, verdict = self.grade(35, run)
        self.assertNotEqual(rc, 0, "a wrong next-game date must FAIL")
        self.assertEqual(verdict["reason"], "answer_next_game_date")

    def v33_meta_article_pass(self):
        run = make_run(self.tmp, 33,
                       ["/nfl/news", "/story/quarterback-evaluation-tools-mvp-april-2024"],
                       "The latest ESPN article discussing NFL MVP candidates for 2023 is "
                       "'Quarterback evaluation tools and MVP thinking' (April 4, 2024, "
                       "Mike Sando): analytics teams around the league have refined the "
                       "toolkit for assessing quarterback MVP cases, with EPA, CPOE, and "
                       "time-to-throw becoming standard reference metrics that voters "
                       "weigh alongside the eye test.")
        rc, verdict = self.grade(33, run)
        self.assertEqual(rc, 0, f"honest meta-article answer must PASS: {verdict}")
        self.assertTrue(verdict["pass"], verdict)

    def v33_retrospective_pass(self):
        run = make_run(self.tmp, 33,
                       ["/nfl/news"],
                       "The latest ESPN article on the 2023 NFL MVP race is the "
                       "'Retrospective: 2023 MVP race revisited' piece (March 12, 2024, "
                       "Mike Sando), an offseason look back at the regular-season honors.")
        rc, verdict = self.grade(33, run)
        self.assertEqual(rc, 0, f"honest retrospective answer must PASS: {verdict}")

    setattr(TestEspnVerifiers, "test_rework_b35_no_opponent_pass", v35_no_opponent_pass)
    setattr(TestEspnVerifiers, "test_rework_b35_wrong_ticket_fail", v35_wrong_ticket_fail)
    setattr(TestEspnVerifiers, "test_rework_b35_wrong_date_fail", v35_wrong_date_fail)
    setattr(TestEspnVerifiers, "test_rework_c33_meta_article_pass", v33_meta_article_pass)
    setattr(TestEspnVerifiers, "test_rework_c33_retrospective_pass", v33_retrospective_pass)


_add_task_tests()
_add_rework_tests()

if __name__ == "__main__":
    unittest.main(verbosity=1)

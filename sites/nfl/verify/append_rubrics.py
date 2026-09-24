#!/usr/bin/env python3
"""append_rubrics.py - record the reviewer's grading contract into tasks.jsonl.

For each NFL task row, append ``verifier_path`` and ``judge_rubric`` keys by
STRING INSERTION so the original 5-key prefix of every line stays byte-for-byte
identical (same trick as the megabus/michaels reviewer suites). Ground truth
lives ONLY inside the verifiers; the rubrics below state the RULES an LLM judge
checks (which pages must have been opened, which facts must appear, that an
empty answer is a FAIL) - never the answers themselves.

r2 sync: the 20 redesigned tasks (NFL--0, 2..20) received new rubrics matching
their extended chains; NFL--1 (text unchanged from the contribution) keeps its
original rubric.
r3 sync: the five deepened tasks (NFL--3, 8, 9, 13, 14) received rubrics
covering the added depth rings (team pages, passing ranks, Week 2 finals,
standings/schedule facts, preview channels + Up Next, article authors/dates).
Usage: python3 append_rubrics.py [--check]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TASKS = Path(__file__).resolve().parent.parent / "tasks.jsonl"

RUBRICS = {
    "NFL--0": (
        "sites/nfl/verify/verify_0.py",
        "FACT CHECKPOINTS: The agent must have signed in as the demo account, opened the "
        "NFL+ plans page, selected the annual plan that includes NFL RedZone for a "
        "subscriber who currently pays monthly, completed the card checkout with a Visa "
        "in the subscriber's name, seen the order confirmation page, opened the account "
        "page (the new plan and renewal date), switched the newsletter on from the "
        "profile edit page, and returned to the homepage where the My Team module "
        "renders. The final answer MUST state the order reference shown on the "
        "confirmation page, the total charged including tax (price plus 8.95% tax), the "
        "plan and renewal date the account now shows, and the My Team module's Week 3 "
        "facts (opponent, day, kickoff). An answer missing any of these, or an empty "
        "answer, is a FAIL.",
    ),
    "NFL--1": (
        "sites/nfl/verify/verify_1.py",
        "FACT CHECKPOINTS: The agent must have created a new account (with the Chicago "
        "Bears as the favorite team), opened the NFL+ plans page, subscribed to the "
        "cheapest monthly plan, paid with a valid test card, seen the order confirmation, "
        "and opened the account page where the renewal date is shown. The final answer "
        "MUST state the order reference, the total charged including tax, and the exact "
        "renewal date. An answer missing any of the three, or an empty answer, is a FAIL.",
    ),
    "NFL--2": (
        "sites/nfl/verify/verify_2.py",
        "FACT CHECKPOINTS: The agent must have signed in as the demo account, opened the "
        "account page listing the current plan, per-cycle price and order history, "
        "cancelled the subscription from the account page, opened the profile edit page "
        "and switched the newsletter on and set the new password, signed out, and signed "
        "back in with the new password (two sign-in visits and the new password typed "
        "must appear in the trajectory), then returned to the homepage for the My Team "
        "module. The final answer MUST state the plan the subscriber was on, its "
        "per-cycle price, the order reference and total of the original purchase, the "
        "post-cancellation status, the newsletter setting, and the My Team module's "
        "Week 3 facts (opponent, day, kickoff). An answer missing any of these, or an "
        "empty answer, is a FAIL.",
    ),
    "NFL--3": (
        "sites/nfl/verify/verify_3.py",
        "FACT CHECKPOINTS: The agent must have opened the rushing leaderboard, BOTH "
        "leaders' player pages, BOTH team pages (head coach + home stadium), the "
        "passing leaderboard (the two quarterbacks' passing-yardage ranks), BOTH Week 3 "
        "game centers, the standings, and the injury report (or a game center's injury "
        "section). The final answer MUST report, for each of the top two rushers: his "
        "team, rushing yards, attempts, yards per attempt, touchdowns, jersey number, "
        "weight and college; for each of their teams: the head coach and home stadium "
        "from the team page; where each team's quarterback ranks in passing yards and "
        "with how many; for each of their teams' Week 3 games: opponent, day, kickoff, "
        "stadium and both teams' records; all four teams' point differentials from the "
        "standings; and whether either rusher's quarterback is on the Week 3 injury "
        "report with his practice status. An answer missing any of these, or an empty "
        "answer, is a FAIL.",
    ),
    "NFL--4": (
        "sites/nfl/verify/verify_4.py",
        "FACT CHECKPOINTS: The agent must have opened the standings, the Week 1 and "
        "Week 2 scores pages (the two finals), the Week 3 and Week 4 scores pages (the "
        "next two scheduled games), both next-game game centers, and both opponents' "
        "team pages. The final answer MUST name the highest-scoring undefeated team "
        "with its division standing, record, points scored and allowed; its Week 1 and "
        "Week 2 finals (opponents and scores); and for each of the next two games: the "
        "opponent, day, kickoff and stadium from the game center, the opponent's record "
        "and point differential from the standings, and the opponent's head coach and "
        "home stadium. An answer missing any of these, or an empty answer, is a FAIL.",
    ),
    "NFL--5": (
        "sites/nfl/verify/verify_5.py",
        "FACT CHECKPOINTS: The agent must have scanned the week-by-week scores pages "
        "(the international weeks' scores pages must appear in the trajectory), opened "
        "the played international game's game center, and opened the standings for the "
        "current records. The final answer MUST list every game the site marks as "
        "international with its week, matchup, and day with kickoff time; and for the "
        "one already played: the final score, the winner, the attendance, the venue "
        "with its city, and the network. NOTE: the game center's quarter-by-quarter "
        "table currently renders corrupted (a known site defect documented in the r2 "
        "review), so quarter detail is not gated. An answer missing the international "
        "games or the played game's facts, or an empty answer, is a FAIL.",
    ),
    "NFL--6": (
        "sites/nfl/verify/verify_6.py",
        "FACT CHECKPOINTS: The agent must have opened the league injury report, the "
        "Week 3 game center of the Thursday-night game, both teams' rosters with the "
        "position filters applied (WR for the Packers, DE for the Falcons), and both "
        "team pages. The final answer MUST list every player officially designated OUT "
        "for the game with position and injury, every QUESTIONABLE player, the game's "
        "day, kickoff, stadium and both teams' records, the jersey number, height, "
        "weight and college of the Packers' OUT wide receiver and the Falcons' OUT "
        "defensive end, and both teams' head coaches and home stadiums. An answer "
        "missing any officially designated player or any of these facts, or an empty "
        "answer, is a FAIL.",
    ),
    "NFL--7": (
        "sites/nfl/verify/verify_7.py",
        "FACT CHECKPOINTS: The agent must have opened BOTH teams' rosters with the "
        "wide receiver filter applied, the Week 3 injury report, the listed receiver's "
        "player page, the game center, and both team pages. The final answer MUST list "
        "every active wide receiver under 200 pounds on BOTH teams with name, jersey "
        "number (or that none is listed), height, weight, experience and college; "
        "identify which of them is officially listed on the injury report with his "
        "injury and game status and what his player page lists as his position and "
        "college; and report the game's day, kickoff and stadium plus each team's "
        "record and head coach. Receivers weighing 200 pounds or more must not be "
        "included. An answer missing any qualifying receiver or any of these facts, or "
        "an empty answer, is a FAIL.",
    ),
    "NFL--8": (
        "sites/nfl/verify/verify_8.py",
        "FACT CHECKPOINTS: The agent must have searched the player directory for the "
        "running back, opened his player page, the Eagles team page, the Eagles roster "
        "with BOTH the running back and quarterback filters applied, the Week 2 scores "
        "page, the Week 3 Monday-night game center, and the Bears team page. The final "
        "answer MUST report the running back's jersey number, height, weight, "
        "experience and college exactly as the site lists them; the Eagles' head coach "
        "and home stadium; every other running back and every quarterback on the "
        "active roster; the team's record and division standing; the Eagles' Week 2 "
        "final (opponent and score) from the scores pages; the Week 3 Monday-night "
        "game's opponent, day, kickoff and stadium; and the Bears' head coach and home "
        "stadium. An answer missing any of these, or an empty answer, is a FAIL.",
    ),
    "NFL--9": (
        "sites/nfl/verify/verify_9.py",
        "FACT CHECKPOINTS: The agent must have opened the transactions hub including "
        "its Reserve List and Waivers categories, the newsroom (paginating as needed) "
        "and the article about the veteran tight end signing to the Eagles' practice "
        "squad, the player directory search for the veteran punter and his player "
        "page, the Vikings team page, the standings, and the Vikings schedule. The "
        "final answer MUST list every player "
        "signed to a practice squad on September 23 with the signing team and whether "
        "he was a veteran signing, name the teams making more than one such signing, "
        "list that day's Reserve/Injured placements and waiver terminations, give the "
        "tight end article's title and author, and report the punter's listed team, "
        "position and experience plus the Vikings' head coach and record; the Vikings' "
        "division rank and point differential from the standings; and their Week 3 "
        "opponent, date and kickoff from the schedule. An answer "
        "missing any of the day's practice-squad signings or any of these facts, or an "
        "empty answer, is a FAIL.",
    ),
    "NFL--10": (
        "sites/nfl/verify/verify_10.py",
        "FACT CHECKPOINTS: The agent must have opened the newsroom (paginating as "
        "needed), the article about the Giants quarterback's season-ending knee "
        "surgery, the article about the Bears quarterback's hamstring injury, the site "
        "search for the earlier September 22 report and that report's page, and both "
        "team pages. The final answer MUST state each quarterback's name, team, "
        "injury and how long the article says he might be out, each article's author "
        "and publish date, the exact title of the September 22 report, and from both "
        "team pages: each head coach, record, division standing, and Week 3 opponent. "
        "An answer missing any of these, or an empty answer, is a FAIL.",
    ),
    "NFL--11": (
        "sites/nfl/verify/verify_11.py",
        "FACT CHECKPOINTS: The agent must have opened the video hub and all four "
        "channel pages, the Thursday-night preview video's page, and the three named "
        "videos' pages or channel listings. The final answer MUST quote the preview "
        "video's exact title, name its channel, quote its full description, name at "
        "least two other Week 3 preview videos on that channel, report the titles of "
        "the Commissioner's Exempt List video (with its channel), the Packers' Week 2 "
        "recap video, and the Good Morning Football video about the linebacker's most "
        "complete game, and state which of the four channels lists the fewest videos. "
        "An answer missing any of these, or an empty answer, is a FAIL.",
    ),
    "NFL--12": (
        "sites/nfl/verify/verify_12.py",
        "FACT CHECKPOINTS: The agent must have signed in as the demo account, changed "
        "the favorite team from the profile edit page, returned to the homepage where "
        "the My Team module renders, opened the new team's page and schedule, both "
        "next-game game centers, and the standings. The final answer MUST report the "
        "module's team full name, record, division standing and next opponent with day "
        "and kickoff; the team's head coach and home stadium; the next two games' "
        "opponents, days, kickoffs and stadiums (the stadiums from the game centers); "
        "the Week 3 game's network; and the team's division rank and point "
        "differential from the standings. An answer missing any of these, or an empty "
        "answer, is a FAIL.",
    ),
    "NFL--13": (
        "sites/nfl/verify/verify_13.py",
        "FACT CHECKPOINTS: The agent must have opened the Week 3 scores, all three "
        "prime-time game centers, the standings, the video hub, all three preview "
        "video pages, and the newsroom article with three must-know storylines for "
        "the Thursday game. The final answer MUST give, for each of the Thursday, "
        "Sunday and Monday night windows: the away-at-home matchup, the day with "
        "kickoff time, the network, the stadium, and both teams' records from the "
        "game center; name which of the six teams is still undefeated per the "
        "standings; for each game, the preview video's exact title, its channel, and "
        "the first video its page lists under Up Next; and the storylines article's "
        "author and date. An answer missing any window or any of these facts, or an "
        "empty answer, is a FAIL.",
    ),
    "NFL--14": (
        "sites/nfl/verify/verify_14.py",
        "FACT CHECKPOINTS: The agent must have identified the AFC West's other "
        "undefeated team from the standings and opened its team page and season "
        "schedule, its Week 1 and Week 2 game centers, its first post-bye home game "
        "center, its Week 3 game center, the post-bye opponent's team page, and the "
        "Week 2 aftermath article spotlighting this team and the Chiefs. The final "
        "answer MUST report the team's record, point differential and division rank; "
        "the two finals from the Week 1 and Week 2 game centers; which week is its "
        "bye (worked out from the schedule); the first home game after the bye with "
        "opponent, date, kickoff and both teams' records from that game center; its "
        "head coach and home stadium; its Week 3 game's day, kickoff and stadium; the "
        "post-bye opponent's head coach; and the aftermath article's author and "
        "date. An answer missing any of these, or an empty answer, is a FAIL.",
    ),
    "NFL--15": (
        "sites/nfl/verify/verify_15.py",
        "FACT CHECKPOINTS: The agent must have opened the NFL+ plans page (comparing "
        "the four plans), signed in as the demo account, completed the Premium "
        "Monthly checkout with a valid test card in the subscriber's name, seen the "
        "order confirmation, and opened the account page for the new renewal date. "
        "The final answer MUST list all four plans by name with their prices and "
        "billing cycles and state which include NFL RedZone; report the old plan and "
        "price, the new order reference, the total charged including tax, the new "
        "renewal date, and whether the monthly plan costs more or less per year with "
        "the math shown (monthly price times twelve versus the annual price). An "
        "answer missing any of these, or an empty answer, is a FAIL.",
    ),
    "NFL--16": (
        "sites/nfl/verify/verify_16.py",
        "FACT CHECKPOINTS: The agent must have run the site search for 'Mahomes', "
        "opened the most recent news article about him, opened at least three of the "
        "video results, opened his player page, his team's page, and the standings. "
        "The final answer MUST state how many player, news and video results the "
        "search returns (the page deliberately shows no count labels - the counts must "
        "come from reading the result rows); the most recent article's title, author, "
        "date, and two facts from its body; the titles and channels of three video "
        "results; his team, jersey number, height and experience from the player page; "
        "his team's head coach and record; and the team's division rank and point "
        "differential from the standings. An answer missing any of these, or an empty "
        "answer, is a FAIL.",
    ),
    "NFL--17": (
        "sites/nfl/verify/verify_17.py",
        "FACT CHECKPOINTS: The agent must have found the player page via the "
        "directory, opened the passing leaderboard, the Chiefs' Week 2 game center, "
        "the Chiefs schedule page, the video hub, and the standings. The final answer "
        "MUST report his career totals for games, pass attempts, passing yards, "
        "touchdowns and interceptions; his single-season best passing yardage with "
        "the year; his 2026 row; his Week 2 stat line; his college; his rank and "
        "yardage on the passing leaderboard; the Week 2 final score with the overtime "
        "result; the Week 3 opponent, day and kickoff from the schedule; the title "
        "of the video previewing that game; and the division rank from the standings. "
        "An answer missing any of these, or an empty answer, is a FAIL.",
    ),
    "NFL--18": (
        "sites/nfl/verify/verify_18.py",
        "FACT CHECKPOINTS: The agent must have opened the standings, all five "
        "leaderboards (passing, rushing, receiving, tackles, interceptions), and "
        "both extreme leaders' team pages, schedules and next-game game centers. The "
        "final answer MUST name the division leader with the best point differential "
        "with its division, record, points scored and allowed; the leader with the "
        "worst differential and its record; each of the five leaderboards' leader "
        "and team; which of those leaders play for division leaders; and for both "
        "extreme leaders: head coach, home stadium, and next game with opponent, day, "
        "kickoff and stadium from the game center. An answer missing any of these, or "
        "an empty answer, is a FAIL.",
    ),
    "NFL--19": (
        "sites/nfl/verify/verify_19.py",
        "FACT CHECKPOINTS: The agent must have used the player directory's search "
        "with the team filter, opened the Week 3 injury report, the Cardinals team "
        "page, the Cardinals roster with the quarterback filter applied, the Week 3 "
        "game center, and the standings. The final answer MUST list EVERY Cardinals "
        "player whose last name is Williams with first name, position, roster status, "
        "jersey number and college; state which of them is on the injury report with "
        "his practice status; and report the head coach, home stadium and record, "
        "every active quarterback, the division rank and point differential, and the "
        "Week 3 game's day, kickoff and stadium. An answer missing any of the "
        "Williamses or any of these facts, or an empty answer, is a FAIL.",
    ),
    "NFL--20": (
        "sites/nfl/verify/verify_20.py",
        "FACT CHECKPOINTS: The agent must have submitted the footer newsletter form "
        "with BOTH given emails (each with its chosen team), opened the Chiefs "
        "schedule, both next-game game centers, and both opponents' team pages. The "
        "final answer MUST confirm the site's confirmation message for both signups "
        "and report the combined record of the Chiefs' next two opponents this "
        "season, each opponent's head coach and home stadium, and each of the two "
        "games' day, kickoff and stadium from the game centers. An answer missing "
        "either signup confirmation or any of these facts, or an empty answer, is a "
        "FAIL.",
    ),
}


def main() -> int:
    check_only = "--check" in sys.argv
    lines = TASKS.read_text(encoding="utf-8").splitlines(keepends=True)
    out = []
    problems = []
    for lineno, line in enumerate(lines, 1):
        stripped = line.rstrip("\r\n")
        eol = line[len(stripped):]
        if not stripped.strip():
            out.append(line)
            continue
        row = json.loads(stripped)
        task_id = row.get("id")
        if task_id not in RUBRICS:
            problems.append(f"line {lineno}: no rubric registered for {task_id!r}")
            out.append(line)
            continue
        verifier_path, rubric = RUBRICS[task_id]
        if "verifier_path" in row or "judge_rubric" in row:
            problems.append(f"line {lineno}: {task_id} already carries the contract")
            out.append(line)
            continue
        suffix = (f', "verifier_path": {json.dumps(verifier_path)}, '
                  f'"judge_rubric": {json.dumps(rubric)}}}')
        new_line = stripped[:-1] + suffix + eol
        # byte-preserving prefix: everything before the closing brace is unchanged
        assert new_line.startswith(stripped[:-1]), f"prefix broken at line {lineno}"
        reparsed = json.loads(new_line)
        if list(reparsed.keys())[:5] != ["web_name", "id", "ques", "web", "upstream_url"]:
            problems.append(f"line {lineno}: key order changed for {task_id}")
        if "answer" in reparsed:
            problems.append(f"line {lineno}: answer key leaked for {task_id}")
        out.append(new_line)
    if problems:
        print("\n".join(problems))
        return 1
    if check_only:
        print("all 21 rows would receive verifier_path + judge_rubric; prefix bytes intact")
        return 0
    TASKS.write_text("".join(out), encoding="utf-8")
    print(f"appended verifier_path + judge_rubric to {len(RUBRICS)} task rows "
          f"(original 5-key prefixes byte-identical)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

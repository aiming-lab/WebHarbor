#!/usr/bin/env python3
"""Self-check suite for the Google Flights grading contract (42 verifiers).

Run from the agent_demo project:

    cd agent_demo
    uv run --with pytest python -m pytest ../sites/google_flights/verify/test_verifiers.py

The suite never touches the network, the LLM, or the database. It exercises
every verifier against SYNTHETIC run packages built from the verifier's own
hardcoded ground truth:

  positive       a run that performed the task's natural search navigation and
                  reports on-page facts -> the verifier MUST emit PASS (exit 0)
  no-op          a run that only opened the homepage with an empty answer
                  -> the verifier MUST FAIL (exit 1)
  shortcut       a correct answer but no on-site navigation for it
                  -> the verifier MUST FAIL
  wrong content  the task's navigation performed but the answer commits to
                  wrong flights/fares -> the verifier MUST FAIL
  tampered run   a run package whose trajectory references the search but the
                  screenshots are missing -> the verifier MUST FAIL
  missing traj   a run dir without trajectory.json -> the verifier MUST FAIL

Every case runs the real verifier script as a subprocess (the same entry point
eval_judge.py uses) and asserts on both its JSON verdict and its exit code.
"""
import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

VERIFY_DIR = Path(__file__).resolve().parent
SITE_DIR = VERIFY_DIR.parent
PY = sys.executable

# 1x1 transparent PNG: screenshots are required to EXIST by the run gate; their
# pixels are never graded (these verifiers are deterministic text/URL graders).
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQ"
    "DwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

TASK_IDS = [f"Google Flights--{n}" for n in range(42)]

NYC = "New%20York"
LON = "London"
TYO = "Tokyo"

# The natural navigation for each task, expressed as the /flights (or
# /tools/price-graph, /flight/<id>, /explore) URLs the mirror serves for the
# task's search. Values mirror the audit's real navigation.
NAV = {
    0: [f"/flights?from=Edinburgh&to=Manchester&depart=2024-12-28&return=2024-12-28"],
    1: [f"/flights?from=Chicago&to=Paris&depart=2024-02-17"],
    2: [f"/flights?from=JFK&to=Heathrow&depart=2024-01-22&sort=price"],
    3: [f"/flights?from=Calgary&to={NYC}&depart=2024-01-01&sort=emissions"],
    4: [f"/flights?from={NYC}&to={LON}&depart=2024-12-26&max_stops=0"],
    5: [f"/flights?from=Chicago&to={LON}&depart=2023-12-20&return=2023-12-23"],
    6: [f"/flights?from=Tel%20Aviv&to=Venice&depart=2023-12-19&return=2023-12-26&class=First&passengers=1"],
    7: [f"/flights?from=Phoenix&to=Miami&depart=2023-12-25&return=2023-12-28&class=First&max_price=1320"],
    8: [f"/flights?from=Dublin&to=Athens&depart=2023-12-30",
        f"/tools/price-graph?from=Dublin&to=Athens&depart=2023-12-30&months=2"],
    9: [f"/flights?from=Pune&to={NYC}&depart=2024-01-15",
        f"/flight/125254?dep=2024-01-15"],
    10: [f"/flights?from={NYC}&to={TYO}&depart=2024-01-25&return=2024-02-15&sort=price"],
    11: [f"/flights?from={NYC}&to={TYO}&depart=2024-02-10&return=2024-02-24"],
    12: [f"/flights?from={NYC}&to={LON}&depart=2023-12-25&return=2024-01-05&max_stops=1&sort=price"],
    13: [f"/flights?from={NYC}&to={TYO}&depart=2024-01-10&return=2024-01-24&sort=price"],
    14: [f"/flights?from={NYC}&to={LON}&depart=2024-01-10&return=2024-01-17&sort=price"],
    15: [f"/flights?from={NYC}&to=Tokyo%20Narita&depart=2024-02-12&return=2024-02-26&max_stops=0"],
    16: [f"/flights?from={NYC}&to={TYO}&depart=2024-01-15&sort=price"],
    17: [f"/flights?from={NYC}&to=Paris&depart=2023-12-27&return=2024-01-10&sort=price"],
    18: [f"/flights?from={NYC}&to={TYO}&depart=2024-01-25&return=2024-02-15&sort=duration"],
    19: [f"/flights?from={LON}&to=Paris&depart=2024-01-25&sort=price"],
    20: [f"/flights?from=San%20Francisco&to=Berlin&depart=2024-03-05&return=2024-03-12&sort=duration"],
    21: [f"/flights?from={TYO}&to=Sydney&depart=2024-02-25&sort=price"],
    22: [f"/flights?from=Rio%20de%20Janeiro&to=Los%20Angeles&depart=2024-03-15&return=2024-03-22&sort=emissions"],
    23: [f"/flights?from=Mumbai&to=Vancouver&depart=2024-02-28&max_stops=1"],
    24: [f"/flights?from=Dubai&to=Rome&depart=2024-03-01&return=2024-03-08"],
    25: [f"/flights?from=Buenos%20Aires&to=Amsterdam&depart=2024-03-10&class=Business&sort=duration"],
    26: [f"/flights?from=Bangkok&to=Madrid&depart=2024-02-26&return=2024-02-28&max_price=1000"],
    27: [f"/flights?from=Johannesburg&to=Toronto&depart=2024-03-30",
         f"/tools/price-graph?from=Johannesburg&to=Toronto&depart=2024-03-30&months=1"],
    28: [f"/flights?from=Seattle&to=Paris&depart=2024-02-27&return=2024-03-01&max_stops=1&sort=price"],
    29: [f"/flights?from=Mexico%20City&to=Frankfurt&depart=2024-03-05&return=2024-03-15&max_stops=0"],
    30: [f"/flights?from=Cape%20Town&to=Singapore&depart=2024-03-20&sort=price"],
    31: [f"/flights?from=Auckland&to=Honolulu&depart=2024-03-25"],
    32: [f"/flights?from=Stockholm&to=Toronto&depart=2024-03-03&return=2024-03-10&sort=duration"],
    33: [f"/flights?from=Shanghai&to=Vancouver&depart=2024-02-27&sort=emissions"],
    34: [f"/flights?from=Lisbon&to=Singapore&depart=2024-03-15&class=Business",
         f"/flight/126375?dep=2024-03-15"],
    35: [f"/flights?from=Cairo&to=Montreal&depart=2024-02-21&sort=price"],
    36: [f"/flights?from=Helsinki&to=New%20Delhi&depart=2024-03-28&return=2024-04-04&max_price=1000"],
    37: [f"/flights?from=Buenos%20Aires&to=Beijing&depart=2024-02-28&return=2024-03-03",
         f"/flight/126426?dep=2024-02-28&return=2024-03-03"],
    38: [f"/flights?from=Oslo&to=Dubai&depart=2024-03-08&max_stops=2"],
    39: [f"/flights?from=Prague&to={TYO}&depart=2024-03-20&sort=price",
         f"/flights?from=Prague&to=Sapporo&depart=2024-03-20&sort=price"],
    40: [f"/explore?origin=SEA"],
    41: [f"/flights?from=Hong%20Kong&to=Glacier%20National%20Park&depart=2024-03-08&class=Business"],
}

# A faithful on-page answer per task (values read off the mirror's pages during
# the browser audit; they are the checks' target facts, not the task answers).
POS = {
    0: "The lowest-price option is United UA316 at $56 one-way ($153 round trip with the Emirates return leg).",
    1: "There are 23 flights from Chicago to Paris on Feb 17, including American Airlines $656, ANA $349, British Airways $422, Delta $492 and Emirates $520.",
    2: "The lowest fare from JFK to Heathrow on Jan 22 is $255 on British Airways BA4390.",
    3: "The flight with the lowest CO2 emissions is Iberia IB7027 at 90 kg CO2.",
    4: "Nonstop options include Qatar Airways $486, Emirates $583, ANA $553 and Air Canada $334.",
    5: "Flights include Alaska Airlines $670, Qatar Airways $823, Spirit $518 and ANA $655 on Dec 20, returning Dec 23.",
    6: "I selected Emirates in First Class for $2,620.",
    7: "First Class tickets under $1320: Singapore Airlines $430, Frontier $495, Lufthansa $560 and Cathay Pacific $595.",
    8: "The one-way search shows a lowest fare of $196 (Spirit), and the 2-month price graph's lowest is $196.",
    9: "Frontier offers a 14h total journey nonstop; other options like Japan Airlines take 13h 6m with 1 stop.",
    10: "The cheapest is United at $336 one-way ($1,135 round trip total).",
    11: "Air France AF3759 is nonstop at $469, the least-stops option.",
    12: "The best price with one stop or fewer is $307 on Southwest WN7518.",
    13: "The cheapest round-trip option is $298 on British Airways BA4967.",
    14: "The lowest round-trip fare is $273 on British Airways ($925 round trip total).",
    15: "Nonstop options: Frontier $823 13h 55m, Cathay Pacific $1,020 13h 10m, Qatar Airways $1,208 12h 51m.",
    16: "The cheapest is $360 on Delta with a total flight duration of 16h 4m.",
    17: "The cheapest is $423 on Southwest WN9365.",
    18: "Prioritizing the shortest travel time, United UA9577 is 12h 30m.",
    19: "The cheapest is $56 on Delta, 1h 31m total travel time, nonstop (no layovers).",
    20: "The shortest total travel time is Alaska Airlines at 16h 0m round trip.",
    21: "The lowest-priced is $621 on British Airways, 18h 41m duration, 2 layovers.",
    22: "The least-emissions option is Southwest WN7959 at 210 kg CO2.",
    23: "With the 1-stop filter: Spirit NK4150 $1,376 nonstop, Delta DL4201 $671 nonstop, and Japan Airlines JL1470 $719 with 1 stop.",
    24: "The fewest-stops option: Air France AF873, nonstop, $578.",
    25: "The shortest-duration flight is Spirit at 5h 32m; business fare $763.",
    26: "Options under $1000: Southwest $62, Qantas $68, Alaska Airlines $83 and American Airlines $96.",
    27: "The lowest price is $550; the price graph for the following month starts at $550.",
    28: "The best price with max one stop is $321 on Qantas.",
    29: "Nonstop options: Spirit $486 6h 38m and Lufthansa $721 5h 44m, both nonstop.",
    30: "The most affordable is $265 on Frontier, 11h 20m, with 1 stop.",
    31: "The option with the most stops is Lufthansa LH2130 at $1,238 with 3 stops.",
    32: "Sorted by travel time, the shortest is British Airways at 7h 34m.",
    33: "Air France has the lowest emissions at 471 kg CO2; the highest option emits 924 kg.",
    34: "For the Delta flight, Delta.com is the cheapest booking site at $1,042.",
    35: "The lowest-priced is $321 on Qatar Airways, 11h 2m total travel time, 3 stops.",
    36: "Flights under $1000 include Singapore Airlines $65, Air Canada $80 and JetBlue $110.",
    37: "The return flight is operated by Etihad, which is different from the outbound airline.",
    38: "Options with at most two layovers: British Airways $830 8h 29m and British Airways $489 8h 41m.",
    39: "Tokyo is cheaper: $385 to Tokyo versus $468 to Sapporo.",
    40: "I recommend Miami from $89, Boston from $89 and Toronto from $89.",
    41: "Qatar Airways offers a 1-stop business class ticket for $2,189.",
}

# A plausible-but-wrong answer per task: right navigation, wrong commitments
# (values that contradict the mirror — none of them appears on the task's pages).
WRONG = {
    0: "The lowest-price option is United at $75.",
    1: "There are 23 flights, e.g. American Airlines $999 and ANA $888.",
    2: "The lowest fare is $310 on Virgin Atlantic.",
    3: "The lowest-CO2 flight is Air Canada at 120 kg CO2.",
    4: "Nonstop options include Ryanair $99 and EasyJet $120.",
    5: "Flights include Air India $500 and Vueling $450.",
    6: "I selected El Al in First Class for $1,900.",
    7: "First Class tickets: Singapore Airlines $540, Frontier $600, Lufthansa $680.",
    8: "The lowest fare is $250.",
    9: "Air India takes 20h with 2 stops.",
    10: "The cheapest is ANA at $399.",
    11: "Air France AF3759 is the least-stops option at $500.",
    12: "The best price is $280 on JetBlue.",
    13: "The cheapest option is $350 on ANA.",
    14: "The lowest fare is $310 on Virgin Atlantic.",
    15: "Nonstop options: Ryanair $300 5h, EasyJet $250 4h.",
    16: "The cheapest is $399 on ANA with 14h duration.",
    17: "The cheapest is $500 on Air France.",
    18: "The shortest travel time is Air Canada at 14h 20m.",
    19: "The cheapest is $75 on Air France, 2h, with 1 stop.",
    20: "The shortest total travel time is Lufthansa at 18h 30m.",
    21: "The lowest-priced is $700 on Qantas, 20h, 1 layover.",
    22: "The least-emissions option is Iberia at 250 kg CO2.",
    23: "With the filter: Spirit $1,500, Delta $1,200, KLM $1,900.",
    24: "The fewest-stops option: Emirates, nonstop, $700.",
    25: "The shortest flight is KLM at 6h 40m; business fare $900.",
    26: "Options under $1000: Thai Airways $400, Vietnam Airlines $350.",
    27: "The lowest price is $480.",
    28: "The best price is $400 on Lufthansa.",
    29: "Nonstop options: Aeromexico $300 7h, Iberia $250 8h.",
    30: "The most affordable is $300 on South African Airways, 15h, 2 stops.",
    31: "The option with the most stops is Delta at $900 with 2 stops.",
    32: "The shortest is SAS at 9h 12m.",
    33: "China Eastern has the lowest emissions at 400 kg CO2; the highest is 800 kg.",
    34: "For the Delta flight, Expedia is the cheapest booking site at $1,097.",
    35: "The lowest-priced is $400 on EgyptAir, 12h, 2 stops.",
    36: "Flights under $1000 include Finnair $400 and Aeroflot $350.",
    37: "The return flight is operated by the same airline as the outbound.",
    38: "Options: SAS $900 7h and Norwegian $750 8h.",
    39: "Sapporo is cheaper: $350 versus $500 to Tokyo.",
    40: "I recommend Paris from $50, Rome from $60 and Madrid from $70.",
    41: "Cathay Pacific offers a 1-stop business class ticket for $1,500.",
}

ORIGIN = "http://localhost:41007"


def make_run(root, name, paths, answer, with_screenshots=True, with_trajectory=True):
    d = Path(root) / name
    (d / "screenshots").mkdir(parents=True, exist_ok=True)
    urls = [ORIGIN + p for p in paths] or [ORIGIN + "/"]
    if with_screenshots:
        for i in range(len(urls) + 1):
            (d / "screenshots" / f"step_{i:03d}.png").write_bytes(PNG)
    if with_trajectory:
        steps = []
        for i, u in enumerate(urls):
            steps.append({"step": i, "url": u, "title": "Google Flights",
                          "thought": "",
                          "action": "navigate" if i == 0 else "click",
                          "params": {"url": u} if i == 0 else {},
                          "screenshot_before": f"step_{i:03d}.png",
                          "screenshot_after": f"step_{i + 1:03d}.png"})
        steps.append({"step": len(urls), "url": urls[-1], "title": "Google Flights",
                      "thought": "", "action": "done",
                      "params": {"text": answer, "success": True},
                      "screenshot_before": f"step_{len(urls):03d}.png",
                      "screenshot_after": f"step_{len(urls):03d}.png"})
        traj = {"task": "synthetic", "task_id": "x", "start_url": ORIGIN + "/",
                "steps": steps, "terminated": True,
                "termination_reason": "agent_done", "final_answer": answer,
                "success_self_report": True}
        (d / "trajectory.json").write_text(json.dumps(traj))
    return str(d)


def run_verifier(n, run_dir):
    cmd = [PY, str(VERIFY_DIR / f"verify_{n}.py"), "--run_dir", run_dir,
           "--no_llm", "True"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        verdict = json.loads(proc.stdout)
    except Exception:
        verdict = {"pass": False, "parse_error": proc.stdout[-400:],
                   "stderr": proc.stderr[-400:]}
    return proc.returncode, verdict


@pytest.fixture(scope="module")
def tmp_root(tmp_path_factory):
    return tmp_path_factory.mktemp("gf_runs")


@pytest.mark.parametrize("n", range(42))
def test_verifier_contract(tmp_root, n):
    # 1. positive: task navigation + on-page facts -> PASS
    pos = make_run(tmp_root, f"pos-{n}", NAV[n], POS[n])
    rc, verdict = run_verifier(n, pos)
    assert rc == 0 and verdict.get("pass") is True, \
        f"positive case must PASS: rc={rc} verdict={verdict}"

    # 2. no-op: homepage only, empty answer -> FAIL
    noop = make_run(tmp_root, f"noop-{n}", [], "")
    rc, verdict = run_verifier(n, noop)
    assert rc == 1 and verdict.get("pass") is False, \
        f"no-op case must FAIL: rc={rc} verdict={verdict}"

    # 3. shortcut: correct answer, no on-site navigation -> FAIL
    shortcut = make_run(tmp_root, f"shortcut-{n}", [], POS[n])
    rc, verdict = run_verifier(n, shortcut)
    assert rc == 1 and verdict.get("pass") is False, \
        f"shortcut case must FAIL: rc={rc} verdict={verdict}"

    # 4. wrong content: task navigation, wrong commitments -> FAIL
    wrong = make_run(tmp_root, f"wrong-{n}", NAV[n], WRONG[n])
    rc, verdict = run_verifier(n, wrong)
    assert rc == 1 and verdict.get("pass") is False, \
        f"wrong-content case must FAIL: rc={rc} verdict={verdict}"

    # 5. tampered package: trajectory references the search, screenshots missing
    tampered = make_run(tmp_root, f"tampered-{n}", NAV[n], POS[n],
                        with_screenshots=False)
    rc, verdict = run_verifier(n, tampered)
    assert rc == 1 and verdict.get("pass") is False, \
        f"tampered package must FAIL: rc={rc} verdict={verdict}"

    # 6. missing trajectory -> FAIL
    missing = make_run(tmp_root, f"missing-{n}", NAV[n], POS[n],
                       with_trajectory=False)
    rc, verdict = run_verifier(n, missing)
    assert rc == 1 and verdict.get("pass") is False, \
        f"missing trajectory must FAIL: rc={rc} verdict={verdict}"


def test_tasks_jsonl_contract():
    tasks = SITE_DIR / "tasks.jsonl"
    rows = [json.loads(l) for l in tasks.read_text().splitlines() if l.strip()]
    assert len(rows) == 42
    for row in rows:
        assert list(row.keys()) == ["web_name", "id", "ques", "web",
                                     "upstream_url", "verifier_path",
                                     "judge_rubric"], row["id"]
        assert "answer" not in row, f"answer key leaked in {row['id']}"
        n = int(row["id"].split("--")[1])
        assert row["verifier_path"] == \
            f"sites/google_flights/verify/verify_{n}.py"
        assert (VERIFY_DIR / f"verify_{n}.py").is_file(), row["verifier_path"]
        assert row["judge_rubric"].startswith("FACT CHECKPOINTS."), row["id"]
        assert len(row["judge_rubric"]) > 80, row["id"]


def test_verifiers_do_not_import_cross_site_or_llm():
    """Site isolation + determinism: the graded suite imports only the stdlib,
    verify_lib, and simpleArgParser; no LLM/network/DB anywhere."""
    for p in sorted(VERIFY_DIR.glob("verify_*.py")) + [VERIFY_DIR / "verify_lib.py"]:
        src = p.read_text()
        assert "from sites." not in src, p
        for banned in ("urllib.request", "openai", "sqlite3", "requests"):
            assert banned not in src, f"{banned} in {p}"


def test_clear_cdp_state_fails_closed_without_cdp():
    """Runner tooling pin: with no CDP endpoint reachable, clear_cdp_state
    must exit 2 (fail-closed), never silently pass."""
    proc = subprocess.run(
        [PY, str(VERIFY_DIR / "clear_cdp_state.py"),
         "--cdp_url", "http://127.0.0.1:59999"],
        capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2, proc.stdout + proc.stderr

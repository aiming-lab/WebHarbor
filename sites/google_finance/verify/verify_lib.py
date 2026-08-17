#!/usr/bin/env python3
"""Deterministic grading helpers for the Google Finance benchmark tasks.

Every read-only task requires both the frozen answer and navigation to the
page(s) that expose it.  The portfolio-write task additionally compares the
seed and live SQLite databases, so a plausible self-report cannot pass when
the requested state was not created.
"""
import argparse
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote


SITE = "google_finance"
TASK_COUNT = 20


def _alt(*groups):
    """One valid navigation alternative made from required URL groups."""
    return tuple(tuple(g) if isinstance(g, (list, tuple)) else (g,)
                 for g in groups)


# Each task has one or more acceptable navigation alternatives.  Every group
# in an alternative must match at least one trajectory URL.  A group can hold
# aliases (for example chooser OR password login).
NAV_ALTERNATIVES = {
    0: (_alt("region=latam", "/quote/ibov"),),
    1: (_alt("/quote/ko"),),
    2: (_alt("/quote/nvda", "range=1y"),),
    3: (_alt("/quote/btc-usd"),),
    4: (_alt("/currency-converter", "amount=2500", "from=usd", "to=jpy"),),
    5: (_alt("/quote/ba", "/news/ba-boeing-co-outlines-a-multi-year"),),
    6: (_alt("/quote/intc", "tab=analysis"),),
    7: (_alt("/quote/googl", "tab=financials"),),
    8: (_alt("/quote/wmt", "tab=financials", "statement=balance"),),
    9: (_alt("/quote/cvx", "tab=financials", "statement=income", "period=annual"),),
    10: (_alt("/quote/nvda", "range=1y"),),
    11: (_alt("/quote/xle", "tab=holdings"),),
    12: (_alt("/quote/msft", "tab=earnings"),),
    13: (
        _alt("/compare", "lmt", "rtx", "hon"),
        _alt("/quote/lmt", "/quote/rtx", "/quote/hon"),
    ),
    14: (_alt(
        "/markets/most-active", "/quote/intc", "/quote/nvda",
        "/quote/t:", "/quote/tsla", "/quote/f:",
    ),),
    15: (_alt(
        "/markets/climate-leaders", "/quote/nvda", "/quote/aapl",
        "/quote/msft", "/quote/googl", "/quote/v:", "/quote/ma:",
    ),),
    16: (_alt(
        "/search", "q=utility", "/quote/aep", "/quote/d:",
        "/quote/duk", "/quote/exc", "/quote/nee", "/quote/so:",
    ),),
    17: (_alt(
        ("/accounts/chooser", "/login"), "/lists/2", "/quote/ko",
        "/quote/pg", "/quote/xom", "/quote/duk", "/quote/o:",
        "/quote/vz",
    ),),
    18: (_alt(("/accounts/chooser", "/login"), "/portfolios/2"),),
    19: (_alt(("/accounts/chooser", "/login"), "/portfolios/"),),
}


PASS_ANSWERS = {
    0: "There are 5 indexes. IBOVESPA (IBOV) is highest; day high 187,092.70 and day low 184,438.47.",
    1: "Coca-Cola's ex-dividend date is Oct 4, 2026 and its quarterly dividend is $0.44.",
    2: "There are 9 key moments. The latest says: Biggest one-day drop in months: 3.5%.",
    3: "Bitcoin's 52-week high is $299,489.06 and its 52-week low is $110,249.89.",
    4: "2,500 USD converts to 404,676.0000 JPY at 1 USD = 161.870400 JPY.",
    5: "The publisher is South China Morning Post and the publication date is Jul 24, 2026.",
    6: "Intel's consensus is Hold, based on 14 analyst ratings, with a $104.21 average target.",
    7: "For Jun 2026, Alphabet revenue is 98.36B and net profit margin is 22.77%.",
    8: "For Jun 2026, Walmart total assets are 506.63B and total liabilities are 385.10B.",
    9: "Chevron's 2025 annual revenue is 182.60B.",
    10: "NVIDIA's 1Y change is -18.57%.",
    11: "Marathon Petroleum (MPC) is largest at 12.69%.",
    12: "Jun 2025 has the largest positive EPS surprise at +9.08%.",
    13: "Honeywell (HON) is lowest at 16.47; LMT is 22.45 and RTX is 26.97.",
    14: "Ford Motor (F) is lowest among the top five at a P/E of 32.19.",
    15: "There are 26 companies; Mastercard (MA) has the highest yield among the largest six at 2.03%.",
    16: "Southern Company (SO) has the highest Utilities-stock dividend yield at 3.41%.",
    17: "Realty Income (O) has the highest dividend yield in Dividend income at 4.49%.",
    18: "Growth ideas has a total gain of +33.23%; NVDA is largest at +121.64%.",
    19: "The JPM position market value is $9,203.00 and its gain is +22.71%.",
}


EXPECTED = {
    0: "5 indexes; IBOVESPA/IBOV; high 187,092.70; low 184,438.47",
    1: "Oct 4, 2026; quarterly dividend 0.44",
    2: "9 moments; Biggest one-day drop in months: 3.5%",
    3: "52-week high 299,489.06; low 110,249.89",
    4: "404,676.0000 JPY at 161.870400",
    5: "South China Morning Post; Jul 24, 2026",
    6: "Hold; 14 ratings; average target 104.21",
    7: "Jun 2026; revenue 98.36B; margin 22.77%",
    8: "Jun 2026; assets 506.63B; liabilities 385.10B",
    9: "2025 revenue 182.60B",
    10: "-18.57%",
    11: "Marathon Petroleum/MPC; 12.69%",
    12: "Jun 2025; +9.08%",
    13: "HON lowest 16.47; LMT 22.45; RTX 26.97",
    14: "Ford; 32.19",
    15: "26 companies; Mastercard; 2.03%",
    16: "Southern Company; 3.41%",
    17: "Realty Income; 4.49%",
    18: "total +33.23%; NVDA +121.64%",
    19: "market value 9,203.00; gain +22.71%, plus matching DB state",
}


def load_run(run_dir):
    path = Path(run_dir) / "trajectory.json"
    return json.loads(path.read_text())


def step_urls(traj):
    return [unquote(str(step.get("url", ""))).casefold()
            for step in traj.get("steps", [])]


def final_answer(traj):
    return str(traj.get("final_answer") or "").strip()


def _navigation_ok(task_index, traj):
    urls = step_urls(traj)
    for alternative in NAV_ALTERNATIVES[task_index]:
        if all(any(any(needle.casefold() in url for needle in group)
                   for url in urls) for group in alternative):
            return True, urls
    return False, urls


def _norm(text):
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def _has_all(text, *tokens):
    value = _norm(text)
    return all(_norm(token) in value for token in tokens)


def _has_any(text, *tokens):
    value = _norm(text)
    return any(_norm(token) in value for token in tokens)


def _numbers(text):
    cleaned = (text or "").replace(",", "")
    return [float(value) for value in re.findall(
        r"(?<![\w.])[-+]?\d+(?:\.\d+)?", cleaned
    )]


def _has_number(text, expected, tolerance=0.005):
    return any(math.isclose(value, expected, abs_tol=tolerance, rel_tol=0)
               for value in _numbers(text))


def _has_numbers(text, *expected):
    return all(_has_number(text, value) for value in expected)


def answer_ok(task_index, answer):
    if not answer.strip():
        return False
    if task_index == 0:
        return (_has_any(answer, "ibovespa", "ibov")
                and _has_numbers(answer, 5, 187092.70, 184438.47))
    if task_index == 1:
        return _has_all(answer, "oct", "2026") and _has_numbers(answer, 4, 0.44)
    if task_index == 2:
        return (_has_all(answer, "biggest one-day drop", "3.5")
                and _has_number(answer, 9))
    if task_index == 3:
        return _has_numbers(answer, 299489.06, 110249.89)
    if task_index == 4:
        return (_has_all(answer, "jpy")
                and _has_numbers(answer, 404676.0, 161.8704))
    if task_index == 5:
        return _has_all(answer, "south china morning post", "jul", "24", "2026")
    if task_index == 6:
        return _has_all(answer, "hold") and _has_numbers(answer, 14, 104.21)
    if task_index == 7:
        return _has_all(answer, "jun 2026") and _has_numbers(answer, 98.36, 22.77)
    if task_index == 8:
        return _has_all(answer, "jun 2026") and _has_numbers(answer, 506.63, 385.10)
    if task_index == 9:
        return _has_number(answer, 182.60) and _has_all(answer, "2025")
    if task_index == 10:
        return _has_number(answer, -18.57)
    if task_index == 11:
        return (_has_any(answer, "marathon petroleum", "mpc")
                and _has_number(answer, 12.69))
    if task_index == 12:
        return _has_all(answer, "jun 2025") and _has_number(answer, 9.08)
    if task_index == 13:
        return (_has_any(answer, "honeywell", "hon")
                and _has_numbers(answer, 16.47, 22.45, 26.97))
    if task_index == 14:
        return _has_all(answer, "ford") and _has_number(answer, 32.19)
    if task_index == 15:
        return (_has_all(answer, "mastercard")
                and _has_numbers(answer, 26, 2.03))
    if task_index == 16:
        return (_has_any(answer, "southern company", "southern co")
                and _has_number(answer, 3.41))
    if task_index == 17:
        return _has_all(answer, "realty income") and _has_number(answer, 4.49)
    if task_index == 18:
        return _has_all(answer, "nvda") and _has_numbers(answer, 33.23, 121.64)
    if task_index == 19:
        return _has_numbers(answer, 9203.00, 22.71)
    raise ValueError(f"unknown task index: {task_index}")


def _fetch_db(container, kind):
    source = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    result = subprocess.run(
        ["docker", "cp", source, path], capture_output=True, text=True
    )
    if result.returncode:
        try:
            os.unlink(path)
        except OSError:
            pass
        return None
    return path


def _resolve_db(path, container, kind):
    return path or _fetch_db(container, kind)


def _bank_basket_rows(db_path):
    if not db_path or not Path(db_path).exists():
        return None
    connection = sqlite3.connect(db_path)
    try:
        return connection.execute(
            "SELECT p.cash, i.ticker, l.shares, l.cost_basis "
            "FROM portfolios p JOIN users u ON u.id=p.user_id "
            "LEFT JOIN portfolio_lots l ON l.portfolio_id=p.id "
            "LEFT JOIN instruments i ON i.id=l.instrument_id "
            "WHERE u.email=? AND p.name=? ORDER BY l.id",
            ("alice.j@test.com", "Bank basket"),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def _state_ok(initial_db, after_db):
    before = _bank_basket_rows(initial_db)
    after = _bank_basket_rows(after_db)
    if before is None or after is None:
        return False, f"initial={before!r}; after={after!r}"
    created = before == [] and len(after) == 1
    if not created:
        return False, f"initial={before!r}; after={after!r}"
    cash, ticker, shares, cost = after[0]
    exact = (
        math.isclose(cash, 5000.0, abs_tol=0.005)
        and ticker == "JPM"
        and math.isclose(shares, 25.0, abs_tol=0.0001)
        and math.isclose(cost, 300.0, abs_tol=0.005)
    )
    return exact, f"initial={before!r}; after={after!r}"


def evaluate(task_index, traj, initial_db="", after_db="", container="wh-review"):
    if task_index not in NAV_ALTERNATIVES:
        raise ValueError(f"unknown task index: {task_index}")
    answer = final_answer(traj)
    nav_ok, urls = _navigation_ok(task_index, traj)
    checks = [
        ("final_answer_nonempty", bool(answer), f"final={answer!r}"),
        ("required_navigation", nav_ok, f"urls={urls!r}"),
        ("frozen_answer", answer_ok(task_index, answer),
         f"expected={EXPECTED[task_index]}; final={answer!r}"),
    ]
    if task_index == 19:
        initial_db = _resolve_db(initial_db, container, "instance_seed")
        after_db = _resolve_db(after_db, container, "instance")
        ok, detail = _state_ok(initial_db, after_db)
        checks.append(("portfolio_after_state", ok, detail))

    passed = all(ok for _, ok, _ in checks)
    reason = next((name for name, ok, _ in checks if not ok), "")
    evidence = [f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}"
                for name, ok, detail in checks]
    return {
        "task_id": f"Google Finance--{task_index}",
        "pass": passed,
        "reason": reason,
        "evidence": evidence,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--initial_db", default="")
    parser.add_argument("--after_db", default="")
    parser.add_argument(
        "--container", default=os.environ.get("WH_CONTAINER", "wh-review")
    )
    parser.add_argument("--no_llm", nargs="?", const="True", default="False")
    return parser.parse_args()


def main(task_index):
    args = parse_args()
    verdict = evaluate(
        task_index,
        load_run(args.run_dir),
        initial_db=args.initial_db,
        after_db=args.after_db,
        container=args.container,
    )
    print(json.dumps(verdict, indent=2))
    sys.exit(0 if verdict["pass"] else 1)

"""Fail-closed, offline snapshot grader; no Docker/live DB or LLM fallback."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import urlsplit, parse_qs

from contract import OPEN, SAVE, MESSAGE, FACTS, BODY, CURRENCY

TABLES = (
    "users",
    "categories",
    "listings",
    "saved_listings",
    "saved_searches",
    "hidden_listings",
    "messages",
)


def database(path):
    if not path.is_file():
        raise ValueError(f"Missing snapshot: {path.name}")
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return {
            t: [dict(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY id")]
            for t in TABLES
        }


def matches(text, pattern):
    return re.search(pattern, text, re.I) is not None


def paragraphs(text):
    # Tables/bullets and multi-sentence paragraphs are all supported.
    return [x.strip().lower() for x in re.split(r"\n+", text) if x.strip()]


def facts_ok(task, answer):
    answer = re.sub(
        r"(\d[\d,]*(?:\.\d+)?)\s+(?:US )?dollars\b", r"$\1", answer, flags=re.I
    )
    answer = re.sub(r"(\d),(?=\d{3}\b)", r"\1", answer)
    facts = FACTS.get(task, [])
    for fact_index, fact in enumerate(facts):
        spans = []
        for row in paragraphs(answer):
            # Never let one property's numbers satisfy another property's fact.
            for anchor in re.finditer(fact[0], row, re.I):
                tail = row[anchor.start() :]
                boundaries = [
                    m.start()
                    for other in facts
                    if other[0] != fact[0]
                    if (
                        m := re.search(
                            other[0], tail[anchor.end() - anchor.start() :], re.I
                        )
                    )
                ]
                if boundaries:
                    tail = tail[: anchor.end() - anchor.start() + min(boundaries)]
                spans.append(tail)
        amounts = CURRENCY.get(task, [None] * len(facts))[fact_index]

        def valid_span(row):
            currencies = {float(n) for n in re.findall(r"\$\s*(\d+(?:\.\d+)?)", row)}
            return all(matches(row, p) for p in fact) and (
                amounts is None or currencies <= amounts
            )

        if not any(valid_span(row) for row in spans):
            return False
    # Reject explicit denial of reported numbers/selection and obvious
    # contradictory claims. Not a general semantic parser (see README).
    if matches(
        answer,
        r"\b(?:not|isn't|is not|wasn't)\s+\$?\d|\b(?:ignore|disregard)\s+(?:the|these)\s+(?:figures|numbers|facts)",
    ):
        return False
    contradictions = {
        1: r"laundry.{0,25}(?<!not )(?:guaranteed in every|available in every)",
        4: r"(?:snell|san jose).{0,35}(?:is cheaper|is lower)",
        8: r"children.{0,8}(?:not welcome|prohibited)|woodhams.{0,30}(?:all ages|child.friendly)",
        14: r"(?:u2414h|24.inch).{0,80}(?:has|includes|with) built.in speakers",
        17: r"downtown.{0,30}(?:three|3) hours|stevenson.{0,30}(?:two|2) hours",
    }
    return not matches(answer, contradictions.get(task, r"(?!)"))


def main(task):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", type=Path, required=True)
    parser.add_argument("--initial_db", type=Path)
    parser.add_argument("--after_db", type=Path)
    parser.add_argument(
        "--no_llm", nargs="?", default="True"
    )  # compatibility; always offline
    args = parser.parse_args()
    checks = []

    def check(label, ok):
        checks.append({"check": label, "pass": bool(ok)})

    try:
        run = args.run_dir
        traj = json.loads((run / "trajectory.json").read_text())
        initial = database(args.initial_db or run / "initial.db")
        final = database(args.after_db or run / "after.db")
        check(
            "initial fixture fingerprint",
            hashlib.sha256(
                json.dumps(initial, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            == "4dc9ed812c3057d2bdaa8ad433082021c12ce0020df79f7519169e2c6ed43506",
        )
        check("task identity", traj.get("task_id") == f"Craigslist--{task}")
        steps = traj.get("steps", [])
        urls = [urlsplit(s.get("url", "")) for s in steps]
        paths = [u.path for u in urls]
        host = urlsplit(traj.get("start_url", "")).netloc
        check(
            "browser evidence on task host",
            bool(host) and bool(steps) and all(u.netloc == host for u in urls),
        )
        check(
            "screenshots exist",
            bool(steps)
            and all(
                (
                    run / s.get("screenshot_after", s.get("screenshot", "__missing__"))
                ).is_file()
                for s in steps
            ),
        )
        opened = {
            int(m.group(1))
            for p in paths
            if (m := re.fullmatch(r"/d/[^/]+/(\d+)\.html", p))
        }
        check("required listings opened", set(OPEN[task]) <= opened)
        alice = next(r for r in initial["users"] if r["email"] == "alice.j@test.com")
        uid = alice["id"]
        check(
            "reviewed source fixture",
            len(initial["listings"]) == 78
            and {
                r["listing_id"]
                for r in initial["saved_listings"]
                if r["user_id"] == uid
            }
            == {1, 34, 35},
        )
        allowed = set()
        if task in SAVE or task == 13:
            allowed = {"saved_listings"}
        elif task in MESSAGE:
            allowed = {"messages"}
        elif task == 5:
            allowed = {"saved_searches"}
        elif task == 6:
            allowed = {"listings"}
        elif task == 12:
            allowed = {"users"}
        elif task == 16:
            allowed = {"hidden_listings"}
        for table in TABLES:
            if table not in allowed:
                check(f"unchanged {table}", initial[table] == final[table])

        def delta(table):
            before = {r["id"]: r for r in initial[table]}
            after = {r["id"]: r for r in final[table]}
            check(
                f"existing {table} rows preserved",
                all(after[k] == v for k, v in before.items() if k in after),
            )
            return [v for k, v in after.items() if k not in before], [
                v for k, v in before.items() if k not in after
            ]

        if task in SAVE:
            added, removed = delta("saved_listings")
            check(
                "exact requested save",
                not removed
                and len(added) == 1
                and added[0]["user_id"] == uid
                and added[0]["listing_id"] == SAVE[task]
                and added[0]["note"] == "",
            )
        if task == 13:
            added, removed = delta("saved_listings")
            check(
                "exact requested removal",
                not added
                and len(removed) == 1
                and removed[0]["user_id"] == uid
                and removed[0]["listing_id"] == 34,
            )
        if task in MESSAGE:
            added, removed = delta("messages")
            check(
                "exact outbound reply",
                not removed
                and len(added) == 1
                and added[0]["listing_id"] == MESSAGE[task]
                and added[0]["direction"] == "outbound"
                and added[0]["is_read"] == 1
                and (
                    added[0]["user_id"] == uid
                    if task == 7
                    else added[0]["user_id"] in (None, uid)
                ),
            )
            if len(added) == 1:
                msg = added[0]
                check(
                    "message content",
                    all(matches(msg["body"], p) for p in BODY[task])
                    and not matches(
                        msg["body"],
                        r"\b(?:do not|don't|cannot|can't|won't|not interested|never mind|cancel)\b",
                    ),
                )
                if msg["user_id"] == uid:
                    check(
                        "sender identity",
                        msg["sender_email"] == alice["email"]
                        and msg["sender_name"] == alice["name"],
                    )
        if task == 5:
            added, removed = delta("saved_searches")
            expected = dict(
                user_id=uid,
                name="Office chair watch",
                query_text="office chair",
                category_slug="furniture",
                area="east bay",
                min_price=None,
                max_price=100,
            )
            check(
                "exact saved search",
                not removed
                and len(added) == 1
                and all(added[0].get(k) == v for k, v in expected.items()),
            )
            check(
                "reopened saved search",
                any(
                    u.path == "/search/furniture"
                    and all(
                        parse_qs(u.query).get(k) == [v]
                        for k, v in {
                            "q": "office chair",
                            "area": "east bay",
                            "max_price": "100",
                        }.items()
                    )
                    for u in urls[paths.index("/account") + 1 :]
                )
                if "/account" in paths
                else False,
            )
        if task == 6:
            added, removed = delta("listings")
            expected = dict(
                owner_id=uid,
                category_slug="bikes",
                category_group="for_sale",
                area="east bay",
                price=325,
                title="Blue commuter bike",
                status="active",
                seller_email=alice["email"],
                seller_name=alice["name"],
                reply_phone=alice["phone"],
                bedrooms=None,
                sqft=None,
                compensation="",
                company="",
                employment_type="",
                image="",
                details_json="{}",
            )
            check(
                "exact new posting",
                not removed
                and len(added) == 1
                and all(added[0].get(k) == v for k, v in expected.items()),
            )
            if len(added) == 1:
                row = added[0]
                check(
                    "posting details and navigation",
                    row["neighborhood"].lower() == "oakland"
                    and row["id"] in opened
                    and matches(row["description"], r"rear rack")
                    and matches(
                        row["description"],
                        r"(?:recently|just|newly).{0,20}(?:replaced|changed).{0,15}brake pads|brake pads.{0,15}(?:recently|just).{0,15}(?:replaced|changed)",
                    )
                    and not matches(row["description"], r"\b(?:not|no|without)\b"),
                )
        if task == 7:
            check("messages viewed", "/messages" in paths)
        if task == 12:
            expected = [
                dict(r, area="peninsula", phone="(650) 555-0144")
                if r["id"] == uid
                else r
                for r in initial["users"]
            ]
            check("only requested account fields", final["users"] == expected)
            check("settings revisited", paths.count("/account/edit") >= 2)
        if task == 16:
            added, removed = delta("hidden_listings")
            check(
                "exact hide",
                not removed
                and len(added) == 1
                and added[0]["user_id"] == uid
                and added[0]["listing_id"] == 25,
            )
            searches = [
                s
                for s, u in zip(steps, urls)
                if u.path.startswith("/search")
                and parse_qs(u.query).get("q", [""])[0].lower() == "honda"
            ]
            text = (
                (searches[-1].get("action_result") or {}).get("extracted_content", "")
                if searches
                else ""
            )
            check(
                "repeat search retains other Hondas",
                len(searches) >= 2
                and "2007 Honda Pilot" not in text
                and all(
                    x in text
                    for x in [
                        "2012 Honda Accord",
                        "2008 HONDA ACCORD",
                        "2013 Honda Odyssey",
                    ]
                ),
            )
        check("natural answer facts", facts_ok(task, traj.get("final_answer", "")))
    except Exception as exc:
        check(f"invalid evidence: {type(exc).__name__}: {exc}", False)
    failed = [r["check"] for r in checks if not r["pass"]]
    result = {
        "task_id": f"Craigslist--{task}",
        "pass": not failed,
        "reason": "All snapshot and evidence checks passed"
        if not failed
        else "; ".join(failed),
        "evidence": checks,
    }
    print(json.dumps(result, indent=2))
    sys.exit(1 if failed else 0)

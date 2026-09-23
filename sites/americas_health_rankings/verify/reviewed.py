"""Review-time fixture, exact state-delta and contextual comparison checks."""

from pathlib import Path
from decimal import Decimal
from urllib.parse import urlsplit, parse_qs
import hashlib, json, re, copy
from verify_lib import navigated_path, shot_at

HERE = Path(__file__).parent
SEED = json.loads((HERE / "reviewed_seed.json").read_text())
CONFIG = json.loads((HERE / "revisions.json").read_text())
NAMES = {
    "CA": "California",
    "MT": "Montana",
    "ME": "Maine",
    "TX": "Texas",
    "MA": "Massachusetts",
    "NH": "New Hampshire",
}


def norm(s):
    return re.sub(r"\s+", " ", s.casefold()).replace("–", "-").replace("—", "-")


def digest(x):
    return hashlib.sha256(
        json.dumps(x, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def labelled(text, label, value):
    values = []
    for m in re.finditer(label, norm(text)):
        tail = norm(text)[m.end() : m.end() + 60]
        v = re.search(r"(?<![\w.])(-?\d+(?:\.\d+)?)", tail)
        if v:
            values.append(Decimal(v[1]))
    return bool(values) and all(v == Decimal(str(value)) for v in values)


def page(j, t, path):
    j.check("page_" + path, navigated_path(t, path) and shot_at(t, path)[0], path)


def scoped(text, name, names):
    """Return an entity's prose spans, independent of line/table layout."""
    text = norm(text)
    hits = []
    for entity in names:
        for match in re.finditer(re.escape(norm(entity)), text):
            hits.append((match.start(), match.end(), entity))
    hits.sort()
    result = []
    for index, (start, end, entity) in enumerate(hits):
        if entity == name:
            result.append(
                text[end : hits[index + 1][0] if index + 1 < len(hits) else len(text)]
            )
    return result


def state_fact(text, value, rank):
    explicit = labelled(text, r"\b(?:value|rate)\b", value)
    if not re.search(r"\b(?:value|rate)\b", text):
        first = re.search(r"(?<![\w.])(\d+(?:\.\d+)?)", text)
        explicit = bool(first and Decimal(first[1]) == Decimal(str(value)))
    return explicit and labelled(text, r"\brank(?:ed)?\b", rank)


def check(j, n, t, b, a):
    j.check(
        "reviewed_initial_fixture",
        b is not None and {k: digest(v) for k, v in b.items()} == SEED,
        "Initial tables match the reviewed seed",
    )
    if b is None or a is None:
        return
    expected = copy.deepcopy(b)
    f = t.get("final_answer", "")
    low = norm(f)
    cfg = CONFIG.get(str(n), {})
    # Whitelist exact row changes, never whole mutable tables.
    if n == 28:
        expected["bookmarks"] = [
            r
            for r in b["bookmarks"]
            if not (
                r["user_id"] == 2
                and r["kind"] == "measure"
                and r["item_slug"] == "mental_distress"
            )
        ]
    table = {29: "newsletter_signups", 30: "inquiries", 34: "bookmarks"}.get(n)
    if table:
        old = {r["id"] for r in b[table]}
        new = [r for r in a[table] if r["id"] not in old]
        required = {
            29: {"name": "Jordan Lee", "email": "jordan.lee@example.com"},
            30: {
                "name": "Dana Torres",
                "email": "dana.torres@example.com",
                "organization": "State Health Institute",
            },
            34: {"user_id": 3, "kind": "state", "item_slug": "MT", "title": "Montana"},
        }[n]
        valid = len(new) == 1 and all(new[0].get(k) == v for k, v in required.items())
        if n == 30 and valid:
            valid = bool(
                re.search(r"(?:reus|us).*?(?:research|paper)", norm(new[0]["comment"]))
            ) and "state" in norm(new[0]["comment"])
        j.check(
            "requested_insert", valid, "Exactly one correctly owned requested record"
        )
        if valid:
            expected[table] += new
    old_history = {r["id"] for r in b["reading_history"]}
    new_history = [r for r in a["reading_history"] if r["id"] not in old_history]
    user = {27: 1, 28: 2, 34: 3}.get(n)
    paths = {urlsplit(s.get("url", "")).path for s in t.get("steps", [])}
    history_valid = all(r["user_id"] == user and r["url"] in paths for r in new_history)
    j.check(
        "history_is_observed",
        history_valid,
        "History can only add pages visited by this task account",
    )
    if history_valid:
        expected["reading_history"] += new_history
    j.check(
        "exact_state_delta", expected == a, "Preserve every unrelated record and field"
    )
    j.check(
        "answer_not_disclaimed",
        not re.search(
            r"(?:this|following|answer|values?)\s+(?:is|are)\s+(?:incorrect|wrong|false)|incorrect\s*:",
            low,
        ),
        "Facts must be asserted",
    )
    for m in cfg.get("measures", []):
        path = "/explore/measures/" + m["slug"]
        page(j, t, path)
        for value in m["values"]:
            state = NAMES[value["state_code"]]
            measure_spans = scoped(f, m["name"], [x["name"] for x in cfg["measures"]])
            blocks = [
                part
                for span in measure_spans
                for part in scoped(
                    span, state, [NAMES[v["state_code"]] for v in m["values"]]
                )
            ]
            valid = any(state_fact(x, value["value"], value["rank"]) for x in blocks)
            j.check(
                m["slug"] + "_" + state,
                valid,
                "Latest value and rank bound to the correct measure/state",
            )
        gap = round(abs(m["values"][0]["value"] - m["values"][1]["value"]), 3)
        winner = NAMES[min(m["values"], key=lambda v: v["rank"])["state_code"]]
        blocks = [
            x
            for x in scoped(f, m["name"], [v["name"] for v in cfg["measures"]])
            if "gap" in x
        ]
        valid = any(
            labelled(x, r"gap", gap)
            and norm(winner) in norm(x)
            and "better" in norm(x)
            and (
                "percentage points" in norm(x)
                if "percentage" in m["unit"].casefold()
                else norm(m["unit"]) in norm(x)
            )
            for x in blocks
        )
        j.check(
            "measure_gap_" + m["slug"],
            valid,
            "Rank direction and numeric gap with the correct unit",
        )
    if cfg.get("states"):
        ranks = {}
        for code in cfg["states"]:
            path = "/explore/states/" + code
            page(j, t, path)
            for edition, eid in [("annual", 284), ("senior", 286)]:
                rank = next(
                    r["rank"]
                    for r in b["edition_measure_states"]
                    if r["state_code"] == code
                    and r["edition_id"] == eid
                    and r["measure_slug"]
                    == ("Overall" if edition == "annual" else "overall_sr_2")
                )
                ranks[(code, edition)] = rank
                visited = any(
                    urlsplit(s.get("url", "")).path == path
                    and parse_qs(urlsplit(s["url"]).query).get("rank", ["annual"])[0]
                    == edition
                    for s in t.get("steps", [])
                )
                blocks = [
                    x
                    for x in scoped(f, NAMES[code], [NAMES[c] for c in cfg["states"]])
                    if edition in x
                ]
                j.check(
                    code + "_" + edition,
                    visited
                    and any(
                        labelled(x, edition + r"(?: overall)? rank(?! gap)", rank)
                        for x in blocks
                    ),
                    "Overall rank bound to state and report edition",
                )
        for edition in ["annual", "senior"]:
            gap = abs(
                ranks[(cfg["states"][0], edition)] - ranks[(cfg["states"][1], edition)]
            )
            j.check(
                edition + "_rank_gap",
                labelled(f, edition + r" rank gap", gap),
                "Gap within the same report edition",
            )
    if cfg.get("reports"):
        for slug, title, measures, sources, first in [
            ("2025-annual-report", "2025 Annual Report", 99, 31, "New Hampshire"),
            ("2026-senior-report", "2026 Senior Report", 56, 25, "Vermont"),
        ]:
            for tail in ["", "/state-rankings"]:
                page(j, t, "/publications/reports/" + slug + tail)
            blocks = scoped(f, title, ["2025 Annual Report", "2026 Senior Report"])
            scope = any(
                re.search(r"\b" + str(measures) + r"\s*measures", norm(x))
                and re.search(r"\b" + str(sources) + r"\s*data sources", norm(x))
                for x in blocks
            )
            ranking = any(
                re.search(norm(first) + r".*?(?:first|#?1\b)", norm(x))
                and re.search(r"louisiana.*?(?:last|50\b)", norm(x))
                for x in blocks
            )
            j.check(
                "report_" + slug,
                scope and ranking,
                "Report scope and first/last states",
            )

"""Reviewed fixture, comparisons and entity-bound answer checks."""

import hashlib, json, re
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from verify_lib import navigated_path, shot_at

HERE = Path(__file__).parent
CONFIG = json.loads((HERE / "revisions.json").read_text())
SEED = json.loads((HERE / "reviewed_seed.json").read_text())


def norm(text):
    return re.sub(
        r"\s+",
        " ",
        re.sub(r"(?<=\d),(?=\d)", "", text.casefold())
        .replace("®", "")
        .replace("™", ""),
    ).strip()


def digest(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def money(text, value):
    from decimal import Decimal

    return any(
        Decimal(m) == Decimal(str(value))
        for m in re.findall(r"\$\s*(\d+(?:\.\d+)?)", norm(text))
    )


def number(text, value):
    return bool(
        re.search(
            r"(?<![\d.])" + re.escape(str(value)) + r"(?:\.0+)?(?!\d|\.\d)", norm(text)
        )
    )


def clauses(text):
    return [
        s.strip()
        for s in re.split(
            r"\n|;|(?<!\d)\.(?!\d)|\bwhereas\b|\bwhile\b",
            norm(text).replace(" u.s.", " US"),
        )
        if s.strip()
    ]


def entity_blocks(text, entities):
    """Keep named cards together with their own claims, never pool numbers."""
    text = norm(text)
    names = [norm(x) for x in entities]
    hits = []
    for idx, name in enumerate(names):
        for m in re.finditer(re.escape(name), text):
            hits.append((m.start(), m.end(), idx))
    hits.sort()
    out = [[] for _ in names]
    for pos, (_, end, idx) in enumerate(hits):
        out[idx].append(
            text[end : hits[pos + 1][0] if pos + 1 < len(hits) else len(text)]
        )
    return out


def labelled(text, label, value, unit="money"):
    """A nearby explicit label and value, accepting prose or table punctuation."""
    from decimal import Decimal

    values = []
    text = norm(text)
    for match in re.finditer(label, text):
        tail = text[match.end() : match.end() + 90]
        candidate = re.search(
            (
                r"\$\s*(\d+(?:\.\d+)?)"
                if unit == "money"
                else r"(?<![\d.])(\d+(?:\.\d+)?)"
            ),
            tail,
        )
        if candidate and not re.search(
            r"\b(?:not|incorrect|wrong|never)\b", tail[: candidate.end()]
        ):
            values.append(Decimal(candidate[1]))
    return bool(values) and all(v == Decimal(str(value)) for v in values)


def check(j, n, t, initial, after):
    j.check(
        "reviewed_initial_fixture",
        initial is not None and {k: digest(v) for k, v in initial.items()} == SEED,
        "Initial tables match the reviewed seed",
    )
    f = t.get("final_answer", "")
    low = norm(f)
    j.check(
        "answer_not_disclaimed",
        not re.search(
            r"(?:this|following|answer|values?|figures?)\s+(?:is|are)\s+(?:incorrect|wrong|false)|incorrect\s*:",
            low,
        ),
        "Reported facts are asserted, not disclaimed",
    )
    cfg = CONFIG.get(str(n), {})
    if cfg.get("pair"):
        found = any(
            urlsplit(s.get("url", "")).path.rstrip("/") == "/credit-cards/compare"
            and set(cfg["pair"]).issubset(
                set(parse_qs(urlsplit(s["url"]).query).get("cards", [""])[0].split(","))
            )
            for s in t.get("steps", [])
        )
        j.check(
            "nav_requested_compare",
            found and shot_at(t, "/credit-cards/compare")[0],
            "Compare feature contains both requested cards",
        )
        blocks = entity_blocks(f, [c["name"] for c in cfg["cards"]])
        for c, parts in zip(cfg["cards"], blocks):
            fee = c["annual_fee_value"]
            headline = norm(c["welcome_headline"])
            numbers = re.findall(r"\d+", headline)
            valid = any(
                (
                    "annual fee" in b
                    and (money(b, fee) if fee else "no annual fee" in b or money(b, 0))
                )
                and "welcome" in b
                and all(number(b, num) for num in numbers)
                for b in parts
            )
            if "first year" in c["annual_fee_text"]:
                valid = valid and any("first year" in b and money(b, 0) for b in parts)
            j.check(
                "ans_comparison_" + c["name"],
                valid,
                "Annual fee and complete welcome headline attached to this card",
            )
        gap = abs(
            cfg["cards"][0]["annual_fee_value"] - cfg["cards"][1]["annual_fee_value"]
        )
        j.check(
            "ans_fee_difference",
            labelled(f, r"(?:difference|gap)", gap),
            "Ongoing annual fee difference",
        )
    if cfg.get("banking"):
        for path in [
            "/banking/high-yield-savings/",
            "/banking/cd/",
            "/banking/checking/",
        ]:
            j.check(
                "nav_page_" + path,
                navigated_path(t, path) and shot_at(t, path)[0],
                path,
            )
        j.check(
            "ans_savings_apy",
            labelled(f, r"(?:savings|hysa)", 3, "number")
            or labelled(f, r"(?:savings|hysa)", "3.00", "number"),
            "Savings APY 3.00%",
        )
        j.check(
            "ans_cd_best",
            bool(re.search(r"10[- ]month.*?4\.25\s*%", low)),
            "10-month CD at 4.25%",
        )
        j.check(
            "ans_apy_gap",
            bool(re.search(r"1\.25\s*percentage points", low)),
            "1.25 percentage points, not percent",
        )
        j.check(
            "ans_checking_bonus",
            labelled(f, r"checking", 300) and money(f, 7500) and number(f, 90),
            "Checking bonus and direct deposits",
        )
    if cfg.get("loan"):
        j.check(
            "ans_platinum_rates",
            navigated_path(t, "/credit-cards/card/platinum/")
            and bool(re.search(r"platinum.*?19\.74%.*?28\.74%", low)),
            "Platinum purchase APR range",
        )
        j.check(
            "ans_minimum_apr_gap",
            "12.75 percentage points" in low,
            "Difference of minimum APRs",
        )
        j.check(
            "ans_amex_debt_restriction",
            bool(
                re.search(
                    r"(?:cannot|can.t|not allowed to).*?(?:consolidat|pay).*?american express",
                    low,
                )
            ),
            "Loan cannot consolidate Amex-issued card balances",
        )
    if cfg.get("statements") and initial:
        total = 0
        cardfacts = []
        for uid in cfg["statements"]:
            uc = next(r for r in initial["user_cards"] if r["id"] == uid)
            card = next(r for r in initial["cards"] if r["id"] == uc["card_id"])
            stmt = max(
                (s for s in initial["statements"] if s["user_card_id"] == uid),
                key=lambda s: s["period_end"],
            )
            total += stmt["min_payment"]
            cardfacts.append((card, stmt))
            path = f"/account/statements/{stmt['id']}/"
            j.check(
                "nav_latest_statement_" + str(uid),
                navigated_path(t, path) and shot_at(t, path)[0],
                path,
            )
        blocks = entity_blocks(f, [c["name"] for c, s in cardfacts])
        for (c, s), parts in zip(cardfacts, blocks):
            j.check(
                "ans_statement_" + c["name"],
                any(
                    labelled(b, "closing balance", s["closing_balance"])
                    and labelled(b, r"(?<!combined )minimum payment", s["min_payment"])
                    for b in parts
                ),
                "Closing balance and minimum payment tied to card",
            )
        j.check(
            "ans_combined_minimum",
            labelled(f, "combined minimum", round(total, 2)),
            "Combined minimum payment",
        )
    if cfg.get("hotel_activity") and initial:
        for uid in cfg["hotel_activity"]:
            tx = max(
                (
                    x
                    for x in initial["transactions"]
                    if x["user_card_id"] == uid and "hotel" in x["category"].lower()
                ),
                key=lambda x: x["date"],
            )
            path = f"/account/cards/{uid}/"
            date = tx["date"][:10].split("-")
            display = "/".join([date[1], date[2], date[0]])
            j.check(
                "ans_hotel_transaction_" + str(uid),
                navigated_path(t, path)
                and norm(tx["merchant"]) in low
                and display in f
                and money(f, tx["amount"]),
                "Most recent hotel merchant, date and amount for each card",
            )
    if n == 0:
        j.check(
            "ans_charge_polarity",
            not re.search(r"(?:not|never|isn.t)\s+(?:a\s+)?charge\s*card", low),
            "Affirmative charge card classification",
        )
    if n in [4, 5]:
        names = (
            ["Delta SkyMiles Gold", "Delta SkyMiles Platinum"]
            if n == 4
            else ["Blue Cash Preferred", "Blue Cash Everyday"]
        )
        blocks = entity_blocks(f, names)
        for parts, value in zip(blocks, [80000, 90000] if n == 4 else [6, 3]):
            j.check(
                "ans_bound_comparison_" + str(value),
                any(
                    number(b, value)
                    and (
                        "miles" in b
                        if n == 4
                        else bool(re.search(r"\b" + str(value) + r"\s*%", b))
                        and "supermarket" in b
                    )
                    for b in parts
                ),
                "Reward attached to correct card",
            )

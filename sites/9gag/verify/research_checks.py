"""Frozen multi-source research contracts; ground truth stays out of tasks.jsonl.

Answers are segmented by named entities, with sentence-to-sentence context for
pronouns. This is a bounded deterministic language checker, not an LLM judge.
It permits prose, headings and tables without requiring a prescribed template.
"""

from __future__ import annotations

import re
from answer_checks import check, clean, phrase, quantity
from verify_lib import (
    check_trajectory_identity,
    check_detail_visited,
    check_read_only,
    check_visited_path,
    check_search_visited,
    final_answer,
    post_by_slug,
    check_signed_in_as,
    check_only_tables_changed,
    saved_post_ids,
    table_delta,
    user_id_for_email,
)

# Entity aliases identify answer subjects, not arbitrary matching fact words.
ENTITIES = {
    12: (
        "tiny-lighthouse-office-with-the-best-ocean-view",
        r"ocean.view|circular room|lighthouse office|office room",
    ),
    32: (
        "miniature-lighthouse-built-for-a-seaside-bookshop",
        r"bookshop|miniature lighthouse|model lighthouse",
    ),
    33: ("remote-lighthouse-receives-a-compact-radio-desk", r"radio|remote lighthouse"),
    13: (
        "rescue-cat-learns-the-sound-of-the-treat-drawer",
        r"miso|rescue.cat|treat.drawer",
    ),
    37: (
        "rescue-dog-recognizes-the-volunteer-who-found-him",
        r"basil|rescue.dog|reunited dog",
    ),
    39: (
        "foster-kitten-discovers-the-automatic-treat-puzzle",
        r"juniper|foster.kitten|treat.puzzle",
    ),
    11: (
        "solar-powered-camping-setup-survives-a-rainy-weekend",
        r"rainy.weekend|solar.setup|solar.camping|folding panel|controller",
    ),
    34: ("solar-lantern-comparison-for-a-week-of-camping", r"lantern"),
    35: (
        "rainy-campsite-kitchen-stays-dry-under-one-clever-tarp",
        r"kitchen|tarp|ridgeline",
    ),
    19: (
        "an-engineer-explains-why-this-bridge-hums-in-the-wind",
        r"humming|hums|resonat",
    ),
    40: ("suspension-bridge-whistles-only-during-winter-gusts", r"suspension|whistl"),
    41: (
        "footbridge-becomes-a-percussion-instrument-in-heavy-rain",
        r"footbridge|percussion",
    ),
    18: (
        "neighborhood-builds-a-miniature-library-for-night-shift-workers",
        r"night.shift|cabinet",
    ),
    43: (
        "community-library-adds-a-shelf-for-night-bus-drivers",
        r"night.bus|depot|drivers|shelf",
    ),
    45: ("hospital-staff-open-a-midnight-reading-cart", r"hospital|cart"),
    15: (
        "grandmother-finishes-her-first-marathon-at-seventy-two",
        r"grandmother|marathon",
    ),
    30: (
        "local-team-celebrates-its-first-championship-in-34-years",
        r"championship|team|deciding goal",
    ),
    16: ("a-baker-recreates-a-city-skyline-in-sourdough", r"baker|sourdough|skyline"),
    17: (
        "the-museum-guard-who-quietly-sketches-every-visitor",
        r"museum|guard|notebooks",
    ),
    29: (
        "a-ten-second-drawing-trick-that-changes-every-cartoon-face",
        r"cartoon|drawing trick|eyebrows",
    ),
    14: (
        "mechanical-keyboard-made-entirely-from-transparent-parts",
        r"keyboard|switches",
    ),
    21: ("hand-painted-arcade-cabinet-celebrates-classic-space-games", r"arcade"),
    22: (
        "street-musician-turns-a-rain-delay-into-a-concert",
        r"concert|musician|commuters",
    ),
    42: ("city-bridge-lights-react-to-nearby-music", r"city.bridge|lights|microphones"),
    20: ("dog-refuses-to-leave-the-kayak-after-the-trip-ends", r"kayak|pepper"),
    23: ("a-fox-naps-on-the-same-garden-wall-every-afternoon", r"fox|copper"),
}
POSTS = {
    0: (12, 32, 33),
    1: (13, 37, 39),
    2: (11, 34, 35),
    3: (19, 40, 41),
    4: (18, 43, 45),
    5: (15, 30),
    6: (16, 17, 29),
    7: (14, 21),
    8: (22, 41, 42),
    9: (13, 20, 23),
}
FEEDS = {3: "science", 5: "sports", 7: "gaming", 9: "animals"}
SEARCH = {
    0: ("lighthouse", "office", "bookshop"),
    1: ("rescue", "cat", "dog", "kitten"),
    2: ("camping", "solar", "tarp", "kitchen"),
    4: ("library", "libraries", "reading"),
    6: ("sourdough", "skyline", "museum", "drawing"),
    8: ("rain", "concert", "musician", "bridge"),
}
SAVE = {5: ("bob.c@test.com", "bob_c", 30), 7: ("alice.j@test.com", "alice_j", 21)}


def slugs(post_id, originals=False):
    stem = ENTITIES[post_id][0]
    original = f"{stem}-{post_id}"
    remix = f"community-remix-{post_id-10}-{stem}-{post_id+35}"
    return (original,) if originals else (original, remix)


def entity_texts(n, answer):
    """Resolve named sentence subjects and carry context through short follow-ups.

    Split coordinating clauses only before a new named subject. Decimal points
    and normalized am/pm survive sentence splitting. An unlabeled bag of facts
    cannot satisfy a multi-source task.
    """
    ids = POSTS[n]
    aliases = "|".join(ENTITIES[i][1] for i in ids)
    answer = re.sub(r"\b([ap])\.\s*m\.(?=\s+[A-Z])", r"\1m\n", answer)
    a = clean(answer).replace("**", "").replace("`", "")
    a = re.sub(rf"\b(?:and|whereas|while)\s+(?=(?:the\s+)?(?:{aliases}))", "\n", a)
    chunks = re.split(r"(?<!\d)\.|\.(?!\d)|[!?;\n]", a)
    result = {i: [] for i in ids}
    current = None
    for chunk in chunks:
        if re.search(r"\b(?:gap|difference|margin)\b", chunk):
            continue
        matches = [
            (m.start(), i) for i in ids if (m := re.search(ENTITIES[i][1], chunk))
        ]
        if matches:
            # First subject owns the clause, e.g. "fox has more than the dog".
            current = min(matches)[1]
        if current is not None:
            result[current].append(chunk)
    return {i: "; ".join(parts) for i, parts in result.items()}


def all_phrases(a, *patterns):
    return all(phrase(a, p) for p in patterns)


def count(a, units, value):
    values = dict(
        zip(
            (
                "zero one two three four five six seven eight nine ten eleven twelve "
                "thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
            ).split(),
            range(20),
        )
    )
    values.update(
        dict(
            zip(
                "twenty thirty forty fifty sixty seventy eighty ninety".split(),
                range(20, 100, 10),
            )
        )
    )
    tokens = "|".join((*values, "hundred", "thousand"))
    pattern = rf"\b(?:{tokens})(?:(?:[ -]+|[ -]+and[ -]+)(?:{tokens}))*\b"

    def convert(match):
        total = group = 0
        for word in re.split(r"[ -]+", match[0]):
            if word == "and":
                continue
            if word == "hundred":
                group = (group or 1) * 100
            elif word == "thousand":
                total += (group or 1) * 1000
                group = 0
            else:
                group += values[word]
        return str(total + group)

    a = re.sub(pattern, convert, a)
    return quantity(
        a,
        units if isinstance(units, dict) else {u: 1 for u in units},
        value,
        reverse=True,
    )


def points(a, expected):
    a = re.sub(r"(?<=\d),(?=\d{3}\b)", "", a)
    return count(a, ("points", "point", "pts"), expected)


def facts(n, answer):
    a = entity_texts(n, answer)
    base_keys = {
        0: ("width", "material"),
        1: ("month", "days"),
        2: ("power", "protection"),
        3: ("frequency", "feature"),
        4: ("color", "day", "time"),
        5: ("distance", "color"),
        6: ("attempts", "hours"),
        7: ("switches", "case"),
        8: ("platform",),
    }
    result = {}
    if n in base_keys:
        for key in base_keys[n]:
            result[f"answer_primary_{key}"] = check(n, key, a[POSTS[n][0]])
    extra = {
        0: lambda: {
            "bookshop_materials": all_phrases(a[32], r"\bpine\b", r"\bbrass\b"),
            "radio_test": all_phrases(
                a[33], r"equipment|radio", r"test|tried", r"winter", r"storm"
            ),
        },
        1: lambda: {
            "cat_identity_behavior": all_phrases(
                a[13], r"\bmiso\b", r"learn|recogni|routine|sound"
            ),
            "dog_identity_occasion": all_phrases(
                a[37],
                r"\bbasil\b",
                r"volunteer",
                r"greet|recogni|reunit",
                r"spring",
                r"open.house",
            ),
            "kitten_identity_solution": all_phrases(
                a[39], r"\bjuniper\b", r"solv|open", r"final|last", r"compartment"
            ),
        },
        2: lambda: {
            "lantern_count": count(a[34], ("lanterns", "compact lanterns"), 6),
            "lantern_criteria": all_phrases(
                a[34],
                r"charg(?:e|ing).{0,20}time|time.{0,20}charg",
                r"bright|light.output",
                r"night",
            ),
            "kitchen_rain": all_phrases(
                a[35],
                r"angl|slop",
                r"ridge",
                r"runoff|run.off|rain|water",
                r"away|divert|direct",
                r"stove",
                r"food",
            ),
        },
        3: lambda: {
            "whistle_source": all_phrases(
                a[40],
                r"narrow",
                r"seam",
                r"beneath|under|below",
                r"east",
                r"walkway",
                r"winter|gust",
            ),
            "rain_source": rain(a[41]),
        },
        4: lambda: {
            "bus_supplies_location": all_phrases(
                a[43], r"travel.books", r"warm|hot", r"drink|beverage", r"depot"
            ),
            "cart_coverage_shift": count(a[45], ("floors", "floor"), 3)
            and all_phrases(a[45], r"overnight|night.shift|midnight"),
        },
        5: lambda: {
            "team_wait": count(a[30], {"years": 1, "year": 1, "months": "1/12"}, 34),
            "goal_time": count(
                a[30], {"seconds": 1, "second": 1, "s": 1, "minutes": 60}, 18
            )
            and all_phrases(
                a[30], r"left|remaining|remain|to.go|before.{0,15}(?:end|buzzer)"
            ),
            "marathon_points": points(a[15], 2852),
            "team_points": points(a[30], 5447),
        },
        6: lambda: {
            "guard_years": count(a[17], {"years": 1, "year": 1, "months": "1/12"}, 5),
            "guard_notebooks": count(a[17], ("notebooks", "pocket notebooks"), 19),
            "drawing_change": all_phrases(a[29], r"eyebrows?")
            and quantity(
                a[29],
                {
                    "mm": 1,
                    "millimeters": 1,
                    "millimetres": 1,
                    "millimeter": 1,
                    "millimetre": 1,
                    "cm": 10,
                    "centimeters": 10,
                    "centimetres": 10,
                },
                2,
            ),
        },
        7: lambda: {
            "arcade_games": count(
                a[21], ("titles", "restored titles", "games", "restored games"), 12
            ),
            "arcade_controls": all_phrases(a[21], r"1980.?s|eighties", r"controls"),
            "keyboard_points": points(a[14], 2679),
            "arcade_points": points(a[21], 3890),
        },
        8: lambda: {
            "rain_source": rain(a[41]),
            "city_response": all_phrases(a[42], r"microphones?|mics?")
            and all_phrases(
                a[42],
                r"beneath|under|below",
                r"deck",
                r"bass",
                r"slow",
                r"blue",
                r"puls",
            ),
        },
        9: lambda: {
            "cat_name_points": all_phrases(a[13], r"\bmiso\b") and points(a[13], 2506),
            "dog_name_points": all_phrases(a[20], r"\bpepper\b")
            and points(a[20], 3717),
            "fox_name_points": all_phrases(a[23], r"\bcopper\b")
            and points(a[23], 4236),
            "dog_wait": all_phrases(
                a[20], r"second|another|one.more", r"lap|trip|round", r"lake"
            ),
            "fox_residents": all_phrases(
                a[23],
                r"respectful.distance|keep.{0,25}distance|stay.{0,20}(?:back|away)|give.{0,25}space",
            ),
            "ranking": ranking(answer),
            "gap": gap(answer),
        },
    }
    result.update({f"answer_{key}": value for key, value in extra[n]().items()})
    result["answer_no_contradictions"] = no_contradictions(n, a)
    return result


def no_contradictions(n, texts):
    # Explicit competing attributes of these frozen entities are contradictions.
    conflicts = {
        32: r"\b(?:steel|oak|plastic|alumini?um|walnut)\b",
        37: r"\b(?:autumn|fall|summer|winter)\b",
        40: r"\b(?:cables?|western|west|northern|southern)\b",
        42: r"\b(?:fast|rapid|red|green|yellow)\b",
    }
    for i, text in texts.items():
        if i in conflicts and phrase(text, conflicts[i]):
            return False
        # A correct claim followed by an explicit denial must also fail.
        if re.search(
            r"\b(?:not|never|no|isn.t|wasn.t)\s+(?:the\s+)?(?:pine|brass|brightness|blue|440|120|4\.2|february|orange|acrylic|copper|miso|pepper|silent|tactile)\b",
            text,
        ):
            return False
    return True


def rain(a):
    return all_phrases(
        a,
        r"deck.panels?|panels",
        r"rain|drops",
        r"strik|hit|fall|land",
        r"notes?|sound",
    )


def ranking(answer):
    a = clean(answer)
    # Explicit ordering or a list in the requested highest-first order. Inspect
    # the first occurrence of each animal, ignoring introductory task names.
    positions = [re.search(ENTITIES[i][1], a) for i in (23, 20, 13)]
    return (
        all(positions)
        and positions[0].start() < positions[1].start() < positions[2].start()
        and check(9, "name", answer)
    )


def gap(answer):
    answer = re.sub(r"\btop[- ]two\b", "", answer, flags=re.I)
    relevant = [
        s
        for s in re.split(r"[;\n]|(?<!\d)\.", clean(answer))
        if re.search(r"gap|ahead|difference|lead|more.than|margin", s)
    ]
    return any(quantity(s, {"points": 1, "point": 1, "pts": 1}, 519) for s in relevant)


def run_checks_for(n, judge, traj, initial_db, after_db):
    check_trajectory_identity(judge, traj, f"9GAG--{n}")
    if n in SAVE:
        email, username, target = SAVE[n]
        check_signed_in_as(judge, traj, email, username)
    if n in FEEDS:
        check_visited_path(
            judge, traj, f"visited_{FEEDS[n]}_interest_feed", f"/interest/{FEEDS[n]}"
        )
    else:
        check_search_visited(judge, traj, SEARCH[n])
    frozen_points = {
        5: {15: 2852, 30: 5447},
        7: {14: 2679, 21: 3890},
        9: {13: 2506, 20: 3717, 23: 4236},
    }
    for post_id in POSTS[n]:
        targets = slugs(post_id, n in (5, 7, 9))
        judge.check(
            f"seed_has_post_{post_id}",
            all(post_by_slug(initial_db, s) for s in targets),
            str(targets),
        )
        check_detail_visited(judge, traj, targets, name=f"visited_detail_{post_id}")
        if n in frozen_points:
            post = post_by_slug(initial_db, targets[0]) or {}
            judge.check(
                f"seed_points_{post_id}",
                post.get("up_votes") == frozen_points[n][post_id],
                "Original point totals must match the reviewed fixture.",
            )
    answer = final_answer(traj)
    for name, passed in facts(n, answer).items():
        judge.check(
            name, passed, "Facts must be correctly attributed to the requested post."
        )
    if n in SAVE:
        uid = user_id_for_email(initial_db, email)
        judge.check(
            "initial_state_requires_action",
            target not in saved_post_ids(initial_db, uid),
            f"target={target}",
        )
        delta = table_delta(initial_db, after_db, "saved_post")
        exact = (
            len(delta["added"]) == 1
            and not delta["removed"]
            and not delta["changed"]
            and int(delta["added"][0][1]) == uid
            and int(delta["added"][0][2]) == target
        )
        judge.check("saved_post_exact_delta", exact, str(delta))
        check_only_tables_changed(judge, initial_db, after_db, allowed=("saved_post",))
    else:
        check_read_only(judge, initial_db, after_db)

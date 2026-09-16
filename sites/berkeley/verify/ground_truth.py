#!/usr/bin/env python3
"""Re-derive every UC Berkeley task target from a supplied initial SQLite snapshot.

``task_ground_truth(db, n)`` selects the target exactly the way the task text and
the app do — the frozen benchmark clock (``BENCHMARK_NOW``), ``PER_PAGE``, the
app's ``ORDER BY`` clauses and its unordered ``LIMIT 3`` related-centres query —
using plain SQL. No answer constant is frozen anywhere except the snapshot
catalog fingerprint in ``verify_lib.py``; a re-frozen seed is caught there
before grading starts, and any derivation that cannot find its target raises
``ValueError`` so the verifier fails closed instead of guessing.

Two rows (11, 17) read values that the app renders from tracked source rather
than from the DB; their derivations parse ``templates/admissions.html`` and
``app.py`` respectively, and ``verify/tests`` asserts those values stay
source-literals (never DB-derived).
"""
from __future__ import annotations

import datetime as _dt
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

VERIFY_DIR = Path(__file__).resolve().parent
SITE_DIR = VERIFY_DIR.parent
TEMPLATES_DIR = SITE_DIR / "templates"
APP_SOURCE = SITE_DIR / "app.py"

# app.py:48 — the frozen clock every "upcoming" view is compared against.
BENCHMARK_NOW = "2026-05-12 00:00:00.000000"
BENCHMARK_NOW_DATE = _dt.date(2026, 5, 12)

# app.py:39 — the listing page size.
PER_PAGE = 20

# The AI-family allowlist for task 7. A *rule*, not an answer: it selects the
# EECS rows whose stated interests are AI-related, and the verifier still binds
# the quoted interests to the named row.
AI_INTEREST_RE = re.compile(
    r"\b(?:ai|artificial intelligence|machine learning|deep learning|"
    r"reinforcement learning|robot|robotics)\b",
    re.I,
)

# Title pattern that yields (subject, award) from an award-reporting headline.
AWARD_TITLE_RE = re.compile(r"^(?P<subject>.+?)\s+Receives?\s+(?P<award>.+?)\s*$")


def _connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def _rows(connection: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(sql, params)]


def _one(rows: Iterable[dict[str, Any]], description: str) -> dict[str, Any]:
    items = list(rows)
    if len(items) != 1:
        raise ValueError(f"{description} must be unique; observed {len(items)} rows")
    return items[0]


def _at_least(rows: Iterable[dict[str, Any]], count: int, description: str) -> list[dict[str, Any]]:
    items = list(rows)
    if len(items) < count:
        raise ValueError(f"{description} needs at least {count} rows; observed {len(items)}")
    return items


# --------------------------------------------------------------------------- #
# Catalog replicas of the app's own queries
# --------------------------------------------------------------------------- #
def _programmes(connection: sqlite3.Connection, where: str = "1=1", params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    """``ORDER BY Program.name`` — the ordering of /programs (app.py:368)."""
    return _rows(
        connection,
        "SELECT p.*, c.name AS college_name, d.name AS department_name "
        "FROM programs p LEFT JOIN colleges c ON c.id = p.college_id "
        "LEFT JOIN departments d ON d.id = p.department_id "
        f"WHERE {where} ORDER BY p.name",
        params,
    )


def programme_by_slug(connection: sqlite3.Connection, slug: str) -> dict[str, Any]:
    return _one(_programmes(connection, "p.slug = ?", (slug,)), f"programme slug {slug!r}")


def _events(
    connection: sqlite3.Connection,
    where: str = "1=1",
    params: Sequence[Any] = (),
    *,
    upcoming: bool = True,
) -> list[dict[str, Any]]:
    """``/events`` semantics: ``upcoming`` filters ``start_datetime >= BENCHMARK_NOW``."""
    clause = "start_datetime >= ?" if upcoming else "1=1"
    clauses = [where, clause]
    values: list[Any] = list(params) + ([BENCHMARK_NOW] if upcoming else [])
    return _rows(
        connection,
        f"SELECT * FROM events WHERE {' AND '.join(clauses)} ORDER BY start_datetime",
        values,
    )


def _departments(connection: sqlite3.Connection, college_id: int) -> list[dict[str, Any]]:
    """``ORDER BY Department.name`` — the ordering of /departments (app.py:482)."""
    return _rows(
        connection,
        "SELECT * FROM departments WHERE college_id = ? ORDER BY name",
        (college_id,),
    )


def _faculty_of_department(connection: sqlite3.Connection, department_id: int) -> list[dict[str, Any]]:
    """``ORDER BY Faculty.name`` — the ordering of /faculty (app.py:587)."""
    return _rows(
        connection,
        "SELECT * FROM faculty WHERE department_id = ? ORDER BY name",
        (department_id,),
    )


def related_centres(connection: sqlite3.Connection, centre: dict[str, Any]) -> list[dict[str, Any]]:
    """The centres the detail page renders: ``ORDER BY name LIMIT 3`` (app.py research_center)."""
    return _rows(
        connection,
        "SELECT * FROM research_centers WHERE college_id = ? AND id != ? "
        "ORDER BY name LIMIT 3",
        (centre["college_id"], centre["id"]),
    )


def centre_by_slug(connection: sqlite3.Connection, slug: str) -> dict[str, Any]:
    return _one(
        _rows(connection, "SELECT * FROM research_centers WHERE slug = ?", (slug,)),
        f"research centre slug {slug!r}",
    )


def _college_by_slug(connection: sqlite3.Connection, slug: str) -> dict[str, Any]:
    return _one(_rows(connection, "SELECT * FROM colleges WHERE slug = ?", (slug,)), f"college slug {slug!r}")


# --------------------------------------------------------------------------- #
# Source-rendered facts (not in the DB)
# --------------------------------------------------------------------------- #
def admissions_facts() -> dict[str, str]:
    """The two Admissions figures, parsed from the tracked template.

    ``templates/admissions.html`` renders ``Freshman Application | November 30``
    and a ``stat-number`` acceptance rate labelled ``Acceptance Rate``. The
    numbers are source literals (not DB rows), so the parser must find them or
    the verifier fails closed.
    """
    html = (TEMPLATES_DIR / "admissions.html").read_text(encoding="utf-8")
    deadline = re.search(r"<td>\s*Freshman Application\s*</td>\s*<td>\s*([^<]+?)\s*</td>", html)
    if not deadline:
        raise ValueError("admissions.html no longer renders the Freshman Application deadline")
    rate = re.search(
        r'stat-number">\s*([\d.]+)\s*%\s*</span>\s*<span class="stat-label">\s*Acceptance Rate',
        html,
    )
    if not rate:
        raise ValueError("admissions.html no longer renders a labelled Acceptance Rate stat")
    return {"deadline": deadline.group(1).strip(), "acceptance_rate": f"{rate.group(1)}%"}


def about_facts() -> dict[str, int]:
    """The three About-page statistics, parsed from ``app.py``'s ``about()`` dict."""
    source = APP_SOURCE.read_text(encoding="utf-8")
    body = re.search(r"def about\(\):(.*?)\n@app\.route", source, re.S)
    if not body:
        raise ValueError("app.py no longer defines about()")
    facts: dict[str, int] = {}
    for key in ("nobel_laureates", "varsity_sports", "national_titles"):
        match = re.search(rf"'{key}':\s*(\d+)", body.group(1))
        if not match:
            raise ValueError(f"about() no longer defines {key!r} as an integer literal")
        facts[key] = int(match.group(1))
    return facts


def about_distractor_prizes() -> int:
    """The near-miss Nobel count the About page prints next to the faculty statistic."""
    html = (TEMPLATES_DIR / "about.html").read_text(encoding="utf-8")
    match = re.search(r"more than\s+(\d+)\s+Nobel Prizes", html)
    if not match:
        raise ValueError("about.html no longer renders the 'more than N Nobel Prizes' distractor")
    return int(match.group(1))


# --------------------------------------------------------------------------- #
# Per-task derivation
# --------------------------------------------------------------------------- #
def requirement_items(requirements: str) -> list[str]:
    """The comma/semicolon-separated requirement items of a programme detail page."""
    items: list[str] = []
    for raw in re.split(r"[;,]", str(requirements or "")):
        item = re.sub(r"^\s*plus\s+", "", raw.strip()).strip(" .")
        if len(item) >= 2:
            items.append(item)
    return items


def _task(db_path: str | Path, n: int) -> dict[str, Any]:
    connection = _connect(db_path)
    try:
        return _derive(connection, n)
    finally:
        connection.close()


def task_ground_truth(db_path: str | Path, n: int) -> dict[str, Any]:
    return _task(db_path, int(n))


def _derive(c: sqlite3.Connection, n: int) -> dict[str, Any]:
    if n == 1:
        program = _one(_programmes(c, "p.degree_type = 'MBA'"), "the MBA programme")
        return {
            "task": n,
            "program": program,
            "college": program["college_name"],
            "duration_years": float(program["duration_years"]),
        }

    if n == 2:
        target = programme_by_slug(c, "computer-science-bs")
        items = requirement_items(target["requirements"])
        if len(items) < 6:
            raise ValueError(f"task 2 needs a populated BS requirements list; observed {items!r}")
        target_tokens = {token for item in items for token in re.findall(r"[a-z0-9]+", item.lower())}
        foreign: list[str] = []
        for sibling in _programmes(c, "p.name = ? AND p.slug != ?", ("Computer Science", target["slug"])):
            for item in requirement_items(sibling["requirements"]):
                tokens = re.findall(r"[a-z0-9]+", item.lower())
                if len(tokens) >= 2 and not (set(tokens) & target_tokens):
                    foreign.append(item)
        if not foreign:
            raise ValueError("task 2 needs sibling requirement items that are absent from the BS list")
        return {"task": n, "program": target, "items": items, "foreign_items": sorted(set(foreign))}

    if n == 4:
        candidates = _rows(
            c,
            "SELECT * FROM news_articles WHERE title LIKE '%CRISPR%' OR content LIKE '%CRISPR%' "
            "OR tags LIKE '%CRISPR%' ORDER BY published_date DESC",
        )
        _at_least(candidates, 2, "task 4 CRISPR articles")
        target = _one(
            [row for row in candidates if AWARD_TITLE_RE.fullmatch(row["title"])],
            "task 4 award-reporting article",
        )
        match = AWARD_TITLE_RE.fullmatch(target["title"])
        subject_tokens = re.findall(r"[A-Z][a-z]+", match.group("subject"))
        if len(subject_tokens) < 2:
            raise ValueError(f"task 4 cannot derive a person from {target['title']!r}")
        return {
            "task": n,
            "article": target,
            "person": " ".join(subject_tokens[-2:]),
            "award": match.group("award"),
            "candidates": candidates,
        }

    if n == 6:
        upcoming = _events(c, "category = 'Lecture'")
        every = _events(c, "category = 'Lecture'", upcoming=False)
        _at_least(upcoming, 3, "task 6 upcoming Lecture events")
        return {"task": n, "events": every, "upcoming": upcoming}

    if n == 7:
        department = _one(_rows(c, "SELECT * FROM departments WHERE slug = 'eecs'"), "the EECS department")
        members = _faculty_of_department(c, department["id"])
        if len(members) < 10:
            raise ValueError(f"task 7 needs the full EECS roster; observed {len(members)}")
        allowed = [row for row in members if AI_INTEREST_RE.search(row["research_interests"] or "")]
        if len(allowed) < 5:
            raise ValueError(f"task 7 needs at least five AI-family EECS faculty; observed {len(allowed)}")
        return {"task": n, "department": department, "members": members, "allowed": allowed}

    if n == 10:
        centre = centre_by_slug(c, "bair")
        return {"task": n, "centre": centre, "director": centre["director"], "founded_year": int(centre["founded_year"])}

    if n == 11:
        return {"task": n, **admissions_facts()}

    if n == 12:
        college = _college_by_slug(c, "haas-business")
        programmes = _programmes(c, "p.college_id = ?", (college["id"],))
        if len(programmes) != 1:
            raise ValueError(f"task 12 expects the single-programme Haas catalogue; observed {len(programmes)}")
        catalogue_types = sorted({row["degree_type"] for row in _programmes(c)})
        offered = {programmes[0]["degree_type"]}
        return {
            "task": n,
            "college": college,
            "programmes": programmes,
            "offered_types": sorted(offered),
            "other_types": [value for value in catalogue_types if value not in offered],
        }

    if n == 13:
        department = _one(_rows(c, "SELECT * FROM departments WHERE slug = 'eecs'"), "the EECS department")
        return {"task": n, "department": department, "chair": department["chair"], "location": department["location"]}

    if n == 14:
        college = _college_by_slug(c, "engineering")
        return {
            "task": n,
            "college": college,
            "dean": college["dean"],
            "undergrad_count": int(college["undergrad_count"]),
            "grad_count": int(college["grad_count"]),
        }

    if n == 16:
        online = _programmes(c, "p.is_online = 1")
        programme = _one(online, "the single online programme")
        others = [row["name"] for row in _programmes(c, "p.slug != ?", (programme["slug"],))]
        return {"task": n, "program": programme, "others": others}

    if n == 17:
        return {"task": n, **about_facts(), "distractor_nobel_prizes": about_distractor_prizes()}

    if n == 19:
        articles = _rows(c, "SELECT * FROM news_articles WHERE category = 'Athletics' ORDER BY published_date DESC")
        _at_least(articles, 5, "task 19 Athletics articles")
        championships = [row for row in articles if "championship" in (row["title"] or "").lower()]
        if len(championships) < 2:
            raise ValueError(f"task 19 needs at least two championship articles; observed {len(championships)}")
        return {"task": n, "articles": articles, "championships": championships}

    if n == 20:
        program = programme_by_slug(c, "juris-doctor-jd")
        return {
            "task": n,
            "program": program,
            "duration_years": float(program["duration_years"]),
            "deadline": program["application_deadline"],
            "college": program["college_name"],
        }

    if n == 22:
        college = _college_by_slug(c, "letters-and-science")
        departments = _departments(c, college["id"])
        if len(departments) < 4:
            raise ValueError(f"task 22 needs the L&S department list; observed {len(departments)}")
        return {"task": n, "college": college, "departments": departments}

    if n == 23:
        centre = centre_by_slug(c, "bids")
        focus = [part.strip() for part in (centre["focus_areas"] or "").split(",") if part.strip()]
        related = related_centres(c, centre)
        if len(focus) < 3 or not related:
            raise ValueError("task 23 needs BIDS focus areas and its rendered related centres")
        return {
            "task": n,
            "centre": centre,
            "focus_areas": focus,
            "related": related,
            "related_names": [row["name"] for row in related],
        }

    if n == 24:
        program = programme_by_slug(c, "economics-phd")
        if not program["department_id"]:
            raise ValueError("task 24 needs the Economics PhD to carry a department")
        department = _one(
            _rows(c, "SELECT * FROM departments WHERE id = ?", (program["department_id"],)),
            "the Economics department",
        )
        programmes = _programmes(c, "p.department_id = ?", (department["id"],))
        members = _faculty_of_department(c, department["id"])
        if len(programmes) < 2 or len(members) < 3:
            raise ValueError("task 24 needs the department's programme list and faculty roster")
        return {
            "task": n,
            "program": program,
            "department": department,
            "programmes": programmes,
            "members": members,
            "chair": department["chair"],
        }

    if n == 25:
        career = _events(c, "category = 'Career'")
        _at_least(career, 3, "task 25 upcoming Career events")
        anchor = _one([row for row in career if "career fair" in (row["title"] or "").lower()], "the Spring Career Fair")
        return {"task": n, "anchor": anchor, "others": [row for row in career if row["id"] != anchor["id"]]}

    if n == 27:
        meng = programme_by_slug(c, "master-of-engineering-meng")
        ms = programme_by_slug(c, "computer-science-ms")
        if meng["department_id"] != ms["department_id"]:
            raise ValueError("task 27 expects both programmes in the same department")
        return {
            "task": n,
            "meng": meng,
            "ms": ms,
            "department": meng["department_name"],
            "durations": (float(meng["duration_years"]), float(ms["duration_years"])),
        }

    if n == 28:
        gre = _programmes(c, "p.gre_required = 1")
        _at_least(gre, 10, "task 28 GRE-required programmes")
        counts: dict[str, int] = {}
        for row in gre:
            counts[row["degree_type"]] = counts.get(row["degree_type"], 0) + 1
        top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if len(top) > 1 and top[0][1] == top[1][1]:
            raise ValueError("task 28 degree-type mode is tied")
        return {"task": n, "count": len(gre), "by_degree": counts, "most_common_degree": top[0][0]}

    if n == 30:
        centre = centre_by_slug(c, "seismo-lab")
        return {"task": n, "centre": centre, "director": centre["director"]}

    if n == 31:
        first = centre_by_slug(c, "msri")
        second = centre_by_slug(c, "cpl")
        return {"task": n, "first": first, "second": second, "directors": (first["director"], second["director"])}

    raise ValueError(f"unsupported UC Berkeley task {n}")


def all_ground_truth(db_path: str | Path) -> dict[int, dict[str, Any]]:
    return {number: task_ground_truth(db_path, number)
            for number in (1, 2, 4, 6, 7, 10, 11, 12, 13, 14, 16, 17, 19, 20, 22, 23, 24, 25, 27, 28, 30, 31)}


if __name__ == "__main__":  # pragma: no cover - manual inspection
    import json

    facts = all_ground_truth(sys.argv[1])
    print(json.dumps(facts, indent=1, default=str))

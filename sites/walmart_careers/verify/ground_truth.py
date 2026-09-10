"""Derive Walmart Careers task targets from a supplied initial SQLite snapshot."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable


def _rows(db_path: str | Path) -> list[dict[str, Any]]:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT j.*, s.store_number, s.banner, s.location_name, s.street, s.city, s.state, s.zip, s.lat, s.lng, "
            "a.slug AS area_slug, a.name AS area_name, c.slug AS category_slug, c.name AS category_name "
            "FROM jobs j JOIN stores s ON s.id=j.store_id JOIN areas a ON a.id=j.area_id "
            "JOIN categories c ON c.id=j.category_id ORDER BY j.job_id"
        ).fetchall()
        output = [dict(row) for row in rows]
    finally:
        connection.close()
    for row in output:
        row["shifts"] = json.loads(row.get("shifts_json") or "[]")
        row["minimum_qualifications"] = json.loads(row.get("min_qualifications_json") or "[]")
    return output


def _one(rows: list[dict[str, Any]], description: str) -> dict[str, Any]:
    if len(rows) != 1:
        raise ValueError(f"{description} must be unique; observed {len(rows)} rows: {[row.get('job_id') for row in rows]}")
    return rows[0]


def _extreme(rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any], maximum: bool, description: str) -> dict[str, Any]:
    if not rows:
        raise ValueError(f"{description} has no candidates")
    value = (max if maximum else min)(key(row) for row in rows)
    winners = [row for row in rows if key(row) == value]
    return _one(winners, description)


def _clock_minutes(window: str) -> int:
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m", window or "", re.I)
    if not match:
        raise ValueError(f"cannot parse shift window {window!r}")
    hour = int(match.group(1)) % 12 + (12 if match.group(3).lower() == "p" else 0)
    return hour * 60 + int(match.group(2) or 0)


def _option_years(row: dict[str, Any], index: int = 1) -> int:
    options = row["minimum_qualifications"]
    if len(options) <= index:
        raise ValueError(f"missing qualification option {index + 1} for {row['job_id']}")
    values = [int(value) for value in re.findall(r"\b(\d+)\s+years?\b", options[index], re.I)]
    if len(values) != 1:
        raise ValueError(f"qualification years are not unique for {row['job_id']}: {values}")
    return values[0]


def _user_id(connection: sqlite3.Connection, email: str) -> int:
    row = connection.execute("SELECT id FROM users WHERE lower(email)=lower(?)", (email,)).fetchone()
    if row is None:
        raise ValueError(f"missing benchmark user {email}")
    return int(row[0])


def _saved_rows(db_path: str | Path, jobs: list[dict[str, Any]], email: str) -> list[dict[str, Any]]:
    by_id = {row["job_id"]: row for row in jobs}
    connection = sqlite3.connect(str(db_path))
    try:
        user_id = _user_id(connection, email)
        ids = [row[0] for row in connection.execute("SELECT job_id FROM saved_jobs WHERE user_id=? ORDER BY id", (user_id,))]
    finally:
        connection.close()
    try:
        return [by_id[job_id] for job_id in ids]
    except KeyError as exc:
        raise ValueError(f"saved role references unknown job {exc.args[0]}") from exc


def task_ground_truth(db_path: str | Path, task_number: int) -> dict[str, Any]:
    jobs = _rows(db_path)
    select = lambda predicate: [row for row in jobs if predicate(row)]

    if task_number == 0:
        candidates = select(lambda row: row["title"] == "Optician" and row["banner"] == "Neighborhood Market" and row["city"] == "Wichita" and row["state"] == "KS")
        target = _one(candidates, "task 0 Wichita Neighborhood Market Optician")
    elif task_number == 1:
        candidates = select(lambda row: row["title"].startswith("Staff, Software Engineer") and row["city"] == "Sunnyvale" and row["state"] == "CA")
        target = _one(candidates, "task 1 Sunnyvale Staff Software Engineer")
    elif task_number == 2:
        candidates = select(lambda row: row["title"] == "Freight Handler" and row["store_number"] == "9054" and row["city"] == "Porterville" and row["state"] == "CA")
        target = _one(candidates, "task 2 Porterville Freight Handler")
    elif task_number == 3:
        candidates = select(lambda row: row["title"] == "Pharmacy Technician" and row["area_slug"] == "healthcare" and row["city"] == "Bentonville" and row["state"] == "AR")
        target = _one(candidates, "task 3 Bentonville Pharmacy Technician")
    elif task_number == 4:
        candidates = select(lambda row: row["brand"] == "Sam's Club" and row["employment_type"] == "Part time" and "Weekend Overnight" in row["shifts"] and float(row["max_pay"]) <= 20 and row["state"] == "TX")
        target = _one(candidates, "task 4 qualifying Texas role")
    elif task_number == 5:
        candidates = select(lambda row: row["employment_type"] == "Full time" and row["area_slug"] == "technology" and row["city"] == "Hoboken" and row["state"] == "NJ" and float(row["max_pay"]) > 200000)
        target = _one(candidates, "task 5 qualifying Hoboken Technology role")
    elif task_number == 6:
        candidates = select(lambda row: row["title"] == "Online Order Filling Team Supervisor" and row["city"] == "Cleveland" and row["state"] == "OH" and row["employment_type"] == "Full time" and "Weekday Day" in row["shifts"])
        target = _one(candidates, "task 6 Cleveland supervisor")
    elif task_number == 7:
        candidates = select(lambda row: row["area_slug"] == "students" and row["employment_type"] == "Intern" and row["brand"] == "Sam's Club" and "merchandising" in row["title"].lower() and row["city"] == "Bentonville" and row["state"] == "AR")
        target = _one(candidates, "task 7 merchandising internship")
    elif task_number == 8:
        candidates = select(lambda row: row["title"] == "Auto Care Center Technician" and row["state"] == "MS")
        if len(candidates) != 2:
            raise ValueError(f"task 8 requires two candidates; observed {len(candidates)}")
        target = _extreme(candidates, lambda row: int(row["positions_available"]), True, "task 8 maximum positions")
    elif task_number == 9:
        candidates = select(lambda row: row["title"] == "Freight Handler" and row["city"] == "Marcy" and row["state"] == "NY")
        if len(candidates) != 2:
            raise ValueError(f"task 9 requires two candidates; observed {len(candidates)}")
        target = _extreme(candidates, lambda row: _clock_minutes(row["shift_time"]), False, "task 9 earliest shift")
    elif task_number == 10:
        title = "Senior Manager, Delivery Search, Arrival & Matching (Last Mile Delivery)"
        candidates = select(lambda row: row["title"] == title and (row["city"], row["state"]) in {("Bentonville", "AR"), ("Hoboken", "NJ")})
        if len(candidates) != 2:
            raise ValueError(f"task 10 requires two candidates; observed {len(candidates)}")
        target = _extreme(candidates, _option_years, True, "task 10 maximum Option 2 experience")
    elif task_number == 11:
        candidates = select(lambda row: "Yard Driver" in row["title"] and row["city"] == "Williamsburg" and row["state"] == "VA")
        target = _one(candidates, "task 11 Williamsburg Yard Driver")
    elif task_number == 12:
        candidates = [row for row in _saved_rows(db_path, jobs, "bob.c@test.com") if row["banner"] == "Neighborhood Market"]
        target = _one(candidates, "task 12 Bob Neighborhood Market saved role")
    elif task_number == 13:
        candidates = select(lambda row: row["title"] == "Pharmacy Technician" and row["city"] == "Tacoma" and row["state"] == "WA")
        target = _one(candidates, "task 13 Tacoma Pharmacy Technician")
    elif task_number == 14:
        candidates = select(lambda row: row["title"] == "eCom Warehouse Worker" and row["store_number"] == "9046" and row["city"] == "Marcy" and row["state"] == "NY")
        target = _one(candidates, "task 14 Marcy eCom Warehouse Worker")
    elif task_number == 15:
        connection = sqlite3.connect(str(db_path)); connection.row_factory = sqlite3.Row
        try:
            user_id = _user_id(connection, "david.k@test.com")
            rows = [dict(row) for row in connection.execute("SELECT * FROM applications WHERE user_id=? ORDER BY id", (user_id,))]
        finally:
            connection.close()
        target = _one(rows, "task 15 David existing application")
        candidates = rows
    elif task_number == 16:
        candidates = select(lambda row: row["state"] == "PR" and row["population"] == "hourly" and "Weekday Day" in row["shifts"] and "Cashier" in row["title"] and row["positions_available"] is not None)
        target = _extreme(candidates, lambda row: int(row["positions_available"]), True, "task 16 maximum PR cashier positions")
    elif task_number == 17:
        candidates = [row for row in _saved_rows(db_path, jobs, "alice.j@test.com") if row["employment_type"] == "Part time"]
        target = _one(candidates, "task 17 Alice Part time saved role")
    elif task_number == 18:
        candidates = select(lambda row: row["title"] == "Class A CDL Truck Driver" and (row["city"], row["state"]) in {("Ottawa", "KS"), ("Williamsburg", "VA")})
        if len(candidates) != 2:
            raise ValueError(f"task 18 requires two candidates; observed {len(candidates)}")
        target = _extreme(candidates, lambda row: int(row["positions_available"]), True, "task 18 maximum positions")
    elif task_number == 19:
        candidates = select(lambda row: row["area_slug"] == "stores-and-clubs" and row["category_slug"] == "digital-pickup-and-delivery" and row["employment_type"] == "Full time" and row["positions_available"] is not None)
        target = _extreme(candidates, lambda row: int(row["positions_available"]), False, "task 19 minimum positions")
    else:
        raise ValueError(f"unsupported Walmart Careers task {task_number}")
    return {"task": task_number, "target": target, "candidates": candidates}


def _shift_endpoints(window: str) -> tuple[str, str]:
    values = re.findall(r"\b\d{1,2}(?::\d{2})?\s*[ap]\.?m", window or "", re.I)
    if len(values) != 2:
        raise ValueError(f"shift window does not have two endpoints: {window!r}")
    return values[0], values[1]


def constants_for_task(db_path: str | Path, task_number: int) -> dict[str, Any]:
    fact = task_ground_truth(db_path, task_number)
    target, candidates = fact["target"], fact["candidates"]
    values: dict[str, Any] = {"JOB_ID": target["job_id"]}
    if task_number in {0, 6, 7, 19}:
        values["STREET"] = target["street"]
    if task_number == 1:
        option = target["minimum_qualifications"][1]
        values.update(OPTION_2_EXACT=re.sub(r"^Option\s*2:\s*", "", option, flags=re.I), OPTION_1_EXACT=target["minimum_qualifications"][0])
    if task_number in {2, 9, 17, 18}:
        values["SHIFT_START"], values["SHIFT_END"] = _shift_endpoints(target["shift_time"])
    if task_number in {2, 3, 4, 6, 8, 16, 18}:
        values["POSITIONS"] = int(target["positions_available"])
    if task_number == 3:
        values["HASHTAG"] = target["hashtag"]
    if task_number == 5:
        values["DEGREE"] = "bachelor's degree in computer science"
    if task_number == 7:
        values["WORKER_TYPE_FRAGMENTS"] = tuple(part.strip().casefold() for part in re.split(r"[()/]", target["worker_type"]) if part.strip())
    if task_number in {8, 9, 10, 18}:
        loser = _one([row for row in candidates if row["job_id"] != target["job_id"]], f"task {task_number} losing candidate")
        values["LOSER_ID"] = loser["job_id"]
        if task_number == 8:
            values.update(WINNER_ID=target["job_id"], WINNER_STORE=int(target["store_number"]), LOSER_STORE=int(loser["store_number"]))
    if task_number == 10:
        values["YEARS"] = _option_years(target)
    if task_number == 15:
        values["CONFIRMATION_NO"] = target["confirmation_no"]
    if task_number in {13, 17}:
        email = "carol.d@test.com" if task_number == 13 else "alice.j@test.com"
        connection = sqlite3.connect(str(db_path))
        try:
            values["USER_ID"] = _user_id(connection, email)
        finally:
            connection.close()
    return values


def all_ground_truth(db_path: str | Path) -> dict[int, dict[str, Any]]:
    return {number: task_ground_truth(db_path, number) for number in range(20)}

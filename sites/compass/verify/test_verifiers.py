"""Synthetic grading fixtures, never counted as browser trajectories."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib as v


ANSWERS = {
    0: "88 SW 7th St #PH4303, Miami; built 2016; MLS A12055974.",
    1: "420 Mission Bay Blvd North, Unit 120, San Francisco — $899,000, year 2012, MLS 426105057.",
    2: "1425 Brickell Ave #42F: $11.75M; 3,913 sq ft; built 2003.\n480 NE 31st St #PH5402: $4.5M; 2,112 sq ft; built 2019.\n480 NE 31st St #PH5402 has the lower price per square foot.",
    3: "195 Willoughby Ave #1517/1518, Brooklyn — 1958; Charlie Lewis.",
    4: "Saved successfully. Recorded price: $565,000. Type: Co-op.",
    5: "Phone: (415) 555-0199. San Francisco, California.",
    6: "The tour is requested. Year built: 2019.",
    7: "Share token: fixture-token.",
    10: "Boston; for-sale; Condo; minimum 3 bedrooms.",
    11: "864 Moore Dr, Aspen — seven bedrooms; 10,615 square feet; year 2005; MLS 188891.",
    12: "Rounded price per square foot: $1,090. Year: 1957. Jenna Citron Pinchuk, jenna.citron@compass.com.",
    13: "Rockwell Island, Miami — 4 bedrooms; 4,588 sqft; built 2026; Renier Casanova.",
    14: "2311 Westoak Dr, Austin; MLS 1726892.",
    15: "669 St Marks Ave #2B, Brooklyn; June 6, 2026; Marta Maletz.",
    16: "195 Willoughby Avenue, Unit 1517/1518 — year 1958; Charlie Lewis.",
    17: "150 Charles St #M10, Manhattan — Holly Parker; built 2013.",
}


def trajectory(task):
    paths = ["/"] + [v.detail_path(key) for key in v.LISTINGS]
    paths += [v.detail_path(89), "/agents/" + v.LISTINGS[89]["agent_slug"], "/account", "/saved", "/tours", "/inquiry/38",
              "/collections/99", "/collections/share/fixture-token", "/saved-searches",
              "/search?q=Boston&status=for-sale&property_type=Condo&beds=3"]
    return {"task_id": f"Compass--{task}", "start_url": "http://localhost:40018/",
            "final_answer": ANSWERS[task], "steps": [{"url": "http://localhost:40018" + path, "action": "click"} for path in paths]}


@pytest.mark.parametrize("task", sorted(ANSWERS))
def test_equivalent_answer_spelling_and_units(task):
    j = v.Checks(task)
    v.answer_checks(j, trajectory(task))
    assert j.result()["pass"], j.result()


@pytest.mark.parametrize("task", sorted(set(ANSWERS) - {7}))
def test_wrong_answer_is_not_saved_by_correct_navigation(task):
    t = trajectory(task)
    t["final_answer"] = "I completed everything successfully."
    j = v.Checks(task)
    v.answer_checks(j, t)
    assert not j.result()["pass"]


@pytest.mark.parametrize("replacement", ["https://www.compass.com", "http://localhost.evil.example:40018", "http://127.0.0.1:40019"])
def test_foreign_origin_and_wrong_port_do_not_supply_navigation(replacement):
    t = trajectory(0)
    for step in t["steps"]:
        step["url"] = step["url"].replace("http://localhost:40018", replacement)
    assert not v.visited(t, v.detail_path(99))


def test_target_path_in_query_is_not_navigation():
    t = trajectory(0)
    t["steps"] = [{"url": "http://localhost:40018/search?q=" + v.detail_path(99)}]
    assert not v.visited(t, v.detail_path(99))


def test_comparison_rejects_swapped_facts_and_incorrect_winner():
    for answer in [ANSWERS[2].replace("2003", "TEMP").replace("2019", "2003").replace("TEMP", "2019"),
                   ANSWERS[2].replace("480 NE 31st St #PH5402 has the lower", "1425 Brickell Ave #42F has the lower")]:
        t = trajectory(2); t["final_answer"] = answer
        j = v.Checks(2); v.answer_checks(j, t)
        assert not j.result()["pass"]


def test_comparison_accepts_additional_derived_ratios():
    t = trajectory(2)
    t["final_answer"] = t["final_answer"].replace("built 2003.", "built 2003; $3,003/sqft.").replace("built 2019.", "built 2019; $2,131/sqft.")
    j = v.Checks(2); v.answer_checks(j, t)
    assert j.result()["pass"], j.result()


@pytest.mark.parametrize("before,after", [("A12055974", "A120559740"), ("2016", "2017")])
def test_exact_fact_boundaries(before, after):
    t = trajectory(0); t["final_answer"] = t["final_answer"].replace(before, after)
    j = v.Checks(0); v.answer_checks(j, t)
    assert not j.result()["pass"]


def test_agent_email_domain_suffix_is_wrong():
    t = trajectory(12); t["final_answer"] = t["final_answer"].replace("@compass.com", "@compass.com.evil.example")
    j = v.Checks(12); v.answer_checks(j, t)
    assert not j.result()["pass"]


@pytest.mark.parametrize("year,bedrooms,sqft", [(2025, 4, 4588), (2026, 6, 6501), (2026, 4, 45880)])
def test_similarly_named_property_is_not_the_same_answer(year, bedrooms, sqft):
    t = trajectory(13)
    t["final_answer"] = f"Rockwell Island, Miami; {bedrooms} bedrooms, {sqft} sqft, built {year}; Renier Casanova."
    j = v.Checks(13); v.answer_checks(j, t)
    assert not j.result()["pass"]


def initial_state():
    result = {key: {} for key in v.TABLES}
    for uid, email in enumerate(("alice.j@test.com", "bob.smith@test.com", "carol.lee@test.com", "david.kim@test.com"), 1):
        result["users"][uid] = {"id": uid, "email": email, "phone": "unchanged-phone", "name": email.split('.')[0]}
    result["listings"][99] = {"id": 99, "price": 5799900}
    result["saved_homes"][1] = {"id": 1, "user_id": 4, "listing_id": 17}
    return result


def completed_state(task, before):
    after = copy.deepcopy(before)
    if task == 5:
        after["users"][1]["phone"] = "(415) 555-0199"
    elif task == 6:
        after["tours"][99] = {"id": 99, "user_id": 3, "listing_id": 110, "requested_date": "2026-07-12", "requested_time": "11:00 AM", "tour_type": "in-person", "status": "requested"}
    elif task in {7, 14}:
        after["collections"][99] = {"id": 99, "user_id": 4, "name": "Austin top picks" if task == 7 else "Austin garage picks", "listing_ids_json": json.dumps([252, 253] if task == 7 else [233]), "share_token": "fixture-token"}
    elif task == 10:
        after["saved_searches"][99] = {"id": 99, "user_id": 1, "name": "Boston condos 3BR", "criteria_json": json.dumps({"city": "Boston", "status": "for-sale", "property_type": "Condo", "beds": "3", "sort": "price_asc"})}
    elif task == 15:
        after["inquiries"][99] = {"id": 99, "user_id": 2, "listing_id": 38, "agent_id": v.LISTINGS[38]["agent_id"], "subject": "Following up on my tour", "message": "Please confirm the date and time for this tour."}
    return after


@pytest.mark.parametrize("task", [5, 6, 7, 10, 14, 15])
def test_exact_state_change_and_noop(task):
    before = initial_state(); after = completed_state(task, before)
    j = v.Checks(task); v.state_checks(j, trajectory(task), before, after)
    assert j.result()["pass"], j.result()
    j = v.Checks(task); v.state_checks(j, trajectory(task), before, before)
    assert not j.result()["pass"]


@pytest.mark.parametrize("task", [5, 6, 7, 10, 14, 15])
@pytest.mark.parametrize("table", sorted(v.TABLES))
def test_unrelated_added_or_changed_records_are_rejected(task, table):
    before = initial_state(); after = completed_state(task, before)
    if table == "users":
        after[table][2]["phone"] = "unexpected-change"
    else:
        after[table][1000] = {"id": 1000, "user_id": 2, "listing_id": 99}
    j = v.Checks(task)
    v.state_checks(j, trajectory(task), before, after)
    assert not j.result()["pass"], (task, table, j.result())


@pytest.mark.parametrize("task,listing", [(7, 252), (14, 233)])
def test_collection_allows_saved_home_navigation_side_effect(task, listing):
    before = initial_state(); after = completed_state(task, before)
    after["saved_homes"][2] = {"id": 2, "user_id": 4, "listing_id": listing}
    j = v.Checks(task); v.state_checks(j, trajectory(task), before, after)
    assert j.result()["pass"], j.result()


def test_signup_requires_working_password_and_correct_save_owner():
    import bcrypt
    before = initial_state(); after = copy.deepcopy(before)
    user = {"id": 5, "email": "taylor.reed+test@example.com", "name": "Taylor Reed",
            "password_hash": bcrypt.hashpw(b"compass-test-1234", bcrypt.gensalt(rounds=4)).decode(),
            "phone": "", "city": "", "state": "", "budget_min": 0, "budget_max": 0,
            "beds_min": 0, "preferred_property_types": "[]", "move_timeline": "", "has_agent": 0,
            "receive_alerts": 1, "agent_id": None}
    after["users"][5] = user
    after["saved_homes"][2] = {"id": 2, "user_id": 5, "listing_id": 36}
    j = v.Checks(4); v.state_checks(j, trajectory(4), before, after)
    assert j.result()["pass"], j.result()
    for mutation in ("password", "owner", "extra_profile"):
        invalid = copy.deepcopy(after)
        if mutation == "password": invalid["users"][5]["password_hash"] = bcrypt.hashpw(b"wrong", bcrypt.gensalt(rounds=4)).decode()
        if mutation == "owner": invalid["saved_homes"][2]["user_id"] = 1
        if mutation == "extra_profile": invalid["users"][5]["budget_min"] = 1234
        j = v.Checks(4); v.state_checks(j, trajectory(4), before, invalid)
        assert not j.result()["pass"]


def test_explicit_follow_agent_and_reopen_are_required_but_direct_browsing_is_not():
    t = trajectory(12)
    for step in t["steps"]:
        step["action"] = "navigate"
    j = v.Checks(12); v.answer_checks(j, t)
    assert not j.result()["pass"]
    t = trajectory(0)
    t["steps"] = [{"url": "http://127.0.0.1:40018" + v.detail_path(99), "action": "navigate"}]
    j = v.Checks(0); v.answer_checks(j, t)
    assert j.result()["pass"]


@pytest.mark.parametrize('answer', [
    'Year built: 2016. Price per square foot: $1,861.93/sqft.',
    'Year built: 2016; 2016 sqft.',
    'Built 2016. Tour on 2026-07-12 at 11:00 AM.',
    'Built 2016. Tour on July 12, 2026.',
])
def test_year_is_not_confused_with_ratios_areas_or_tour_dates(answer):
    assert v.scalar(answer, 2016, 'year')


@pytest.mark.parametrize('answer', [
    'Year built: 2017. Tour on 2016-07-12.',
    'Year built: 2016 or 2017.',
    'Year built: 2016. Built in 2017.',
    '$2016 per sqft; construction year unknown.',
    '2016 sqft; construction year unknown.',
    'Tour on July 12, 2016; construction year unknown.',
])
def test_year_still_rejects_missing_or_contradictory_construction_year(answer):
    assert not v.scalar(answer, 2016, 'year')


@pytest.mark.parametrize('status_text,expected', [
    ('Requested the in-person tour for 2026-07-12 and confirmed it on Tours. Tour status: requested.', True),
    ('The tour is requested. I confirmed its details on Tours.', True),
    ('Status: requested, not confirmed.', True),
    ('I requested a tour. Tour status: confirmed.', False),
    ('The requested tour is confirmed.', False),
    ('Tour status: requested or confirmed.', False),
    ('The tour is not requested.', False),
])
def test_tour_status_is_distinct_from_ui_confirmation(status_text, expected):
    t = trajectory(6)
    t['final_answer'] = status_text + ' Year built: 2019.'
    j = v.Checks(6)
    v.answer_checks(j, t)
    assert j.result()['pass'] is expected, j.result()

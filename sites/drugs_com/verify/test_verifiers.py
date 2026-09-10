from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode

import pytest
from PIL import Image, ImageDraw

SITE = Path(__file__).resolve().parents[1]
VERIFY = Path(__file__).resolve().parent
PYTHON = sys.executable
ROOT = "http://localhost:40024"


def query(database, sql, params=()):
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


@pytest.fixture(scope="session")
def canonical_seed():
    process = subprocess.run([PYTHON, str(SITE / "seed_data.py")], cwd=SITE, capture_output=True, text=True, timeout=180)
    assert process.returncode == 0, process.stdout + process.stderr
    return SITE / "instance_seed" / "drugs_com.db"


@pytest.fixture
def snapshots(canonical_seed, tmp_path):
    initial = tmp_path / "initial.db"
    after = tmp_path / "after.db"
    shutil.copy2(canonical_seed, initial)
    shutil.copy2(canonical_seed, after)
    return initial, after


def drug(database, slug):
    return dict(query(database, "SELECT d.*,c.name class_name FROM drug d JOIN drug_class c ON c.id=d.drug_class_id WHERE d.slug=?", (slug,))[0])


def brands(record):
    return json.loads(record["brand_names_json"])


def conditions(database, drug_id):
    return [row[0] for row in query(database, "SELECT c.name FROM drug_condition x JOIN condition c ON c.id=x.condition_id WHERE x.drug_id=? ORDER BY c.name", (drug_id,))]


def condition_drugs(database, slug):
    return [row[0] for row in query(database, "SELECT d.generic_name FROM drug_condition x JOIN condition c ON c.id=x.condition_id JOIN drug d ON d.id=x.drug_id WHERE c.slug=? ORDER BY d.generic_name", (slug,))]


def class_drugs(database, slug):
    return [row[0] for row in query(database, "SELECT d.generic_name FROM drug d JOIN drug_class c ON c.id=d.drug_class_id WHERE c.slug=? ORDER BY d.generic_name", (slug,))]


def interaction_url(names):
    return ROOT + "/drug-interactions?" + urlencode({"drugs": names}, doseq=True)


def positive_answer(number, database):
    if number == 0:
        record = drug(database, "ibuprofen")
        return f"Ibuprofen; class {record['class_name']}; brands {', '.join(brands(record))}."
    if number == 1:
        record = drug(database, "metformin")
        return f"Metformin availability: {record['availability']}; CSA schedule: {record['csa_schedule']}."
    if number == 2:
        row = query(database, "SELECT i.severity,i.description FROM drug_interaction i JOIN drug a ON a.id=i.drug_a_id JOIN drug b ON b.id=i.drug_b_id WHERE (a.slug='ibuprofen' AND b.slug='warfarin') OR (a.slug='warfarin' AND b.slug='ibuprofen')")[0]
        return f"Ibuprofen and warfarin have a {row['severity']} interaction: {row['description']}"
    if number == 3:
        row = query(database, "SELECT d.generic_name,i.shape,i.color FROM drug_image i JOIN drug d ON d.id=i.drug_id WHERE i.imprint='I-2'")[0]
        return f"I-2; drug: {row['generic_name']}; shape: {row['shape']}; color: {row['color']}."
    if number == 4:
        values = [row[0] for row in query(database, "SELECT generic_name FROM drug WHERE lower(generic_name) LIKE 'l%' ORDER BY generic_name LIMIT 5")]
        return ", ".join(values)
    if number == 5:
        record = drug(database, "sertraline")
        return f"Sertraline brands: {', '.join(brands(record))}; conditions: {', '.join(conditions(database, record['id']))}."
    if number == 6:
        return ", ".join(condition_drugs(database, "diabetes")[:4])
    if number == 7:
        record = drug(database, "semaglutide")
        return f"Semaglutide brands: {', '.join(brands(record))}; class: {record['class_name']}."
    if number == 8:
        rows = query(database, "SELECT id,slug FROM drug WHERE slug IN ('alprazolam','oxycodone')")
        ids = {row["slug"]: row["id"] for row in rows}
        severities = [row[0] for row in query(database, "SELECT severity FROM drug_interaction WHERE (drug_a_id=? AND drug_b_id=?) OR (drug_a_id=? AND drug_b_id=?)", (ids["alprazolam"], ids["oxycodone"], ids["oxycodone"], ids["alprazolam"]))]
        severities += [row[0] for row in query(database, "SELECT severity FROM lifestyle_interaction WHERE kind='alcohol' AND drug_id IN (?,?)", (ids["alprazolam"], ids["oxycodone"]))]
        highest = max(severities, key={"minor": 1, "moderate": 2, "major": 3}.get)
        return f"For alprazolam, oxycodone, and alcohol, there are {len(severities)} interactions; the highest severity is {highest}."
    if number == 9:
        return ", ".join(class_drugs(database, "statins")[:3])
    if number == 10:
        record = drug(database, "ibuprofen")
        match = re.search(r"(\d+)-(\d+) mg every (\d+) to (\d+) hours.*?exceed (\d+) mg in (\d+) hours", record["dosage"], re.I)
        return f"Ibuprofen OTC: {match[1]}-{match[2]} mg every {match[3]}-{match[4]} hours; maximum {match[5]} mg in {match[6]} hours."
    if number == 11:
        return query(database, "SELECT title FROM news_article WHERE category='New Drug Approvals' ORDER BY published_at DESC,id DESC LIMIT 1")[0]["title"]
    if number == 12:
        record = drug(database, "atorvastatin")
        return f"Atorvastatin has a rating of {record['avg_rating']}/10 and {record['review_count']} reviews."
    if number == 13:
        rows = query(database, "SELECT d.generic_name,i.imprint FROM drug_image i JOIN drug d ON d.id=i.drug_id WHERE lower(i.shape)='oval' AND lower(i.color)='white' ORDER BY i.id LIMIT 3")
        return "; ".join(f"{row['generic_name']} — {row['imprint']}" for row in rows)
    if number == 14:
        values = [row[0] for row in query(database, "SELECT d.generic_name FROM saved_drug s JOIN drug d ON d.id=s.drug_id JOIN user u ON u.id=s.user_id WHERE u.email='alice.j@test.com' ORDER BY d.generic_name")]
        return ", ".join(values)
    if number == 15:
        record = drug(database, "lisinopril")
        return f"Lisinopril has a fetal toxicity warning: discontinue when pregnancy is detected. Availability: {record['availability']}."
    if number == 16:
        return ", ".join(class_drugs(database, "benzodiazepines")[:3])
    if number == 17:
        record = drug(database, "ciprofloxacin")
        return f"Ciprofloxacin; brands: {', '.join(brands(record))}; conditions: {', '.join(conditions(database, record['id']))}."
    if number == 18:
        return "Amoxicillin standard adult frequency: every 8 hours."
    if number == 19:
        row = query(database, "SELECT li.severity,li.description FROM lifestyle_interaction li JOIN drug d ON d.id=li.drug_id WHERE d.slug='metformin' AND li.kind='alcohol'")[0]
        return f"Metformin and alcohol have a {row['severity']} interaction: {row['description']}"
    if number == 20:
        return ", ".join(condition_drugs(database, "hypertension")[:5])
    raise AssertionError(number)


def _click(url):
    return {"url": url, "action": "click", "params": {"index": 1}}


def _input(url, text):
    return {"url": url, "action": "input", "params": {"index": 1, "text": text}}


def positive_steps(number):
    root = ROOT + "/"
    if number in {0, 5, 7, 12}:
        slug = {0: "ibuprofen", 5: "sertraline", 7: "semaglutide", 12: "atorvastatin"}[number]
        return [_click(root), {"url": ROOT + f"/{slug}", "action": "done"}]
    if number == 1:
        return [_input(root, "metformin"), _click(root), _click(ROOT + "/search?q=metformin"), {"url": ROOT + "/metformin", "action": "done"}]
    if number in {2, 8, 19}:
        names = {2: ["ibuprofen", "warfarin"], 8: ["alprazolam", "oxycodone", "alcohol"], 19: ["metformin", "alcohol"]}[number]
        steps = [_click(root)]
        steps += [_input(ROOT + "/drug-interactions", name) for name in names]
        steps += [_click(ROOT + "/drug-interactions"), {"url": interaction_url(names), "action": "done"}]
        return steps
    if number == 3:
        return [_click(root), _input(ROOT + "/pill-identifier", "I-2"), _click(ROOT + "/pill-identifier"), {"url": ROOT + "/pill-identifier?imprint=I-2", "action": "done"}]
    if number == 4:
        return [_click(root), _click(ROOT + "/drug_information.html"), {"url": ROOT + "/drug_information.html?letter=L", "action": "done"}]
    if number in {6, 20}:
        slug = "diabetes" if number == 6 else "hypertension"
        return [_click(root), _click(ROOT + "/conditions"), {"url": ROOT + f"/conditions/{slug}", "action": "done"}]
    if number in {9, 16}:
        slug = "statins" if number == 9 else "benzodiazepines"
        return [_click(root), _click(ROOT + "/drug-classes"), {"url": ROOT + f"/drug-classes/{slug}", "action": "done"}]
    if number == 10:
        return [_click(root), _click(ROOT + "/ibuprofen"), {"url": ROOT + "/ibuprofen/faq", "action": "done"}]
    if number == 11:
        return [_click(root), _click(ROOT + "/news"), {"url": ROOT + "/new-drug-approvals", "action": "done"}]
    if number == 13:
        return [_click(root), _click(ROOT + "/pill-identifier"), _click(ROOT + "/pill-identifier"), _click(ROOT + "/pill-identifier"), {"url": ROOT + "/pill-identifier?imprint=&shape=Oval&color=White", "action": "done"}]
    if number == 14:
        return [_click(root), _input(ROOT + "/login", "alice.j@test.com"), _input(ROOT + "/login", "TestPass123!"), _click(ROOT + "/login"), _click(ROOT + "/account"), {"url": ROOT + "/my-med-list", "action": "done"}]
    if number == 15:
        return [_click(root), _click(ROOT + "/lisinopril"), {"url": ROOT + "/lisinopril/warnings", "action": "done"}]
    if number == 17:
        return [_input(root, "antibiotics"), _click(root), _click(ROOT + "/search?q=antibiotics"), {"url": ROOT + "/ciprofloxacin", "action": "done"}]
    if number == 18:
        return [_click(root), _click(ROOT + "/amoxicillin"), {"url": ROOT + "/amoxicillin/dosage", "action": "done"}]
    raise AssertionError(number)


def _write_rich_screenshot(path, index):
    image = Image.new("RGB", (1024, 768), (248, 249, 252))
    draw = ImageDraw.Draw(image)
    for y in range(0, 768, 24):
        color = ((17 * index + y) % 190 + 30, (37 * index + 2 * y) % 180 + 35, (71 * index + y) % 170 + 40)
        draw.rectangle((0, y, 1024, y + 11), fill=color)
    draw.rectangle((35 + index * 3, 45, 960, 180 + index * 2), fill=(255, 255, 255), outline=(10, 70, 130), width=4)
    draw.text((60, 80), f"Browser page evidence step {index}", fill=(0, 0, 0))
    image.save(path, format="PNG")


def make_run(tmp_path, number, database, *, steps=None, answer=None, task_id=None, origin=ROOT):
    run = tmp_path / f"run-{number}-{len(list(tmp_path.iterdir()))}"
    shots = run / "screenshots"
    shots.mkdir(parents=True)
    steps = [dict(step) for step in (steps if steps is not None else positive_steps(number))]
    answer = positive_answer(number, database) if answer is None else answer
    records = []
    for index, specification in enumerate(steps):
        action = specification["action"]
        params = dict(specification.get("params", {}))
        if action == "done":
            params = {"text": answer, "success": True}
        record = {
            "step": index,
            "url": specification["url"],
            "title": f"Local benchmark page {index}",
            "thought": "test protocol fixture",
            "action": action,
            "params": params,
            "screenshot_before": f"step_{index:03d}.png",
            "screenshot_after": f"step_{index + 1:03d}.png",
        }
        if action != "done":
            record["action_result"] = {"success": True, "error": None, "is_done": False, "extracted_content": ""}
        records.append(record)
    for index in range(len(records) + 1):
        _write_rich_screenshot(shots / f"step_{index:03d}.png", index if index < len(records) else max(0, index - 1))
    trajectory = {
        "task_id": task_id or f"Drugs.com--{number}",
        "start_url": origin + "/",
        "steps": records,
        "terminated": True,
        "termination_reason": "agent_done",
        "success_self_report": True,
        "final_answer": answer,
    }
    (run / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    return run


def execute(number, run, initial, after):
    return subprocess.run([PYTHON, str(VERIFY / f"verify_{number}.py"), "--run_dir", str(run), "--initial_db", str(initial), "--after_db", str(after), "--no_llm"], cwd=VERIFY, capture_output=True, text=True, timeout=60)


def assert_fails(number, run, snapshots):
    process = execute(number, run, *snapshots)
    assert process.returncode == 1, process.stdout + process.stderr
    assert json.loads(process.stdout)["pass"] is False


@pytest.mark.parametrize("number", range(21))
def test_positive_entrypoint(number, snapshots, tmp_path):
    initial, after = snapshots
    process = execute(number, make_run(tmp_path, number, initial), initial, after)
    assert process.returncode == 0, process.stdout + process.stderr
    assert json.loads(process.stdout)["pass"] is True


@pytest.mark.parametrize("number", range(21))
def test_direct_done_shortcut_fails(number, snapshots, tmp_path):
    initial, _after = snapshots
    steps = [_click(ROOT + "/"), {"url": ROOT + "/", "action": "done"}]
    assert_fails(number, make_run(tmp_path, number, initial, steps=steps), snapshots)


@pytest.mark.parametrize("number", range(21))
def test_wrong_answer_fails(number, snapshots, tmp_path):
    initial, _after = snapshots
    assert_fails(number, make_run(tmp_path, number, initial, answer="No relevant information is available."), snapshots)


def test_wrong_task_id_fails(snapshots, tmp_path):
    assert_fails(0, make_run(tmp_path, 0, snapshots[0], task_id="Drugs.com--20"), snapshots)


@pytest.mark.parametrize("origin", ["http://localhost:9", "http://127.0.0.1:40024", "http://evil.example"])
def test_noncanonical_origin_fails(origin, snapshots, tmp_path):
    initial, _after = snapshots
    steps = positive_steps(0)
    for step in steps:
        step["url"] = step["url"].replace(ROOT, origin)
    assert_fails(0, make_run(tmp_path, 0, initial, steps=steps, origin=origin), snapshots)


def test_blank_inspect_only_evidence_fails(snapshots, tmp_path):
    run = make_run(tmp_path, 0, snapshots[0])
    trajectory_path = run / "trajectory.json"
    trajectory = json.loads(trajectory_path.read_text())
    for step in trajectory["steps"]:
        step["action"] = "done" if step is trajectory["steps"][-1] else "inspect"
    trajectory_path.write_text(json.dumps(trajectory))
    for image in (run / "screenshots").glob("*.png"):
        Image.new("RGB", (1024, 768), "white").save(image)
    assert_fails(0, run, snapshots)


def test_failed_browser_action_fails(snapshots, tmp_path):
    run = make_run(tmp_path, 1, snapshots[0])
    path = run / "trajectory.json"
    value = json.loads(path.read_text())
    value["steps"][0]["action_result"] = {"success": False, "error": "injected"}
    path.write_text(json.dumps(value))
    assert_fails(1, run, snapshots)


def test_corrupt_png_fails(snapshots, tmp_path):
    run = make_run(tmp_path, 0, snapshots[0])
    (run / "screenshots" / "step_001.png").write_bytes(b"\x89PNG\r\n\x1a\ncorrupt")
    assert_fails(0, run, snapshots)


def test_reused_visual_evidence_fails(snapshots, tmp_path):
    run = make_run(tmp_path, 0, snapshots[0])
    shutil.copy2(run / "screenshots" / "step_000.png", run / "screenshots" / "step_001.png")
    assert_fails(0, run, snapshots)


def test_database_row_mutation_fails(snapshots, tmp_path):
    initial, after = snapshots
    connection = sqlite3.connect(after)
    connection.execute("UPDATE user SET first_name='Changed' WHERE id=1")
    connection.commit()
    connection.close()
    assert_fails(0, make_run(tmp_path, 0, initial), snapshots)


def test_database_schema_mutation_fails(snapshots, tmp_path):
    initial, after = snapshots
    connection = sqlite3.connect(after)
    connection.execute("CREATE INDEX forbidden_index ON drug(generic_name)")
    connection.commit()
    connection.close()
    assert_fails(0, make_run(tmp_path, 0, initial), snapshots)


def test_substituted_initial_database_fails(snapshots, tmp_path):
    initial, after = snapshots
    connection = sqlite3.connect(initial)
    connection.execute("UPDATE drug SET warnings='forged' WHERE slug='ibuprofen'")
    connection.commit()
    connection.close()
    shutil.copy2(initial, after)
    assert_fails(0, make_run(tmp_path, 0, initial), snapshots)


def test_task14_decoy_credentials_without_input_fail(snapshots, tmp_path):
    run = make_run(tmp_path, 14, snapshots[0])
    path = run / "trajectory.json"
    value = json.loads(path.read_text())
    for step in value["steps"]:
        if step["action"] == "input":
            step["action"] = "scroll"
            step["params"] = {"note": "alice.j@test.com TestPass123!", "down": True, "pages": 1}
    path.write_text(json.dumps(value))
    assert_fails(14, run, snapshots)


def test_task14_extra_medication_fails(snapshots, tmp_path):
    answer = positive_answer(14, snapshots[0]) + ", aspirin"
    assert_fails(14, make_run(tmp_path, 14, snapshots[0], answer=answer), snapshots)


@pytest.mark.parametrize("number", [2, 3, 4, 6, 8, 9, 11, 13, 16, 19, 20])
def test_direct_final_filtered_url_without_workflow_fails(number, snapshots, tmp_path):
    initial, _after = snapshots
    destination = positive_steps(number)[-1]["url"]
    steps = [_click(ROOT + "/"), {"url": destination, "action": "done"}]
    assert_fails(number, make_run(tmp_path, number, initial, steps=steps), snapshots)


def test_correct_fact_followed_by_contradiction_fails(snapshots, tmp_path):
    record = drug(snapshots[0], "ibuprofen")
    answer = positive_answer(0, snapshots[0]) + f" However, {record['class_name']} is incorrect."
    assert_fails(0, make_run(tmp_path, 0, snapshots[0], answer=answer), snapshots)


def test_correct_list_with_invalid_extra_drug_fails(snapshots, tmp_path):
    answer = positive_answer(6, snapshots[0]) + ", lisinopril"
    assert_fails(6, make_run(tmp_path, 6, snapshots[0], answer=answer), snapshots)


def test_negated_rating_and_review_count_fail(snapshots, tmp_path):
    record = drug(snapshots[0], "atorvastatin")
    answer = f"Atorvastatin rating: not {record['avg_rating']}/10; reviews: not {record['review_count']}."
    assert_fails(12, make_run(tmp_path, 12, snapshots[0], answer=answer), snapshots)


def test_wrong_interaction_count_with_unrelated_expected_number_fails(snapshots, tmp_path):
    answer = "For alprazolam, oxycodone, and alcohol there are 99 interactions; 3 is an unrelated number; highest severity major."
    assert_fails(8, make_run(tmp_path, 8, snapshots[0], answer=answer), snapshots)


@pytest.mark.parametrize("answer_builder", [
    lambda rows: f"{rows[0]['generic_name']}, {rows[1]['generic_name']}, {rows[2]['generic_name']}; imprints: {rows[0]['imprint']}, {rows[1]['imprint']}, {rows[2]['imprint']}",
    lambda rows: f"{rows[0]['generic_name']} — {rows[1]['imprint']}; {rows[1]['generic_name']} — {rows[2]['imprint']}; {rows[2]['generic_name']} — {rows[0]['imprint']}",
])
def test_task13_unpaired_or_swapped_pairs_fail(answer_builder, snapshots, tmp_path):
    rows = query(snapshots[0], "SELECT d.generic_name,i.imprint FROM drug_image i JOIN drug d ON d.id=i.drug_id WHERE lower(i.shape)='oval' AND lower(i.color)='white' ORDER BY i.id LIMIT 3")
    assert len(rows) == 3
    assert_fails(13, make_run(tmp_path, 13, snapshots[0], answer=answer_builder(rows)), snapshots)


def test_task13_verbose_exact_pairs_pass(snapshots, tmp_path):
    rows = query(snapshots[0], "SELECT d.generic_name,i.imprint FROM drug_image i JOIN drug d ON d.id=i.drug_id WHERE lower(i.shape)='oval' AND lower(i.color)='white' ORDER BY i.id LIMIT 3")
    filler = " with an explicitly local synthetic descriptor diagram and no claim about a real pill " * 3
    answer = "; ".join(f"{row['generic_name']}{filler}imprint {row['imprint']}" for row in rows)
    process = execute(13, make_run(tmp_path, 13, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


def test_task12_natural_number_before_reviews_passes(snapshots, tmp_path):
    record = drug(snapshots[0], "atorvastatin")
    answer = f"Atorvastatin rating: {record['avg_rating']}/10; it has {record['review_count']} reviews."
    process = execute(12, make_run(tmp_path, 12, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


def test_task2_semantic_paraphrase_passes(snapshots, tmp_path):
    answer = "Ibuprofen and warfarin have a major interaction because the combination can cause gastrointestinal hemorrhage."
    process = execute(2, make_run(tmp_path, 2, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


def test_task10_shuffled_numbers_fail(snapshots, tmp_path):
    answer = "Ibuprofen numbers are 24, 1200, 6, 4, 400, and 200 mg hours."
    assert_fails(10, make_run(tmp_path, 10, snapshots[0], answer=answer), snapshots)


def test_task18_negated_frequency_fails(snapshots, tmp_path):
    answer = "Amoxicillin is not taken every 8 hours for standard adult infections."
    assert_fails(18, make_run(tmp_path, 18, snapshots[0], answer=answer), snapshots)


def test_duplicate_query_values_fail(snapshots, tmp_path):
    steps = positive_steps(1)
    steps[2]["url"] = ROOT + "/search?q=wrong&q=metformin"
    assert_fails(1, make_run(tmp_path, 1, snapshots[0], steps=steps), snapshots)


def test_global_answer_retraction_fails(snapshots, tmp_path):
    answer = positive_answer(0, snapshots[0]) + " Everything above is false."
    assert_fails(0, make_run(tmp_path, 0, snapshots[0], answer=answer), snapshots)


def test_not_only_is_not_treated_as_negation(snapshots, tmp_path):
    record = drug(snapshots[0], "ibuprofen")
    answer = f"Ibuprofen is not only in the {record['class_name']} class; its brands are {', '.join(brands(record))}."
    process = execute(0, make_run(tmp_path, 0, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


@pytest.mark.parametrize("number,answer", [
    (2, "Ibuprofen and warfarin can cause gastrointestinal bleeding. Their interaction severity is minor. Major is merely a category label."),
    (8, "For alprazolam, oxycodone, and alcohol, there are 3 interactions; the highest severity is minor. Major is merely a category label."),
])
def test_conflicting_severity_relations_fail(number, answer, snapshots, tmp_path):
    assert_fails(number, make_run(tmp_path, number, snapshots[0], answer=answer), snapshots)


@pytest.mark.parametrize("answer", [
    "Atorvastatin has a rating that is not 7.0/10 and 4 reviews.",
    "Atorvastatin has a rating of 7.0/10, but its actual rating is 1/10; it has 4 reviews.",
])
def test_rating_negation_or_competition_fails(answer, snapshots, tmp_path):
    assert_fails(12, make_run(tmp_path, 12, snapshots[0], answer=answer), snapshots)


def test_competing_standard_frequency_fails(snapshots, tmp_path):
    answer = "Amoxicillin standard adult dosing is every 12 hours, although the page also says every 8 hours."
    assert_fails(18, make_run(tmp_path, 18, snapshots[0], answer=answer), snapshots)


def test_indirect_competing_interaction_total_fails(snapshots, tmp_path):
    answer = "For alprazolam, oxycodone, and alcohol there are 3 interactions, but the actual total is 99; highest severity is major."
    assert_fails(8, make_run(tmp_path, 8, snapshots[0], answer=answer), snapshots)


def test_do_not_exceed_dosage_wording_passes(snapshots, tmp_path):
    answer = "Ibuprofen OTC: 200-400 mg every 4-6 hours; do not exceed 1200 mg in 24 hours."
    process = execute(10, make_run(tmp_path, 10, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


def test_task14_password_requires_exact_case_and_punctuation(snapshots, tmp_path):
    run = make_run(tmp_path, 14, snapshots[0])
    path = run / "trajectory.json"
    value = json.loads(path.read_text())
    password_step = next(step for step in value["steps"] if step.get("params", {}).get("text") == "TestPass123!")
    password_step["params"]["text"] = "testpass123"
    path.write_text(json.dumps(value))
    assert_fails(14, run, snapshots)


@pytest.mark.parametrize("number,step_index,extra", [
    (1, 2, "&availability=Rx"),
    (3, 3, "&color=White"),
    (13, 4, "&imprint=I-2"),
    (17, 2, "&availability=Rx"),
])
def test_unrequested_query_state_fails(number, step_index, extra, snapshots, tmp_path):
    steps = positive_steps(number)
    steps[step_index]["url"] += extra
    assert_fails(number, make_run(tmp_path, number, snapshots[0], steps=steps), snapshots)


def test_deep_link_start_url_fails(snapshots, tmp_path):
    steps = [_click(ROOT + "/ibuprofen"), {"url": ROOT + "/ibuprofen/faq", "action": "done"}]
    run = make_run(tmp_path, 10, snapshots[0], steps=steps, origin=ROOT)
    trajectory_path = run / "trajectory.json"
    trajectory = json.loads(trajectory_path.read_text())
    trajectory["start_url"] = ROOT + "/ibuprofen"
    trajectory_path.write_text(json.dumps(trajectory))
    assert_fails(10, run, snapshots)


@pytest.mark.parametrize("answer", [
    "For alprazolam, oxycodone, and alcohol, there are 3 interactions, but that count is false; the highest severity is major.",
    "For alprazolam, oxycodone, and alcohol, there are 3 interactions; the highest severity is major, which is false.",
])
def test_task8_retracted_count_or_severity_fails(answer, snapshots, tmp_path):
    assert_fails(8, make_run(tmp_path, 8, snapshots[0], answer=answer), snapshots)


def test_task8_reverse_natural_severity_relation_passes(snapshots, tmp_path):
    answer = "For alprazolam, oxycodone, and alcohol, there are 3 interactions; major is the most severe."
    process = execute(8, make_run(tmp_path, 8, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


@pytest.mark.parametrize("number,answer", [
    (0, "Ibuprofen; brands: Nonsteroidal anti-inflammatory drugs; class: Advil, Motrin, Nuprin."),
    (5, "Sertraline; brands: Anxiety, Depression, Obsessive-Compulsive Disorder (OCD), Panic Disorder, Post-Traumatic Stress Disorder (PTSD), Premenstrual Dysphoric Disorder (PMDD), Social Anxiety Disorder; conditions: Zoloft."),
    (17, "Ciprofloxacin; brands: Bacterial Infections, Pneumonia, Urinary Tract Infection (UTI); conditions: Cipro."),
])
def test_values_swapped_between_requested_fields_fail(number, answer, snapshots, tmp_path):
    assert_fails(number, make_run(tmp_path, number, snapshots[0], answer=answer), snapshots)


@pytest.mark.parametrize("number,suffix", [
    (4, ", inventedazole"),
    (13, "; inventedazole — XX 999"),
    (14, ", inventedazole"),
])
def test_invented_closed_world_results_fail(number, suffix, snapshots, tmp_path):
    answer = positive_answer(number, snapshots[0]) + suffix
    assert_fails(number, make_run(tmp_path, number, snapshots[0], answer=answer), snapshots)


def test_competing_dosage_claims_fail(snapshots, tmp_path):
    answer = "Ibuprofen OTC: 200-400 mg every 4-6 hours; maximum 1200 mg in 24 hours. The actual dose is 800 mg every 2 hours, maximum 5000 mg in 24 hours."
    assert_fails(10, make_run(tmp_path, 10, snapshots[0], answer=answer), snapshots)


def test_competing_pill_shape_or_color_fails(snapshots, tmp_path):
    answer = positive_answer(3, snapshots[0]) + " It is also square, triangular, blue, and neon green."
    assert_fails(3, make_run(tmp_path, 3, snapshots[0], answer=answer), snapshots)


def test_input_on_unrelated_page_fails(snapshots, tmp_path):
    steps = positive_steps(1)
    steps[0]["url"] = ROOT + "/pill-identifier"
    assert_fails(1, make_run(tmp_path, 1, snapshots[0], steps=steps), snapshots)


def test_unrequested_query_on_path_only_destination_fails(snapshots, tmp_path):
    steps = positive_steps(10)
    steps[-1]["url"] += "?unexpected=1"
    assert_fails(10, make_run(tmp_path, 10, snapshots[0], steps=steps), snapshots)


def test_same_pixels_for_successful_same_page_input_are_allowed(snapshots, tmp_path):
    run = make_run(tmp_path, 2, snapshots[0])
    shutil.copy2(run / "screenshots" / "step_001.png", run / "screenshots" / "step_002.png")
    process = execute(2, run, *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


def test_initial_wal_content_is_inside_snapshot_boundary(canonical_seed, snapshots, tmp_path):
    wal_database = tmp_path / "wal-initial.db"
    shutil.copy2(canonical_seed, wal_database)
    connection = sqlite3.connect(wal_database)
    try:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
        connection.execute("UPDATE user SET username='wal-mutated' WHERE id=1")
        connection.commit()
        assert Path(str(wal_database) + "-wal").is_file()
        run = make_run(tmp_path, 0, snapshots[0])
        process = execute(0, run, wal_database, snapshots[1])
        assert process.returncode == 1, process.stdout + process.stderr
        assert json.loads(process.stdout)["pass"] is False
    finally:
        connection.close()


def test_correct_first_then_swapped_field_claims_fail(snapshots, tmp_path):
    record = drug(snapshots[0], "ibuprofen")
    answer = (
        f"Ibuprofen; brands: {', '.join(brands(record))}; class: {record['class_name']}. "
        f"Brands: {record['class_name']}; class: {brands(record)[0]}."
    )
    assert_fails(0, make_run(tmp_path, 0, snapshots[0], answer=answer), snapshots)


def test_correct_first_then_conflicting_availability_fails(snapshots, tmp_path):
    answer = "Metformin availability: Rx; CSA schedule: Not a controlled drug. Actual availability: OTC; actual CSA schedule: II."
    assert_fails(1, make_run(tmp_path, 1, snapshots[0], answer=answer), snapshots)


def test_natural_combined_class_and_brand_sentence_passes(snapshots, tmp_path):
    record = drug(snapshots[0], "ibuprofen")
    answer = f"Ibuprofen class {record['class_name']} and brands {', '.join(brands(record))}."
    process = execute(0, make_run(tmp_path, 0, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


@pytest.mark.parametrize("number,answer", [
    (8, "For alprazolam, oxycodone, and alcohol, there are 3 interactions; the highest severity is major. In fact there are ninety-nine interactions, and the actual severity is minor."),
    (10, "Ibuprofen OTC: 200-400 mg every 4-6 hours; maximum 1200 mg in 24 hours. The actual dose is eight hundred mg every two hours."),
    (12, "Atorvastatin rating: 7.0/10; 4 reviews. Its actual rating is one out of ten and it actually has ninety-nine reviews."),
    (18, "Amoxicillin standard adult frequency: every 8 hours. The actual standard frequency is every twelve hours."),
])
def test_number_word_competing_claims_fail(number, answer, snapshots, tmp_path):
    assert_fails(number, make_run(tmp_path, number, snapshots[0], answer=answer), snapshots)


def test_task8_number_word_count_passes(snapshots, tmp_path):
    answer = "For alprazolam, oxycodone, and alcohol, there are three interactions; major is the most severe."
    process = execute(8, make_run(tmp_path, 8, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


def test_competing_actual_main_risk_fails(snapshots, tmp_path):
    answer = "Ibuprofen and warfarin have a major interaction because the combination can cause gastrointestinal hemorrhage. The actual main risk is kidney failure."
    assert_fails(2, make_run(tmp_path, 2, snapshots[0], answer=answer), snapshots)


def test_digestive_tract_blood_loss_paraphrase_passes(snapshots, tmp_path):
    answer = "Ibuprofen and warfarin have a major interaction because they can increase internal digestive-tract blood loss."
    process = execute(2, make_run(tmp_path, 2, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


def test_pregnancy_warning_paraphrase_passes(snapshots, tmp_path):
    answer = "Lisinopril can harm or kill the unborn baby; stop taking it as soon as pregnancy is recognized. Availability: Rx."
    process = execute(15, make_run(tmp_path, 15, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


@pytest.mark.parametrize("number", [1, 17])
def test_search_and_detail_workflow_order_is_enforced(number, snapshots, tmp_path):
    if number == 1:
        query_url, detail_url, text = ROOT + "/search?q=metformin", ROOT + "/metformin", "metformin"
    else:
        query_url, detail_url, text = ROOT + "/search?q=antibiotics", ROOT + "/ciprofloxacin", "antibiotics"
    steps = [
        _click(ROOT + "/"), _click(query_url), _click(detail_url),
        _input(ROOT + "/", text), _click(ROOT + "/"), {"url": query_url, "action": "done"},
    ]
    assert_fails(number, make_run(tmp_path, number, snapshots[0], steps=steps), snapshots)


def test_login_and_med_list_workflow_order_is_enforced(snapshots, tmp_path):
    steps = [
        _click(ROOT + "/"), _click(ROOT + "/account"), _input(ROOT + "/login", "alice.j@test.com"),
        _input(ROOT + "/login", "TestPass123!"), _click(ROOT + "/login"), {"url": ROOT + "/account", "action": "done"},
    ]
    assert_fails(14, make_run(tmp_path, 14, snapshots[0], steps=steps), snapshots)


@pytest.mark.parametrize("number,answer", [
    (1, "Metformin availability: Rx; CSA schedule: Not a controlled drug and Schedule II."),
    (8, "For alprazolam, oxycodone, and alcohol, there are 3 interactions; the highest severity is major. The actual total is a dozen and the actual severity is catastrophic."),
    (10, "Ibuprofen OTC: 200-400 mg every 4-6 hours; maximum 1200 mg in 24 hours. In fact, there is no maximum in 24 hours."),
    (12, "Atorvastatin rating: 7.0/10; 4 reviews. The actual rating is not seven out of ten, and there are no reviews."),
    (15, "Lisinopril can harm or kill the unborn baby; stop taking it when pregnancy is recognized. Availability: Rx. It is actually safe to continue throughout pregnancy."),
    (18, "Amoxicillin standard adult frequency: every 8 hours. The actual standard frequency is hourly."),
])
def test_explicit_non_digit_and_status_contradictions_fail(number, answer, snapshots, tmp_path):
    assert_fails(number, make_run(tmp_path, number, snapshots[0], answer=answer), snapshots)


def test_all_interaction_risk_concepts_require_entity_binding(snapshots, tmp_path):
    answer = "Ibuprofen and warfarin have a major interaction causing brain bleeding. Gastrointestinal is only a navigation heading."
    assert_fails(2, make_run(tmp_path, 2, snapshots[0], answer=answer), snapshots)


def test_nsaid_alias_cannot_negate_expanded_class(snapshots, tmp_path):
    answer = "Ibuprofen; class: NSAID, not Nonsteroidal anti-inflammatory drugs; brands: Advil, Motrin, Nuprin."
    assert_fails(0, make_run(tmp_path, 0, snapshots[0], answer=answer), snapshots)


@pytest.mark.parametrize("number", [4, 6, 9, 14, 16, 20])
def test_numbered_known_item_lists_pass(number, snapshots, tmp_path):
    items = [item.strip() for item in positive_answer(number, snapshots[0]).split(",")]
    answer = "\n".join(f"{index}. {item}" for index, item in enumerate(items, 1))
    process = execute(number, make_run(tmp_path, number, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


def test_numbered_pill_pairs_pass(snapshots, tmp_path):
    items = positive_answer(13, snapshots[0]).split("; ")
    answer = "; ".join(f"{index}. {item}" for index, item in enumerate(items, 1))
    process = execute(13, make_run(tmp_path, 13, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


def test_unlabelled_clear_status_sentence_passes(snapshots, tmp_path):
    answer = "Metformin is prescription-only and is not a controlled drug."
    process = execute(1, make_run(tmp_path, 1, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


def test_adverb_separated_negation_fails(snapshots, tmp_path):
    answer = "Ibuprofen; class: NSAID is currently not class; brands: Advil, Motrin, Nuprin are currently not brands."
    assert_fails(0, make_run(tmp_path, 0, snapshots[0], answer=answer), snapshots)


def test_secondary_interaction_risk_heading_with_entity_fails(snapshots, tmp_path):
    answer = "Ibuprofen and warfarin have a major interaction causing brain bleeding. For ibuprofen, gastrointestinal is only a navigation heading."
    assert_fails(2, make_run(tmp_path, 2, snapshots[0], answer=answer), snapshots)


@pytest.mark.parametrize("number,answer", [
    (8, "For alprazolam, oxycodone, and alcohol, there are 3 interactions; the highest severity is major. The actual total is 99.5."),
    (10, "Ibuprofen OTC: 200-400 mg every 4-6 hours; maximum 1200 mg in 24 hours. The actual dose is 800.5 mg every 2.5 hours, maximum 5000.5 mg in 24 hours."),
    (12, "Atorvastatin rating: 7.0/10; 4 reviews. The actual review count is 99."),
    (18, "Amoxicillin standard adult frequency: every 8 hours. The actual standard adult frequency is every 12.5 hours."),
])
def test_decimal_and_review_count_competitors_fail(number, answer, snapshots, tmp_path):
    assert_fails(number, make_run(tmp_path, number, snapshots[0], answer=answer), snapshots)


def test_latest_article_title_requires_latest_relation(snapshots, tmp_path):
    expected = positive_answer(11, snapshots[0])
    answer = f'The most recent article is "Completely Invented Approval." The page also lists "{expected}".'
    assert_fails(11, make_run(tmp_path, 11, snapshots[0], answer=answer), snapshots)


@pytest.mark.parametrize("number,answer", [
    (1, "Metformin availability: Rx; CSA schedule: Not a controlled drug. Metformin is OTC."),
    (15, "Lisinopril can harm or kill the unborn baby; stop taking it as soon as pregnancy is recognized. Availability: Rx. Lisinopril is OTC."),
])
def test_unlabelled_availability_competitor_fails(number, answer, snapshots, tmp_path):
    assert_fails(number, make_run(tmp_path, number, snapshots[0], answer=answer), snapshots)


def test_natural_according_to_page_field_answer_passes(snapshots, tmp_path):
    record = drug(snapshots[0], "ibuprofen")
    answer = f"Ibuprofen is in the {record['class_name']} class. According to the page, the brand names are {', '.join(brands(record))}."
    process = execute(0, make_run(tmp_path, 0, snapshots[0], answer=answer), *snapshots)
    assert process.returncode == 0, process.stdout + process.stderr


def test_failure_evidence_does_not_disclose_expected_answer(snapshots, tmp_path):
    run = make_run(tmp_path, 0, snapshots[0], answer="wrong")
    process = execute(0, run, *snapshots)
    assert process.returncode == 1
    assert "Advil" not in process.stdout
    assert "Motrin" not in process.stdout

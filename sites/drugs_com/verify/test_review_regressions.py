"""Synthetic regression controls; not browser completion evidence."""
import json
import shutil
import sqlite3
import subprocess

import pytest

import verify_lib as v
from test_verifiers import (PYTHON, VERIFY, ROOT, canonical_seed, snapshots,
                            execute, make_run, positive_answer, positive_steps)


@pytest.mark.parametrize('number', range(21))
def test_natural_answers_for_every_task(number, snapshots, tmp_path):
    initial = v.Snapshot(str(snapshots[0]))
    try:
        valid, prose = v.structured_answer_contract(number, positive_answer(number, snapshots[0]), initial)
        assert valid
    finally:
        initial.close()
    run = make_run(tmp_path, number, snapshots[0], answer=prose)
    result = execute(number, run, *snapshots)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize('number,fields', [
    (2, {'risks': ['serious bleeding, particularly gastrointestinal bleeding']}),
    (15, {'pregnancy_warnings': ['When pregnancy is detected, discontinue lisinopril as soon as possible.', 'Drugs that act directly on the renin-angiotensin system can cause injury and death to the developing fetus.']}),
    (19, {'risks': ['lactic acidosis', 'hypoglycemia or hyperglycemia']}),
])
def test_visible_page_quotations_are_accepted(number, fields, snapshots, tmp_path):
    value = json.loads(positive_answer(number, snapshots[0]))
    value.update(fields)
    result = execute(number, make_run(tmp_path, number, snapshots[0], answer=json.dumps(value)), *snapshots)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize('number', [1, 14, 17])
def test_reading_after_arrival_is_allowed(number, snapshots, tmp_path):
    steps = positive_steps(number)
    steps.insert(-1, dict(url=steps[-1]['url'], action='scroll', params={'direction': 'down'}))
    result = execute(number, make_run(tmp_path, number, snapshots[0], steps=steps), *snapshots)
    assert result.returncode == 0, result.stdout


def test_a_z_letter_to_drug_is_a_valid_path(snapshots, tmp_path):
    steps = [dict(url=ROOT+'/', action='click'), dict(url=ROOT+'/drug_information.html', action='click'),
             dict(url=ROOT+'/drug_information.html?letter=I', action='click'), dict(url=ROOT+'/ibuprofen', action='done')]
    result = execute(0, make_run(tmp_path, 0, snapshots[0], steps=steps), *snapshots)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize('origin,good', [('http://localhost:44826', True), ('http://evil.example', False), ('http://localhost:44825', False)])
def test_runtime_origin_is_bound_to_trusted_configuration(origin, good):
    judge = v.Judge('Drugs.com--0')
    trajectory = dict(start_url=origin+'/', steps=[{'url':origin+'/'}, {'url':origin+'/ibuprofen.html#uses'}])
    v.validate_urls(judge, trajectory, 'http://localhost:44826')
    assert judge.ok is good


@pytest.mark.parametrize('number,answer', [
    (0, '| Drug | Class | Brands |\n|---|---|---|\n| Ibuprofen | Nonsteroidal anti-inflammatory drugs | Advil, Motrin, Nuprin |'),
    (0, 'Ibuprofen\n- Class: Nonsteroidal anti-inflammatory drugs\n- Brands: Advil, Motrin, Nuprin'),
    (0, 'Ibuprofen is a nonsteroidal anti-inflammatory drug (NSAID), sold as Advil, Motrin, and Nuprin.'),
    (2, 'The interaction between ibuprofen and warfarin is Major. It increases the risk of gastrointestinal bleeding.'),
    (12, '| Drug | Rating | Reviews |\n|---|---|---|\n| Atorvastatin | 7/10 | 4 |'),
    (15, 'When pregnancy is detected, discontinue lisinopril as soon as possible. Drugs that act directly on the renin-angiotensin system can cause injury and death to the developing fetus. Lisinopril is prescription-only (Rx).'),
])
def test_equivalent_layouts_and_quotations(number, answer, snapshots, tmp_path):
    result = execute(number, make_run(tmp_path, number, snapshots[0], answer=answer), *snapshots)
    assert result.returncode == 0, result.stdout


def test_implicit_saved_pair_wins_over_live_container(snapshots, tmp_path):
    run = make_run(tmp_path, 0, snapshots[0])
    for source, name in zip(snapshots, ['initial.db', 'after.db']):
        shutil.copy2(source, run / name)
    with sqlite3.connect(run/'after.db') as connection:
        connection.execute('DELETE FROM saved_drug WHERE id=(SELECT min(id) FROM saved_drug)')
    result = subprocess.run([PYTHON, str(VERIFY/'verify_0.py'), '--run_dir', str(run), '--container', 'must-not-contact-live-container'], capture_output=True, text=True)
    assert result.returncode == 1
    assert '[FAIL] rows_unchanged' in json.loads(result.stdout)['evidence']


def test_incomplete_saved_pair_never_falls_back(snapshots, tmp_path, monkeypatch):
    run = make_run(tmp_path, 0, snapshots[0])
    shutil.copy2(snapshots[0], run/'initial.db')
    def forbidden(*args):
        pytest.fail('live container must not replace a partial saved pair')
    monkeypatch.setattr(v, 'fetch_db', forbidden)
    assert not v.grade(0, v.Args(run, '', '', 'unused', live_db=True))['pass']

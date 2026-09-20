#!/usr/bin/env python3
"""Self-check for the arXiv grading contract (all 43 verifiers).

Synthesizes run packages from the fixtures below (agent_demo trajectory schema)
and runs every verifier against four cells per task:

  genuine   valid synthetic run with correct navigation + answer   -> PASS
  noop      homepage-only trajectory with an empty answer           -> FAIL
  wrong     valid navigation with a corrupted answer                -> FAIL
  shortcut  correct answer but homepage-only navigation            -> FAIL

plus a set of run-package gate probes (missing trajectory, missing screenshots,
task-id mismatch, non-loopback start_url, undersized screenshot).

These are test fixtures, not agent trajectories. Ground truth below mirrors
the seeded data the live site serves. Run from agent_demo/ (simpleArgParser
and pytest must be importable):

    uv run pytest ../sites/arxiv/verify/test_verifiers.py -q
"""
import binascii
import json
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

VERIFY_DIR = Path(__file__).resolve().parent
BASE = "http://localhost:41003"


def _resolve_python():
    """Pick an interpreter that can import simpleArgParser.

    `uv run pytest` may execute under a system python that lacks the agent_demo
    dependencies; the verifiers need the agent_demo virtualenv.
    """
    candidates = [
        Path(os.environ["ARXIV_VERIFY_PYTHON"]) if os.environ.get("ARXIV_VERIFY_PYTHON") else None,
        VERIFY_DIR.parents[2] / "agent_demo" / ".venv" / "bin" / "python",
        VERIFY_DIR.parents[2] / "agent_demo" / ".venv" / "bin" / "python3",
        Path(sys.executable),
    ]
    for cand in candidates:
        if cand is None:
            continue
        try:
            r = subprocess.run([str(cand), "-c", "import simpleArgParser"],
                                capture_output=True, timeout=60)
            if r.returncode == 0:
                return str(cand)
        except Exception:
            continue
    pytest.skip("no python interpreter with simpleArgParser available")


PYTHON = _resolve_python()

# Per-task fixtures: navigation URL suffixes, a correct final answer, and a
# guaranteed-wrong final answer for the wrong-answer cell.
FIXTURES = {
    0: {
        "urls": ["/search?query=quantum+computing"],
        "answer": "The latest quantum computing preprints include 'Error-corrected quantum "
                  "computing with neutral atom arrays' (arXiv:2604.40001, submitted 2026-04-28) "
                  "by Preskill, Aaronson, Arute and Nielsen, and 'Variational quantum "
                  "eigensolvers for strongly correlated electrons' (arXiv:2604.40002).",
        "wrong": "The latest preprint is 'A Study of Tea Leaf Motion' by unknown authors.",
    },
    1: {
        "urls": ["/search?query=quantum+computing&last_days=2"],
        "answer": "Within the last two days the search returns 10 papers, including "
                  "'Error-corrected quantum computing with neutral atom arrays' (arXiv:2604.40001) "
                  "and 'Variational quantum eigensolvers for strongly correlated electrons' "
                  "(arXiv:2604.40002).",
        "wrong": "No papers were found for this query.",
    },
    2: {
        "urls": ["/list/cs.CL/new", "/abs/2604.08527"],
        "answer": "One of the most recent cs.CL papers is 'Demystifying OPD: Length Inflation and "
                  "Stabilization Strategies for Large Language Models' (arXiv:2604.08527). "
                  "Abstract: On-policy distillation (OPD) trains student models under their own "
                  "induced distribution while leveraging supervision from stronger teachers.",
        "wrong": "The most recent cs.CL paper is 'Random Thoughts on Clouds'.",
    },
    3: {
        "urls": ["/list/math.AT/new", "/abs/2604.08166"],
        "answer": "The most recent Algebraic Topology paper under Mathematics is 'L-fuzzy simplicial "
                  "homology' (arXiv:2604.08166, submitted 2026-04-11) by Daniel Zhang and Fatima "
                  "Bianchi. Abstract: Simplicial homology is a classical tool that assigns a "
                  "sequence of modules to a simplicial complex, providing invariants for the "
                  "study of its topological properties.",
        "wrong": "The paper is 'Coffee Algebra: A Survey' by A. Nonym.",
    },
    4: {
        "urls": ["/list/astro-ph.GA/new"],
        "answer": "In Astrophysics of Galaxies the most recent announce day is 2026-04-28 with "
                  "1 paper announced: 'The stellar mass function of galaxies at z > 6' "
                  "(arXiv:2604.69678).",
        "wrong": "12 papers were announced in the last day.",
    },
    5: {
        "urls": ["/search?query=quantum+computing&category=quant-ph"],
        "answer": "Searching 'quantum computing' in the Quantum Physics category returns 48 "
                  "results in total; searching all archives returns 207 results.",
        "wrong": "There are 10 results in quant-ph and 12 in all archives.",
    },
    6: {
        "urls": ["/search?query=On+the+Sentence+Embeddings&searchtype=title", "/abs/2011.05864"],
        "answer": "The paper 'On the Sentence Embeddings from Pre-trained Language Models' "
                  "(arXiv:2011.05864) has 5 figures and 7 tables (Comments: EMNLP 2020, "
                  "5 figures, 7 tables).",
        "wrong": "It has 9 figures and 12 tables.",
    },
    7: {
        "urls": ["/search?query=machine+learning&category=cs&sort=date"],
        "answer": "The most recent machine-learning paper in the Computer Science category is "
                  "'Scaling laws for foundation models of machine learning' (arXiv:2604.34272, "
                  "cs.LG, submitted 2026-04-28).",
        "wrong": "The most recent paper is 'Steam Engine Dynamics'.",
    },
    8: {
        "urls": ["/news"],
        "answer": "The latest news on arXiv (2026-04-05) is 'arXiv reaches 3 million submissions' "
                  "— more than three million scholarly articles have been submitted since 1991.",
        "wrong": "The latest news is about a new coffee machine in the break room.",
    },
    9: {
        "urls": ["/search?query=neural+networks&last_days=7&sort=date"],
        "answer": "The latest neural-networks paper submitted within the last week is "
                  "'Convolutional neural networks for low-light image denoising' "
                  "(arXiv:2604.60001, submitted 2026-04-28).",
        "wrong": "The latest paper is 'Octopus Behavior Patterns'.",
    },
    10: {
        "urls": ["/help/withdraw"],
        "answer": "If the submission has not yet been announced, you can withdraw it directly "
                  "from your user page without leaving any public trace: locate the pending "
                  "submission in your queue and click the Delete button before the announcement "
                  "deadline.",
        "wrong": "You should send an email to the moderators and wait for a reply.",
    },
    11: {
        "urls": ["/help/non-english"],
        "answer": "Yes — for non-English submissions authors must provide a multi-language "
                  "abstract; the multiple abstracts are separated by -- (two hyphens) on a "
                  "line by itself.",
        "wrong": "No, English-only abstracts are fine and no separator is needed.",
    },
    12: {
        "urls": ["/help/store", "/store", "/store/arxiv-logo-shirt"],
        "answer": "The arXiv Logo Shirt is available in 4 styles: Unisex short sleeve, Women's "
                  "short sleeve, Unisex long sleeve, Women's long sleeve.",
        "wrong": "There are 9 styles of the arXiv Logo Shirt.",
    },
    13: {
        "urls": ["/search?query=SimCSE&searchtype=title"],
        "answer": "There are 7 articles with 'SimCSE' in the title.",
        "wrong": "There are 3 articles with SimCSE in the title.",
    },
    14: {
        "urls": ["/search?query=SimCSE&year=2023&month=10"],
        "answer": "5 articles have 'SimCSE' in the article and are originally announced in "
                  "October 2023, including 'SimCSE Revisited: Unified Contrastive Learning for "
                  "Sentence Representations' (arXiv:2310.15432).",
        "wrong": "There are 2 such articles.",
    },
    15: {
        "urls": ["/search?query=Chinese+Benchmark&year=2023&month=12"],
        "answer": "9 papers were announced in December 2023 for the Chinese Benchmark search; "
                  "6 papers mention being accepted for AAAI 2024.",
        "wrong": "9 papers mention being accepted for AAAI 2024.",
    },
    16: {
        "urls": ["/search?query=gravitational+waves&last_days=7"],
        "answer": "The latest gravitational-waves paper this week is 'Detection of continuous "
                  "gravitational waves from a spinning neutron star' (arXiv:2604.43728, uploaded "
                  "2026-04-28). Main findings: a continuous 240 Hz signal from a spinning "
                  "neutron star, a mass estimate of 1.4 solar masses, and evidence for an "
                  "accretion-powered source.",
        "wrong": "The latest paper is 'Ocean Wave Dynamics' describing tidal patterns.",
    },
    17: {
        "urls": ["/search?query=GPT-4+Technical+Report&searchtype=title", "/abs/2303.08774"],
        "answer": "The GPT-4 Technical Report (arXiv:2303.08774) submission history shows v3 was "
                  "submitted on 2023-03-27.",
        "wrong": "v3 was submitted on 2023-05-01.",
    },
    18: {
        "urls": ["/abs/2004.04906"],
        "answer": "'Dense Passage Retrieval for Open-Domain Question Answering' "
                  "(arXiv:2004.04906) contains 9 formulas (Comments: EMNLP 2020, 9 formulas, "
                  "6 tables, 3 figures). The loss function is the in-batch negative "
                  "log-likelihood over the similarity sim(q, p) between query and passage "
                  "representations.",
        "wrong": "It contains 12 formulas and the loss function is the mean squared error.",
    },
    19: {
        "urls": ["/about", "/external/cornell"],
        "answer": "ArXiv is maintained and managed by Cornell University; per the Cornell page, "
                  "there are currently 15,735 undergraduate students.",
        "wrong": "ArXiv is managed by MIT, which has 11,000 undergraduates.",
    },
    20: {
        "urls": ["/list/stat.ML/new", "/abs/2604.50001"],
        "answer": "The latest machine-learning paper in the Statistics section is 'Stability "
                  "selection via cross-fitted machine learning' (arXiv:2604.50001, stat.ML, "
                  "2026-04-28) by Wasserman, Efron and Tibshirani. Abstract: We develop a "
                  "stability selection procedure that leverages cross-fitted machine learning "
                  "predictions to obtain valid p-values in the presence of high-dimensional "
                  "nuisance components.",
        "wrong": "The latest paper is 'Farming Yields with ML' about crop prediction.",
    },
    21: {
        "urls": ["/search?query=neural+networks+for+image+processing&category=cs&last_days=7"],
        "answer": "The search for 'neural networks for image processing' in the Computer Science "
                  "category returns 14 results submitted in the last week.",
        "wrong": "There are 8 results in the last week.",
    },
    22: {
        "urls": ["/help/subscribe"],
        "answer": "To subscribe to daily listing emails: create an arXiv account and log in, "
                  "open Alerts from the user menu, enter the category code (e.g. cs.AI), select "
                  "daily as the frequency, and click Subscribe.",
        "wrong": "You should subscribe by sending an email to the mailing list.",
    },
    23: {
        "urls": ["/search?query=autonomous+vehicles&category=eess&date_from=2026-04-27&date_to=2026-04-27"],
        "answer": "2 articles with the keyword 'autonomous vehicles' were published in the "
                  "Electrical Engineering and Systems Science section yesterday (2026-04-27): "
                  "'Sensor fusion for autonomous vehicles with LiDAR and vision' and 'Model "
                  "predictive trajectory planning for autonomous vehicles at unsignalised "
                  "intersections'.",
        "wrong": "There are 5 such articles.",
    },
    24: {
        "urls": ["/search?query=graph+neural+networks&sort=date", "/abs/2604.79721"],
        "answer": "The most recent paper related to graph neural networks is 'Graph neural "
                  "networks for protein interaction prediction' (arXiv:2604.79721, cs.LG, "
                  "submitted 2026-04-24) by Desai, Priya and Mori, Kenji. The mirror does not "
                  "display author affiliations.",
        "wrong": "The most recent paper is 'Blockchain Fundamentals'.",
    },
    25: {
        "urls": ["/store"],
        "answer": "The arXiv store offers 7 different types of merchandise: arXiv Logo Shirt, "
                  "arXiv Forever Short Sleeve, arXiv Ceramic Mug, arXiv Canvas Tote Bag, arXiv "
                  "Sticker Pack, arXiv Hoodie, arXiv Dot Grid Notebook.",
        "wrong": "There are 3 types of merchandise.",
    },
    26: {
        "urls": ["/search?query=climate+change+modeling&category=astro-ph.EP&last_days=7"],
        "answer": "5 papers related to climate change modeling were published in the "
                  "astro-ph.EP category in the last week.",
        "wrong": "2 papers were published in the last week.",
    },
    27: {
        "urls": ["/category/econ", "/category_taxonomy"],
        "answer": "Economics (econ) includes three subcategories: Econometrics (econ.EM), "
                  "General Economics (econ.GN), and Theoretical Economics (econ.TH).",
        "wrong": "Economics includes Microeconomics (econ.MI) and Macroeconomics (econ.MA).",
    },
    28: {
        "urls": ["/search?query=Poly+encoder&searchtype=title", "/search?query=Poly+encoder"],
        "answer": "A title search for 'Poly encoder' returns no exact matches; the all-fields "
                  "search finds 'Poly-encoders: Architectures and Pre-training Strategies for "
                  "Fast and Accurate Multi-sentence Scoring' (arXiv:1905.01969), and the "
                  "articles in the results provide HTML access (each result card carries the "
                  "[pdf, html, other] links).",
        "wrong": "The articles do not provide HTML access.",
    },
    29: {
        "urls": ["/search?query=Neural+Network+Optimization&searchtype=title&year=2023"],
        "answer": "7 papers with 'Neural Network Optimization' in the title were published in "
                  "2023.",
        "wrong": "There are 4 such papers.",
    },
    30: {
        "urls": ["/help/submit", "/help/figures"],
        "answer": "arXiv accepts the following figure formats: PDF (preferred for vector "
                  "graphics), PNG (preferred for photographs and raster images), JPG/JPEG "
                  "(acceptable for photographs), and EPS (accepted but deprecated, converted "
                  "to PDF). SVG and GIF are not supported.",
        "wrong": "The supported figure formats are TIFF and SVG.",
    },
    31: {
        "urls": ["/search?query=Graph+Neural+Networks&searchtype=abstract&date_from=2024-01-01&date_to=2024-01-03"],
        "answer": "The search returns 6 papers; 3 papers have more than five authors.",
        "wrong": "All 6 papers have more than five authors.",
    },
    32: {
        "urls": ["/list/nlin.CD/new", "/abs/2604.12345"],
        "answer": "The latest paper in Nonlinear Sciences - Chaotic Dynamics is 'Chaos in driven "
                  "nonlinear oscillators with memory' (arXiv:2604.12345), submitted 2026-04-09. "
                  "Abstract summary: the paper introduces the quantum kicked top (QKT), one of "
                  "the most widely studied models in quantum chaos, with a finite-dimensional "
                  "Hilbert space.",
        "wrong": "The latest paper is 'Butterfly Migration Patterns' submitted 2026-04-09.",
    },
    33: {
        "urls": ["/list/cs.SY/new", "/abs/2604.71175"],
        "answer": "The latest Systems and Control (cs.SY) article is 'Data-driven model "
                  "predictive control of HVAC systems' (arXiv:2604.71175, submitted 2026-04-28) "
                  "by Pang, Xiuling and Leclerc, Yannick. Main objective: develop a data-driven "
                  "model predictive control scheme for HVAC systems to reduce energy consumption "
                  "by 30% while maintaining comfort; hypothesis: learned dynamics can replace "
                  "hand-tuned models without loss of performance.",
        "wrong": "The latest paper is 'Traffic Signal Optimization' by Smith and Jones.",
    },
    34: {
        "urls": ["/search?query=non-commutative+geometry&sort=date", "/abs/2604.55278"],
        "answer": "The most recent non-commutative geometry paper submitted by an author with "
                  "the first name John is 'Non-commutative geometry of foliations' "
                  "(arXiv:2604.55278, 2026-04-01) by Smith, John Adam and Kurosawa, Tomoko. "
                  "Abstract: A study of non-commutative geometry of foliations and their "
                  "K-theory.",
        "wrong": "The most recent paper is 'Commutative Ring Theory' by John Smith.",
    },
    35: {
        "urls": ["/list/quant-ph/new", "/abs/2604.40002"],
        "answer": "The latest research paper in Quantum Physics is 'Variational quantum "
                  "eigensolvers for strongly correlated electrons' (arXiv:2604.40002) by "
                  "Nielsen, Michael A., Chuang, Isaac L., and Kitaev, Alexei, submitted on "
                  "2026-04-28.",
        "wrong": "The latest paper is 'Quantum Teleportation Protocols' by Alice and Bob.",
    },
    36: {
        "urls": ["/search?query=CVPR+2023&searchtype=journal_ref",
                 "/search?query=CVPR2023&searchtype=journal_ref"],
        "answer": "Searching journal ref for 'CVPR 2023' returns 4 results; 'CVPR2023' returns "
                  "3 results.",
        "wrong": "Both journal-ref searches return 4 results.",
    },
    37: {
        "urls": ["/about"],
        "answer": "arXiv's Leadership Team: Ramin Zabih (Faculty Director), Stacy Konkiel "
                  "(Director of Research Development and Outreach), Steinn Sigurdsson "
                  "(Scientific Director), Charles Frankston (Senior Technical Director), Jake "
                  "Weiskoff (Engineering Lead), Laurinda Demers (Operations Manager), and "
                  "Alison Fromme (Communications Manager).",
        "wrong": "The leadership team consists of Alice, Bob, and Carol.",
    },
    38: {
        "urls": ["/blog", "/blog/open-access-2026"],
        "answer": "The arXiv Blog's latest article is 'Open Access in 2026: What's Next for "
                  "arXiv' (2026-04-02, arXiv Editorial Team). It reflects on 35 years of open "
                  "access and lays out the roadmap for the next decade: expanding HTML "
                  "rendering, adding new subject areas, and deepening partnerships with "
                  "libraries worldwide to keep arXiv free for every researcher.",
        "wrong": "The latest article is about transparency in moderation.",
    },
    39: {
        "urls": ["/search?query=GPT-4+Technical+Report&searchtype=title",
                 "/abs/2303.08774", "/html/2303.08774"],
        "answer": "One of the main goals of developing such models is to improve their ability "
                  "to understand and generate natural language text, particularly in more "
                  "complex and nuanced scenarios.",
        "wrong": "The main goal is to play chess better than humans.",
    },
    40: {
        "urls": ["/list/astro-ph.SR/new", "/abs/2604.89300"],
        "answer": "The three most recent announce days in Solar and Stellar Astrophysics show "
                  "3 entries (28 Apr 2026), 2 entries (27 Apr 2026), and 3 entries "
                  "(26 Apr 2026). Chosen paper: 'A new stellar flare catalog from TESS' "
                  "(arXiv:2604.89300); the first version was uploaded on 2026-04-28.",
        "wrong": "There were 5, 4, and 5 entries; 'Random Stellar Object' was first uploaded "
                 "2026-04-25.",
        "extra_neg": "The three most recent announce days show 3 entries (28 Apr 2026), "
                     "2 entries (27 Apr 2026), and 3 entries (24 Apr 2026); chosen paper "
                     "'Random Stellar Object' (first version 2026-04-26).",
    },
    41: {
        "urls": ["/store", "/store/arxiv-forever-short-sleeve"],
        "answer": "On the arXiv Forever Short Sleeve item page I selected style Unisex XL and "
                  "clicked Add to Cart. (The mirror has no share button or QR code on the "
                  "store page.)",
        "wrong": "I selected size S and added it to the cart.",
    },
    42: {
        "urls": ["/search?query=Support+Vector+Machines&searchtype=title&date_from=2000-01-01&date_to=2005-01-01",
                 "/abs/0404.00123"],
        "answer": "A matching article is 'Support Vector Machines for Text Categorization with "
                  "Application to Sentiment Analysis' (arXiv:0404.00123, submitted 2004-04-01); "
                  "its journal reference is ACL Workshop 2004.",
        "wrong": "The paper is 'Neural Nets for NER' with journal ref EMNLP 2023.",
    },
}

TASKS = sorted(FIXTURES)


# ------------------------------------------------------------------ fixtures
def _chunk(kind, payload):
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(
        ">I", binascii.crc32(body) & 0xFFFFFFFF)


def make_png(width=1280, height=900, small=False):
    """A deterministic valid PNG above the package gate's 1,000-byte floor."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + b"\x2b\x6f\xa3" * width
    pixels = zlib.compress(row * height, 9)
    note = b"Comment\x00" + b"synthetic verifier fixture; not an agent screenshot. " * 4
    png = signature + _chunk(b"IHDR", ihdr) + _chunk(b"tEXt", note) + \
        _chunk(b"IDAT", pixels) + _chunk(b"IEND", b"")
    return png[:200] if small else png


def write_run(task, cell, destination, fixture=None):
    """Build one synthetic run package. cell in {genuine, noop, wrong, shortcut}."""
    fixture = fixture or FIXTURES[task]
    destination = Path(destination)
    shutil.rmtree(destination, ignore_errors=True)
    shots = destination / "screenshots"
    shots.mkdir(parents=True)
    if cell == "shortcut" or cell == "noop":
        urls = ["/"]
    else:
        urls = ["/"] + fixture["urls"]
    steps = []
    for index, suffix in enumerate(urls):
        url = BASE + suffix
        before, after = f"step_{index:03d}.png", f"step_{index + 1:03d}.png"
        (shots / before).write_bytes(make_png())
        (shots / after).write_bytes(make_png())
        steps.append({
            "step": index,
            "url": url,
            "title": "arXiv.org e-Print archive",
            "thought": f"synthetic {cell} fixture",
            "action": "navigate",
            "params": {"url": url},
            "observed_text": "synthetic fixture dom",
            "observed_text_before": "synthetic fixture dom",
            "screenshot_before": before,
            "screenshot_after": after,
            "url_after": url,
            "action_result": {"is_done": False, "success": True, "error": None,
                              "extracted_content": ""},
        })
    if cell == "noop":
        answer = ""
    elif cell == "wrong":
        answer = fixture["wrong"]
    else:
        answer = fixture["answer"]
    trajectory = {
        "task": f"arXiv task {task}",
        "task_id": f"ArXiv--{task}",
        "start_url": BASE + "/",
        "model": "synthetic-fixture",
        "max_steps": 15,
        "steps": steps,
        "terminated": cell != "noop",
        "termination_reason": "agent_done" if cell != "noop" else "agent_done",
        "final_answer": answer,
        "success_self_report": cell == "genuine",
        "judge_rubric": "",
        "verifier_path": f"sites/arxiv/verify/verify_{task}.py",
        "final_url": BASE + (urls[-1] if urls else "/"),
    }
    (destination / "trajectory.json").write_text(json.dumps(trajectory, indent=2))
    return destination


def run_verifier(task, run_dir):
    """Run verify_<task>.py on run_dir. Returns (returncode, parsed verdict)."""
    cmd = [PYTHON, str(VERIFY_DIR / f"verify_{task}.py"),
           "--run_dir", str(run_dir), "--no_llm", "True"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        verdict = json.loads(r.stdout)
    except Exception:
        verdict = {"pass": False, "reason": f"verifier crashed: {r.stderr[:300]}"}
    return r.returncode, verdict


@pytest.fixture(scope="module")
def workdir(tmp_path_factory):
    return tmp_path_factory.mktemp("arxiv_verify_matrix")


# ------------------------------------------------------------------ tests
@pytest.mark.parametrize("task", TASKS)
def test_genuine_pass(task, workdir):
    run_dir = write_run(task, "genuine", workdir / f"t{task}_genuine")
    code, verdict = run_verifier(task, run_dir)
    assert code == 0 and verdict.get("pass") is True, json.dumps(verdict, indent=1)


@pytest.mark.parametrize("task", TASKS)
def test_noop_fail(task, workdir):
    run_dir = write_run(task, "noop", workdir / f"t{task}_noop")
    code, verdict = run_verifier(task, run_dir)
    assert code == 1 and verdict.get("pass") is False
    assert verdict.get("reason") == "run_package_answer", json.dumps(verdict, indent=1)


@pytest.mark.parametrize("task", TASKS)
def test_wrong_answer_fail(task, workdir):
    run_dir = write_run(task, "wrong", workdir / f"t{task}_wrong")
    code, verdict = run_verifier(task, run_dir)
    assert code == 1 and verdict.get("pass") is False
    assert verdict.get("reason") != "run_package_answer", json.dumps(verdict, indent=1)


# task-specific extra negatives (e.g. hallucinated day labels for task 40)
EXTRA_NEGATIVES = {
    40: lambda fixture: fixture["extra_neg"],
}


@pytest.mark.parametrize("task", sorted(EXTRA_NEGATIVES))
def test_extra_negative_fail(task, workdir):
    fixture = dict(FIXTURES[task])
    fixture["wrong"] = EXTRA_NEGATIVES[task](fixture)
    run_dir = write_run(task, "wrong", workdir / f"t{task}_extra_neg", fixture)
    code, verdict = run_verifier(task, run_dir)
    assert code == 1 and verdict.get("pass") is False
    assert verdict.get("reason") not in ("run_package_answer", "answer_day_counts_3_and_2"), \
        json.dumps(verdict, indent=1)


@pytest.mark.parametrize("task", TASKS)
def test_shortcut_fail(task, workdir):
    run_dir = write_run(task, "shortcut", workdir / f"t{task}_shortcut")
    code, verdict = run_verifier(task, run_dir)
    assert code == 1 and verdict.get("pass") is False
    # a shortcut keeps the correct answer, so it must fail on navigation or a
    # later check — never on the answer gate
    assert verdict.get("reason") not in ("run_package_answer",), json.dumps(verdict, indent=1)


# ------------------------------------------------------------------ gate probes
def _probe(workdir, name, task, mutate, expect_reason):
    run_dir = write_run(task, "genuine", workdir / f"probe_{name}")
    traj = json.loads((run_dir / "trajectory.json").read_text())
    mutate(run_dir, traj)
    (run_dir / "trajectory.json").write_text(json.dumps(traj, indent=2))
    code, verdict = run_verifier(task, run_dir)
    assert code == 1 and verdict.get("pass") is False
    assert verdict.get("reason") == expect_reason, json.dumps(verdict, indent=1)


def test_gate_missing_trajectory(workdir):
    run_dir = write_run(0, "genuine", workdir / "probe_no_traj")
    (run_dir / "trajectory.json").unlink()
    code, verdict = run_verifier(0, run_dir)
    assert code == 1 and verdict.get("reason") == "run_package_trajectory"


def test_gate_missing_screenshots(workdir):
    run_dir = write_run(0, "genuine", workdir / "probe_no_shots")
    shutil.rmtree(run_dir / "screenshots")
    code, verdict = run_verifier(0, run_dir)
    assert code == 1 and verdict.get("reason") == "run_package_screenshot"


def test_gate_task_id_mismatch(workdir):
    _probe(workdir, "task_id", 0,
           lambda d, t: t.update(task_id="ArXiv--42"),
           "run_package_task_id")


def test_gate_external_start_url(workdir):
    _probe(workdir, "start_url", 0,
           lambda d, t: t.update(start_url="https://arxiv.org/"),
           "run_package_start_url")


def test_gate_external_step_url(workdir):
    def mutate(d, t):
        t["steps"][1]["url"] = "https://arxiv.org/search?query=quantum+computing"
    _probe(workdir, "step_url", 0, mutate, "run_package_url")


def test_gate_undersized_screenshot(workdir):
    def mutate(d, t):
        (d / "screenshots" / t["steps"][1]["screenshot_before"]).write_bytes(make_png(small=True))
    _probe(workdir, "tiny_shot", 0, mutate, "run_package_screenshot")


def test_gate_empty_steps(workdir):
    _probe(workdir, "no_steps", 0, lambda d, t: t.update(steps=[]),
           "run_package_steps")

#!/usr/bin/env python3
"""Site self-check for the coursera deterministic verifiers.

Builds synthetic run packages on disk (trajectory.json + screenshots/) against a
copy of the mirror's seed DB and asserts the grading contract of all 42
verifiers (merriam_webster/phet exemplar style; run with:

    cd agent_demo && uv run pytest ../sites/coursera/verify/test_verifiers.py -q

or from the repo root: uv run pytest sites/coursera/verify/test_verifiers.py).

Matrix per task (deterministic only — verifiers are --no_llm clean):
  positive      — a well-formed package that satisfies the task contract PASSES
  no_op         — homepage-only trajectory with an empty answer FAILS
  shortcut      — correct answer but a homepage-only trajectory FAILS
  wrong_answer  — qualifying navigation but a content-adversarial answer FAILS
  task_id       — a package graded under the wrong task id FAILS

Shared contract probes:
  package gates  — missing trajectory.json / missing screenshots FAIL closed
  origin spoof   — an external-origin (real coursera.org) trajectory FAILS
  state mismatch — an otherwise-valid package with a mutated after-DB FAILS

The synthetic ground truth below mirrors the live-mirror audit (see
../../..../reports/coursera/audit/audit_all.json); it is test data, not the
grading key (the grading key is hardcoded in each verify_N.py).
"""
import json
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
SITE_DIR = VERIFY_DIR.parent
AGENT_DEMO = VERIFY_DIR.parents[2] / "agent_demo"
BASE = "http://localhost:41013"
# The verifiers import simpleArgParser, a dependency of the agent_demo project:
# always run them with the agent_demo venv interpreter (also correct when the
# suite itself is executed by `uv run pytest` from an ephemeral overlay env).
VENV_PY = AGENT_DEMO / ".venv" / "bin" / "python"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable

SEED_DB = SITE_DIR / "instance_seed" / "coursera.db"
CONTAINER = "wh-ver-coursera"


def seed_db_path():
    """Locate the seed DB: tracked checkout, or docker cp from the container."""
    if SEED_DB.exists():
        return SEED_DB
    import os
    import tempfile
    target = Path(tempfile.gettempdir()) / "coursera-verify-test-seed.db"
    if not target.exists():
        container = os.environ.get("WH_CONTAINER", CONTAINER)
        r = subprocess.run(["docker", "cp",
                            f"{container}:/opt/WebSyn/coursera/instance_seed/coursera.db",
                            str(target)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(
                f"seed DB not found at {SEED_DB} and docker cp failed: {r.stderr.strip()}")
    return target


# --------------------------------------------------------------------------- helpers

def tiny_png(path):
    """Write a valid 1x1 PNG (the package gate only requires step_*.png files)."""
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = zlib.compress(b"\x00\xff\x00\x00")
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", raw) + chunk(b"IEND", b""))
    Path(path).write_bytes(png)


def write_package(root, task_id, visits, final_answer, shots=2,
                  with_trajectory=True, with_screenshots=True, start=BASE + "/"):
    """visits: list of (path, dom_text). Steps walk home -> visit1 -> visit2...

    Each landing page's DOM is recorded in observed_text/observed_text_after of
    the step that lands on it (mirroring agent.py's trajectory format)."""
    run_dir = Path(root) / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    steps = []
    prev = start
    for i, (path, dom) in enumerate(visits):
        url = path if str(path).startswith("http") else BASE + path
        steps.append({
            "step": i, "url": prev, "url_after": url, "title": "Coursera",
            "thought": "", "action": "navigate" if i == 0 else "click",
            "params": {"url": url} if i == 0 else {"index": 1},
            "observed_text": dom, "observed_text_before": dom,
            "observed_text_after": dom,
            "screenshot_before": f"step_{i:03d}.png",
            "screenshot_after": f"step_{i + 1:03d}.png",
            "action_result": {"is_done": False, "success": True, "error": None,
                              "extracted_content": ""},
        })
        prev = url
    if with_trajectory:
        traj = {
            "task": "synthetic", "task_id": task_id, "start_url": start,
            "model": "test", "max_steps": 15, "steps": steps,
            "terminated": True, "termination_reason": "agent_done",
            "final_answer": final_answer, "success_self_report": True,
            "judge_rubric": "", "verifier_path": "",
            "final_url": prev, "final_observed_text": visits[-1][1] if visits else "",
        }
        (run_dir / "trajectory.json").write_text(json.dumps(traj, ensure_ascii=False),
                                                 encoding="utf-8")
    if with_screenshots:
        shots_dir = run_dir / "screenshots"
        shots_dir.mkdir(exist_ok=True)
        for i in range(shots + 1):
            tiny_png(shots_dir / f"step_{i:03d}.png")
    return run_dir


def run_verifier(n, run_dir, initial_db, after_db, no_llm=True, extra_env=None):
    cmd = [PY, str(VERIFY_DIR / f"verify_{n}.py"), "--run_dir", str(run_dir),
           "--initial_db", str(initial_db), "--after_db", str(after_db),
           "--no_llm", "True"]
    import os
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(AGENT_DEMO),
                       timeout=60, check=False, env=env)
    try:
        verdict = json.loads(r.stdout)
    except Exception:
        verdict = {"pass": False, "reason": f"verifier crashed: {r.stderr[-300:]}"}
    return r.returncode, verdict


# ------------------------------------------------------------------ per-task fixtures

def dom(text):
    return text


POS = {}   # task -> (visits, answer)
WRONG = {}  # task -> content-adversarial answer (used with the positive visits)

SEARCH = "/search?q=x"
POS[0] = ([(SEARCH, "Results for 3d printing — 3D Printing Revolution — University of Illinois Urbana-Champaign — Beginner — 1-3 Months"),
            ("/learn/3d-printing-revolution",
             "COURSE 3D Printing Revolution University of Illinois Urbana-Champaign "
             "Beginner Certificate 1-3 Months Vishal Singh")],
           "3D Printing Revolution, offered by the University of Illinois Urbana-Champaign, "
           "is a Beginner-level course about 3D printing lasting 1-3 Months.")
WRONG[0] = ("3D Printing Revolution is offered by the University of California, Irvine "
            "and lasts 6 months.")

POS[1] = ([(SEARCH, "Python programming results: Python for Everybody — University of Michigan"),
            ("/learn/python-for-everybody",
             "COURSE Python for Everybody University of Michigan Beginner Certificate "
             "Charles Severance Built for absolute beginners — no prior coding background needed.")],
           "Python for Everybody from the University of Michigan is a beginner-level "
           "Python course suitable for someone with no programming experience.")
WRONG[1] = "I would recommend the Machine Learning Specialization."

SUBS_DOM = ("SPECIALIZATION Learn Spanish: Basic Spanish Vocabulary Specialization "
            "University of California, Davis Courses in this Specialization: "
            "Spanish Vocabulary: Meeting People Spanish Vocabulary: Around Town "
            "Spanish Vocabulary: At Home Spanish Vocabulary: At Work "
            "Spanish Vocabulary: Nature and Environment")
POS[2] = ([(SEARCH, "Beginner Spanish Specialization results"),
            ("/learn/learn-spanish-basic-vocabulary-specialization", SUBS_DOM)],
           "The Beginner's Spanish Specialization is Learn Spanish: Basic Spanish "
           "Vocabulary Specialization. Its courses are: Spanish Vocabulary: Meeting People; "
           "Spanish Vocabulary: Around Town; Spanish Vocabulary: At Home; Spanish Vocabulary: "
           "At Work; Spanish Vocabulary: Nature and Environment.")
WRONG[2] = ("The Specialization contains Spanish Vocabulary: Meeting People and "
            "Spanish Vocabulary: Around Town.")

POS[3] = ([("/search?q=Python+Data+Science&sort=newest",
             "Results for Python Data Science sorted by newest: Python for Data Science "
             "and Machine Learning — IBM — Beginner"),
            ("/learn/python-data-science-ml-2024",
             "COURSE Python for Data Science and Machine Learning IBM Beginner Certificate "
             "Approx. 22 hours Joseph Santarcangelo")],
           "Sorting Python Data Science results by newest, the first course is Python for "
           "Data Science and Machine Learning, offered by IBM.")
WRONG[3] = ("The first course is Python Data Science Fundamentals, offered by "
            "the University of Michigan.")

POS[4] = ([(SEARCH, "business process management results"),
            ("/learn/business-process-management",
             "COURSE Business Process Management University of Queensland Beginner "
             "Certificate Approx. 17 hours rating 4.7 (12,000 reviews)")],
           "Business Process Management from the University of Queensland helps with "
           "business process management and has a rating of 4.7.")
WRONG[4] = "Business Process Management has a rating of 3.9."

POS[5] = ([(SEARCH, "C++ specialization results"),
            ("/learn/coding-everyone-c-cpp",
             "SPECIALIZATION Coding for Everyone: C and C++ Specialization University of "
             "California, San Diego What you'll learn: Write C programs Use C++ classes and "
             "objects Implement data structures Build real-world applications")],
           "The Coding for Everyone: C and C++ Specialization (UC San Diego) teaches "
           "beginners C and C++; learning outcomes include Write C programs, Use C++ classes "
           "and objects, Implement data structures, and Build real-world applications.")
WRONG[5] = ("The C and C++ Specialization teaches machine learning and data science.")

POS[6] = ([(SEARCH, "Artificial Intelligence for Healthcare results"),
            ("/learn/artificial-intelligence-healthcare",
             "COURSE Artificial Intelligence for Healthcare Stanford University "
             "Intermediate Certificate Approx. 20 hours There are 4 modules in this "
             "course WEEK 1 Introduction to AI in Healthcare 1 quizzes WEEK 2 Medical "
             "Imaging with AI 2 quizzes WEEK 3 Clinical NLP and EHR Analytics 1 quizzes "
             "WEEK 4 AI Ethics and Regulation in Medicine 1 quizzes")],
           "Artificial Intelligence for Healthcare (Stanford) has a duration of Approx. "
           "20 hours and its assessments include 5 quizzes in total.")
WRONG[6] = ("Artificial Intelligence for Healthcare takes 45 hours and has "
            "12 quizzes.")

POS[7] = ([(SEARCH, "Reinforcement Learning intermediate results"),
            ("/learn/reinforcement-learning-specialization",
             "SPECIALIZATION Reinforcement Learning Specialization University of Michigan "
             "Intermediate Certificate 4 Months rating 4.7 (18,000 reviews) Martha White")],
           "The Reinforcement Learning Specialization, offered by the University of Michigan, "
           "is Intermediate-level with a rating of 4.7 and has received 18,000 reviews.")
WRONG[7] = ("The Reinforcement Learning Specialization from the University of Michigan "
            "has 450 reviews.")

POS[8] = ([("/search?q=R+for+Data+Science&free=1",
             "Free R courses: R Programming — Johns Hopkins University — Free"),
            ("/learn/r-programming",
             "COURSE R Programming Johns Hopkins University Beginner Free Certificate "
             "Approx. 57 hours English · Subtitles available")],
           "R Programming is a free course related to R for Data Science, and the course "
           "is taught in English.")
WRONG[8] = "The R for Data Science course is taught in Mandarin."

POS[9] = ([(SEARCH, "artificial intelligence ethics results"),
            ("/learn/ethics-of-artificial-intelligence",
             "COURSE Ethics of Artificial Intelligence Princeton University Beginner "
             "Certificate Approx. 18 hours rating 4.8")],
           "Ethics of Artificial Intelligence (Princeton University) is an AI ethics course "
           "with a duration of Approx. 18 hours (less than 20 hours) rated 4.8 stars.")
WRONG[9] = "The AI ethics course lasts 60 hours and is rated 3.1 stars."

POS[10] = ([(SEARCH, "artificial intelligence beginner results"),
            ("/learn/ai-empathy-ethics",
             "COURSE AI, Empathy & Ethics Stanford University Beginner Certificate "
             "Approx. 14 hours Modules: AI Ethics Machine Learning Ethics Bias in AI")],
           "AI, Empathy & Ethics (Stanford) is an introductory, beginner-friendly AI course "
           "that includes an AI Ethics module discussing ethical considerations.")
WRONG[10] = "Introduction to Cognitive Psychology is the introductory AI course."

POS[11] = ([(SEARCH, "project management specialization results"),
            ("/learn/engineering-project-management-specialization",
             "SPECIALIZATION Engineering Project Management Specialization Rice University "
             "Learner Testimonials: 'Great instructor, well organised content, and lots of "
             "opportunities to apply what you learn. Worth every minute.' Olusola Adebayo")],
           "The Engineering Project Management Specialization is produced by Rice University. "
           "A testimonial: 'Great instructor, well organised content, and lots of "
           "opportunities to apply what you learn. Worth every minute.' — Olusola Adebayo.")
WRONG[11] = ("The Engineering Project Management Specialization from Google has this "
             "testimonial: 'I loved this course.' — Anonymous User.")

POS[12] = ([(SEARCH, "Java programming course results"),
            ("/learn/object-oriented-programming-java",
             "COURSE Object Oriented Programming in Java University of California, San Diego "
             "Beginner Certificate Approx. 42 hours Leo Porter")],
           "Object Oriented Programming in Java (UC San Diego) is a Course (not a "
           "Specialization) that teaches Java programming basics.")
WRONG[12] = "Programming for Everybody is the Java basics course to take."

POS[13] = ([(SEARCH, "Python specialization results"),
            ("/learn/python-3-programming-specialization",
             "SPECIALIZATION Python 3 Programming Specialization University of Michigan "
             "Skills you'll gain: Python Functions Files and Dictionaries Data Collection "
             "Classes Paul Resnick")],
           "The Python 3 Programming Specialization (University of Michigan) teaches Python "
           "programming; the skills you will learn include Python, Functions, Files and "
           "Dictionaries, Data Collection, and Classes.")
WRONG[13] = ("The Python 3 Programming Specialization teaches sailing, cooking, "
             "and welding.")

POS[14] = ([(SEARCH, "project management results"),
            ("/learn/introduction-to-project-management",
             "COURSE Introduction to Project Management University of Melbourne Beginner "
             "Certificate Approx. 10 hours Modules: Introduction to Project Management "
             "Project Planning and Scheduling Agile Project Management Risk Management")],
           "Introduction to Project Management (University of Melbourne) is the introductory "
           "project management course and includes an Agile Project Management module on "
           "Agile methodology.")
WRONG[14] = ("Introduction to Project Management covers only waterfall scheduling "
             "and financial modelling.")

POS[15] = ([(SEARCH, "Introduction to Mathematical Thinking results"),
            ("/learn/introduction-to-mathematical-thinking",
             "COURSE Introduction to Mathematical Thinking Stanford University Beginner "
             "Rating Breakdown 5 stars 65% 4 stars 22% 3 stars 8% 2 stars 3% 1 star 2% "
             "Dr. Keith Devlin")],
           "For Introduction to Mathematical Thinking, 65% of the ratings are 5 stars, and "
           "the 1 star level has the least percentage (2%).")
WRONG[15] = "5-star ratings are 22% and the 4 star level has the least percentage."

POS[16] = ([(SEARCH, "Introduction to Finance: The Basics results"),
            ("/learn/introduction-to-finance-the-basics",
             "COURSE Introduction to Finance: The Basics University of Michigan Gautam Kaul "
             "Professor of Finance"),
            ("/instructor/gautam-kaul",
             "Gautam Kaul Professor of Finance, University of Michigan 2 courses on Coursera "
             "Courses taught by Gautam Kaul: Introduction to Finance: The Basics, "
             "Finance for Non-Finance Professionals")],
           "The instructor of Introduction to Finance: The Basics is Gautam Kaul; his other "
           "course on Coursera is Finance for Non-Finance Professionals.")
WRONG[16] = "The instructor is Andrew Ng and he teaches 15 other courses."

POS[17] = ([("/search?q=Machine+Learning&credit=1&duration=1-4_years",
              "Results for Machine Learning — Credit Eligible — 1-4 Years: Master of "
              "Science in Machine Learning — Georgia Institute of Technology; Master of "
              "Engineering in Machine Learning and AI — Columbia University")],
           "There are 2 results for a Machine Learning search filtered by Credit Eligible "
           "and 1-4 Years duration.")
WRONG[17] = "There are 17 results for the filtered search."

POS[18] = ([(SEARCH, "JavaScript beginner results"),
            ("/learn/html-css-javascript-web-developers",
             "COURSE HTML, CSS, and Javascript for Web Developers Johns Hopkins University "
             "Beginner Certificate on completion Approx. 40 hours Yaakov Chaikin")],
           "HTML, CSS, and Javascript for Web Developers (Johns Hopkins University) is a "
           "beginner-friendly JavaScript course that includes a certificate upon completion.")
WRONG[18] = "Programming with Python is the beginner JavaScript course with a certificate."

POS[19] = ([(SEARCH, "Introduction to Psychology results"),
            ("/learn/introduction-to-psychology",
             "COURSE Introduction to Psychology Yale University Beginner Free Certificate "
             "Approx. 14 hours Instructor Paul Bloom Professor of Psychology, Yale University")],
           "Introduction to Psychology is taught by instructor Paul Bloom at Yale University "
           "and takes approximately 14 hours to complete.")
WRONG[19] = "Introduction to Psychology is taught by Adam White at MIT over 99 hours."

POS[20] = ([(SEARCH, "Blockchain Technology intermediate 1-4 weeks results"),
            ("/learn/blockchain-basics",
             "COURSE Blockchain Basics University at Buffalo Intermediate Certificate 1-4 "
             "Weeks Bina Ramamurthy What you'll learn: Understand blockchain technology "
             "Explain Bitcoin architecture Describe smart contracts Analyse consensus "
             "mechanisms")],
           "Blockchain Basics from the University at Buffalo is an Intermediate course "
           "lasting 1-4 Weeks; its main goals include Understand blockchain technology and "
           "Explain Bitcoin architecture, and the instructor is Bina Ramamurthy.")
WRONG[20] = ("Blockchain Basics is a Beginner course lasting 2 years taught by "
             "Sandra Wachter.")

POS[21] = ([(SEARCH, "Digital Marketing beginner results"),
            ("/learn/fundamentals-digital-marketing",
             "COURSE Fundamentals of Digital Marketing Google Beginner Free Certificate "
             "Approx. 40 hours What you'll learn: Create a digital marketing strategy "
             "Optimize for search engines Run social media campaigns Use Google Analytics")],
           "Fundamentals of Digital Marketing (Google) is a beginner course lasting Approx. "
           "40 hours; main learning outcomes include Create a digital marketing strategy "
             "and Optimize for search engines.")
WRONG[21] = "Fundamentals of Digital Marketing lasts 5 years and is offered by Yale."

POS[22] = ([(SEARCH, "Human Resource specialization results"),
            ("/learn/human-resource-management-specialization",
             "SPECIALIZATION Human Resource Management: HR for People Managers Specialization "
             "University of Minnesota Courses in this Specialization: Preparing to Manage "
             "Human Resources Recruiting, Hiring, and Onboarding Employees Managing Employee "
             "Performance Managing Employee Compensation Human Resources Management "
             "Capstone: HR for People Managers")],
           "The Human Resource Management: HR for People Managers Specialization from the "
           "University of Minnesota includes: Preparing to Manage Human Resources; "
           "Recruiting, Hiring, and Onboarding Employees; Managing Employee Performance; "
           "Managing Employee Compensation; Human Resources Management Capstone: HR for "
           "People Managers.")
WRONG[22] = ("The HR Specialization from the University of Minnesota includes only "
             "Preparing to Manage Human Resources.")

POS[23] = ([(SEARCH, "Artificial Intelligence Ethics results"),
            ("/learn/ethics-of-artificial-intelligence",
             "COURSE Ethics of Artificial Intelligence Princeton University Beginner "
             "Certificate Approx. 18 hours rating 4.8 Instructor Sandra Wachter")],
           "Ethics of Artificial Intelligence (Princeton University) has a duration under "
           "5 weeks and a rating of 4.8; the instructor is Sandra Wachter.")
WRONG[23] = "The course is AI Ethics Crash Course taught by Bina Ramamurthy."

POS[24] = ([(SEARCH, "Sustainability physical science results"),
            ("/learn/sustainability-and-development",
             "COURSE Sustainability and Development University of Michigan Beginner "
             "Certificate Approx. 14 hours Modules: Foundations of Sustainability Measuring "
             "Sustainability Energy Systems and Climate")],
           "Sustainability and Development (University of Michigan) is the Physical Science "
           "and Engineering sustainability course with a Measuring Sustainability module; "
           "its duration is Approx. 14 hours.")
WRONG[24] = "Sustainability and Development is offered by Yale and lasts 120 hours."

POS[25] = ([(SEARCH, "Relativity beginner results"),
            ("/learn/understanding-einstein-special-relativity",
             "COURSE Understanding Einstein: The Special Theory of Relativity Stanford "
             "University Beginner Certificate Approx. 18 hours Modules: The Principle of "
             "Relativity Special Theory of Relativity Space-Time Diagrams Time Dilation and "
             "Length Contraction Mass-Energy Equivalence")],
           "Understanding Einstein: The Special Theory of Relativity (Stanford) is a "
           "beginner course on relativity covering Time Dilation and Length Contraction, "
           "with an estimated 18 hours to complete.")
WRONG[25] = "The relativity course takes 400 hours and covers pottery."

POS[26] = ([(SEARCH, "Renewable Energy specialization results"),
            ("/learn/renewable-energy-green-building-specialization",
             "SPECIALIZATION Renewable Energy and Green Building Entrepreneurship "
             "Specialization Duke University Beginner Certificate 4 Months Bruce Usher "
             "Courses in this Specialization: Solar Energy Basics Wind Energy Batteries and "
             "the Future of Energy Storage Economics of Renewable Energy Renewable Energy "
             "Futures Approx. 15 hours")],
           "The Renewable Energy and Green Building Entrepreneurship Specialization (Duke "
           "University) is taught by Bruce Usher and includes the Renewable Energy Futures "
           "course; at 5 hours a week the Renewable Energy Futures course takes 3 weeks.")
WRONG[26] = "The specialization is taught by Don Tapscott and takes 100 weeks."

POS[27] = ([(SEARCH, "Data Visualization specialization results"),
            ("/learn/data-visualization-tableau-specialization",
             "SPECIALIZATION Data Visualization with Tableau Specialization University of "
             "California, Davis Skills: Tableau Data Visualization Dashboard Design Visual "
             "Analytics Storytelling with Data Courses: Fundamentals of Visualization with "
             "Tableau Data Visualization with Tableau Project")],
           "The Data Visualization with Tableau Specialization (University of California, "
           "Davis) includes a project; skills developed include Tableau, Dashboard Design, "
           "and Visual Analytics.")
WRONG[27] = ("The Tableau Specialization develops skills in gardening and has no "
             "project.")

POS[28] = ([(SEARCH, "Astrophysics guided project results"),
            ("/learn/analyzing-astrophysics-data-python",
             "GUIDED PROJECT Analyzing Astrophysics Data with Python Johns Hopkins "
             "University Advanced Less Than 2 Hours Skills: Astrophysics Python astropy "
             "Data Analysis matplotlib Dr. Nathan Anderson")],
           "Analyzing Astrophysics Data with Python is an advanced Guided Project from Johns "
           "Hopkins University lasting Less Than 2 Hours; main subjects include Astrophysics, "
           "Python, and astropy.")
WRONG[28] = ("The astrophysics project lasts 6 months, is offered by Meta, and covers "
             "marketing.")

POS[29] = ([("/coursera-plus",
              "Coursera Plus Choose your plan Annual Subscription $399 / year Save $309/year "
              "(43% off vs. monthly) Monthly Subscription $59 / month World-class "
              "universities: Courses from Stanford, Yale, Google, IBM and 300+ more.")],
           "One year of Coursera Plus costs $399; the discount is $309 (43% off vs. monthly). "
           "Companies that work with Coursera include Google, IBM, and Meta.")
WRONG[29] = ("Coursera Plus costs $99/year with no discount; partners include "
             "Bob's Auto Repair.")

POS[30] = ([(SEARCH, "Modern Art & Ideas results"),
            ("/learn/modern-art-ideas",
             "COURSE Modern Art & Ideas The Museum of Modern Art Beginner Free Certificate "
             "Approx. 8 hours Rating Breakdown 5 stars 65% 4 stars 22% 3 stars 8% 2 stars 3% "
             "1 star 2%")],
           "For Modern Art & Ideas, 8% of the ratings are 3 stars, and the 1 star level has "
           "the lowest percentage (2%).")
WRONG[30] = "3-star ratings are 65% and the 5 star level has the lowest percentage."

POS[31] = ([(SEARCH, "Exploring Quantum Physics results"),
            ("/learn/exploring-quantum-physics",
             "COURSE Exploring Quantum Physics University of Maryland Intermediate "
             "Certificate Credit Eligible Approx. 30 hours Rating Breakdown 5 stars 55% "
             "4 stars 28% 3 stars 10% 2 stars 4% 1 star 3%")],
           "For Exploring Quantum Physics, 55% of the reviews are 5-star ratings.")
WRONG[31] = "28% of the reviews are 5-star ratings."

POS[32] = ([("/search?q=Data+Analysis&level=Beginner&duration=1-3_months",
              "Results for Data Analysis — Beginner — 1-3 Months: Data Analysis and "
              "Visualization with Excel and Cognos; Python for Data Science, AI & Development; "
              "Python Data Science Fundamentals; Business Process Management")],
           "A Data Analysis search filtered by Beginner Level and 1-3 Months duration "
           "returns 4 courses in total.")
WRONG[32] = "The filtered search returns 40 courses."

POS[33] = ([(SEARCH, "Internet of Things beginner results"),
            ("/learn/introduction-internet-things-embedded-systems",
             "COURSE Introduction to the Internet of Things and Embedded Systems University "
             "of California, Irvine Beginner Certificate Approx. 15 hours rating 4.6 "
             "Instructor Ian Harris Skills: Internet of Things Embedded Systems Arduino "
             "Sensors Networking")],
           "Introduction to the Internet of Things and Embedded Systems (UC Irvine) is a "
           "beginner IoT course with a high rating; taught by Ian Harris, it covers skills "
           "such as the Internet of Things, Embedded Systems, and Arduino.")
WRONG[33] = ("The IoT course is taught by Bina Ramamurthy and covers financial "
             "reporting.")

POS[34] = ([(SEARCH, "Essentials of Global Health results"),
            ("/learn/essentials-of-global-health",
             "COURSE Essentials of Global Health Yale University Beginner Certificate "
             "Approx. 33 hours Instructor Richard Skolnik Lecturer in Global Affairs, Yale "
             "University"),
            ("/instructor/richard-skolnik",
             "Richard Skolnik Lecturer in Global Affairs, Yale University 1 course on "
             "Coursera Courses taught by Richard Skolnik: Essentials of Global Health")],
           "Essentials of Global Health is taught by Richard Skolnik, Lecturer in Global "
           "Affairs at Yale University; he offers no additional courses on Coursera (1 "
           "course only).")
WRONG[34] = ("Richard Skolnik teaches 20 other courses on Coursera.")

POS[35] = ([(SEARCH, "Sustainable Agriculture results"),
            ("/learn/sustainable-agricultural-land-management",
             "COURSE Sustainable Agricultural Land Management University of Florida "
             "Beginner Certificate Approx. 12 hours Instructor Ann Wilkie Professor, "
             "University of Florida What you'll learn: Implement sustainable farming "
             "practices Manage soil health Conserve water in agriculture Apply agroforestry "
             "principles")],
           "Sustainable Agricultural Land Management (University of Florida) is led by Ann "
           "Wilkie, Professor at the University of Florida; its objectives include Implement "
           "sustainable farming practices, Manage soil health, and Apply agroforestry "
           "principles.")
WRONG[35] = ("The agriculture course is led by Larry Randles Lagerstrom and covers "
             "relativity theory.")

MAS_DOM = ("Online Degrees Master of Advanced Study in Data Science Georgia Institute of "
           "Technology Application deadline: June 30, 2026 Master of Advanced Study in "
           "Engineering Columbia University Application deadline: May 15, 2026 Master of "
           "Advanced Study in Engineering Mechanics University of Illinois Urbana-Champaign "
           "Application deadline: April 22, 2026 Master of Advanced Study in Engineering "
           "Sciences Rice University Application deadline: March 31, 2026")
POS[36] = ([("/degrees?type=MasterAdvancedStudy", MAS_DOM),
             ("/learn/master-advanced-study-engineering-ucberkeley",
              "DEGREE Master of Advanced Study in Engineering Columbia University "
              "Application deadline: May 15, 2026")],
           "Columbia University offers the Master of Advanced Study in Engineering; the "
           "latest application deadline for this degree is May 15, 2026.")
WRONG[36] = ("Georgia Tech offers the MAS in Engineering with a deadline of "
             "June 30, 2026.")

POS[37] = ([("/", "Coursera homepage Learn without limits Free courses to get you "
                "started: Introduction to Psychology Modern Art & Ideas Programming for "
                "Everybody (Getting Started with Python) R Programming R for Data Science "
                "and Machine Learning Fundamentals of Digital Marketing")],
           "Free courses on Coursera include Introduction to Psychology, Modern Art & Ideas, "
           "and R Programming.")
WRONG[37] = ("Free courses include Machine Learning Specialization, Blockchain Basics, "
             "and AWS Cloud Technical Essentials.")

AU_DOM = ("Our Partners Partners in Australia Atlassian Australian National University "
          "Canva Commonwealth Bank Deakin University Macquarie Bank Macquarie University "
          "Monash University PwC RMIT University UNSW Sydney University of Adelaide "
          "University of Melbourne University of Queensland University of Sydney "
          "University of Western Australia")
POS[38] = ([("/partners?country=Australia", AU_DOM)],
           "The Australian partners of Coursera are: Atlassian; Australian National "
           "University; Canva; Commonwealth Bank; Deakin University; Macquarie Bank; "
           "Macquarie University; Monash University; PwC; RMIT University; UNSW Sydney; "
           "University of Adelaide; University of Melbourne; University of Queensland; "
           "University of Sydney; University of Western Australia.")
WRONG[38] = ("Australian partners are Atlassian and Canva.")

POS[39] = ([(SEARCH, "Space Safety results"),
            ("/learn/space-safety",
             "COURSE Space Safety Technical University of Munich Beginner Certificate "
             "Approx. 15 hours Prof. Ulrich Walter WEEK 2 Space Debris 7 videos: Where "
             "Space Debris Comes From The Kessler Syndrome Explained Tracking Debris from "
             "the Ground On-Orbit Conjunction Assessment Active Debris Removal Concepts "
             "Post-Mission Disposal Guidelines Future Outlook for Orbital Sustainability")],
           "Module 2 (Space Debris) of the Space Safety course contains 7 videos: Where Space "
           "Debris Comes From; The Kessler Syndrome Explained; Tracking Debris from the "
           "Ground; On-Orbit Conjunction Assessment; Active Debris Removal Concepts; "
           "Post-Mission Disposal Guidelines; Future Outlook for Orbital Sustainability.")
WRONG[39] = ("Module 2 has 3 videos: Intro, Basics, and Conclusion.")

POS[40] = ([("/business",
              "Coursera for Business Why Coursera for Business? World-class content "
              "Measurable outcomes Recognized credentials Curated content Skill "
              "development Mobile learning"),
             ("/for-teams",
              "Coursera for Teams Advantages of Coursera for Teams Unlimited learning "
              "Team analytics Industry certificates Collaborative learning Any device LMS "
              "integration")],
           "Coursera for Business advantages include World-class content and Measurable "
           "outcomes; Coursera for Teams advantages include Unlimited learning and Team "
           "analytics.")
WRONG[40] = "Coursera for Business offers free pizza Fridays."

BACH_DOM = ("Online Degrees Bachelor's: BSc Computer Science University of London "
            "Bachelor of Applied Arts and Sciences Arizona State University Bachelor of Arts "
            "in Communication Vanderbilt University Bachelor of Science in Business "
            "Administration Arizona State University Bachelor of Science in Data Science "
            "Arizona State University Bachelor of Science in Information Technology "
            "University of Illinois Urbana-Champaign")
POS[41] = ([("/degrees?type=bachelor", BACH_DOM)],
           "Three Bachelor's degree programmes on Coursera: BSc Computer Science, Bachelor "
           "of Applied Arts and Sciences, and Bachelor of Science in Data Science.")
WRONG[41] = "Master of Applied Data Science, Master of Computer Science, and MAS in Engineering."


# Card-path positives: tasks whose question is fully answerable from the
# search-results card. A trajectory that only ran the mirror search (never
# opened the course page) must still PASS when the card exports the facts.
CARD_POS = {
    0: ("Results for 3d printing: 3D Printing Revolution — University of Illinois "
        "Urbana-Champaign — Beginner — Course — 1-3 Months — 4.6 (8,000)",
        POS[0][1]),
    3: ("Results for Python Data Science sorted by newest: Python for Data Science "
        "and Machine Learning — IBM — Beginner — Course — Approx. 22 hours",
        POS[3][1]),
    4: ("Results: Business Process Management — University of Queensland — Beginner "
        "— Course — Approx. 17 hours — 4.7 (12,000)",
        POS[4][1]),
    7: ("Results: Reinforcement Learning Specialization — University of Michigan — "
        "Intermediate — Specialization — 4 Months — 4.7 (18,000)",
        POS[7][1]),
    9: ("Results: Ethics of Artificial Intelligence — Princeton University — "
        "Beginner — Course — Approx. 18 hours — 4.8 (9,200)",
        POS[9][1]),
    10: ("Results: AI, Empathy & Ethics — Stanford University — Beginner — Course "
         "— Approx. 14 hours — 4.7 (7,500)",
         POS[10][1]),
    12: ("Results: Object Oriented Programming in Java — University of California, "
         "San Diego — Beginner — Course — Approx. 42 hours",
         POS[12][1]),
    13: ("Results: Python 3 Programming Specialization — University of Michigan — "
         "Beginner — Specialization — 5 Months — skills: Python, Functions, Files "
         "and Dictionaries, Data Collection, Classes",
         POS[13][1]),
    18: ("Results: HTML, CSS, and Javascript for Web Developers — Johns Hopkins "
         "University — Beginner — Course — Approx. 40 hours",
         POS[18][1]),
    24: ("Results: Sustainability and Development — University of Michigan — "
         "Beginner — Course — Approx. 14 hours",
         POS[24][1]),
    27: ("Results: Data Visualization with Tableau Specialization — University of "
         "California, Davis — Beginner — Specialization — 5 Months",
         POS[27][1]),
}


# --------------------------------------------------------------------------- suite

class CourseraVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = Path(seed_db_path())
        assert cls.seed.exists(), f"seed DB missing: {cls.seed}"

    def _dbs(self, root, mutate_after=None):
        initial = Path(root) / "initial.db"
        after = Path(root) / "after.db"
        shutil.copy2(self.seed, initial)
        shutil.copy2(self.seed, after)
        if mutate_after:
            con = sqlite3.connect(after)
            try:
                mutate_after(con)
                con.commit()
            finally:
                con.close()
        return initial, after

    def grade(self, task, visits, answer, mutate_after=None, task_id=None,
              with_trajectory=True, with_screenshots=True, shots=3,
              start_url=BASE + "/"):
        with tempfile.TemporaryDirectory(prefix=f"coursera-verify-{task}-") as tmp:
            root = Path(tmp)
            initial, after = self._dbs(root, mutate_after)
            run_dir = write_package(root, task_id or f"Coursera--{task}", visits,
                                    answer, shots=shots,
                                    with_trajectory=with_trajectory,
                                    with_screenshots=with_screenshots,
                                    start=start_url)
            return run_verifier(task, run_dir, initial, after)

    def test_all_positive_cases(self):
        for task in range(42):
            with self.subTest(task=task):
                visits, answer = POS[task]
                code, verdict = self.grade(task, visits, answer)
                self.assertEqual(code, 0, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_noop_packages_fail(self):
        home = ("/", "Coursera homepage Learn without limits")
        for task in range(42):
            with self.subTest(task=task):
                code, verdict = self.grade(task, [home], "")
                self.assertNotEqual(code, 0)
                self.assertFalse(verdict["pass"])
                self.assertEqual(verdict["reason"], "answer_nonempty")

    def test_shortcut_packages_fail(self):
        # task 37 ("browse the homepage and list three free courses") is a
        # homepage-only task by design: every run starts on the homepage, so a
        # trajectory-level shortcut probe is vacuous for it. Its contract is
        # enforced by the no-op (empty answer), wrong-answer and task-id probes.
        for task in range(42):
            if task == 37:
                continue
            with self.subTest(task=task):
                _, answer = POS[task]
                code, verdict = self.grade(
                    task, [("/", "Coursera homepage Learn without limits")], answer)
                self.assertNotEqual(code, 0)
                self.assertFalse(verdict["pass"])

    def test_wrong_answers_fail(self):
        for task in range(42):
            with self.subTest(task=task):
                visits, _ = POS[task]
                code, verdict = self.grade(task, visits, WRONG[task])
                self.assertNotEqual(code, 0)
                self.assertFalse(verdict["pass"])

    def test_t29_price_digit_boundary(self):
        # ACCEPT.md §7 item 4: the T29 price tokens used to be substring
        # matches, so a 10x price embedding the true price ("$3990 ... $3090
        # ...") PASSed. The price checks now carry digit boundaries (the
        # (?<!\d) guard pct_of uses); the same genuine mirror navigation with
        # an embedded-digit price must FAIL on the price checks, while the
        # exact $399 price still PASSes.
        visits, answer = POS[29]
        code, verdict = self.grade(29, visits, answer)
        self.assertEqual(code, 0, verdict)
        self.assertTrue(verdict["pass"], verdict)

        # 10x annual price + 10x discount (both embed the true tokens)
        code, verdict = self.grade(
            29, visits, "One year of Coursera Plus costs $3990, with a discount "
            "of $3090 (430% off). Companies that work with Coursera include "
            "Google, IBM, and Meta.")
        self.assertNotEqual(code, 0)
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["reason"], "answer_year_price")

        # correct annual price but a 10x discount ("$3090" embeds "309")
        code, verdict = self.grade(
            29, visits, "One year of Coursera Plus costs $399, with a discount "
            "of $3090 (430% off). Companies that work with Coursera include "
            "Google, IBM, and Meta.")
        self.assertNotEqual(code, 0)
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["reason"], "answer_discount")

    def test_wrong_task_id_fails(self):
        for task in range(42):
            with self.subTest(task=task):
                visits, answer = POS[task]
                code, verdict = self.grade(task, visits, answer,
                                           task_id="Coursera--999")
                self.assertNotEqual(code, 0)
                self.assertEqual(verdict["reason"], "task_id_matches")

    def test_missing_trajectory_fails_closed(self):
        for task in (0, 15, 29, 41):
            with self.subTest(task=task):
                visits, answer = POS[task]
                code, verdict = self.grade(task, visits, answer,
                                           with_trajectory=False)
                self.assertNotEqual(code, 0)
                self.assertEqual(verdict["reason"], "run_package_invalid")

    def test_missing_screenshots_fails_closed(self):
        for task in (2, 17, 38):
            with self.subTest(task=task):
                visits, answer = POS[task]
                code, verdict = self.grade(task, visits, answer,
                                           with_screenshots=False)
                self.assertNotEqual(code, 0)
                self.assertEqual(verdict["reason"], "run_package_invalid")

    def test_external_origin_spoof_fails(self):
        # correct-looking navigation + answer, but on the REAL coursera.org:
        # must FAIL (only the loopback mirror counts).
        visits = [("https://www.coursera.org/learn/modern-art-ideas",
                   "Modern Art & Ideas The Museum of Modern Art")]
        with tempfile.TemporaryDirectory(prefix="coursera-ext-") as tmp:
            root = Path(tmp)
            initial, after = self._dbs(root)
            run_dir = write_package(root, "Coursera--30",
                                    [("https://www.coursera.org/learn/modern-art-ideas",
                                      "Modern Art & Ideas The Museum of Modern Art")],
                                    "8% of ratings are 3 stars and 1 star is the lowest.",
                                    start="https://www.coursera.org/")
            code, verdict = run_verifier(30, run_dir, initial, after)
            self.assertNotEqual(code, 0)
            self.assertFalse(verdict["pass"])

    def test_state_mismatch_fails(self):
        def add_saved(con):
            con.execute(
                "INSERT INTO saved_courses(id, user_id, course_id, saved_at) "
                "VALUES((SELECT COALESCE(MAX(id),0)+1 FROM saved_courses), "
                "(SELECT id FROM users WHERE email='alice.j@test.com'), "
                "(SELECT id FROM courses WHERE slug='modern-art-ideas'), "
                "'2026-09-20 10:00:00')")
        for task in (0, 15, 30, 39):
            with self.subTest(task=task):
                visits, answer = POS[task]
                code, verdict = self.grade(task, visits, answer,
                                           mutate_after=add_saved)
                self.assertNotEqual(code, 0)
                self.assertEqual(verdict["reason"], "read_only_db")

    def test_tampered_navigation_fails(self):
        # navigation URL present but the observed DOM never showed the course:
        # the page-content check must FAIL (fabricated trajectory).
        visits = [("/learn/modern-art-ideas", "Some unrelated page content")]
        code, verdict = self.grade(30, visits,
                                   "8% of ratings are 3 stars and 1 star is the lowest.")
        self.assertNotEqual(code, 0)
        self.assertFalse(verdict["pass"])


    def test_card_path_positives_pass(self):
        # the search-results card alone exports the facts for these tasks
        for task in sorted(CARD_POS):
            with self.subTest(task=task):
                dom, answer = CARD_POS[task]
                url = "/search?q=Python+Data+Science&sort=newest" if task == 3 \
                    else SEARCH
                code, verdict = self.grade(task, [(url, dom)], answer)
                self.assertEqual(code, 0, verdict)
                self.assertTrue(verdict["pass"], verdict)

    def test_card_path_without_course_in_dom_fails(self):
        # a search page that never showed the qualifying course card must not
        # rescue a recalled answer
        for task in sorted(CARD_POS):
            with self.subTest(task=task):
                dom, answer = CARD_POS[task]
                code, verdict = self.grade(
                    task, [(SEARCH, "Results: some unrelated course list")], answer)
                self.assertNotEqual(code, 0)
                self.assertFalse(verdict["pass"])


if __name__ == "__main__":
    unittest.main()

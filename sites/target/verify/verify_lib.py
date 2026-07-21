#!/usr/bin/env python3
"""verify_lib.py — shared deterministic + LLM utilities for Target task verification.

Philosophy: DETERMINISTIC FIRST.
  1. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the relevant on-site page. A correct answer with no matching
     navigation is a memory-recall shortcut = FAIL. This matters more on a
     retail mirror than elsewhere: a model may "know" that Red Baron pizza
     exists, but it cannot know THIS mirror's prices or nutrition rows.
  2. Answer check: exact / numeric / token-containment against frozen ground
     truth hardcoded in each verify_N.py — never read from tasks.jsonl.
  3. DB after-state check (stateful tasks): query the SQLite instance DB
     directly. Cart contents, wishlist rows and placed orders are the
     strongest deterministic signal that a flow actually completed.
  4. LLM utilities are used ONLY where exact matching is brittle, and are
     ALWAYS anchored on ground truth: the model verifies *presence* of given
     content, it never supplies knowledge. One call each.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: fetched instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: fetched live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-review)
  --no_llm           skip LLM-based checks (run deterministic-only)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import base64, json, os, re, sqlite3, subprocess, sys, tempfile, urllib.request
from pathlib import Path
from dataclasses import dataclass

SITE = "target"

BENCHMARK_PASSWORD = "TestPass123!"


# ---------------------------------------------------------------- trajectory
def load_run(run_dir):
    d = Path(run_dir)
    traj = json.loads((d / "trajectory.json").read_text())
    traj["_run_dir"] = d
    traj["_shots"] = {p.name: p for p in sorted((d / "screenshots").glob("step_*.png"))}
    return traj


def step_urls(traj):
    return [s.get("url", "") for s in traj.get("steps", [])]


def navigated_to(traj, substr, times=1):
    """Deterministic: at least `times` trajectory steps have a URL containing substr."""
    return sum(1 for u in step_urls(traj) if substr in u) >= times


def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


def visited_product(traj, sku):
    """The agent opened this specific product's detail page."""
    return navigated_to(traj, f"/product/{sku}")


def searched_for(traj, *terms):
    """A /search (or filtered listing) URL carried every one of these terms.

    Query strings are URL-encoded, so compare on a normalised form where
    '+', '%20' and literal spaces are all equivalent.
    """
    def norm_url(u):
        return u.replace("+", " ").replace("%20", " ").lower()
    urls = [norm_url(u) for u in step_urls(traj) if "q=" in u]
    return any(all(t.lower() in u for t in terms) for u in urls)


def final_answer(traj):
    return (traj.get("final_answer") or "").strip()


def _shot(traj, name):
    if not name:
        return None
    p = traj["_shots"].get(Path(name).name)
    return p if (p and p.exists()) else None


def shot_after_url(traj, substr):
    """screenshot_after path of the first step whose URL contains substr."""
    for s in traj.get("steps", []):
        if substr in s.get("url", ""):
            p = _shot(traj, s.get("screenshot_after"))
            if p:
                return p
    return None


def last_shot(traj):
    for s in reversed(traj.get("steps", [])):
        p = _shot(traj, s.get("screenshot_after")) or _shot(traj, s.get("screenshot_before"))
        if p:
            return p
    shots = sorted(traj["_shots"].values())
    return shots[-1] if shots else None


# ---------------------------------------------------------------- deterministic answer match
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def answer_equals(final, expected):
    return norm(final) == norm(expected)


def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)


def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)


def numbers_in(text):
    """Every number in the text, as floats. '$12.99' -> [12.99]; '1,240' -> [1240.0]."""
    out = []
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", text or ""):
        try:
            out.append(float(m.group(0).replace(",", "")))
        except ValueError:
            pass
    return out


def has_number(text, value, tol=0.001):
    """The answer states this number. Tolerant of $, commas and trailing units."""
    return any(abs(n - value) <= tol for n in numbers_in(text))


def has_money(text, amount):
    """Currency match that tolerates '12.99' / '$12.99' / '12.99 USD'.

    Tolerance is deliberately below one cent: $249.98 is a different answer
    from $249.99, and only float representation noise should be absorbed.
    """
    return has_number(text, round(float(amount), 2), tol=0.005)


# ---------------------------------------------------------------- DB state
def fetch_db(container, kind):
    """kind: 'instance' (after-state) or 'instance_seed' (initial-state)."""
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{SITE}.db"
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    r = subprocess.run(["docker", "cp", src, path], capture_output=True, text=True)
    if r.returncode != 0:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise RuntimeError(f"docker cp {src} failed: {r.stderr.strip()}")
    return path


def resolve_db(arg, container, kind):
    if arg:
        return arg
    try:
        return fetch_db(container, kind)
    except Exception:
        return None  # caller treats None as "unavailable" and FAILs that check


def db_query(db_path, sql, params=()):
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


# --- product-side reads (ground truth is hardcoded per task; these are for
# --- cross-checking that the mirror still holds what the verifier expects)
def product_row(db_path, sku):
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT sku, name, price, list_price, rating, review_count, percent_recommended "
        "FROM products WHERE sku=?", (sku,))
    if not rows:
        return None
    keys = ("sku", "name", "price", "list_price", "rating", "review_count",
            "percent_recommended")
    return dict(zip(keys, rows[0]))


# --- user-side after-state reads
def cart_for(db_path, email):
    """[(sku, name, quantity)] currently in this user's cart, ordered by sku."""
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT p.sku, p.name, c.quantity FROM cart_items c "
        "JOIN users u ON u.id = c.user_id JOIN products p ON p.id = c.product_id "
        "WHERE u.email = ? ORDER BY p.sku", (email,))
    return [tuple(r) for r in rows]


def cart_skus(db_path, email):
    rows = cart_for(db_path, email)
    return None if rows is None else [r[0] for r in rows]


def wishlist_skus(db_path, email):
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT p.sku FROM wishlist_items w "
        "JOIN users u ON u.id = w.user_id JOIN products p ON p.id = w.product_id "
        "WHERE u.email = ? ORDER BY p.sku", (email,))
    return [r[0] for r in rows]


def orders_for(db_path, email):
    """[(order_number, status, total, fulfillment_method)] oldest first."""
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT o.order_number, o.status, o.total, o.fulfillment_method FROM orders o "
        "JOIN users u ON u.id = o.user_id WHERE u.email = ? ORDER BY o.id", (email,))
    return [tuple(r) for r in rows]


def new_orders(initial_db, after_db, email):
    """Orders that exist in the after-state but not the initial state.

    This is how a 'place an order' task is proven: the flow must have created
    a row, not merely reached a confirmation-looking page.
    """
    before = orders_for(initial_db, email)
    after = orders_for(after_db, email)
    if before is None or after is None:
        return None
    seen = {o[0] for o in before}
    return [o for o in after if o[0] not in seen]


def order_items(db_path, order_number):
    """[(sku, item_name, quantity)] on a given order."""
    if not db_path:
        return None
    rows = db_query(db_path,
        "SELECT p.sku, oi.item_name, oi.quantity FROM order_items oi "
        "JOIN orders o ON o.id = oi.order_id LEFT JOIN products p ON p.id = oi.product_id "
        "WHERE o.order_number = ? ORDER BY oi.id", (order_number,))
    return [tuple(r) for r in rows]


def user_exists(db_path, name=None, email=None):
    if not db_path:
        return None
    rows = db_query(db_path, "SELECT full_name, email FROM users")
    return any((name is None or r[0] == name) and (email is None or r[1] == email)
               for r in rows)


def db_unchanged_for(initial_db, after_db, email):
    """True when this user's cart, wishlist and orders are all untouched.

    Used by read-only tasks: an answer-only task should not have mutated state,
    and a no-op run should not accidentally satisfy a stateful task.
    """
    parts = (cart_for, wishlist_skus, orders_for)
    for fn in parts:
        a, b = fn(initial_db, email), fn(after_db, email)
        if a is None or b is None or a != b:
            return False
    return True


# ---------------------------------------------------------------- shared LLM utilities (anchored)
# Unified LLM config, same env vars as agent.py / eval_judge.py:
#   OPENAI_API_KEY, OPENAI_BASE_URL, JUDGE_MODEL
import simpleArgParser as sap

# When --no_llm is set (via Judge), the llm_* helpers short-circuit so verifiers
# that call them directly (before j.check(llm=True)) still make ZERO LLM calls.
_NO_LLM = False


def _llm_config():
    key = os.environ.get("OPENAI_API_KEY", "")
    base = os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("JUDGE_MODEL", "")
    return key, base, model


def _chat(messages, max_tokens=1024):
    """One LLM call against the configured OpenAI-compatible endpoint."""
    if _NO_LLM:
        return None
    key, base, model = _llm_config()
    if not (key and base and model):
        return None  # no LLM configured -> callers treat as non-PASS
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "temperature": 1.0}
    req = urllib.request.Request(base,
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=180).read())
    except Exception:
        return None  # caller treats None as a non-PASS; never raises
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def _verdict(out):
    if not out:
        return False, "<no reply from LLM>"
    s = out.strip()
    return s.upper().startswith("PASS"), s


def llm_text_match(agent_answer, ground_truth, question):
    """One LLM call: does agent_answer answer question AND stay consistent with
    the frozen ground truth? The model gets the ground truth as an anchor and is
    told NOT to use its own knowledge."""
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
    out = _chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\nQuestion: {question}\n"
        f"Ground-truth answer (ANCHOR — judge against THIS, never use your own knowledge): {ground_truth}\n"
        f"Agent's answer: {agent_answer}\n"
        f"Decide PASS or FAIL ignoring case/punctuation/word order/surrounding prose. "
        f"PASS only if the agent's answer is consistent with the ground truth AND actually answers the question. "
        f"Line 1: PASS or FAIL. Line 2: one-sentence reason."}])
    return _verdict(out)


def llm_screenshot_shows(shot_path, must_show, question=""):
    """One vision LLM call: does this screenshot visibly render the expected content?"""
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
    b64 = base64.b64encode(Path(shot_path).read_bytes()).decode()
    out = _chat([{"role": "user", "content": [
        {"type": "text", "text":
            f"You are a STRICT binary grader. Only what is VISIBLY rendered in this screenshot counts.\n"
            f"Question the page should answer: {question}\n"
            f"Expected content to verify PRESENCE of: {must_show}\n"
            f"PASS only if the expected content (or a semantically equivalent on-screen answer) is visibly shown. "
            f"Do NOT use prior knowledge — judge only the rendered pixels.\n"
            f"Line 1: PASS or FAIL. Line 2: quote the visible evidence."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}])
    return _verdict(out)


def llm_asked_for_clarification(agent_answer, options, what):
    """Disambiguation tasks: the agent should ask WHICH one, not silently pick.

    Anchored on the actual ambiguous options so the grader can tell a genuine
    clarifying question from a confident wrong guess.
    """
    if _NO_LLM:
        return False, "[skipped: --no_llm]"
    out = _chat([{"role": "user", "content":
        f"You are a STRICT binary grader.\n"
        f"The user asked the agent to: {what}\n"
        f"This is AMBIGUOUS because these options all match: {options}\n"
        f"Agent's final response: {agent_answer}\n"
        f"PASS only if the agent recognised the ambiguity and asked the user which one they meant "
        f"(or explicitly listed the options and requested a choice). "
        f"FAIL if the agent silently picked one, or acted without asking.\n"
        f"Line 1: PASS or FAIL. Line 2: one-sentence reason."}])
    return _verdict(out)


# ---------------------------------------------------------------- judge harness + CLI
class Judge:
    def __init__(self, task_id, no_llm=False):
        global _NO_LLM
        _NO_LLM = bool(no_llm)   # gate the llm_* helpers at the source
        self.task_id = task_id
        self.no_llm = no_llm
        self.ok = True
        self.reason = ""
        self.evidence = []

    def check(self, name, cond, evidence="", llm=False):
        if llm and self.no_llm:
            self.evidence.append(f"[SKIP] {name} (--no-llm)")
            return True
        if cond:
            self.evidence.append(f"[PASS] {name}: {evidence}")
        else:
            self.ok = False
            if not self.reason:
                self.reason = name   # record the FIRST failing check
            self.evidence.append(f"[FAIL] {name}: {evidence}")
        return bool(cond)

    def emit(self):
        print(json.dumps({"task_id": self.task_id, "pass": self.ok,
                          "reason": self.reason, "evidence": self.evidence}, indent=2))
        sys.exit(0 if self.ok else 1)


def parse_args():
    @dataclass
    class VerifyArgs:
        run_dir: str = ""
        initial_db: str = ""
        after_db: str = ""
        container: str = os.environ.get("WH_CONTAINER", "wh-review")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)

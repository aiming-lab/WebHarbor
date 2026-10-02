#!/usr/bin/env python3
"""verify_lib.py — shared deterministic utilities for Amazon task verification.

Philosophy (same contract as the merriam_webster / phet_simulations exemplars):
DETERMINISTIC FIRST.
  1. Run-package gate: a run dir is only gradeable when it holds a parseable
     trajectory.json with non-empty steps whose referenced screenshots exist,
     a matching task id, an on-site start URL, and a non-empty final answer.
     Missing files / missing trajectory / empty answer => structured FAIL.
  2. Trajectory navigation check (anti knowledge-shortcut): the agent MUST have
     opened the on-site page(s) that carry the task's facts; a correct answer
     with no matching navigation is a recall shortcut = FAIL.
  3. Answer check: token / price containment against ground truth hardcoded in
     each verify_<n>.py (ground truth confirmed on the served mirror pages; the
     catalog is fixed by the seed DB and the mirror has no wall-clock content).
  4. DB state check: read-only tasks require the instance DB to be identical to
     its seed snapshot (anonymous carts are cookie-backed, so an honest run of
     any task in this task file leaves the DB untouched). DBs are fetched with
     docker cp from the site container (default $WH_CONTAINER or wh-ver-amazon),
     or passed explicitly via --initial_db / --after_db.

No LLM is needed anywhere in this suite; --no_llm is accepted for interface
compatibility with agent_demo/eval_judge.py and the site-wide CLI shape.

Input signature (per task):
  --run_dir DIR      agent trajectory dir: trajectory.json + screenshots/step_NNN.png
  --initial_db PATH  initial-state SQLite DB (default: instance_seed from container)
  --after_db PATH    after-state  SQLite DB (default: live instance DB from container)
  --container NAME   docker container to fetch DBs from (default: $WH_CONTAINER or wh-ver-amazon)
  --no_llm           accepted no-op (deterministic-only suite)
Output: JSON {task_id, pass, reason, evidence[]} to stdout; exit 0 on PASS, 1 on FAIL.
"""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

SITE = "amazon"
DB_FILENAME = "amazon_store.db"

TABLES = ("users", "categories", "products", "cart_items", "orders",
          "order_items", "wishlist_items", "reviews", "payment_methods",
          "saved_addresses", "returns", "return_items")


# ---------------------------------------------------------------- run package
class RunPackageError(Exception):
    pass


def expected_task_id():
    """Amazon--<n> inferred from the verify_<n>.py entry-point filename."""
    m = re.fullmatch(r"verify_(\d+)", Path(sys.argv[0]).stem)
    return f"{SITE.title()}--{m.group(1)}" if m else None


def load_run(run_dir):
    """Load and structurally validate the run package. Raises RunPackageError."""
    d = Path(run_dir)
    if not d.is_dir():
        raise RunPackageError(f"run_dir does not exist: {d}")
    traj_path = d / "trajectory.json"
    if not traj_path.exists():
        raise RunPackageError(f"missing trajectory.json under {d}")
    try:
        traj = json.loads(traj_path.read_text())
    except Exception as e:
        raise RunPackageError(f"trajectory.json is not valid JSON: {e}")
    if not isinstance(traj, dict):
        raise RunPackageError("trajectory.json must contain a JSON object")

    expected = expected_task_id()
    task_id = traj.get("task_id")
    if expected and task_id != expected:
        raise RunPackageError(f"task_id mismatch: expected {expected!r}, got {task_id!r}")
    if not isinstance(task_id, str) or not task_id.strip():
        raise RunPackageError("task_id must be a non-empty string")

    start_url = traj.get("start_url") or ""
    if "/search" in start_url or "/product" in start_url:
        pass  # still the site origin; allowed
    if not re.match(r"^https?://", start_url):
        raise RunPackageError(f"start_url must be an http(s) URL, got {start_url!r}")

    shots_dir = d / "screenshots"
    if not shots_dir.is_dir():
        raise RunPackageError(f"missing screenshots/ directory under {d}")
    shots = {p.name: p for p in sorted(shots_dir.glob("step_*.png"))}
    if not shots:
        raise RunPackageError("no step_*.png screenshots under screenshots/")

    steps = traj.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RunPackageError("trajectory must hold a non-empty steps list")

    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            raise RunPackageError(f"step {i} is not an object")
        if not (s.get("url") or s.get("url_after")):
            raise RunPackageError(f"step {i} has no url / url_after")
        for field in ("screenshot_before", "screenshot_after"):
            name = s.get(field)
            if isinstance(name, str) and name:
                if Path(name).name not in shots:
                    raise RunPackageError(
                        f"step {i} references {field} {name!r} which is missing from screenshots/")

    traj["_run_dir"] = d
    traj["_shots"] = shots
    return traj


def load_run_checked(run_dir, judge):
    try:
        return load_run(run_dir)
    except RunPackageError as e:
        judge.check("run_package_valid", False, str(e))
        judge.emit()


def final_answer(traj):
    return (traj.get("final_answer") or "").strip()


# ---------------------------------------------------------------- navigation
def search_evidence_url(url):
    """Recognize canonical search routes without weakening the task's filters."""
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, unquote
    try:
        p = urlsplit(url)
    except ValueError:
        return url
    path = p.path
    query = parse_qsl(p.query, keep_blank_values=True)
    if p.path == '/s':
        path = '/search'
        term = (next((v for k, v in query if k == 'q'), '')
                or next((v for k, v in query if k == 'k'), ''))
        query = [('q', term)] + [(k, v) for k, v in query if k not in ('q', 'k')]
        return urlunsplit((p.scheme, p.netloc, path, urlencode(query), p.fragment))
    return url


def step_urls(traj):
    """Every recorded step URL (before + after the action) in chronological order."""
    out = []
    for s in traj.get("steps", []):
        for field in ("url", "url_after"):
            u = s.get(field)
            if isinstance(u, str) and u:
                out.append(search_evidence_url(u))
    return out


def navigated_to(traj, substr, times=1):
    """Case-insensitive substring match on recorded step URLs."""
    needle = substr.lower()
    return sum(1 for u in step_urls(traj) if needle in u.lower()) >= times


def navigated_any(traj, substrs):
    return any(navigated_to(traj, s) for s in substrs)


def visited_product(traj, slug):
    return navigated_to(traj, f"/product/{slug}")


def visited_root(traj):
    """True when some step URL is the bare site origin (the mirror homepage)."""
    return any(re.match(r"^https?://[^/]+/?$", u) for u in step_urls(traj))


def search_url_with(traj, must_have_all):
    """True when some visited URL is a /search (or /c/) page whose query string
    contains every required param substring (e.g. ['q=xbox', 'color=green'])."""
    for u in step_urls(traj):
        if "/search" not in u and "/c/" not in u:
            continue
        if all(m.lower() in u.lower() for m in must_have_all):
            return True
    return False


# ---------------------------------------------------------------- answer matching
def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def contains_all(final, tokens):
    f = norm(final)
    return all(norm(t) in f for t in tokens)


def contains_any(final, tokens):
    f = norm(final)
    return any(norm(t) in f for t in tokens)


def _strip_thousands(text):
    """Drop commas that group thousands ($1,299.99). A comma decimal (64,99)
    has only two digits after it and is left alone."""
    return re.sub(r"(?<=\d),(?=\d{3}\b)", "", text or "")


def price_in(final, price):
    """True when the answer mentions the given price as its own amount.

    64.99 matches '$64.99' / '64.99' / 'USD 64.99' and does not match '$164.99'.
    179.00 matches '179.00', '$179', '179 dollars', or bare '179', and does not
    match '$179.95'. 1299.99 matches '$1,299.99'."""
    raw = norm(final)
    f = _strip_thousands(raw)
    if abs(price - round(price)) > 1e-9:
        txt = f"{price:.2f}"
        alt = txt.replace(".", ",")
        return bool(re.search(r"(?<![\d.])" + re.escape(txt) + r"(?![\d])", f)
                    or re.search(r"(?<![\d.])" + re.escape(alt) + r"(?![\d])", raw))
    whole = str(int(round(price)))
    return bool(re.search(
        r"(?<![\d.])" + whole + r"(?:\.00)?(?![\d])(?!\.\d*[1-9])", f))


# --------------------------------------------- subject binding (mutual nearest)
#
# A price belongs to a product only when the two mentions are mutually nearest
# within _PRICE_BIND_WINDOW: the price's nearest product label is that product,
# and that label's nearest price is this price. Co-presence anywhere in the
# answer is not attribution, so swapping two products' prices does not still
# count. Spec numbers (9.5 mm rope, 60m, 8000 BTU, 4.7 stars, 10 colors) are
# not prices; a price is a $ amount, an amount written with cents, or
# "N dollars".

_PRICE_BIND_WINDOW = 240
_DOLLAR_RE = re.compile(r"(?:\$|\busd\s*)\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?![\d]|\.\d)")
_CENTS_RE = re.compile(
    r"(?<![\d.$])(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2,})(?![\d])")
_DOLLARS_WORD_RE = re.compile(
    r"(?<![\d.$])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{2}))?\s+dollars?\b", re.I)


def _num_eq(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return False


def _gap(a, b):
    if a[1] <= b[0]:
        return b[0] - a[1]
    if b[1] <= a[0]:
        return a[0] - b[1]
    return 0


def _overlaps(start, end, spans):
    return any(not (end <= s or e <= start) for s, e in spans)


def _price_value(whole, cents):
    raw = whole.replace(",", "")
    return float(f"{raw}.{cents}") if cents is not None else float(raw)


# List items are separated by commas, semicolons, or "and" outside parentheses.
# A comma between digits is a thousands separator, not a boundary. Commas inside
# "(8000 BTU, CEER 7.0)" or "(was $9.99)" stay in the product's clause.
_THRESHOLD_RE = re.compile(
    r"\bbetween\s+\$\s*\d[\d,]*(?:\.\d{2})?\s+and\s+\$\s*\d[\d,]*(?:\.\d{2})?"
    r"|(?:\b(?:under|below|over|above|at least|less than|more than|up to)\s+)"
    r"\$\s*\d[\d,]*(?:\.\d{2})?"
    r"|\$\s*\d[\d,]*(?:\.\d{2})?\s*(?:-|to)\s*\$\s*\d[\d,]*(?:\.\d{2})?",
    re.I,
)


# Prefer each sentence or table row when attaching values to subjects.
# Commas and conjunctions remain soft boundaries for multi-fact prose.
_STATEMENT_END = re.compile(r"\n|[!?]|\.(?!\d)(?=\s|$)")
_NEGATED = re.compile(r"\b(?:not(?!\s+only\b)|never|isn't|isnt|wasn't|wasnt|aren't|arent)\b", re.I)


class _BindingClauses(list):
    def __init__(self, ranges, text):
        super().__init__(ranges)
        self.text = text
        self.boundaries = list(_STATEMENT_END.finditer(text))

    def same_statement(self, a, b):
        low, high = sorted((a[0], b[0]))
        return not any(low < m.start() < high for m in self.boundaries)

    def affirmative(self, label, value):
        start, end = min(label[0], value[0]), max(label[1], value[1])
        # Include a negator directly before the subject/value as well as one
        # between them, but not a separate earlier clause.
        prefix = self.text[:start]
        prefix = re.split(r"[;,:\n.!?]", prefix)[-1]
        prefix = re.split(r"\band\b", prefix)[-1]
        return not _NEGATED.search(prefix + self.text[start:end])


def _clause_ranges(text):
    text = text or ""
    ranges = []
    last = 0
    depth = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
        elif depth == 0 and (ch in ",;" or text.startswith("and", i)):
            if ch in ",;":
                if ch == ",":
                    before = text[i - 1] if i else ""
                    after = text[i + 1] if i + 1 < len(text) else ""
                    if before.isdigit() and after.isdigit():
                        i += 1
                        continue
                ranges.append((last, i))
                last = i + 1
            elif (i == 0 or not text[i - 1].isalnum()) and (
                    i + 3 == len(text) or not text[i + 3].isalnum()):
                ranges.append((last, i))
                last = i + 3
                i += 3
                continue
        i += 1
    ranges.append((last, len(text)))
    return _BindingClauses(ranges or [(0, 0)], text)


def _clause_index(pos, ranges):
    for index, (start, end) in enumerate(ranges):
        if start <= pos < end:
            return index
    return max(0, len(ranges) - 1)


def _touches_clause(span, clauses, origin):
    start, end = clauses[origin]
    return span[0] < end and span[1] > start


def _nearest(span, others, window, clauses, prefer):
    """Nearest span of the preferred side.

    Catalog answers read 'product at $price', so a product prefers the price
    that follows it and a price prefers the product that precedes it. That
    keeps 'Honeywell ... at $409.99. The BLACK+DECKER is the cheapest' on
    Honeywell even when the later name is closer to the amount. Same-clause
    spans beat other clauses. The other side is used only when the preferred
    side has nothing, so '$29.99 Amazon Essentials' still binds.
    """
    local = [other for other in others
             if clauses.same_statement(span, other) and _gap(span, other) <= window]
    others = local or others
    origin = _clause_index(span[0], clauses)
    buckets = {key: [] for key in (
        "in_follow", "in_precede", "out_follow", "out_precede")}
    for other in others:
        if other[0] == span[0] and other[1] == span[1]:
            continue
        gap = _gap(span, other)
        if gap > window:
            continue
        if other[0] >= span[1]:
            side = "follow"
        elif other[1] <= span[0]:
            side = "precede"
        else:
            continue
        same = (_touches_clause(other, clauses, origin)
                or _touches_clause(span, clauses, _clause_index(other[0], clauses)))
        same = same and clauses.same_statement(span, other)
        buckets[("in_" if same else "out_") + side].append(((gap, other[0]), other))
    if prefer == "follow":
        order = ("in_follow", "in_precede", "out_follow", "out_precede")
    else:
        order = ("in_precede", "in_follow", "out_precede", "out_follow")
    for key in order:
        if buckets[key]:
            return min(buckets[key], key=lambda item: item[0])[1]
    return None


def _binds(label, value, value_spans, labels, window, clauses):
    nearest = _nearest(label, value_spans, window, clauses, "follow")
    if nearest is None or not _num_eq(nearest[2], value):
        return False
    if not clauses.affirmative(label, nearest):
        return False
    back = _nearest(nearest, labels, window, clauses, "precede")
    return back is not None and back[0] == label[0] and back[1] == label[1]


def _threshold_ranges(text):
    return [(m.start(), m.end()) for m in _THRESHOLD_RE.finditer(text or "")]


def _price_spans(text):
    spans = []
    occupied = []
    thresholds = _threshold_ranges(text)
    for pattern in (_DOLLAR_RE, _DOLLARS_WORD_RE, _CENTS_RE):
        for match in pattern.finditer(text or ""):
            start, end = match.start(), match.end()
            if _overlaps(start, end, occupied) or _overlaps(start, end, thresholds):
                continue
            occupied.append((start, end))
            spans.append((start, end, _price_value(match.group(1), match.group(2))))
    return spans


def _label_spans(text, aliases, competitor_groups):
    entries = [(alias, "target") for alias in aliases if alias]
    for index, group in enumerate(competitor_groups):
        for alias in group:
            if alias:
                entries.append((alias, f"c{index}"))
    entries.sort(key=lambda item: len(item[0]), reverse=True)
    spans = []
    for alias, tag in entries:
        for match in re.finditer(r"\b" + re.escape(alias) + r"\b", text or "", re.I):
            if _overlaps(match.start(), match.end(), [(s, e) for s, e, _ in spans]):
                continue
            spans.append((match.start(), match.end(), tag))
    return spans


def price_bound_to(final, aliases, price, competitor_groups=()):
    """True when `price` is mutually nearest to this product, not merely
    co-present with its name. `aliases` name the product; each competitor
    group is the alias list of another product."""
    text = "\n".join(norm(line) for line in (final or "").splitlines())
    labels = _label_spans(text, aliases, competitor_groups)
    prices = _price_spans(text)
    clauses = _clause_ranges(text)
    targets = [span for span in labels if span[2] == "target"]
    return any(_binds(label, price, prices, labels, _PRICE_BIND_WINDOW, clauses)
               for label in targets)


def _color_count_spans(text):
    found = []
    occupied = []
    patterns = (
        re.compile(r"(\d+)\s+colors?\b"),
        re.compile(r"colors?\s*[:=]\s*(\d+)"),
        re.compile(r"(\d+)\s+color\s+options\b"),
    )
    for pattern in patterns:
        for match in pattern.finditer(text or ""):
            start, end = match.start(1), match.end(1)
            if _overlaps(start, end, occupied):
                continue
            occupied.append((start, end))
            found.append((start, end, float(match.group(1))))
    return found


def price_and_count_bound_to(final, aliases, price, count, competitor_groups=()):
    """One mention of the product owns both this price and this color count."""
    text = "\n".join(norm(line) for line in (final or "").splitlines())
    labels = _label_spans(text, aliases, competitor_groups)
    prices = _price_spans(text)
    counts = _color_count_spans(text)
    clauses = _clause_ranges(text)
    targets = [span for span in labels if span[2] == "target"]
    window = _PRICE_BIND_WINDOW
    return any(
        _binds(label, price, prices, labels, window, clauses)
        and _binds(label, count, counts, labels, window, clauses)
        for label in targets
    )


def first_mention(final, tokens):
    """Index (in the normalized answer) of the earliest occurrence among tokens,
    or None when none of them appears. Used for ordering-sensitive answers."""
    f = norm(final)
    idxs = [f.find(norm(t)) for t in tokens if f.find(norm(t)) >= 0]
    return min(idxs) if idxs else None


def count_claim(final, number, word):
    """True when the answer claims `number` of `word`, tolerating up to three
    attributive words in between ('24 vibrant colors', '24 colors') or the
    number after the word ('colors: 24', 'colors — 24')."""
    f = norm(final)
    return bool(re.search(rf"(?<![\d.]){number}(?![\d])(\s+[a-z-]+){{0,3}}\s+{word}s?\b", f)) \
        or bool(re.search(rf"{word}s?[^.;]{{0,20}}(?<![\d.]){number}(?![\d])", f))


def mentions_percent_for(final, name_tokens, pct):
    """True when the answer mentions the product (all name tokens) together with
    the exact discount percentage (e.g. '-33%', '33% off')."""
    if not contains_all(final, name_tokens):
        return False
    f = norm(final)
    return bool(re.search(rf"(?<!\d){pct}\s?%", f))


def extract_color_count_claim(final):
    """Return the number the answer claims as the total color count, best-effort:
    looks for '<n> [attr] colors' / 'colors: <n>' / '<n> color options'."""
    f = norm(final)
    m = re.search(r"(\d+)(\s+[a-z]+){0,3}\s+colors?\b", f) or \
        re.search(r"colors?\s*[:=]?\s*(\d+)", f) or \
        re.search(r"(\d+)\s*color\s*options", f)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- DB state
def fetch_db(container, kind):
    """kind: 'instance' (after-state) or 'instance_seed' (initial-state)."""
    src = f"{container}:/opt/WebSyn/{SITE}/{kind}/{DB_FILENAME}"
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
        return None  # caller FAILs the check that needs it


def db_fingerprint(db_path):
    """Content fingerprint of the benchmark tables: (rows, sha256)."""
    if not db_path:
        return None
    con = sqlite3.connect(db_path)
    try:
        parts = []
        for t in TABLES:
            try:
                rows = con.execute(f"SELECT * FROM {t}").fetchall()
            except sqlite3.Error:
                rows = []
            blob = json.dumps([list(map(repr, r)) for r in rows], default=str)
            parts.append(f"{t}:{len(rows)}:{hashlib.sha256(blob.encode()).hexdigest()[:16]}")
        return ";".join(parts)
    finally:
        con.close()


def read_only_run(initial_db, after_db):
    """True when the after-state DB is byte-for-row identical to the seed state.
    None when either DB is unavailable."""
    a = db_fingerprint(initial_db)
    b = db_fingerprint(after_db)
    if a is None or b is None:
        return None
    return a == b


def db_table_rows(db_path, table):
    if not db_path:
        return None
    con = sqlite3.connect(db_path)
    try:
        try:
            return con.execute(f"SELECT * FROM {table}").fetchall()
        except sqlite3.Error:
            return []
    finally:
        con.close()


def db_delta(initial_db, after_db, allowed_cart_products=(), allowed_wishlist_products=()):
    """Classify the DB delta of a run against the seed state.

    Returns (ok, detail): ok=True when the only differences are additions of
    cart_items / wishlist_items rows whose product_id is in the task's allowed
    product set — exactly the state change the task wording invites ("add to
    cart", "save"). Every other table must be identical; a modified or deleted
    existing row, or an added row for an unrelated product, is a violation.
    None when either DB is unavailable.
    """
    if not initial_db or not after_db:
        return None, "initial/after DB unavailable"
    violations = []
    allowed_added = []
    allowed_cart = set(allowed_cart_products)
    allowed_wish = set(allowed_wishlist_products)
    for table in TABLES:
        before = db_table_rows(initial_db, table)
        after = db_table_rows(after_db, table)
        if before == after:
            continue
        bset = {repr(r) for r in before}
        aset = {repr(r) for r in after}
        added = [r for r in after if repr(r) not in bset]
        removed = [r for r in before if repr(r) not in aset]
        if removed:
            violations.append(f"{table}: {len(removed)} row(s) removed/changed")
        if not added:
            continue
        if table == "cart_items":
            for row in added:
                pid = row[2] if len(row) > 2 else None
                if pid in allowed_cart:
                    allowed_added.append(("cart_items", pid))
                else:
                    violations.append(
                        f"cart_items: added row for product_id={pid} (not an allowed product for this task)")
        elif table == "wishlist_items":
            for row in added:
                pid = row[2] if len(row) > 2 else None
                if pid in allowed_wish:
                    allowed_added.append(("wishlist_items", pid))
                else:
                    violations.append(
                        f"wishlist_items: added row for product_id={pid} (not an allowed product for this task)")
        else:
            violations.append(f"{table}: {len(added)} row(s) added (no table writes are allowed)")
    if violations:
        return False, "; ".join(violations)[:300]
    if allowed_added:
        return True, "db = seed + allowed cart/wishlist adds " + str(sorted(set(allowed_added)))
    return True, "db identical to seed"


def db_query(db_path, sql, params=()):
    if not db_path:
        return []
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


# ---------------------------------------------------------------- judge harness + CLI
class Judge:
    def __init__(self, task_id, no_llm=False):
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
    import simpleArgParser as sap

    @dataclass
    class VerifyArgs:
        run_dir: str = ""
        initial_db: str = ""
        after_db: str = ""
        container: str = os.environ.get("WH_CONTAINER", "wh-ver-amazon")
        no_llm: bool = False

        def post_process(self):
            if not self.run_dir:
                raise SystemExit("--run_dir is required")
    return sap.parse_args(VerifyArgs)


def grade_common(judge, a, allowed_cart_products=(), allowed_wishlist_products=()):
    """Package gate + non-empty answer + DB-state check shared by every task.
    Returns (traj, final_answer). The DB check is strict read-only unless the
    task passes an allowed product set (cart/wishlist adds the task invites)."""
    t = load_run_checked(a.run_dir, judge)
    fa = final_answer(t)
    judge.check("final_answer_nonempty", bool(fa), f"final={fa[:120]!r}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    ok, detail = db_delta(init, after, allowed_cart_products, allowed_wishlist_products)
    if ok is None:
        judge.check("db_state", False,
                    "initial/after DB unavailable (container not running?)")
    else:
        judge.check("db_state", ok, detail)
    return t, fa

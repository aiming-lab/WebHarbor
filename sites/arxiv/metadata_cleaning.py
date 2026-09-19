"""Conservative cleanup of duplicated LaTeX/math fragments in arXiv metadata.

Mixed text/MathJax extraction sometimes concatenates the same fragment twice,
for example ``\\mathbb{P}^1\\mathbb{P}^1`` or ``z=1.37z=1.37``. This helper
only collapses those *adjacent* duplicates. It does not rewrite unrelated
prose, double primes (``\\prime\\prime``), ``\\log \\log``, or identifiers
such as ``K_{11,11}``.
"""
from __future__ import annotations

import re

# Commands that are routinely written twice on purpose (arcseconds, etc.).
_NO_COLLAPSE_CMDS = (
    "prime",
    "circ",
    "dag",
    "dagger",
    "ast",
    "star",
    "bullet",
)

_LATEX_CMD = (
    r"\\(?!(?:" + "|".join(_NO_COLLAPSE_CMDS) + r")\b)[A-Za-z]+"
    r"(?:\{(?:[^{}]|\{[^{}]*\})*\})?"
    r"(?:[_^](?:\{[^{}]+\}|[0-9A-Za-z+-]+))*"
    r"(?:=[0-9A-Za-z]+)?"
)

# Adjacent copies of a LaTeX command, optionally with a " 100\times" tail.
_DUP_LATEX_RE = re.compile(
    rf"((?:{_LATEX_CMD})(?:\s+\d+)?(?:\\times)?)\1"
)
# z=1.37z=1.37 (redshift / similar scalar duplicates)
_DUP_Z_RE = re.compile(r"\b(z\s*=\s*[0-9]+(?:\.[0-9]+)?)\1", re.I)
# GL(d_1)\times GL(d_2)GL(d_1)\times GL(d_2)
_DUP_TIMES_PRODUCT_RE = re.compile(
    r"((?:[A-Za-z]+\([^)]{1,40}\)(?:\s*\\times\s*)){1,4}"
    r"[A-Za-z]+\([^)]{1,40}\))\1"
)
# (D+1)(D+1), (L^{2},H^{-1})(L^{2},H^{-1}), S(2,7,505)S(2,7,505)
_DUP_PARENS_RE = re.compile(r"(\([^()]{1,40}\))\1")
# K_{11,11}K_{11,11}, ζ{(2)}ζ{(2)}
_DUP_BRACED_ATOM_RE = re.compile(r"([^\s\\][_^]?\{[^{}]{1,40}\})\1")
# WE_6WE_6, K_4K_4
_DUP_TYPED_INDEX_RE = re.compile(r"\b([A-Za-z]+_\d+)\1")
# CFT_3_3, AdS_4_4, WSe_2_2, CaF_2_2
_DUP_SUBSCRIPT_RE = re.compile(r"\b([A-Za-z]+)_(\d+)_\2\b")
# MoS{}_2{}_2
_DUP_EMPTY_SUB_RE = re.compile(r"(\{\}_\d+)\1")
# ^{229}^{229}Th
_DUP_ISOTOPE_RE = re.compile(r"(\^\{?\d+\}?)\1")
# CH^+^+, Yb^+^+
_DUP_ION_PLUS_RE = re.compile(r"(\^\+)\1")
# $...$$...$ or $...$ $...$
_DUP_MATH_DOLLARS_RE = re.compile(r"(\$[^$]{1,160}\$)\s*\1")
# Spectroscopic transition duplicated with a space.
_DUP_SPACED_TRANSITION_RE = re.compile(
    r"(\^[0-9A-Za-z]+_\{[^}]+\}\\rightarrow\s*\{[^}]+\}[A-Za-z]*_\{[^}]+\})\s+\1"
)

_DUP_LOOP_PATTERNS = (
    _DUP_LATEX_RE,
    _DUP_Z_RE,
    _DUP_TIMES_PRODUCT_RE,
    _DUP_PARENS_RE,
    _DUP_BRACED_ATOM_RE,
    _DUP_TYPED_INDEX_RE,
    _DUP_EMPTY_SUB_RE,
    _DUP_ISOTOPE_RE,
    _DUP_ION_PLUS_RE,
    _DUP_MATH_DOLLARS_RE,
    _DUP_SPACED_TRANSITION_RE,
)

# Restore math delimiters only for fragments the issue called out, and only
# when a duplicate of that fragment was actually collapsed.
_WRAP_GTRSIM_RE = re.compile(r"(?<!\$)(\\gtrsim\s+\d+\\times)(?!\$)")
_WRAP_Z_RE = re.compile(r"(?<!\$)\b(z=[0-9]+(?:\.[0-9]+)?)(?!\$)", re.I)

_METADATA_FIELDS = ("title", "abstract", "comments", "journal_ref")


def clean_arxiv_metadata_text(text):
    """Collapse adjacent duplicated LaTeX/math fragments in one metadata string.

    Returns ``text`` unchanged when it is empty/None or contains no adjacent
    duplicates. Idempotent: ``clean(clean(x)) == clean(x)``.
    """
    if text is None:
        return text
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return text

    had_gtrsim_dup = bool(
        re.search(r"(\\gtrsim\s+\d+\\times)\1", text)
    )
    had_z_dup = bool(_DUP_Z_RE.search(text))

    cleaned = text
    previous = None
    # Bound the loop so a pathological pattern cannot spin forever.
    for _ in range(20):
        if cleaned == previous:
            break
        previous = cleaned
        for pattern in _DUP_LOOP_PATTERNS:
            cleaned = pattern.sub(r"\1", cleaned)
        cleaned = _DUP_SUBSCRIPT_RE.sub(r"\1_\2", cleaned)

    if had_gtrsim_dup:
        cleaned = _WRAP_GTRSIM_RE.sub(r"$\1$", cleaned)
    if had_z_dup:
        cleaned = _WRAP_Z_RE.sub(r"$\1$", cleaned)
    return cleaned


def clean_paper_metadata_fields(paper_like) -> dict:
    """Return ``{field: cleaned}`` for fields whose cleaned value differs.

    ``paper_like`` may be a mapping or any object with the metadata attributes
    ``title``, ``abstract``, ``comments``, and ``journal_ref``.
    """
    changed = {}
    for field in _METADATA_FIELDS:
        if isinstance(paper_like, dict):
            current = paper_like.get(field) or ""
        else:
            current = getattr(paper_like, field, None) or ""
        cleaned = clean_arxiv_metadata_text(current)
        if cleaned != current:
            changed[field] = cleaned
    return changed

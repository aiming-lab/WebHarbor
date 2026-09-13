"""Metadata cleanup helpers for arXiv seed data."""

import re


_DUP_LATEX_FRAGMENT_RE = re.compile(
    r"("
    r"(?:\\[A-Za-z]+(?:\{[^{}]*\})?(?:[_^]\{?[^{}\s]+\}?)*)"
    r"(?:=[0-9A-Za-z_.+-]+)?"
    r"(?:\s*(?:\\times|\\rightarrow|to|-|\+)\s*)?"
    r"(?:[A-Za-z0-9_.{}^+\-/]+)?"
    r")\1"
)
_DUP_PLAIN_FRAGMENT_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_.+-]{1,}(?:\s+[A-Za-z0-9_.+-]{1,}){0,5})\1\b"
)
_DUP_Z_VALUE_RE = re.compile(r"\b(z\s*=\s*[0-9.]+)\1\b")
_DUP_ISOTOPE_RE = re.compile(r"(\^\{?\d+\}?)(?=\1)")
_DUP_ION_PLUS_RE = re.compile(r"(\^[A-Za-z0-9_/{}+-]+)\+(?=\+)")
_DUP_TIMES_EXPR_RE = re.compile(r"([A-Za-z]+\([^)]{1,30}\)\\times [A-Za-z]+\([^)]{1,30}\))\1")
_DUP_ADJACENT_MATH_RE = re.compile(r"(\$[^$]{1,120}\$)\s*\1")
_HREF_RE = re.compile(r"\\href\{([^{}]*)\}\{([^{}]*)\}")
_URL_RE = re.compile(r"\\url\{([^{}]*)\}")

_GREEK = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "lambda": "λ",
    "mu": "μ",
    "nu": "ν",
    "phi": "φ",
    "pi": "π",
    "sigma": "σ",
    "theta": "θ",
    "upsilon": "υ",
    "zeta": "ζ",
}

_SYMBOLS = {
    "approx": "≈",
    "bullet": "•",
    "cdot": "·",
    "epsilon": "ε",
    "geq": "≥",
    "gt": ">",
    "gtrsim": "≥",
    "in": "∈",
    "infty": "∞",
    "leq": "≤",
    "log": "log",
    "lt": "<",
    "nabla": "∇",
    "odot": "⊙",
    "pm": "±",
    "prime": "′",
    "rightarrow": "→",
    "sim": "∼",
    "sqrt": "√",
    "textendash": "–",
    "times": "×",
    "to": "→",
}
_SYMBOLS.update(_GREEK)


def clean_arxiv_metadata_text(text):
    """Repair scrape artifacts from mixed text/MathJax extraction."""
    if not text:
        return text
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    cleaned = _HREF_RE.sub(r"\2", cleaned)
    cleaned = _URL_RE.sub(r"\1", cleaned)
    previous = None
    while cleaned != previous:
        previous = cleaned
        cleaned = _DUP_LATEX_FRAGMENT_RE.sub(r"\1", cleaned)
        cleaned = _DUP_Z_VALUE_RE.sub(r"\1", cleaned)
        cleaned = _DUP_TIMES_EXPR_RE.sub(r"\1", cleaned)
        cleaned = _DUP_PLAIN_FRAGMENT_RE.sub(r"\1", cleaned)
        cleaned = _DUP_ISOTOPE_RE.sub(r"\1", cleaned)
        cleaned = _DUP_ION_PLUS_RE.sub(r"\1+", cleaned)
    cleaned = re.sub(r"(\\mathcal\{N\}=)(\d+)\s+to\s+(\d+)", r"\1\2 to \3", cleaned)
    cleaned = re.sub(r"\bCFT_(\d+)_(?=\d+\b)", r"CFT_", cleaned)
    cleaned = re.sub(r"\bAdS_(\d+)_(?=\d+\b)", r"AdS_", cleaned)
    if r"\gtrsim 100\times" in cleaned and "$" not in cleaned:
        cleaned = cleaned.replace(r"\gtrsim 100\times", r"$\gtrsim 100\times$")
    cleaned = re.sub(r"(?<!\$)\bz=([0-9]+(?:\.[0-9]+)?)(?!\$)", r"$z=\1$", cleaned)
    previous = None
    while cleaned != previous:
        previous = cleaned
        cleaned = _DUP_ADJACENT_MATH_RE.sub(r"\1", cleaned)
    return cleaned


def _replace_tex_command(match):
    command = match.group(1)
    braced = match.group(2)
    if command in _SYMBOLS:
        return _SYMBOLS[command] + (braced or "")
    if command == "mathbb":
        return braced or ""
    if command == "mathcal":
        return braced or ""
    if command == "mathrm":
        return braced or ""
    if command == "mathbf":
        return braced or ""
    if command == "textbf":
        return braced or ""
    if command == "textit":
        return braced or ""
    if command == "textsc":
        return (braced or "").upper()
    if command == "texttt":
        return braced or ""
    if command == "emph":
        return braced or ""
    if command in {"operatorname", "mathsf", "mathit", "mathscr"}:
        return braced or ""
    if braced:
        return braced
    return "\\" + command


def _format_math_text(expr):
    expr = expr.replace(r"\,", "")
    expr = expr.replace(r"\ ", " ")
    expr = expr.replace("~", " ")
    expr = re.sub(r"\\([A-Za-z]+)(?:\{([^{}]*)\})?", _replace_tex_command, expr)
    expr = re.sub(r"\^\{([^{}]+)\}", r"^\1", expr)
    expr = re.sub(r"_\{([^{}]+)\}", r"_\1", expr)
    expr = expr.replace("{", "").replace("}", "")
    expr = re.sub(r"\s+", " ", expr).strip()
    return expr


def format_arxiv_display_text(text):
    """Return metadata text formatted for human-readable HTML display."""
    if not text:
        return text
    formatted = clean_arxiv_metadata_text(text)
    formatted = formatted.replace(r"\$", "$")
    formatted = _HREF_RE.sub(r"\2", formatted)
    formatted = _URL_RE.sub(r"\1", formatted)
    formatted = re.sub(r"\$([^$]{1,240})\$", lambda m: _format_math_text(m.group(1)), formatted)
    formatted = _format_math_text(formatted)
    formatted = re.sub(r"\s+", " ", formatted).strip()
    return formatted

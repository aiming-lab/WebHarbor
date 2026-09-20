"""Typed, entity-bound answer comparison. No substring or global-token grading."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime


def normalized(value):
    return (
        re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value)))
        .strip()
        .casefold()
    )


def number(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a number")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        text = normalized(value).replace(",", "")
        text = re.sub(r"^(?:usd\s*|\$\s*)", "", text)
        text = re.sub(r"\s*(?:dollars|usd|points|minutes)$", "", text)
        if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
            result = float(text)
        else:
            words = dict(
                zip(
                    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(),
                    range(20),
                )
            )
            words.update(
                dict(
                    zip(
                        "twenty thirty forty fifty sixty seventy eighty ninety".split(),
                        range(20, 100, 10),
                    )
                )
            )
            tokens = text.replace("-", " ").split()

            def below_hundred(parts):
                if len(parts) == 1 and parts[0] in words:
                    return words[parts[0]]
                if (
                    len(parts) == 2
                    and words.get(parts[0], 0) >= 20
                    and 1 <= words.get(parts[1], 0) <= 9
                ):
                    return words[parts[0]] + words[parts[1]]
                raise ValueError("not an exact numeric value")

            def below_thousand(parts):
                if len(parts) >= 2 and parts[1] == "hundred":
                    if not 1 <= words.get(parts[0], 0) <= 9:
                        raise ValueError("invalid hundreds")
                    rest = parts[2:]
                    if not rest:
                        return words[parts[0]] * 100
                    if rest[0] == "and":
                        rest = rest[1:]
                    return words[parts[0]] * 100 + below_hundred(rest)
                return below_hundred(parts)

            if "thousand" in tokens:
                if tokens.count("thousand") != 1:
                    raise ValueError("invalid thousands")
                split = tokens.index("thousand")
                thousands = below_thousand(tokens[:split])
                if not thousands:
                    raise ValueError("invalid thousands")
                rest = tokens[split + 1 :]
                if rest and rest[0] == "and":
                    rest = rest[1:]
                    if not rest:
                        raise ValueError("incomplete number")
                result = float(thousands * 1000 + (below_thousand(rest) if rest else 0))
            else:
                result = float(below_thousand(tokens))
    else:
        raise ValueError("not a number")
    if not math.isfinite(result):
        raise ValueError("non-finite value")
    return result


def equivalent(actual, expected):
    if isinstance(expected, bool):
        return type(actual) is bool and actual == expected
    if isinstance(expected, (int, float)):
        try:
            return abs(number(actual) - expected) < 0.000001
        except ValueError:
            return False
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(equivalent(actual[k], v) for k, v in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(equivalent(a, b) for a, b in zip(actual, expected))
        )
    if not isinstance(actual, str):
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", expected):
        for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%B %d %Y", "%m/%d/%Y"):
            try:
                if (
                    datetime.strptime(actual.strip(), fmt).strftime("%Y-%m-%d")
                    == expected
                ):
                    return True
            except ValueError:
                pass
        return False
    if re.fullmatch(r"\d{2}:\d{2}", expected):
        for fmt in ("%H:%M", "%I:%M %p"):
            try:
                if datetime.strptime(actual.strip(), fmt).strftime("%H:%M") == expected:
                    return True
            except ValueError:
                pass
        return False
    # Exact quoted labels/policy sentences tolerate case, whitespace and terminal
    # punctuation only; negation, additional claims and entity swaps do not.
    return normalized(actual).rstrip(".") == normalized(expected).rstrip(".")


def parse_answer(text):
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate answer key")
            result[key] = value
        return result

    result = json.loads(
        text,
        object_pairs_hook=unique,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
    )
    if not isinstance(result, dict):
        raise ValueError("answer must be one JSON object")
    return result

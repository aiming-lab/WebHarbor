"""Bounded checks for the support brief and delivery-planning comparisons."""
import re

from answers import affirmative, clauses, money, negative, norm


def support_order(text, ctx):
    order = ctx.get('order', {})
    number = order.get('order_number', '').lower()
    s = norm(text)
    if not number or set(re.findall(r'\bwa-\d{6}-\d+\b', s)) != {number}:
        return False
    if not affirmative(text, re.escape(number)):
        return False
    # Count bottles, not line items. Accept spelled-out counts and either order
    # of a label/value, without accepting an unrelated reference number.
    words = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6}
    counts = []
    for c in clauses(text):
        found = re.findall(r'\b(\d+|one|two|three|four|five|six)\s+(?:total\s+)?bottles?\b|\bbottles?\s*(?:count|total)?\s*[:|=]?\s*(\d+|one|two|three|four|five|six)\b', c)
        if found and negative(c):
            return False
        counts.extend(words.get(a or b, int(a or b) if (a or b).isdigit() else 0) for a, b in found)
    if not counts or any(v != ctx.get('bottles') for v in counts):
        return False
    totals = []
    for c in clauses(text):
        found = re.findall(r'\b(?:total(?: paid)?|paid|charged)\s*(?:is|was|of|:|\||=)?\s*\$?\s*(\d+(?:\.\d+)?)|\$\s*(\d+(?:\.\d+)?)\s*(?:total|paid|charged)\b', c)
        if found and negative(c):
            return False
        totals.extend(float(a or b) for a, b in found)
    return bool(totals) and all(abs(v - order['total']) < .005 for v in totals)


def club_comparison(text):
    # A normal Markdown table can put the unit in its column header.
    lines = text.splitlines()
    unit_column = None
    expanded = []
    for line in lines:
        cells = [c.strip() for c in line.strip('| ').split('|')]
        if len(cells) > 1:
            header = next((i for i, cell in enumerate(cells) if re.search(r'per bottle|/\s*bottle', cell, re.I)), None)
            if header is not None and not any(re.search(r'\d', cell) for cell in cells):
                unit_column = header
            elif unit_column is not None and len(cells) > unit_column and re.search(r'discovery|connoisseurs', line, re.I):
                cells[unit_column] += ' per bottle'
                line = ' | '.join(cells)
        else:
            unit_column = None
        expanded.append(line)
    text = '\n'.join(expanded)
    # Bind each explicitly requested per-bottle price to its club. Shipment
    # prices may accompany the arithmetic, but cannot substitute for unit cost.
    parts = re.split(r'\b(?:versus|vs\.?|compared with|compared to)\b|\band\s+(?=(?:the\s+)?(?:discovery|connoisseurs))', text.lower())
    seen = set()
    for part in parts:
        for c in clauses(part):
            names = [name for name in ('discovery', 'connoisseurs') if name in c]
            if len(names) != 1:
                continue
            name = names[0]
            unit = r'(?:per|a|each)\s+bottle|/\s*bottle'
            values = re.findall(r'(?:\$\s*|usd\s*)?(\d+(?:\.\d+)?)\s*(?:dollars?\s*)?(?:' + unit + r')|(?:' + unit + r')\s*(?:is|costs?|price|:|\||=|at)*\s*\$?\s*(\d+(?:\.\d+)?)', c)
            if values:
                expected = 27.5 if name == 'discovery' else 75
                if negative(c) or any(abs(float(a or b) - expected) >= .005 for a, b in values):
                    return False
                seen.add(name)
    if seen != {'discovery', 'connoisseurs'}:
        return False
    # Correct arithmetic alone is not the requested recommendation. Reject a
    # contrary recommendation even when correct prices also occur elsewhere.
    cheaper = r'cheaper|lower|less expensive|more affordable|recommend|choose|pick'
    for c in clauses(text):
        if re.search(r'connoisseurs.{0,25}(?:cheaper|lower|less expensive|more affordable).{0,15}discovery', c):
            return False
        if 'connoisseurs' in c and 'discovery' not in c and re.search(cheaper, c):
            return False
        if 'discovery' in c and re.search(r'more expensive|higher|not.{0,20}(?:cheaper|lower|recommend)', c):
            return False
    return any('discovery' in c and re.search(cheaper, c) and not negative(c) for c in clauses(text))

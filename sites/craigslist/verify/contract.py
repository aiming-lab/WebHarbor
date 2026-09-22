"""Reviewer-side expectations. No answers are shipped in agent-facing tasks.

Natural-answer checks cover bounded English clauses, tables and bullets, not
arbitrary semantic equivalence. The independent LLM judge remains secondary.
"""

OPEN = {
    0: [1, 2, 7],
    1: [35, 37],
    2: [20, 24],
    3: [28, 34],
    4: [35, 39],
    5: [],
    6: [],
    7: [35],
    8: [69, 71],
    9: [54, 55],
    10: [58],
    11: [60, 62],
    12: [],
    13: [34],
    14: [49, 50],
    15: [63],
    16: [25, 28, 34, 27],
    17: [77],
    18: [13, 16],
    19: [12, 14],
}
SAVE = {0: 2, 3: 28, 8: 71, 14: 49, 18: 13, 19: 12}
MESSAGE = {2: 24, 7: 35, 9: 55, 10: 58, 11: 60, 15: 63, 17: 77}

# Allowed monetary amounts per entity clause. An unrelated correct reference
# number cannot rescue a wrong advertised price in the same clause.
CURRENCY = {
    1: [{2498}, {2558}, None],
    4: [{2498, 5.45, 5.454}, {2765, 2.05, 2.050}, None],
    10: [{65}, {68}, None],
    11: [{60}, {120}],
    14: [{75}, {120}, {75}],
    15: [{285, 95}, None, {15}],
    18: [{65}, {1850}],
    19: [{119}, {675, 50}, None],
}

# Each fact is bound to a named entity within one paragraph/table row.
# Values require currency/measurement context; bare reference numbers cannot pass.
FACTS = {
    1: [
        (
            r"snell|san jose",
            r"\$\s*2,?498",
            r"458\s*(?:sq\.?\s*ft|square\s*feet|ft[²2])",
        ),
        (
            r"stoneridge|pleasanton",
            r"\$\s*2,?558",
            r"525\s*(?:sq\.?\s*ft|square\s*feet|ft[²2])",
        ),
        (
            r"laundry|washer",
            r"select (?:homes|units)|not guaranteed|not every|confirm.*unit",
        ),
    ],
    4: [
        (
            r"snell|san jose",
            r"\$\s*2,?498",
            r"458\s*(?:sq\.?\s*ft|square\s*feet|ft[²2])",
            r"\$\s*5\.45(?:4)?\b.*(?:sq|square|ft)",
        ),
        (
            r"oakland|23rd",
            r"\$\s*2,?765",
            r"1,?350\s*(?:sq\.?\s*ft|square\s*feet|ft[²2])",
            r"\$\s*2\.05(?:0)?\b.*(?:sq|square|ft)",
            r"lower|cheaper",
        ),
        (r"fees|charges", r"exclud|not includ|before|extra|additional"),
    ],
    7: [
        (r"wednesday|wed\b", r"5:30\s*p\.?m\.?|17:30"),
        (r"thursday|thu\b", r"noon|12(?::00)?\s*p\.?m\.?"),
    ],
    8: [
        (
            r"woodhams|comedy",
            r"wednesday|wed\b",
            r"8(?::00)?\s*p\.?m\.?|20:00",
            r"21\s*\+|21 (?:and|or) (?:over|older)",
        ),
        (
            r"castro|cleanup",
            r"saturday|sat\b",
            r"10(?::00)?\s*a\.?m\.?|10:00",
            r"children (?:are )?welcome|child.friendly|all ages",
        ),
    ],
    10: [
        (r"compensation|structured|field", r"\$\s*65(?:\.0+)?\b"),
        (r"description|body", r"\$\s*68\b.*(?:hour|/hr)"),
        (r"alameda", r"in.person|on.site", r"(?:2|two) days(?: a| per|/)?\s*week"),
    ],
    11: [
        (
            r"expert|phd|ph\.d",
            r"(?:start|from|minimum|as low).*\$\s*60\b.*(?:hour|/hr)",
        ),
        (r"cupertino", r"\$\s*120\b.*(?:hour|/hr)"),
    ],
    14: [
        (r"u2414h|24.inch", r"\$\s*75\b", r"1920\s*[x×]\s*1080|1080p"),
        (r"u2717d|27.inch", r"\$\s*120\b", r"2560\s*[x×]\s*1440|1440p"),
        (
            r"u2414h|24.inch",
            r"no (?:built.in )?speakers|(?:does not|doesn.t) have (?:built.in )?speakers",
        ),
    ],
    15: [
        (
            r"minimum|minimum charge",
            r"\$\s*285\b",
            r"(?:3|three).?hours?",
            r"\$\s*95\b",
        ),
        (r"fuel", r"extra|additional|exclud|not includ|plus"),
        (r"tips?", r"extra|additional|exclud|not includ|plus"),
    ],
    17: [
        (
            r"stevenson",
            r"9:45\s*(?:am|a.m.)?\s*[-–—to]+\s*12:45",
            r"(?:3|three) hours?",
        ),
        (r"downtown", r"10:30\s*(?:am|a.m.)?\s*[-–—to]+\s*12:30", r"(?:2|two) hours?"),
    ],
    18: [
        (
            r"antique|petaluma|1860",
            r"\$\s*65\b",
            r'29\s*(?:inches|in\b|["″])?.{0,8}(?:wide|w\b).*18.{0,8}(?:deep|d\b).*28.{0,8}(?:high|tall|h\b)|29\s*[x×]\s*18\s*[x×]\s*28',
            r'inches|\bin\b|["″]',
            r"finial",
            r"missing|broken|damage",
            r"cash",
        ),
        (
            r"knoll|executive",
            r"\$\s*1,?850\b",
            r'76\s*(?:inches|in\b|["″])?.{0,8}(?:wide|w\b).*36.{0,8}(?:deep|d\b).*29.{0,8}(?:high|tall|h\b)|76\s*[x×]\s*36\s*[x×]\s*29',
            r'inches|\bin\b|["″]',
        ),
    ],
    19: [
        (r"fezibo", r"\$\s*119\b", r'48\s*["″]?\s*[x×]\s*26', r"assembl", r"drill"),
        (
            r"workrite",
            r"\$\s*675\b",
            r'60\s*["″]?\s*[x×]\s*24',
            r"tax",
            r"panel",
            r"\$\s*50\b",
        ),
        (r"workrite|delivery", r"deliver", r"install", r"fee|extra|additional"),
    ],
}

BODY = {
    2: [
        r"weekend|saturday|sunday",
        r"pick.?up|collect",
        r"chain",
        r"gears?",
        r"rust",
        r"replac",
    ],
    7: [
        r"wednesday|wed\b",
        r"5:30\s*p\.?m\.?|17:30",
        r"choose|confirm|works|take|attend|book",
    ],
    9: [
        r"after\s*6\s*p\.?m\.?|after\s*18:00",
        r"pick.?up|collect",
        r"unflattened|not flattened",
        r"remain|left|available",
    ],
    10: [r"65", r"68", r"which|clarif|correct", r"(?:hour|/hr)", r"in.person|on.site"],
    11: [r"(?:two|2).*(?:slots?|times?)", r"ap calculus ab", r"next week"],
    15: [r"saturday morning", r"estimate|quote", r"fuel"],
    17: [r"downtown|429 bryant", r"volunteer|sign me up|help", r"10:30", r"12:30"],
}

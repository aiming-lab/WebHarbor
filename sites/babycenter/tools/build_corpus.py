#!/usr/bin/env python3
"""Turn the fetched source articles into the mirror's content corpus.

Design rules, in order of importance:

1. Every factual sentence the site serves is a **verbatim excerpt** from an
   openly licensed upstream article, carried with its source, section and the
   exact revision it came from.
2. Excerpts are located by explicit anchors. If an anchor stops matching --
   because the upstream article was edited -- the build **fails loudly** rather
   than silently dropping or inventing content.
3. No template text stands in for a fact. Presentation wording is clearly
   presentation; facts are quoted.

Input : sites/babycenter/source_data/wikipedia/*.json  (from fetch_sources.py)
Output: sites/babycenter/source_data/corpus.json       (tracked, deterministic)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "source_data" / "wikipedia"
OUT = HERE.parent / "source_data" / "corpus.json"

# --------------------------------------------------------------------------
# Pregnancy checkpoints.
#
# Only weeks that carry a real, citable clinical or developmental fact get a
# page. That is fewer pages than a commercial week-by-week guide, and it is the
# deliberate trade: every page here is sourced, none is filler.
#
# `baby`, `body` and `todo` are lists of (source-slug, anchor) pairs. The anchor
# is an exact substring of the upstream plain-text extract; the whole sentence
# containing it is quoted.
# --------------------------------------------------------------------------
WEEKS = [
    dict(week=4, stage="Embryo", title="Week 4: implantation and the first gland",
         baby=[("prenatal-development", "The thyroid is the first gland to develop")],
         body=[("prenatal-development", "the embryo implants 8 to 10 days after ovulation")],
         todo=[("prenatal-care", "monthly visits during the first two trimesters")]),
    dict(week=5, stage="Embryo", title="Week 5: first electrical brain activity",
         baby=[("prenatal-development", "Electrical brain activity is first detected")],
         body=[("pregnancy", "Blood and urine tests can detect pregnancy by 11 and 14 days")],
         todo=[("pregnancy", "Home pregnancy tests are urine tests")]),
    dict(week=6, stage="Embryo", title="Week 6: the early dating scan",
         baby=[("prenatal-development", "Rh antigen appears at about 40 days")],
         body=[("prenatal-testing", "early dating ultrasound scan may be offered")],
         todo=[("prenatal-care", "The WHO recommends that pregnant women receive at least eight antenatal visits")]),
    dict(week=8, stage="Embryo", title="Week 8: the immune system starts up",
         baby=[("prenatal-development", "The fetus starts producing leukocytes at 2 months")],
         body=[("pregnancy", "hCG levels double every 36 to 72 hours")],
         todo=[("gestational-age", "Such methods include adding 14 days to a known duration since fertilization")]),
    dict(week=10, stage="Fetus", title="Week 10: the embryo becomes a fetus",
         baby=[("prenatal-development", "the developing embryo is called a fetus")],
         body=[("pregnancy", "It ends at week 12 (11 weeks + 6 days of GA)")],
         todo=[("prenatal-testing", "Non-invasive prenatal genetic screening is typically performed")]),
    dict(week=12, stage="Fetus", title="Week 12: insulin secretion starts",
         baby=[("prenatal-development", "Insulin secretion in the fetus starts")],
         body=[("prenatal-testing", "Around weeks 11–13, nuchal translucency scan")],
         todo=[("prenatal-testing", "The triple test measures serum levels of AFP")]),
    dict(week=13, stage="Fetus", title="Week 13: the second trimester begins",
         baby=[("prenatal-development", "Allometric growth is observed during the first trimester")],
         body=[("pregnancy", "The second trimester is defined as starting")],
         todo=[("prenatal-testing", "amniocentesis, which can be done from about 14 weeks gestation")]),
    dict(week=15, stage="Fetus", title="Week 15: the quad test window opens",
         baby=[("prenatal-testing", "during the beginning of the second trimester (15–20 weeks)")],
         body=[("prenatal-care", "Obstetric ultrasounds are most commonly performed")],
         todo=[("prenatal-testing", "81% sensitivity and 5% false-positive rate")]),
    dict(week=18, stage="Fetus", title="Week 18: the anomaly scan window",
         baby=[("prenatal-testing", "this ultrasound is performed as a matter of routine prenatal care")],
         body=[("prenatal-testing", "The First Trimester Combined Test and the Triple/Quad test together")],
         todo=[("prenatal-testing", "The anomaly scan is performed between 18 and 22 weeks")]),
    dict(week=20, stage="Fetus", title="Week 20: the halfway mark",
         baby=[("prenatal-care", "Obstetric ultrasounds are most commonly performed during the second trimester")],
         body=[("pregnancy", "Women who have never carried a pregnancy more than 20 weeks")],
         todo=[("prenatal-testing", "A second-trimester Quad blood test may be taken")]),
    dict(week=22, stage="Fetus", title="Week 22: the perinatal period begins",
         baby=[("prenatal-development", "it is considered from 22 completed weeks")],
         body=[("gestational-age", "The WHO defines the perinatal period")],
         todo=[("prenatal-care", "Assessment of parental needs and family dynamics")]),
    dict(week=23, stage="Fetus", title="Week 23: the edge of viability",
         baby=[("gestational-age", "20 to 35 percent of babies born at 23 weeks")],
         body=[("gestational-age", "There is no sharp limit of development")],
         todo=[("gestational-age", "Prognosis depends also on medical protocols")]),
    dict(week=24, stage="Fetus", title="Week 24: survival odds climb",
         baby=[("gestational-age", "A baby's chances for survival increases 3–4% per day")],
         body=[("prenatal-care", "the symphysial fundal height (SFH) is measured")],
         todo=[("prenatal-care", "A review looking at routine ultrasounds past 24 weeks")]),
    dict(week=26, stage="Fetus", title="Week 26: hearing is fully formed",
         baby=[("prenatal-development", "After 26 weeks of gestation, the peripheral auditory system")],
         body=[("gestational-age", "After 26 weeks the rate of survival increases at a much slower rate")],
         todo=[("prenatal-care", "fortnightly visits from the 28th week to the 36th week")]),
    dict(week=28, stage="Fetus", title="Week 28: the third trimester begins",
         baby=[("pregnancy", "At 28 weeks, more than 90% of babies can survive")],
         body=[("gestational-age", "extremely preterm (fewer than 28 weeks)")],
         todo=[("prenatal-development", "the starting point of this period is considered 28 completed weeks")]),
    dict(week=30, stage="Fetus", title="Week 30: REM sleep appears",
         baby=[("prenatal-development", "REM sleep develops at around 30 weeks")],
         body=[("gestational-age", "childbirth has a standard deviation of 14 days")],
         todo=[("prenatal-testing", "Vaginal screening for GBS is performed")]),
    dict(week=34, stage="Fetus", title="Week 34: group B strep screening",
         baby=[("prenatal-testing", "Vaginal screening for GBS is performed between 34 and 37 weeks")],
         body=[("pregnancy", "Babies born before 37 weeks are preterm")],
         todo=[("prenatal-care", "weekly visits after 36th week to the delivery")]),
    dict(week=37, stage="Early term", title="Week 37: early term begins",
         baby=[("prenatal-development", "The growth rate of a fetus is linear up to 37 weeks")],
         body=[("pregnancy", "A pregnancy is considered term at 37 weeks of gestation")],
         todo=[("pregnancy", "Delivery before 39 weeks by labour induction")]),
    dict(week=39, stage="Full term", title="Week 39: full term begins",
         baby=[("gestational-age", "the normal pregnancy duration is assumed by medical professionals to be 280 days")],
         body=[("pregnancy", "The American College of Obstetricians and Gynecologists have recommended further division")],
         todo=[("gestational-age", "An estimated due date is given by Naegele's rule")]),
    dict(week=42, stage="Post term", title="Week 42: post term",
         baby=[("gestational-age", "Using the LMP (last menstrual period) method, a full-term human pregnancy")],
         body=[("pregnancy", 'Babies born between weeks 41 and 42 weeks are considered "late-term"')],
         todo=[("pregnancy", "It is preterm if less than 37 weeks and post-term")]),
]

# --------------------------------------------------------------------------
# Baby months. Sourced from the per-age sections of "Child development stages",
# which is the granularity that article actually supports.
# --------------------------------------------------------------------------
MONTHS = [
    dict(month=0, section="Newborn", title="Your newborn"),
    dict(month=1, section="One month old", title="Your baby at 1 month"),
    dict(month=2, section="Two months old", title="Your baby at 2 months"),
    dict(month=3, section="Three months old", title="Your baby at 3 months"),
    dict(month=4, section="Four months old", title="Your baby at 4 months"),
    dict(month=6, section="Six months old", title="Your baby at 6 months"),
    dict(month=7, section="Seven months old", title="Your baby at 7 months"),
    dict(month=10, section="8–12 months", title="Your baby at 8 to 12 months"),
    dict(month=18, section="Toddler (12–24 months)", title="Your toddler at 12 to 24 months"),
    dict(month=24, section="Two-year-old", title="Your two-year-old"),
]

# The source article documents each age as Physical / Motor / Language-Social.
# Those are the fields the site carries. It would be dishonest to file this text
# under "feeding" and "sleep" headings the source never wrote.
MONTH_FIELDS = [
    ("physical", ["Physical development", "Physical"]),
    ("motor", ["Motor development", "Motor skills", "Motor"]),
    ("communication", ["Communication skills", "Communication and language skills",
                       "Language development", "Language", "Cognitive skills",
                       "Cognitive", "Social development", "Social and emotional",
                       "Sensory development"]),
]
ALL_BLOCK_LABELS = {l for _, ls in MONTH_FIELDS for l in ls} | {
    "Social development", "Sensory development", "Cognitive skills", "Emotional development"}
# Not every age section carries all three; a missing block is recorded as null
# rather than back-filled, but at least two must be present.
MIN_MONTH_BLOCKS = 2

# --------------------------------------------------------------------------
# Articles. Each is a real section of a source article, quoted.
# --------------------------------------------------------------------------
ARTICLES = [
    dict(slug="viability-and-preterm-birth", title="Viability and preterm birth",
         category="Pregnancy Health", trimester="Third trimester",
         source="gestational-age", section="Medical fetal viability"),
    dict(slug="how-births-are-classified", title="How births are classified by gestational age",
         category="Pregnancy Health", trimester="Third trimester",
         source="gestational-age", section="Birth classification"),
    dict(slug="what-prenatal-care-covers", title="What prenatal visits cover",
         category="Prenatal Care", trimester="First trimester",
         source="prenatal-care", section="Visits"),
    dict(slug="prenatal-screening-explained", title="Prenatal screening explained",
         category="Prenatal Testing", trimester="First trimester",
         source="prenatal-testing", section="Prenatal screening"),
    dict(slug="first-second-third-trimester-screen", title="First, second and third trimester screens",
         category="Prenatal Testing", trimester="Second trimester",
         source="prenatal-testing", section="First/Second/Third trimester Screen"),
    dict(slug="amniocentesis", title="Amniocentesis",
         category="Prenatal Testing", trimester="Second trimester",
         source="prenatal-testing", section="Amniocentesis"),
    dict(slug="chorionic-villus-sampling", title="Chorionic villus sampling",
         category="Prenatal Testing", trimester="First trimester",
         source="prenatal-testing", section="Chorionic Villus Sampling (CVS)"),
    dict(slug="the-three-trimesters", title="The three trimesters",
         category="Pregnancy Week by Week", trimester="First trimester",
         source="pregnancy", section="Trimesters"),
    dict(slug="fetal-growth-rate", title="How fetal growth rate changes",
         category="Baby Development", trimester="Third trimester",
         source="prenatal-development", section="Growth rate"),
    dict(slug="fetal-cognitive-development", title="Fetal cognitive development",
         category="Baby Development", trimester="Second trimester",
         source="prenatal-development", section="Cognitive development"),
    dict(slug="breastfeeding-benefits", title="Benefits of breastfeeding",
         category="Baby Feeding", trimester="Postpartum",
         source="breastfeeding", section="Health effects"),
    dict(slug="infant-sleep-approaches", title="Approaches to infant sleep",
         category="Baby Sleep", trimester="Postpartum",
         source="infant-sleep", section="Development of sleep over the first year"),
]


# --------------------------------------------------------------------------

def load(slug: str) -> dict:
    p = SRC / f"{slug}.json"
    if not p.exists():
        sys.exit(f"missing source {p}; run tools/fetch_sources.py first")
    return json.loads(p.read_text())


def sentence_at(text: str, anchor: str) -> str:
    """Return the full sentence containing `anchor`, verbatim."""
    i = text.find(anchor)
    if i < 0:
        raise LookupError(anchor)
    start = max(text.rfind(". ", 0, i) + 2, text.rfind("\n", 0, i) + 1, 0)
    m = re.compile(r"(?<=[.!?])(\s|$)").search(text, i + len(anchor))
    end = m.start() if m else min(len(text), i + len(anchor) + 260)
    return " ".join(text[start:end].split())


def section_text(doc: dict, heading: str, limit: int = 1400) -> str:
    """Return the body of a named section, verbatim, trimmed to whole sentences."""
    text = doc["text"]
    pat = re.compile(r"^(=+) *" + re.escape(heading) + r" *\1$", re.M)
    m = pat.search(text)
    if not m:
        raise LookupError(f"{doc['title']} :: section {heading!r}")
    level = len(m.group(1))
    nxt = None
    for candidate in re.finditer(r"^(=+) [^=\n]+ \1$", text[m.end():], re.M):
        if len(candidate.group(1)) <= level:
            nxt = candidate
            break
    end = m.end() + nxt.start() if nxt else len(text)
    body = text[m.end():end].strip()
    body = re.sub(r"^=+ *([^=\n]+?) *=+$", r"\1", body, flags=re.M)
    body = re.sub(r"\n+", "\n", body)
    if len(body) > limit:
        cut = body.rfind(". ", 0, limit)
        body = body[: cut + 1] if cut > 200 else body[:limit]
    return body.strip()


def sub_block(section_body: str, labels: list[str], limit: int = 700) -> str:
    """Pull a labelled block (e.g. 'Motor development') out of a section body."""
    lines = section_body.split("\n")
    for label in labels:
        for i, ln in enumerate(lines):
            if ln.strip().rstrip(":") == label:
                out = []
                for nxt in lines[i + 1:]:
                    s = nxt.strip()
                    if not s:
                        continue
                    if s.rstrip(":") in ALL_BLOCK_LABELS or (
                            len(s) < 40 and s.endswith(("development", "skills"))):
                        break
                    out.append(s)
                    if sum(len(x) for x in out) > limit:
                        break
                if out:
                    text = " ".join(out).strip()
                    if len(text) <= limit and text.endswith((".", "!", "?", ")")):
                        return text
                    effective_limit = min(limit, len(text))
                    sentence_ends = [
                        text.rfind(mark, 0, effective_limit)
                        for mark in (". ", "! ", "? ")
                    ]
                    cut = max(sentence_ends)
                    if cut < 120:
                        raise ValueError(
                            f"cannot trim {label!r} to a whole sentence within {limit} chars"
                        )
                    return text[: cut + 1].strip()
    return ""


def cite(doc: dict, section: str | None = None) -> dict:
    c = {
        "source_title": doc["title"],
        "revision_id": doc["revision_id"],
        "permanent_url": doc["permanent_url"],
        "licence": doc["licence"]["spdx"],
    }
    if section:
        c["section"] = section
    return c


def main() -> int:
    docs = {slug: load(slug) for slug in
            {s for w in WEEKS for s, _ in w["baby"] + w["body"] + w["todo"]}
            | {"child-development-stages"}
            | {a["source"] for a in ARTICLES}}
    problems: list[str] = []

    weeks_out = []
    for w in WEEKS:
        row = {"week": w["week"], "stage": w["stage"], "headline": w["title"],
               "citations": []}
        for field, key in (("baby_summary", "baby"), ("body_summary", "body"),
                           ("checklist", "todo")):
            parts, cites = [], []
            for slug, anchor in w[key]:
                doc = docs[slug]
                try:
                    parts.append(sentence_at(doc["text"], anchor))
                except LookupError:
                    problems.append(f"week {w['week']} {field}: anchor not found "
                                    f"in {slug} r{doc['revision_id']}: {anchor!r}")
                    continue
                cites.append(cite(doc))
            row[field] = " ".join(parts)
            row["citations"].extend(cites)
        # de-duplicate citations, preserve order
        seen, uniq = set(), []
        for c in row["citations"]:
            k = (c["source_title"], c["revision_id"])
            if k not in seen:
                seen.add(k)
                uniq.append(c)
        row["citations"] = uniq
        weeks_out.append(row)

    cds = docs["child-development-stages"]
    months_out = []
    for m in MONTHS:
        try:
            body = section_text(cds, m["section"], limit=4000)
        except LookupError as e:
            problems.append(f"month {m['month']}: {e}")
            continue
        row = {"month": m["month"], "headline": m["title"],
               "citations": [cite(cds, m["section"])]}
        present = 0
        for field, labels in MONTH_FIELDS:
            block = sub_block(body, labels)
            row[field] = block or None
            present += bool(block)
        if present < MIN_MONTH_BLOCKS:
            problems.append(f"month {m['month']}: only {present} sourced block(s) "
                            f"in section {m['section']!r}; need {MIN_MONTH_BLOCKS}")
        row["missing_fields"] = [f for f, _ in MONTH_FIELDS if not row[f]]
        months_out.append(row)

    articles_out = []
    for a in ARTICLES:
        doc = docs[a["source"]]
        try:
            body = section_text(doc, a["section"])
        except LookupError as e:
            problems.append(f"article {a['slug']}: {e}")
            continue
        summary = next(
            (line for line in body.split("\n") if len(line.strip()) >= 40),
            body.split("\n")[0],
        )
        if len(summary) > 260:
            cut = summary.rfind(". ", 0, 260)
            summary = summary[: cut + 1] if cut > 80 else summary[:260]
        if len(summary.strip()) < 40 or len(body.strip()) < 120:
            problems.append(
                f"article {a['slug']}: section {a['section']!r} is not substantive"
            )
        articles_out.append({
            "slug": a["slug"], "title": a["title"], "category": a["category"],
            "trimester": a["trimester"],
            "read_minutes": max(2, round(len(body.split()) / 200)),
            "summary": summary.strip(), "body": body,
            "citations": [cite(doc, a["section"])],
        })

    # No two pages may carry the same sentence in the same slot. Duplicated
    # filler is the exact defect this rebuild exists to remove, so it is a
    # build error, not a warning.
    for field in ("baby_summary", "body_summary", "checklist"):
        seen_txt: dict[str, int] = {}
        for row in weeks_out:
            prev = seen_txt.get(row[field])
            if prev is not None:
                problems.append(f"weeks {prev} and {row['week']} share the same "
                                f"{field}; give each week its own sourced fact")
            seen_txt[row[field]] = row["week"]
    for field, _ in MONTH_FIELDS:
        seen_txt = {}
        for row in months_out:
            if not row[field]:
                continue
            prev = seen_txt.get(row[field])
            if prev is not None:
                problems.append(f"months {prev} and {row['month']} share the same {field}")
            seen_txt[row[field]] = row["month"]

    if problems:
        print("CORPUS BUILD FAILED — upstream text no longer matches:", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 1

    corpus = {
        "licence": {
            "spdx": "CC-BY-SA-4.0",
            "url": "https://creativecommons.org/licenses/by-sa/4.0/",
            "notice": ("Site content is quoted from English Wikipedia and is reused "
                       "under CC BY-SA 4.0. Each page cites the article and the exact "
                       "revision it was taken from."),
        },
        "sources": {slug: {"title": d["title"], "revision_id": d["revision_id"],
                           "permanent_url": d["permanent_url"],
                           "text_sha256": d["text_sha256"]}
                    for slug, d in sorted(docs.items())},
        "weeks": weeks_out,
        "months": months_out,
        "articles": articles_out,
    }
    OUT.write_text(json.dumps(corpus, ensure_ascii=False, indent=1, sort_keys=False) + "\n")
    print(f"corpus: {len(weeks_out)} weeks, {len(months_out)} months, "
          f"{len(articles_out)} articles -> {OUT.relative_to(HERE.parent.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Parse the MTA's official railroad fare PDFs into source_data/railroad_fares.json.

Sources (all captured from new.mta.info /document/ endpoints):
- lirr_fares.pdf               LIRR station fare chart (zone map + zone-pair price matrix)
- mnr_harlem_hudson_gct.pdf    Metro-North Harlem/Hudson fares to Grand Central
- mnr_newhaven_gct.pdf         Metro-North New Haven fares to Grand Central
- port_jervis_pascack.pdf      Port Jervis / Pascack Valley fares (NJ Transit-operated)

LIRR: station -> zone comes from the chart's vertical band alignment plus
multi-line label pairing (all validated against the GTFS stop list), and the
zone-pair price matrix comes from the boxed tables (column order
1,3,4,7,9,10,12,14; the parsed matrix is checked for symmetry).
MNR: zone sections list their stations in the left column(s); ticket prices
follow per zone. Port Jervis/Pascack: per-station price blocks.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "source_data" / "fare_docs"
OUT = ROOT / "source_data"

LIRR_ZONES = ["1", "3", "4", "7", "9", "10", "12", "14"]


def norm_name(name: str) -> str:
    """Normalized key for station-name matching."""
    s = re.sub(r"[^A-Za-z0-9 ]", " ", name.upper())
    s = re.sub(r"\s+", " ", s).strip()
    # ordinal suffixes: 125TH == 125, 153RD == 153
    s = re.sub(r"\b(\d+)(?:ST|ND|RD|TH)\b", r"\1", s)
    # abbreviations
    s = re.sub(r"\bHTS\b", "HEIGHTS", s)
    s = re.sub(r"\bMOUNT\b", "MT", s)
    # unify street suffix and drop it (Harlem-125 St == Harlem-125th Street)
    s = re.sub(r"\bSTREET\b", "ST", s)
    s = re.sub(r"\bST$", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def load_gtfs_names(which: str) -> dict[str, str]:
    import csv
    import zipfile

    names: dict[str, str] = {}
    with zipfile.ZipFile(ROOT / "source_data" / "gtfs" / f"{which}.zip") as z:
        for row in csv.DictReader(z.read("stops.txt").decode("utf-8-sig").splitlines()):
            name = row["stop_name"].strip()
            names[norm_name(name)] = name
    return names


# --------------------------------------------------------------------------
# LIRR
# --------------------------------------------------------------------------

LIRR_ALIASES = {
    "FLUSHING": "Flushing Main Street",
    "ELMONT UBS": "Elmont-UBS Arena",
    "YAPHANK": "Yaphank-BNL",
}


def match_station_labels(slines: list[list], consumed: set, match_fn,
                         max_gap: float = 15.0, max_span: int = 4) -> list[tuple]:
    """Match station labels against visual word lines.

    Enumerates every candidate label — contiguous same-line word groups and
    two-line joins of x-adjacent groups — then applies matches longest-first
    so a wrapped label ("North White" + "Plains") always beats the shorter
    single-line read ("White Plains" stealing the second line's word).
    """
    candidates: list[tuple] = []
    # same-line contiguous groups
    for line in slines:
        for i in range(len(line)):
            for length in range(min(max_span, len(line) - i), 0, -1):
                words = line[i:i + length]
                name = match_fn(" ".join(w["text"] for w in words))
                if name:
                    candidates.append((length, tuple(id(w) for w in words), words, name))
    # two-line joins
    for li in range(len(slines)):
        for lj in range(li + 1, len(slines)):
            if slines[lj][0]["top"] - slines[li][0]["top"] > 30:
                break
            a, b = slines[li], slines[lj]
            for ai in range(len(a)):
                for bi in range(len(b)):
                    gap = max(a[ai]["x0"], b[bi]["x0"]) - min(a[ai]["x1"], b[bi]["x1"])
                    if gap > max_gap:
                        continue
                    for a_len in range(1, min(max_span, len(a) - ai) + 1):
                        for b_len in range(1, min(max_span, len(b) - bi) + 1):
                            words = a[ai:ai + a_len] + b[bi:bi + b_len]
                            name = match_fn(" ".join(w["text"] for w in words))
                            if name:
                                candidates.append((a_len + b_len, tuple(id(w) for w in words), words, name))
    candidates.sort(key=lambda c: -c[0])
    out: list[tuple] = []
    for _count, _ids, words, name in candidates:
        if any(id(w) in consumed for w in words):
            continue
        consumed.update(id(w) for w in words)
        top = sum(w["top"] for w in words) / len(words)
        out.append((name, top))
    return out


def parse_lirr() -> dict:
    import pdfplumber

    pdf = pdfplumber.open(DOCS / "lirr_fares.pdf")
    page = pdf.pages[0]
    words = page.extract_words()

    monthly_tops = [156, 335, 513, 692, 871, 1050, 1228, 1407]
    row_offsets = [
        ("Monthly", 0), ("Weekly", 19), ("One-Way Peak", 39), ("One-Way Off-Peak", 59),
        ("One-Way Senior/Disabled/Medicare", 79), ("Day Pass - Weekday", 98),
        ("Day Pass - Weekend", 117), ("Onboard Peak One-Way", 138), ("Onboard Off-Peak One-Way", 158),
    ]
    matrix = {}
    for zone, mtop in zip(LIRR_ZONES, monthly_tops):
        rows = {}
        for label, off in row_offsets:
            ws = [w for w in words if abs(w["top"] - (mtop + off)) < 3 and w["x0"] > 1000]
            ws = sorted(ws, key=lambda w: w["x0"])
            vals = []
            for w in ws:
                v = w["text"].replace("$", "").replace(",", "")
                vals.append(float(v) if re.fullmatch(r"\d+(\.\d+)?", v) else None)
            if len(vals) != 8 or any(v is None for v in vals):
                raise ValueError(f"zone {zone} row {label}: got {vals}")
            rows[label] = vals
        matrix[zone] = rows
    for i, a in enumerate(LIRR_ZONES):
        for j, b in enumerate(LIRR_ZONES):
            if matrix[a]["One-Way Peak"][j] != matrix[b]["One-Way Peak"][i]:
                raise ValueError(f"asymmetric LIRR fare {a}->{b}")

    boxes = [(150, 328, "1"), (328, 507, "3"), (507, 686, "4"), (686, 865, "7"),
             (865, 1044, "9"), (1044, 1222, "10"), (1222, 1401, "12"), (1401, 1580, "14")]
    mapwords = [w for w in words if w["x1"] < 805 and 150 < w["top"] < 1580]
    lines = []
    for w in sorted(mapwords, key=lambda w: (w["top"], w["x0"])):
        for ln in lines:
            if abs(ln["top"] - w["top"]) < 6:
                ln["words"].append(w)
                break
        else:
            lines.append({"top": w["top"], "words": [w]})

    gtfs = load_gtfs_names("lirr")

    def match_name(candidate: str) -> str | None:
        cand = re.sub(r"\*+", "", candidate).strip()
        cand = re.sub(r"\s*\(.*?\)$", "", cand).strip()
        key = norm_name(cand)
        if key in gtfs:
            return gtfs[key]
        if key in LIRR_ALIASES:
            return LIRR_ALIASES[key]
        return None

    def zone_of(top: float) -> str | None:
        return next((z for t, b, z in boxes if t <= top < b), None)

    stations: dict[str, str] = {}
    consumed: set[int] = set()

    word_list = sorted(mapwords, key=lambda w: (w["top"], w["x0"]))
    slines = [ln["words"] for ln in lines]
    for name, top in match_station_labels(slines, consumed, match_name):
        zone = zone_of(top)
        if zone:
            stations[name] = zone

    return {"zones": LIRR_ZONES, "matrix": matrix, "stations": stations}


# --------------------------------------------------------------------------
# Metro-North (Harlem/Hudson + New Haven)
# --------------------------------------------------------------------------

def _dedupe(word: str) -> str:
    """The zone headers are printed with doubled characters (ZZOONNEE11)."""
    if len(word) % 2 == 0 and word[::2] == word[1::2]:
        return word[::2]
    return word


def parse_mnr_pdf(pdf_path: pathlib.Path, station_x_max: float, label_x_min: float,
                  price_x_min: float) -> list[dict]:
    import pdfplumber

    gtfs = load_gtfs_names("metro_north")
    pdf = pdfplumber.open(pdf_path)
    sections: list[dict] = []
    for page in pdf.pages:
        words = page.extract_words()
        # zone markers: words like ZZOONNEE11, or ZZOONNEE + 1111 on one line
        zone_marks = []
        by_top: dict[int, list] = {}
        for w in words:
            by_top.setdefault(round(w["top"] / 4), []).append(w)
        for key in sorted(by_top):
            ws = sorted(by_top[key], key=lambda w: w["x0"])
            text = "".join(_dedupe(w["text"]) for w in ws)
            m = re.search(r"ZONE(\d+)", text)
            if m:
                zone_marks.append((int(m.group(1)), min(w["top"] for w in ws)))
        zone_marks.sort(key=lambda t: t[1])
        for zi, (zone, top) in enumerate(zone_marks):
            end_top = zone_marks[zi + 1][1] if zi + 1 < len(zone_marks) else 10_000
            sec_words = [w for w in words if top <= w["top"] < end_top]

            # stations: left column words, clustered into visual lines
            station_words = [w for w in sec_words if w["x1"] <= station_x_max]
            slines: list[list] = []
            for w in sorted(station_words, key=lambda w: w["top"]):
                if slines and w["top"] - slines[-1][-1]["top"] <= 5:
                    slines[-1].append(w)
                else:
                    slines.append([w])
            stations: list[str] = []
            consumed: set[int] = set()

            def _mnr_match(cand: str):
                key = norm_name(cand)
                return gtfs.get(key)

            for name, _top in match_station_labels(slines, consumed, _mnr_match):
                stations.append(name)

            # prices: rows built from label words + number words, clustered
            # into visual lines (labels and prices can sit 1-2pt apart)
            label_words = [w for w in sec_words if label_x_min <= w["x0"] < price_x_min]
            price_words = [w for w in sec_words if w["x0"] >= price_x_min]
            prow: list[list] = []
            for w in sorted(label_words + price_words, key=lambda w: w["top"]):
                if prow and w["top"] - prow[-1][-1]["top"] <= 5:
                    prow[-1].append(w)
                else:
                    prow.append([w])
            context = "adult"
            prices: dict[str, list[float]] = {}
            for line in prow:
                ws = sorted(line, key=lambda w: w["x0"])
                text = " ".join(w["text"] for w in ws)
                nums = [float(m.replace("$", "")) for m in re.findall(r"\$?\s*(\d+\.\d{2})", text)]
                if re.search(r"Senior", text):
                    context = "senior"
                    continue
                if re.search(r"Child", text):
                    context = "child"
                    continue
                if re.search(r"Adult", text):
                    context = "adult"
                    continue
                if re.search(r"Monthly", text):
                    prices["Monthly"] = nums
                elif re.search(r"Weekly", text):
                    prices["Weekly"] = nums
                elif re.search(r"Day\s*Pass", text):
                    prices["Day Pass"] = nums
                elif re.search(r"Onboard", text):
                    prices[f"Onboard ({context})"] = nums
                elif re.search(r"One.Way", text):
                    prices[f"One-Way ({context})"] = nums
                elif re.search(r"Family", text):
                    prices["Family Fare"] = nums
                elif re.search(r"LIRR Combo", text):
                    prices["LIRR Combo"] = nums
                elif re.search(r"10.Trip", text):
                    prices["10-Trip"] = nums
                elif re.search(r"Off-Peak Round", text):
                    prices.setdefault("Off-Peak Round-Trip", []).extend(nums)
            sections.append({"zone": str(zone), "stations": stations, "prices": prices})
    return sections


# --------------------------------------------------------------------------
# Port Jervis / Pascack Valley
# --------------------------------------------------------------------------

def parse_port_jervis() -> list[dict]:
    import pdfplumber

    pdf = pdfplumber.open(DOCS / "port_jervis_pascack.pdf")
    out: list[dict] = []
    for page in pdf.pages:
        words = page.extract_words()
        y_min, y_max = 120, page.height - 90
        # station-name words in the left column
        name_words = [w for w in words
                      if w["x0"] < 90 and re.match(r"^[A-Za-z]", w["text"])
                      and y_min < w["top"] < y_max]
        # group names into blocks: gaps > 40pt start a new block
        blocks: list[list] = []
        for w in sorted(name_words, key=lambda w: w["top"]):
            if blocks and w["top"] - blocks[-1][-1]["top"] < 40:
                blocks[-1].append(w)
            else:
                blocks.append([w])
        # drop header blocks ("Port Jervis" / "Pascack Valley" line names, To/From...)
        for bi, block in enumerate(blocks):
            start = block[0]["top"] - 20
            end = blocks[bi + 1][0]["top"] - 20 if bi + 1 < len(blocks) else page.height
            # join names: words on the same line merge; multi-line names merge
            names: list[str] = []
            names_top: list[float] = []
            for w in sorted(block, key=lambda w: (w["top"], w["x0"])):
                if names and abs(names_top[-1] - w["top"]) < 6:
                    names[-1] = (names[-1] + " " + w["text"]).strip()
                elif names and w["x0"] < 40 and names[-1].split()[-1].endswith("-"):
                    names[-1] = names[-1] + w["text"]
                else:
                    names.append(w["text"])
                names_top.append(w["top"])
            # prices in the block
            sec = [w for w in words if start <= w["top"] < end and w["x0"] >= 90]
            rows = {}
            for w in sec:
                key = round(w["top"] / 7)
                rows.setdefault(key, []).append(w)
            prices: dict[str, list[float]] = {}
            context = "adult"
            for key in sorted(rows):
                ws = sorted(rows[key], key=lambda w: w["x0"])
                text = " ".join(w["text"] for w in ws)
                nums = [float(m.replace("$", "")) for m in re.findall(r"\$?\s*(\d+\.\d{2})", text)]
                if re.search(r"Senior", text):
                    context = "senior"
                    continue
                if re.search(r"Child", text):
                    context = "child"
                    continue
                if re.search(r"Adult", text):
                    context = "adult"
                    continue
                if re.search(r"Monthly", text):
                    prices["Monthly"] = nums
                elif re.search(r"Weekly", text):
                    prices["Weekly"] = nums
                elif re.search(r"10.Trip", text):
                    prices["10-Trip"] = nums
                elif re.search(r"Off-Peak Round", text):
                    prices.setdefault(f"Off-Peak Round-Trip ({context})", []).extend(nums)
                elif re.search(r"Onboard", text):
                    prices[f"Onboard ({context})"] = nums
                elif re.search(r"One.Way", text):
                    prices[f"One-Way ({context})"] = nums
            for name in names:
                if name.lower() in {"port jervis", "pascack valley", "all stations"}:
                    continue
                if not prices:
                    continue
                out.append({"name": name, "prices": prices})
    return out


def harvest():
    lirr = parse_lirr()
    print("LIRR stations found:", len(lirr["stations"]))

    hh = parse_mnr_pdf(DOCS / "mnr_harlem_hudson_gct.pdf", station_x_max=200,
                       label_x_min=200, price_x_min=350)
    nh = parse_mnr_pdf(DOCS / "mnr_newhaven_gct.pdf", station_x_max=110,
                       label_x_min=110, price_x_min=200)
    print("Harlem/Hudson zones:", [(s["zone"], len(s["stations"])) for s in hh])
    print("New Haven zones:", [(s["zone"], len(s["stations"])) for s in nh])
    for s in hh[:3]:
        print(" HH zone", s["zone"], s["stations"][:8], "prices:", {k: v for k, v in list(s["prices"].items())[:4]})
    for s in nh[:2]:
        print(" NH zone", s["zone"], s["stations"][:6], "prices:", {k: v for k, v in list(s["prices"].items())[:4]})

    pj = parse_port_jervis()
    print("Port Jervis/Pascack stations:", [(p["name"], p["prices"].get("Monthly")) for p in pj])

    out = {
        "lirr": lirr,
        "mnr_harlem_hudson": hh,
        "mnr_newhaven": nh,
        "port_jervis_pascack": pj,
    }
    (OUT / "railroad_fares.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("wrote", OUT / "railroad_fares.json")


if __name__ == "__main__":
    harvest()

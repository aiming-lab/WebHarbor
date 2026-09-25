"""Parse static content pages into structured source data."""
import json, pathlib, re, html as htmllib
import os
import pathlib
HARVEST = pathlib.Path(os.environ.get("PS_HARVEST_DIR", pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "ps_harvest"))

OUT = pathlib.Path(str(HARVEST) + "/pages")
result = {}

def clean(s):
    s = htmllib.unescape(s or "")
    s = re.sub(r'<[^>]+>', '\n', s)
    s = re.sub(r'\n\s*\n+', '\n', s)
    return s.strip()

def text_of(html, sel_start=None):
    return clean(html)

# --- size guide detail pages: title, intro, "right size for", comparison rows
for f in sorted(OUT.glob("sg_*.html")):
    html = f.read_text()
    d = {}
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
    d["h1"] = clean(m.group(1)) if m else None
    m = re.search(r'<title>(.*?)</title>', html, re.S)
    d["title"] = clean(m.group(1)) if m else None
    # intro paragraph
    m = re.search(r'<h1[^>]*>.*?</h1>\s*<p[^>]*>(.*?)</p>', html, re.S)
    d["intro"] = clean(m.group(1)) if m else None
    # "The right size for:" list
    rsm = re.search(r'The right size for:?\s*</[^>]+>(.*?)(?:<h\d|Does this size)', html, re.S)
    if rsm:
        items = [clean(x) for x in re.findall(r'<li[^>]*>(.*?)</li>', rsm.group(1), re.S)]
        d["right_size_for"] = [i for i in items if i][:8]
    d["name"] = f.stem
    result[f"size_{f.stem}"] = d
    print(f.stem, "|", d["h1"], "| right:", d.get("right_size_for"))

# --- storage solutions pages: h1 + first paragraphs + headings
for f in sorted(OUT.glob("sol_*.html")):
    html = f.read_text()
    d = {}
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
    d["h1"] = clean(m.group(1)) if m else None
    m = re.search(r'<title>(.*?)</title>', html, re.S)
    d["title"] = clean(m.group(1)) if m else None
    # main content paragraphs
    scrubbed = re.sub(r'<script.*?</script>', ' ', html, flags=re.S)
    scrubbed = re.sub(r'<style.*?</style>', ' ', scrubbed, flags=re.S)
    paras = [clean(p) for p in re.findall(r'<p[^>]*>(.*?)</p>', scrubbed, re.S)]
    d["paragraphs"] = [p for p in paras if len(p) > 60 and "{" not in p[:40]][:14]
    h2s = [clean(h) for h in re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.S)]
    d["h2s"] = [h for h in h2s if h][:14]
    result[f.stem] = d
    print(f.stem, "|", d["h1"], "| paras:", len(d["paragraphs"]))

pathlib.Path(str(HARVEST) + "/static_pages.json").write_text(json.dumps(result, indent=1))
print("saved static_pages.json", len(result))

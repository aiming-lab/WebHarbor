"""Extract FAQ Q&A pairs from size-guide detail pages."""
import json, pathlib, re, html as htmllib
import os
import pathlib
HARVEST = pathlib.Path(os.environ.get("PS_HARVEST_DIR", pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "ps_harvest"))

OUT = pathlib.Path(str(HARVEST) + "/pages")

def clean(s):
    s = htmllib.unescape(s or "")
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

result = {}
for f in sorted(OUT.glob("sg_*.html")):
    html = f.read_text()
    d = {"name": f.stem}
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
    d["h1"] = clean(m.group(1)) if m else None
    m = re.search(r'<title>(.*?)</title>', html, re.S)
    d["title"] = clean(m.group(1)) if m else None
    # FAQ pairs: <h3>question</h3> ... <div ...>answer</div> — find accordion structure
    faqs = []
    # try schema.org FAQPage JSON-LD first
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            obj = json.loads(m.group(1).strip())
        except Exception:
            continue
        items = obj.get("mainEntity") if isinstance(obj, dict) else None
        if not items:
            continue
        for q in items:
            faqs.append({"q": clean(q.get("name", "")), "a": clean(q.get("acceptedAnswer", {}).get("text", ""))})
    if not faqs:
        # fallback: h3 + following panel body
        for m in re.finditer(r'<h3[^>]*>(.*?)</h3>(.*?)(?=<h3|</section|$)', html, re.S):
            q = clean(m.group(1))
            a = clean(m.group(2))
            if q and len(a) > 40 and "?" in q:
                faqs.append({"q": q, "a": a[:600]})
    d["faqs"] = faqs
    result[f.stem] = d
    print(f.stem, "|", d["h1"], "| faqs:", len(faqs))
    for faq in faqs[:3]:
        print("   Q:", faq["q"][:90])
        print("   A:", faq["a"][:140])
pathlib.Path(str(HARVEST) + "/size_faqs.json").write_text(json.dumps(result, indent=1))

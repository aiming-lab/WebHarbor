"""Screen candidate products by whether their specs are actually sourceable.

The catalogue is source-driven: a candidate that does not yield the fields this
site renders, from a citable page, is not added. Nothing is filled in from
memory.
"""
import json, re, subprocess, sys, urllib.parse

UA = "WebHarbor-review/1.0 (research benchmark; jackjin1997@gmail.com)"
API = "https://en.wikipedia.org/w/api.php"

CANDIDATES = {
 "smartphones": ["Google Pixel 9 Pro","Samsung Galaxy S23 Ultra","iPhone 14 Pro","OnePlus 11",
   "Xiaomi 14 Ultra","Google Pixel 7 Pro","iPhone 15","Samsung Galaxy S24","Asus Zenfone 10",
   "Sony Xperia 1 V","Nothing Phone (2)","Motorola Edge 40 Pro"],
 "cameras": ["Sony α7R V","Canon EOS R5","Nikon Z9","Fujifilm X-H2","Sony α6700","Canon EOS R8",
   "Nikon Z6III","Panasonic Lumix DC-S5II","Olympus OM-1","Leica Q3","Fujifilm X-S20","Sony α7C II"],
 "graphics-cards": ["GeForce RTX 4090","GeForce RTX 4070 Ti","GeForce RTX 4060 Ti","GeForce RTX 3080",
   "Radeon RX 7600","Radeon RX 6800 XT","GeForce RTX 4060","Radeon RX 7900 GRE"],
 "smartwatches": ["Apple Watch Ultra 2","Apple Watch Series 8","Samsung Galaxy Watch 5",
   "Google Pixel Watch 2","Garmin Forerunner 965","Garmin Fenix 7","Withings ScanWatch","Amazfit GTR 4"],
 "headphones": ["Sony WH-1000XM4","Bose QuietComfort 45","Sennheiser HD 660S","AirPods Pro",
   "Beats Studio Pro","Bowers & Wilkins Px8","Shure Aonic 50","Audio-Technica ATH-M50x"],
}

NEEDED = {
 "smartphones": ("weight","battery","released"),
 "cameras": ("res","weight","price"),
 "graphics-cards": (),          # sourced from the list articles instead
 "smartwatches": ("weight","released"),
 "headphones": ("weight",),
}

def fetch(title):
    q = urllib.parse.urlencode({"action":"query","format":"json","prop":"revisions",
        "rvprop":"content|ids","rvslots":"main","titles":title,"redirects":1})
    r = subprocess.run(["curl","-sL","--max-time","25","-A",UA,f"{API}?{q}"],
                       capture_output=True, text=True)
    try:
        p = list(json.loads(r.stdout)["query"]["pages"].values())[0]
        rev = p["revisions"][0]
        return rev["slots"]["main"]["*"], rev["revid"], p["title"]
    except Exception:
        return None, None, None

def field(text, name):
    m = re.search(rf"\|\s*{name}\s*=\s*(.+)", text, re.I)
    return re.sub(r"<[^>]+>|\[\[|\]\]|'''", " ", m.group(1)).strip()[:100] if m else None

report = {}
for cat, names in CANDIDATES.items():
    need = NEEDED[cat]
    usable = []
    print(f"\n{cat}  (needs: {', '.join(need) or 'list-article row'})")
    for n in names:
        text, rev, resolved = fetch(n)
        if not text:
            print(f"   --  {n[:30]:32} no article"); continue
        got = {k: field(text, k) for k in need}
        ok = all(got.get(k) for k in need)
        usable.append({"name": n, "title": resolved, "revid": rev, "fields": got}) if ok else None
        print(f"   {'OK ' if ok else '-- '} {n[:30]:32} " +
              ", ".join(f"{k}={'y' if got.get(k) else 'n'}" for k in need))
    report[cat] = usable
    print(f"   => {len(usable)}/{len(names)} usable")
json.dump(report, open("/tmp/candidate_report.json","w"), indent=1)

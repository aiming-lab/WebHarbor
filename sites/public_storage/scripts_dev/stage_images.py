"""Stage the downloaded real images into static/images with clean paths,
dropping anything the mirror does not actually reference."""
import json, pathlib, re, shutil
import os
import pathlib
HARVEST = pathlib.Path(os.environ.get("PS_HARVEST_DIR", pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "ps_harvest"))

SRC = pathlib.Path(str(HARVEST) + "/images")
DEST = pathlib.Path("/data/zhaoyang-user-projects/websyn/WebHarbor/_wh_review_tools/orch/contribute/build/public_storage/sites/public_storage/static/images")
TPL = pathlib.Path("/data/zhaoyang-user-projects/websyn/WebHarbor/_wh_review_tools/orch/contribute/build/public_storage/sites/public_storage/templates")

# 1) which relative paths do templates + seed data reference?
referenced = set()
for f in list(TPL.glob("*.html")) + list(TPL.parent.glob("static/css/*.css")) + list(TPL.parent.glob("static/js/*.js")):
    text = f.read_text()
    for m in re.finditer(r'/static/images/([A-Za-z0-9_\-./@]+)', text):
        referenced.add("static/images/" + m.group(1))
for card in json.loads((TPL.parent / "source_data/site_content.json").read_text())["size_guide"]["size_cards"]:
    if card.get("image"):
        referenced.add(card["image"])
fac = json.loads((DEST.parent.parent / "source_data/facilities.json").read_text())
content = json.loads((DEST.parent.parent / "source_data/site_content.json").read_text())
for d in fac.values():
    for p in d["photos"]:
        referenced.add(p)
for a in content.get("blog_articles", []):
    if a.get("image_path"):
        referenced.add(a["image_path"])

# 2) map each downloaded file to its clean static path
mapping = {}
for f in SRC.rglob("*"):
    if not f.is_file():
        continue
    rel = f.relative_to(SRC)
    if rel.parts[0] == "dwstatic":
        # drop the hash prefix -> clean name under dwstatic/
        name = rel.name.split("_", 1)[1]
        mapping[str(rel)] = f"static/images/dwstatic/{name}"
    else:
        mapping[str(rel)] = f"static/images/{rel}"

# 3) figure out which template refs map to actual dwstatic files
dw_names = {p.split("/")[-1]: p for p in mapping.values() if "/dwstatic/" in p}
tpl_dw_refs = {r for r in referenced if "/dwstatic/" in r}
unmatched = {r for r in tpl_dw_refs if r not in set(mapping.values())}
# try matching by suffix filename
fixed = set()
for r in sorted(unmatched):
    fname = r.split("/")[-1]
    if fname in dw_names:
        fixed.add((r, dw_names[fname]))
print("template dwstatic refs:", len(tpl_dw_refs), "unmatched:", len(unmatched))
for r, p in sorted(fixed):
    print("  RENAME-NEEDED:", r, "->", p)

# 4) copy everything referenced (plus all Property/ photos used by seed data)
copied = 0
for src_rel, dest_rel in sorted(mapping.items()):
    if dest_rel not in referenced:
        continue
    dest = DEST / dest_rel.removeprefix("static/images/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC / src_rel, dest)
    copied += 1
print("copied:", copied, "of", len(mapping))
missing = sorted(r for r in referenced if not (DEST / r.removeprefix("static/images/")).exists())
print("missing referenced:", len(missing))
for m in missing[:20]:
    print("  MISS:", m)

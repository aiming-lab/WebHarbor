"""Build a new seed from captured release responses; never edit the input DB.

The capture index contains url, status, file, sha256 and observed_at for each
response. Exclusions are an explicit JSON list of source-less release IDs.
All retained releases must have verified response bytes before any DB is built.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import unicodedata

from PIL import Image

from catalog import normalize_release


def slugify(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "x"


def load_sources(directory):
    directory = Path(directory)
    records = {}
    for receipt in json.loads((directory / "requests.json").read_text()):
        if receipt.get("status") != 200:
            continue
        path = (directory / receipt["file"]).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Capture file is outside its directory")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError(f"Capture hash mismatch: {path.name}")
        source = json.loads(raw)
        normalized = normalize_release(source)
        if receipt["url"] != source["resource_url"]:
            raise ValueError(f"Capture URL mismatch: {path.name}")
        records[normalized["id"]] = (normalized, receipt, raw.decode("utf-8"))
    return records


def load_images(directory, records):
    if directory is None:
        return {}
    directory = Path(directory).resolve()
    images = {}
    for receipt in json.loads((directory / "requests.json").read_text()):
        if receipt.get("status") != 200:
            continue
        release_id = receipt.get("release_id")
        if release_id in images:
            raise ValueError(f"Duplicate verified image for release {release_id}")
        if release_id not in records:
            raise ValueError(f"Image has no captured release source: {release_id}")
        source_url = receipt.get("source_url")
        if source_url not in records[release_id][0]["image_urls"]:
            raise ValueError(f"Release {release_id}: image URL mismatch")
        if receipt.get("file") != f"{release_id}.jpg":
            raise ValueError(f"Release {release_id}: image filename mismatch")
        path = (directory / receipt["file"]).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Image file is outside its directory")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError(f"Image hash mismatch: {path.name}")
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                size = image.size
        except Exception as error:
            raise ValueError(f"Invalid image: {path.name}") from error
        expected_size = (receipt.get("width"), receipt.get("height"))
        if None not in expected_size and size != expected_size:
            raise ValueError(f"Image dimensions mismatch: {path.name}")
        images[release_id] = f"images/release/{release_id}.jpg"
    return images


def add_columns(db, table, columns):
    present = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
    for name, declaration in columns.items():
        if name not in present:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def update_catalog(db, records, excluded, images=None):
    images = images or {}
    add_columns(db, "releases", {
        "artist_credit": "TEXT DEFAULT ''", "format_description": "TEXT DEFAULT ''",
        "source_json": "TEXT DEFAULT ''", "source_sha256": "TEXT DEFAULT ''",
        "source_captured_at": "TEXT DEFAULT ''",
    })
    add_columns(db, "tracks", {"kind": "TEXT DEFAULT 'track'", "depth": "INTEGER DEFAULT 0"})
    for table in ("artists", "labels", "masters"):
        add_columns(db, table, {"discogs_id": "INTEGER"})
        db.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS ix_{table}_discogs_id ON {table}(discogs_id)")
    db.execute("""CREATE TABLE IF NOT EXISTS release_artists (
        release_id INTEGER NOT NULL REFERENCES releases(id),
        artist_id INTEGER NOT NULL REFERENCES artists(id),
        PRIMARY KEY (release_id, artist_id))""")
    removed = [row[0] for row in db.execute("SELECT id, discogs_id FROM releases") if row[1] in excluded]
    db.execute("CREATE TEMP TABLE excluded_releases (id INTEGER PRIMARY KEY)")
    db.executemany("INSERT INTO excluded_releases VALUES (?)", [(rid,) for rid in removed])
    for table in ("ratings", "reviews", "collection_items", "wantlist_items", "list_items", "listings"):
        db.execute(f"DELETE FROM {table} WHERE release_id IN (SELECT id FROM excluded_releases)")
    for table in ("release_genres", "release_styles", "release_formats", "release_labels", "release_artists", "tracks"):
        db.execute(f"DELETE FROM {table}")
    db.execute("UPDATE releases SET master_id=NULL")
    db.execute("DELETE FROM masters")
    db.execute("DELETE FROM releases WHERE id IN (SELECT id FROM excluded_releases)")
    source_ids = {row[1]: row[0] for row in db.execute("SELECT id, discogs_id FROM releases")}
    caches = defaultdict(dict)

    def entity(table, source):
        sid, name = source.get("id"), source["name"]
        cache_key = ("id", sid) if sid is not None else ("name", name)
        if cache_key in caches[table]:
            return caches[table][cache_key]
        row = None
        if sid is not None:
            row = db.execute(f"SELECT id FROM {table} WHERE discogs_id=?", (sid,)).fetchone()
        if row is None:
            row = db.execute(f"SELECT id FROM {table} WHERE name=? AND discogs_id IS NULL ORDER BY id LIMIT 1", (name,)).fetchone()
        if row:
            eid = row[0]
            db.execute(f"UPDATE {table} SET discogs_id=?, name=? WHERE id=?", (sid, name, eid))
        else:
            slug = f"{slugify(name)[:160]}-{sid}" if sid is not None else slugify(name)[:200]
            if db.execute(f"SELECT 1 FROM {table} WHERE slug=?", (slug,)).fetchone():
                slug = f"{slug[:180]}-{hashlib.sha256(name.encode()).hexdigest()[:8]}"
            if table == "artists":
                eid = db.execute("""INSERT INTO artists
                    (discogs_id,name,slug,real_name,profile,members,sites,image_path,rating,in_collection)
                    VALUES (?,?,?,'','','','','',0,0)""", (sid, name, slug)).lastrowid
            else:
                eid = db.execute("""INSERT INTO labels
                    (discogs_id,name,slug,profile,contact_info) VALUES (?,?,?,'','')""", (sid, name, slug)).lastrowid
        caches[table][cache_key] = eid
        return eid

    def named(table, name):
        if name in caches[table]:
            return caches[table][name]
        row = db.execute(f"SELECT id FROM {table} WHERE name=?", (name,)).fetchone()
        if row:
            nid = row[0]
        else:
            slug = slugify(name)
            if db.execute(f"SELECT 1 FROM {table} WHERE slug=?", (slug,)).fetchone():
                slug += "-" + hashlib.sha256(name.encode()).hexdigest()[:8]
            nid = db.execute(f"INSERT INTO {table} (name,slug) VALUES (?,?)", (name, slug)).lastrowid
        caches[table][name] = nid
        return nid

    masters = {}
    for did, (data, receipt, raw) in sorted(records.items()):
        if did in excluded:
            continue
        artist_ids = [entity("artists", artist) for artist in data["artists"]]
        aid = artist_ids[0]
        mid = None
        if data["master_id"]:
            source_mid = data["master_id"]
            if source_mid not in masters:
                # The release endpoint establishes membership, not a master's
                # first-release year or main edition. Leave those unknown.
                masters[source_mid] = db.execute(
                    "INSERT INTO masters (discogs_id,title,artist_id) VALUES (?,?,?)",
                    (source_mid, data["title"], aid)).lastrowid
            mid = masters[source_mid]
        rid = source_ids.get(did)
        if rid is None:
            rid = db.execute("""INSERT INTO releases
                (discogs_id,title,artist_id,avg_rating,rating_count,have_count,want_count,num_for_sale)
                VALUES (?,?,?,0,0,0,0,0)""", (did, data["title"], aid)).lastrowid
        values = {
            "title": data["title"], "artist_id": aid, "master_id": mid,
            "year": data["year"], "released": data["released"], "country": data["country"],
            "notes": data["notes"], "barcode": " / ".join(data["barcodes"]),
            "catno": " / ".join(dict.fromkeys(l.get("catno", "") for l in data["labels"])),
            "data_quality": data["data_quality"], "added_at": data["added_at"],
            "artist_credit": data["artist_credit"], "format_description": data["format_description"],
            "source_json": raw, "source_sha256": receipt["sha256"],
            "source_captured_at": receipt["observed_at"],
            # Only a hash-verified image tied to this exact release response is safe.
            "image_path": images.get(did, ""),
        }
        assignments = ",".join(f"{key}=?" for key in values)
        db.execute(f"UPDATE releases SET {assignments} WHERE id=?", [*values.values(), rid])
        for artist_id in dict.fromkeys(artist_ids):
            db.execute("INSERT INTO release_artists VALUES (?,?)", (rid, artist_id))
        for table, relation, key, names in (
                ("genres", "release_genres", "genre_id", data["genres"]),
                ("styles", "release_styles", "style_id", data["styles"]),
                ("formats", "release_formats", "format_id", data["format_names"])):
            for name in dict.fromkeys(names):
                db.execute(f"INSERT INTO {relation} (release_id,{key}) VALUES (?,?)", (rid, named(table, name)))
        labels = defaultdict(list)
        for label in data["labels"]:
            labels[entity("labels", label)].append(label.get("catno") or "")
        for lid, catnos in labels.items():
            db.execute("INSERT INTO release_labels (release_id,label_id,catno) VALUES (?,?,?)",
                       (rid, lid, " / ".join(dict.fromkeys(catnos))))
        for track in data["tracks"]:
            db.execute("""INSERT INTO tracks
                (release_id,position,title,duration,artist_credit,kind,depth) VALUES (?,?,?,?,?,?,?)""",
                (rid, track["position"], track["title"], track["duration"], track["artist_credit"], track["kind"], track["depth"]))
    # These are explicitly synthetic community state, not live Discogs counts.
    db.execute("""UPDATE releases SET
        have_count=(SELECT count(*) FROM collection_items WHERE release_id=releases.id),
        want_count=(SELECT count(*) FROM wantlist_items WHERE release_id=releases.id),
        rating_count=(SELECT count(*) FROM ratings WHERE release_id=releases.id),
        avg_rating=coalesce((SELECT avg(value) FROM ratings WHERE release_id=releases.id),0),
        num_for_sale=(SELECT count(*) FROM listings WHERE release_id=releases.id AND status='For Sale'),
        lowest_price=(SELECT min(price) FROM listings
                       WHERE release_id=releases.id AND status='For Sale' AND currency='USD')""")
    # A single numeric minimum across currencies has no defined meaning; the
    # cached release-level minimum is explicitly USD.
    db.execute("""DELETE FROM artists WHERE id NOT IN (SELECT artist_id FROM release_artists)
        AND id NOT IN (SELECT artist_id FROM list_items WHERE artist_id IS NOT NULL)""")
    db.execute("""DELETE FROM labels WHERE id NOT IN (SELECT label_id FROM release_labels)
        AND id NOT IN (SELECT label_id FROM list_items WHERE label_id IS NOT NULL)""")
    db.execute("UPDATE artists SET in_collection=(SELECT count(*) FROM release_artists WHERE artist_id=artists.id)")
    for table, relation, key in (("genres", "release_genres", "genre_id"),
                                 ("styles", "release_styles", "style_id"),
                                 ("formats", "release_formats", "format_id")):
        db.execute(f"DELETE FROM {table} WHERE id NOT IN (SELECT {key} FROM {relation})")
    return {"excluded_internal_ids": removed, "releases": db.execute("SELECT count(*) FROM releases").fetchone()[0]}


def refresh(seed, sources, excluded, output, images=None):
    seed, output = Path(seed).resolve(), Path(output).resolve()
    if output.exists() or seed == output:
        raise ValueError("Output must be a new file; the input seed is immutable")
    records = load_sources(sources)
    verified_images = load_images(images, records)
    with sqlite3.connect(f"file:{seed}?mode=ro", uri=True) as original:
        original_ids = {row[0] for row in original.execute("SELECT discogs_id FROM releases")}
        if not set(excluded) <= original_ids:
            raise ValueError("Exclusion list contains IDs absent from the input seed")
        missing = original_ids - set(excluded) - records.keys()
        if missing:
            raise ValueError(f"Missing verified sources for {len(missing)} retained releases: {sorted(missing)[:8]}")
        fd, temporary = tempfile.mkstemp(prefix=".discogs-seed-", suffix=".db", dir=output.parent)
        os.close(fd)
        try:
            with sqlite3.connect(temporary) as candidate:
                original.backup(candidate)
                result = update_catalog(candidate, records, set(excluded), verified_images)
                violations = candidate.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise ValueError(f"Foreign key violations: {violations[:5]}")
                if candidate.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("SQLite integrity check failed")
                candidate.commit()
            os.link(temporary, output)  # Fails instead of replacing an existing output.
        finally:
            Path(temporary).unlink(missing_ok=True)
    result["seed_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, type=Path)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--exclude", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--images", type=Path)
    args = parser.parse_args()
    print(json.dumps(refresh(args.seed, args.sources, json.loads(args.exclude.read_text()),
                             args.output, images=args.images), indent=2))

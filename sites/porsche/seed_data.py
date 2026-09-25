#!/usr/bin/env python3
"""Deterministic seed builder for the porsche mirror.

Reads the tracked snapshots under source_data/ (captured from the live
porsche.com / finder.porsche.com / shop.porsche.com / configurator.porsche.com;
see provenance.json) and materializes the full catalog:

  models.json              -> ModelVariant rows (76 real model variants)
  configurator_options.json -> ConfiguratorOption rows (8 models)
  vehicles.json            -> Vehicle rows (real in-stock listings, VINs)
  dealers.json             -> Dealer rows (218 US Porsche Centers)
  shop_products.json       -> ShopProduct rows (Porsche Shop catalog)
  homepage_text.txt        -> SiteContent (homepage copy)

The build is deterministic (PYTHONHASHSEED=0, sorted iteration, frozen
bcrypt digest) so the SQLite seed is byte-reproducible on every rebuild.

Run from sites/porsche/:  PYTHONHASHSEED=0 python3 seed_data.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

BASE_DIR = pathlib.Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data"

# Frozen bcrypt digest for the benchmark password 'TestPass123!' so the seed
# DB is byte-identical on every rebuild (standard Flask-Bcrypt cost factor).
BENCHMARK_PASSWORD_DIGEST = (
    "$2b$12$mTNQa9oqZyOoIJBpKN.0p.LVaApMSu9gZnYufEZrciM5QgBN7EM7u"
)

BENCHMARK_USERS = [
    {
        "email": "casey.taylor@test.com",
        "first_name": "Casey",
        "last_name": "Taylor",
    },
    {
        "email": "jordan.morgan@test.com",
        "first_name": "Jordan",
        "last_name": "Morgan",
    },
]

# The live Finder publishes clean fuel / drivetrain labels ("Electric",
# "Gasoline", "All-wheel-drive", ...). The raw capture carried the same
# facts under two spellings depending on the listing payload shape
# ("ELECTRIC"/"Electric", "AllWheelDriveConfiguration"/"All-wheel-drive");
# normalize to the upstream labels so facets and filters have one value.
FUEL_LABELS = {
    "ELECTRIC": "Electric",
    "PETROL": "Gasoline",
    "DIESEL": "Diesel",
    "MILD_HYBRID": "Mild Hybrid",
    "PLUG_IN_HYBRID": "Plug-in Hybrid",
}
DRIVETRAIN_LABELS = {
    "AllWheelDriveConfiguration": "All-wheel-drive",
    "RearWheelDriveConfiguration": "Rear-wheel-drive",
}


def _load(name):
    return json.loads((SOURCE / name).read_text())


def _local_model_image(code, m):
    if m.get("image"):
        return f"/static/images/models/{code}.png"
    return ""


def _gallery_for(code, m):
    paths = []
    for i in range(8):
        paths.append(f"/static/images/models/{code}_g{i}")
    return json.dumps(paths)


def build_seed(db):
    """Materialize the catalog. Deterministic; sorted iteration everywhere."""
    from app import (ConfiguratorOption, Dealer, ModelVariant, ShopProduct,
                     SiteContent, Vehicle)

    # The shipped asset inventory is the source of truth for local image
    # paths (the downloader sniffs true formats, so extensions can differ
    # from what the upstream URLs suggested).
    inventory = json.loads((BASE_DIR / "asset_inventory.json").read_text())
    known_paths = {a["path"] for a in inventory["assets"]}

    def resolve(prefix: str) -> list[str]:
        """Local URLs for the inventory paths under one prefix."""
        hits = sorted(p for p in known_paths if p.startswith(prefix))
        return [f"/{p}" for p in hits]

    models = _load("models.json")
    for m in sorted(models, key=lambda x: (x.get("modelRange", ""), x.get("modelType", ""))):
        code = m.get("modelType", "")
        price = (m.get("price") or {}).get("value")
        hp = (m.get("powerHp") or {}).get("value")
        gallery = resolve(f"static/images/models/{code}_g") if code else []
        highlights = resolve(f"static/images/models/{code}_hl.") if code else []
        # Upstream 718 lineup cards link to the Porsche Finder search instead
        # of a model page, so their extracted "detail_slug" is a query string
        # ("search?ORDERTYPE=..."). Normalize any non-slug value to a real slug
        # derived from the model name so every lineup card resolves (audit fix:
        # ten 718 variants produced 404 detail links otherwise).
        raw_slug = m.get("detail_slug", "")
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", raw_slug or ""):
            detail_slug = raw_slug
        else:
            detail_slug = re.sub(r"[^a-z0-9]+", "-",
                                 (m.get("modelName", "")).lower()).strip("-")
        db.session.add(ModelVariant(
            model_type=code,
            model_name=m.get("modelName", ""),
            model_year=m.get("modelYear", ""),
            body_type=m.get("bodyType", ""),
            model_range=m.get("modelRange", ""),
            model_series=m.get("modelSeries", ""),
            wheel_drive=m.get("wheelDrive", ""),
            seats=m.get("seats", ""),
            fuel_type=m.get("fuelTypeText", ""),
            gear_type=m.get("gearTypeText", ""),
            price_value=price,
            price_formatted=(m.get("price") or {}).get("formattedValue", ""),
            hp_value=hp,
            hp_formatted=(m.get("powerHp") or {}).get("formattedValue", ""),
            accel_0_60=m.get("accel_0_60", ""),
            top_speed=m.get("top_speed", ""),
            leasing_monthly=m.get("leasing_monthly", ""),
            image=_local_model_image(code, m),
            detail_slug=detail_slug,
            configure_code=code if m.get("configure_url") else "",
            equipment_highlights=json.dumps(m.get("standard_equipment_highlights", [])),
            tech_categories=json.dumps(m.get("tech_categories", [])),
            highlights_attributes=json.dumps(m.get("highlights_attributes", [])),
            highlights_image=highlights[0] if highlights else "",
            gallery=json.dumps(gallery),
        ))

    cfg = _load("configurator_options.json")
    for code in sorted(cfg):
        for o in sorted(cfg[code], key=lambda x: (x.get("price", 0), x.get("id", ""))):
            sw = o.get("swatch", "")
            local = f"/static/images/configurator/{code}_{o['id']}.jpg" if sw else ""
            db.session.add(ConfiguratorOption(
                model_code=code, option_id=o.get("id", ""), name=o.get("name", ""),
                price=o.get("price", 0), swatch=local,
            ))

    vehicles = _load("vehicles.json")
    for v in sorted(vehicles, key=lambda x: x["listing_id"]):
        db.session.add(Vehicle(
            listing_id=v["listing_id"], slug=v["slug"], name=v["name"],
            full_title=v.get("full_title", ""),
            model_range=v.get("model_range", ""),
            model_generation=v.get("model_generation", ""),
            condition=v.get("condition", ""),
            condition_label=v.get("condition_label", ""),
            price=v.get("price", 0), vin=v.get("vin", ""),
            model_year=v.get("model_year", 0),
            color=v.get("color", ""), interior_color=v.get("interior_color", ""),
            transmission=v.get("transmission", ""),
            drivetrain=DRIVETRAIN_LABELS.get(v.get("drivetrain", ""), v.get("drivetrain", "")),
            fuel=FUEL_LABELS.get(v.get("fuel", ""), v.get("fuel", "")), hp=v.get("hp", 0) or None,
            mileage=v.get("mileage", 0), previous_owners=v.get("previous_owners", 0),
            body_type=v.get("body_type", ""), seller_id=v.get("seller_id", ""),
            partner_no=v.get("seller_partner_no", ""),
            dealer_name=v.get("dealer_name", ""), dealer_city=v.get("dealer_city", ""),
            dealer_zip=v.get("dealer_zip", ""), dealer_street=v.get("dealer_street", ""),
            image=f"/static/images/vehicles/{v['listing_id']}.jpg",
            lease_payment=v.get("lease_payment", ""),
            price_breakdown=json.dumps(v.get("price_breakdown", [])),
            characteristics=json.dumps(v.get("characteristics", [])),
            weight_kg=v.get("weight_kg", 0),
            dimensions=json.dumps(v.get("dimensions", {})),
        ))

    dealers = _load("dealers.json")
    for d in sorted(dealers, key=lambda x: (x.get("state", ""), x.get("name", ""))):
        db.session.add(Dealer(
            ppn_org_id=d.get("ppn_org_id", ""), name=d.get("name", ""),
            partner_no=d.get("partner_no", ""), street=d.get("street", ""),
            city=d.get("city", ""), state=d.get("state", ""), zip=d.get("zip", ""),
            phone=d.get("phone", ""), email=d.get("email", ""),
            homepage=d.get("homepage", ""),
            contact_hours=json.dumps(d.get("contact_hours", [])),
            service_hours=json.dumps(d.get("service_hours", [])),
            lat=d.get("lat"), lng=d.get("lng"),
        ))

    products = _load("shop_products.json")
    for p in sorted(products, key=lambda x: x["object_id"]):
        images = []
        for i, u in enumerate(p.get("images", [])[:2]):
            if u:
                images.append(f"/static/images/shop/{p['object_id']}_{i}.webp")
        db.session.add(ShopProduct(
            object_id=p["object_id"], name=p.get("name", ""), sku=p.get("sku", ""),
            slug=p.get("slug", ""), shop_category=p.get("shop_category", ""),
            main_category=p.get("main_category", ""),
            categories_json=json.dumps(p.get("categories", [])),
            description=p.get("description", ""),
            price_cents=p.get("price_cents", 0), brand=p.get("brand", ""),
            in_stock=bool(p.get("in_stock")), images=json.dumps(images),
            color=json.dumps(p.get("color", [])), size=p.get("size", ""),
            labels=json.dumps(p.get("labels", [])),
        ))

    homepage = (SOURCE / "homepage_text.txt").read_text()
    db.session.add(SiteContent(key="homepage_text", content=homepage))

    db.session.commit()


def _guess_ext(url):
    lower = url.lower()
    if ".svg" in lower:
        return "svg"
    if ".png" in lower:
        return "png"
    if ".webp" in lower:
        return "webp"
    if ".jpg" in lower or ".jpeg" in lower:
        return "jpg"
    return "png"


def canonicalize_sqlite(path: pathlib.Path) -> None:
    """Rewrite the SQLite file in a fixed schema order so the seed is
    byte-reproducible across processes.

    SQLAlchemy's create_all() emits CREATE INDEX statements in per-table
    set order, which depends on object identity and therefore varies
    between processes. Rebuilding the file here with tables and indexes
    in sorted name order (rows in rowid order) makes the seed byte-stable.
    """
    import sqlite3

    tmp = path.with_suffix(path.suffix + ".canonical")
    if tmp.exists():
        tmp.unlink()
    src = sqlite3.connect(str(path))
    dst = sqlite3.connect(str(tmp))
    try:
        objects = src.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()
        tables = sorted((name, sql) for t, name, sql in objects if t == "table")
        indexes = sorted((name, sql) for t, name, sql in objects
                         if t == "index" and sql)
        for _name, sql in tables:
            dst.execute(sql)
        for name, _sql in tables:
            rows = src.execute(
                f'SELECT * FROM "{name}" ORDER BY rowid'
            ).fetchall()
            if rows:
                placeholders = ",".join("?" * len(rows[0]))
                dst.executemany(
                    f'INSERT INTO "{name}" VALUES ({placeholders})', rows)
        for _name, sql in indexes:
            dst.execute(sql)
        dst.commit()
    finally:
        dst.close()
        src.close()
    import os

    os.replace(tmp, path)


def build_benchmark_users(db, bcrypt=None):
    """Seed the My Porsche demo accounts with the frozen password digest."""
    from app import User
    for spec in BENCHMARK_USERS:
        if User.query.filter_by(email=spec["email"]).first():
            continue
        db.session.add(User(
            email=spec["email"],
            password_hash=BENCHMARK_PASSWORD_DIGEST,
            first_name=spec["first_name"], last_name=spec["last_name"],
            created_at="2026-09-01",
        ))
    db.session.commit()


if __name__ == "__main__":
    import os
    import shutil

    from app import app, db

    with app.app_context():
        db.create_all()
        from app import seed_database, seed_benchmark_users
        seed_database()
        seed_benchmark_users()
        from app import ModelVariant, Vehicle, Dealer, ShopProduct, ConfiguratorOption, User
        print("seeded", ModelVariant.query.count(), "model variants,",
              ConfiguratorOption.query.count(), "configurator options,",
              Vehicle.query.count(), "vehicles,",
              Dealer.query.count(), "dealers,",
              ShopProduct.query.count(), "shop products,",
              User.query.count(), "users")

    instance_db = pathlib.Path(os.environ.get("WEBHARBOR_MIRROR_DB")
                               or BASE_DIR / "instance" / "porsche.db")
    canonicalize_sqlite(instance_db)

    os.makedirs(os.path.join(BASE_DIR, "instance_seed"), exist_ok=True)
    shutil.copyfile(instance_db,
                    os.path.join(BASE_DIR, "instance_seed", "porsche.db"))
    print("copied seed to instance_seed/porsche.db")

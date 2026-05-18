#!/usr/bin/env python3
"""Regression checks for deterministic Booking filter fixtures."""

import importlib.util
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOKING_DIR = ROOT / "sites/booking"


def load_booking_app():
    sys.path.insert(0, str(BOOKING_DIR))
    os.chdir(BOOKING_DIR)
    spec = importlib.util.spec_from_file_location("booking_app_for_fixture_check", BOOKING_DIR / "app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    instance_dir = BOOKING_DIR / "instance"
    if instance_dir.exists():
        shutil.rmtree(instance_dir)
    instance_dir.mkdir(exist_ok=True)

    app = load_booking_app()
    with app.app.app_context():
        app.db.create_all()
        app.seed_database()
        city = app.City.query.filter_by(key="barcelona").first()
        if not city:
            raise SystemExit("missing Barcelona city fixture")

        query = app.Property.query.filter_by(city_id=city.id)
        query = query.filter(app.Property.breakfast_included.is_(True))
        query = query.filter(app.Property.has_wifi.is_(True))
        query = query.filter(app.Property.rating >= 8.0)
        query = query.filter(app.Property.price_per_night >= 50)
        query = query.filter(app.Property.price_per_night <= 500)
        matches = query.order_by(app.Property.rating.desc(), app.Property.review_count.desc()).all()
        if not matches:
            raise SystemExit("Barcelona filter fixture produced no matching hotels")

        for prop in matches:
            if not (prop.breakfast_included and prop.has_wifi and prop.rating >= 8.0
                    and 50 <= prop.price_per_night <= 500):
                raise SystemExit(f"invalid matching hotel fixture: {prop.name}")

        praktik = app.Property.query.filter_by(name="Praktik Èssens").first()
        if not praktik:
            raise SystemExit("missing Praktik Èssens fixture")
        expected = {
            "rating": 8.9,
            "review_count": 83,
            "price_per_night": 83.0,
            "stars": 3,
            "property_type": "Hotel",
            "brand": "Independent",
        }
        for field, value in expected.items():
            if getattr(praktik, field) != value:
                raise SystemExit(f"Praktik Èssens {field}={getattr(praktik, field)!r}, expected {value!r}")
        if not praktik.breakfast_included or not praktik.has_wifi:
            raise SystemExit("Praktik Èssens must satisfy breakfast + WiFi filters")

        hotel_brick = app.Property.query.filter_by(name="Hotel Brick Barcelona").first()
        if hotel_brick and hotel_brick.breakfast_included and hotel_brick.has_wifi:
            raise SystemExit("Hotel Brick Barcelona should not satisfy breakfast + WiFi filters")

        print("Booking filter fixture checks passed")


if __name__ == "__main__":
    main()

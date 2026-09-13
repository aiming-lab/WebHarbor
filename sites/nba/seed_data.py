#!/usr/bin/env python3
"""Build-time seed entry point for the NBA mirror."""
from app import app, db, seed_benchmark_users, seed_database


def main():
    with app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()


if __name__ == "__main__":
    main()

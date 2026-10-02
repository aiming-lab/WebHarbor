#!/usr/bin/env python3
"""Deterministic build-time seeder for the sec mirror.

Importing app.py already materializes the seed inside
`with app.app_context():` (db.create_all + the gated seed functions);
main() re-runs the same gated path as a no-op so this entry point is
idempotent. Run with PYTHONHASHSEED=0 during the image build so the
SQLite output is byte-reproducible.
"""
from app import main

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Deterministic build-time seeder for the ryanair mirror.

Thin wrapper: importing app.py already materializes the seed inside
`with app.app_context():` (db.create_all + the gated seed_database /
seed_benchmark_users); main() re-runs the same gated path as a no-op so this
entry point is idempotent. Run with PYTHONHASHSEED=0 during the image build so
the SQLite output is byte-reproducible: the benchmark users use a frozen
bcrypt hash and every other row comes from the tracked source_data_*.json
snapshots in a fixed order.
"""
from app import main

if __name__ == '__main__':
    main()

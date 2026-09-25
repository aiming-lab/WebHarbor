"""Preserve distinct source color codes when source color names collide."""
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path


def migrate(path):
    with sqlite3.connect(path) as con:
        groups = defaultdict(list)
        for vid, pid, color, sku in con.execute('SELECT id, product_id, color, sku FROM product_variants'):
            parts = sku.split('-')
            if len(parts) == 4 and parts[1].isdigit(): groups[pid, color].append((vid, parts[1]))
        changes = []
        for (pid, color), rows in groups.items():
            if len({code for _, code in rows}) > 1:
                changes.extend((f'{color} ({code})', vid) for vid, code in rows)
        if changes: con.executemany('UPDATE product_variants SET color=? WHERE id=?', changes)


if __name__ == '__main__':
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'instance_seed' / 'uniqlo.db'
    if path.is_dir(): path = path / 'instance_seed' / 'uniqlo.db'
    if not path.is_file(): raise SystemExit(f'Missing seed: {path}')
    migrate(path)

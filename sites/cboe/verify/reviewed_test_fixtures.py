"""Private synthetic contract fixtures; not browser or independent-agent evidence."""
import json
import sqlite3
from pathlib import Path
FIXTURES = json.loads(Path(__file__).with_name("reviewed_test_fixtures.json").read_text())

def fixture(number, base):
    data = FIXTURES[str(number)]
    steps = [(base + s[0], s[1], s[2], s[3]) for s in data["steps"]]
    def mutate(path):
        with sqlite3.connect(path) as db:
            for operation in data["changes"]:
                table = operation["table"]
                if operation["kind"] == "delete":
                    db.execute(f'DELETE FROM "{table}" WHERE id=?', (operation["id"],))
                else:
                    row = operation["row"]
                    columns = ", ".join('"' + key + '"' for key in row)
                    placeholders = ", ".join("?" for _ in row)
                    db.execute(f'INSERT OR REPLACE INTO "{table}" ({columns}) VALUES ({placeholders})', tuple(row.values()))
    return steps, data["answer"], mutate if data["changes"] else None

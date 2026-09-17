#!/usr/bin/env python3
"""Apply tracked Phys.org data-quality corrections to a downloaded seed database."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from seed_data import SOURCE_METADATA_OVERRIDES, VIEW_OVERRIDES, _truncate_summary

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "instance_seed" / "phys_org.db"
SYNTHETIC_FIRST_NAMES = {
    "Sarah", "Michael", "Ananya", "Jorge", "Mei", "David", "Priya", "Liam",
    "Fatima", "Hiroshi", "Olivia", "Karim", "Nina", "Oluwa", "Bjorn", "Elena",
}
SYNTHETIC_LAST_NAMES = {
    "Patel", "Garcia", "Nguyen", "Kowalski", "Rossi", "Tanaka", "Andersen",
    "Okafor", "Singh", "Yamamoto", "Hernandez", "Mueller", "Ahmed", "Park",
}


def _is_synthetic_author(author: str) -> bool:
    parts = author.split()
    return (
        len(parts) == 2
        and parts[0] in SYNTHETIC_FIRST_NAMES
        and parts[1] in SYNTHETIC_LAST_NAMES
    )


def migrate_database(database_path: str | Path = DEFAULT_DB) -> int:
    """Update changed rows and return the number of corrected articles."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    changed = 0
    try:
        rows = connection.execute(
            "SELECT a.id,a.slug,a.subtitle,a.body,a.author_name,a.source_journal,"
            "a.source_institution,a.doi_url,a.views,c.slug AS category_slug "
            "FROM articles a JOIN categories c ON c.id=a.category_id"
        ).fetchall()
        for row in rows:
            metadata = SOURCE_METADATA_OVERRIDES.get(row["slug"], {})
            source_body = (row["body"] or "").split("\n\n", 1)[0].strip()
            body = source_body
            if metadata.get("body_append"):
                body = f"{body}\n\n{metadata['body_append']}"
            author = row["author_name"] or ""
            if _is_synthetic_author(author):
                author = metadata.get("author") or (
                    "Tech Xplore" if row["category_slug"] == "technology" else "Phys.org"
                )
            corrected = (
                _truncate_summary(source_body),
                body,
                author,
                metadata.get("journal", ""),
                metadata.get("institution", ""),
                metadata.get("doi", ""),
                VIEW_OVERRIDES.get(row["slug"], row["views"]),
            )
            current = (
                row["subtitle"], row["body"], row["author_name"],
                row["source_journal"], row["source_institution"], row["doi_url"],
                row["views"],
            )
            if corrected == current:
                continue
            connection.execute(
                "UPDATE articles SET subtitle=?,body=?,author_name=?,source_journal=?,"
                "source_institution=?,doi_url=?,views=? WHERE id=?",
                (*corrected, row["id"]),
            )
            changed += 1
        if changed:
            connection.commit()
        return changed
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", nargs="?", default=str(DEFAULT_DB))
    args = parser.parse_args()
    changed = migrate_database(args.database)
    noun = "row" if changed == 1 else "rows"
    print(f"Phys.org seed migration complete: {changed} article {noun} changed.")


if __name__ == "__main__":
    main()

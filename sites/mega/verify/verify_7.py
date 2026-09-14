#!/usr/bin/env python3
"""MEGA--7: create Q3 Press Kit under /Projects/Atlas and upload press-summary.pdf 4.2 MB."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, cloud_items_for, load_run, navigated_to, parse_args,
                        resolve_db)

EMAIL = "alice.j@test.com"
FOLDER_NAME = "Q3 Press Kit"
PARENT = "/Projects/Atlas"
FILE_NAME = "press-summary.pdf"

def main():
    a = parse_args()
    j = Judge("MEGA--7", a.no_llm)
    t = load_run(a.run_dir)
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    j.bind_run(t, require_answer=False, shot_url="/cloud")
    j.check("nav_login", navigated_to(t, "/login"), "logged in")
    j.check("nav_drive", navigated_to(t, "/cloud") or navigated_to(t, "/drive"), "opened Cloud drive")
    seed_folders = cloud_items_for(init, EMAIL, item_type="folder", name=FOLDER_NAME) if init else None
    after_folders = cloud_items_for(after, EMAIL, item_type="folder", name=FOLDER_NAME) if after else None
    j.check("seed_no_folder", seed_folders == [], f"seed_folders={seed_folders!r}")
    folder_ok = False
    if after_folders:
        folder_ok = any(row[3] == PARENT and row[1].casefold() == FOLDER_NAME.casefold()
                        for row in after_folders)
    j.check("db_folder", folder_ok, f"folders={after_folders!r}")
    seed_files = cloud_items_for(init, EMAIL, name=FILE_NAME) if init else None
    after_files = cloud_items_for(after, EMAIL, name=FILE_NAME) if after else None
    j.check("seed_no_file", seed_files == [], f"seed_files={seed_files!r}")
    file_ok = False
    nested = f"{PARENT}/{FOLDER_NAME}"
    if after_files:
        for row in after_files:
            size = float(row[5] or 0)
            if abs(size - 4.2) > 0.05:
                continue
            folder = (row[3] or "").casefold()
            if "q3 press kit" in folder:
                file_ok = True
    j.check("db_file", file_ok, f"files={after_files!r}")
    j.emit()

if __name__ == "__main__":
    main()

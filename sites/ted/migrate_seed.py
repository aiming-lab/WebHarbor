#!/usr/bin/env python3
"""Apply idempotent integrity constraints to the downloaded TED seed database."""
from __future__ import annotations
import argparse
import sqlite3
from pathlib import Path

BASE_DIR=Path(__file__).resolve().parent
DEFAULT_DB=BASE_DIR/'instance_seed'/'ted.db'
INDEXES={
 'uq_saved_talk_user_talk':'CREATE UNIQUE INDEX uq_saved_talk_user_talk ON saved_talk(user_id,talk_id)',
 'uq_registration_user_event':'CREATE UNIQUE INDEX uq_registration_user_event ON registration(user_id,event_id)',
}

def migrate_database(database_path: str|Path=DEFAULT_DB)->int:
 con=sqlite3.connect(database_path)
 try:
  existing={row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='index'")};created=0
  for name,statement in INDEXES.items():
   if name not in existing:con.execute(statement);created+=1
  con.commit();return created
 finally:con.close()

def main()->None:
 parser=argparse.ArgumentParser();parser.add_argument('database',nargs='?',default=str(DEFAULT_DB));args=parser.parse_args();created=migrate_database(args.database);print(f'TED seed migration complete: {created} indexes created.')
if __name__=='__main__':main()

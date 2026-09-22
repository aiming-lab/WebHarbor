"""Regression controls alter copies of DB evidence, never a browser completion."""
from pathlib import Path
import shutil
import sqlite3
import sys
import pytest

SITE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SITE/'verify'))
from verify_lib import check_download_recorded, check_rename_recorded


class Checks:
    def __init__(self):self.results={}
    def check(self,name,condition,evidence=''):self.results[name]=bool(condition)


@pytest.mark.parametrize('corruption',[None,'DELETE FROM downloads WHERE id=1','UPDATE downloads SET user_id=4 WHERE id=1'])
def test_download_preserves_prior_history(tmp_path,corruption):
    initial=tmp_path/'initial.db';after=tmp_path/'after.db'
    shutil.copy2(SITE/'instance_seed/4shared.db',initial);shutil.copy2(initial,after)
    with sqlite3.connect(after) as c:
        c.execute("INSERT INTO downloads (user_id,file_id,downloaded_at) VALUES (NULL,81,'2026-09-21 12:00:00')")
        c.execute('UPDATE files SET download_count=download_count+1 WHERE id=81')
        if corruption:c.execute(corruption)
    checks=Checks();check_download_recorded(checks,initial,after,81)
    assert all(checks.results.values())==(corruption is None)
    if corruption:assert checks.results['prior_downloads_preserved'] is False


@pytest.mark.parametrize('event',[False,True])
def test_timestamps_alone_do_not_prove_rename(tmp_path,event):
    initial=tmp_path/'initial.db';after=tmp_path/'after.db'
    shutil.copy2(SITE/'instance_seed/4shared.db',initial);shutil.copy2(initial,after)
    with sqlite3.connect(after) as c:
        c.execute("UPDATE files SET filename='2027 Retreat Budget.xlsx',modified_at='2026-09-21 12:00:00' WHERE id=123")
        if event:c.execute("INSERT INTO file_renames (user_id,file_id,old_name,new_name,created_at) VALUES (1,123,'Alice Quarterly retreat budget.xlsx','2027 Retreat Budget.xlsx','2026-09-21 12:00:00')")
    checks=Checks();check_rename_recorded(checks,initial,after,123,1,'Alice Quarterly retreat budget.xlsx','2027 Retreat Budget.xlsx')
    assert all(checks.results.values())==event

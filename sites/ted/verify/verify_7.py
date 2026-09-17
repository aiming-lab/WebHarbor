#!/usr/bin/env python3
from verify_lib import Judge, changed_tables, check_common, load_run, login_submitted_as, parse_args, registration_snapshot, resolve_db, submitted_from_path, table_snapshot, visited_in_order
TASK_ID="TED--7";EMAIL="alice.j@test.com";EVENT="ted2026"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);check_common(j,t,TASK_ID);j.check("login_as_alice",login_submitted_as(t,EMAIL),EMAIL);j.check("ordered_events_flow",visited_in_order(t,[("/login",{}),("/events",{}),("/account",{})]),"login, events, account");j.check("registration_submitted",submitted_from_path(t,"/events","/account"),"events form submitted")
 initial=resolve_db(a.initial_db,a.container,"instance_seed");after=resolve_db(a.after_db,a.container,"instance");j.check("databases_readable",bool(initial and after),f"initial={initial} after={after}")
 if initial and after:
  before=registration_snapshot(initial,EMAIL);now=registration_snapshot(after,EMAIL);before_ids={r['id'] for r in before};added=[r for r in now if r['id'] not in before_ids]
  before_all=table_snapshot(initial,"registration");after_all=table_snapshot(after,"registration")
  j.check("exact_registration_delta",len(added)==1 and added[0]['slug']==EVENT and added[0]['status']=='waitlisted' and len(now)==len(before)+1 and all(r in now for r in before),repr(added));j.check("complete_registration_table_delta",len(after_all)==len(before_all)+1 and all(row in after_all for row in before_all),f"before={len(before_all)} after={len(after_all)}");j.check("only_registration_changed",changed_tables(initial,after)=={"registration"},repr(changed_tables(initial,after)))
 j.emit()
if __name__=="__main__":main()

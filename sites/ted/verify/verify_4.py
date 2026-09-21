#!/usr/bin/env python3
from verify_lib import Judge, changed_tables, check_common, load_run, login_submitted_as, parse_args, resolve_db, submitted_from_path, user_snapshot, visited_in_order
TASK_ID="TED--4";EMAIL="alice.j@test.com"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);check_common(j,t,TASK_ID);j.check("login_as_alice",login_submitted_as(t,EMAIL),EMAIL);j.check("ordered_account_flow",visited_in_order(t,[("/login",{}),("/account",{})]),"login then account");j.check("profile_submitted",submitted_from_path(t,"/account","/account"),"account form submitted")
 initial=resolve_db(a.initial_db,a.container,"instance_seed");after=resolve_db(a.after_db,a.container,"instance");j.check("databases_readable",bool(initial and after),f"initial={initial} after={after}")
 if initial and after:
  before=user_snapshot(initial);now=user_snapshot(after);expected=[dict(r) for r in before]
  for row in expected:
   if row['email']==EMAIL:row['newsletter_topic']='conservation'
  j.check("only_requested_profile_field_changed",now==expected,f"before={before} after={now}");j.check("only_user_table_changed",changed_tables(initial,after)=={"user"},repr(changed_tables(initial,after)))
 j.emit()
if __name__=="__main__":main()

#!/usr/bin/env python3
from verify_lib import Judge, changed_tables, check_common, clicked_transition, load_run, login_submitted_as, parse_args, resolve_db, saved_snapshot, submitted_from_path, table_snapshot, visited_in_order
TASK_ID="TED--9";EMAIL="alice.j@test.com";SLUG="joy-milne-the-nurse-who-can-smell-parkinson-s";PATH=f"/talks/{SLUG}"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);check_common(j,t,TASK_ID);j.check("login_as_alice",login_submitted_as(t,EMAIL),EMAIL);j.check("ordered_parkinson_save_flow",visited_in_order(t,[("/login",{}),("/search",{"q":"Parkinson"}),(PATH,{})]),"login, search, detail");j.check("clicked_parkinson_result",clicked_transition(t,"/search",PATH),"detail opened from search");j.check("save_submitted",submitted_from_path(t,PATH,PATH),"save form submitted")
 initial=resolve_db(a.initial_db,a.container,"instance_seed");after=resolve_db(a.after_db,a.container,"instance");j.check("databases_readable",bool(initial and after),f"initial={initial} after={after}")
 if initial and after:
  before=saved_snapshot(initial,EMAIL);now=saved_snapshot(after,EMAIL);before_ids={r['id'] for r in before};added=[r for r in now if r['id'] not in before_ids]
  before_all=table_snapshot(initial,"saved_talk");after_all=table_snapshot(after,"saved_talk")
  j.check("exact_saved_delta",len(added)==1 and added[0]['slug']==SLUG and added[0]['note']=="public health review" and len(now)==len(before)+1 and all(r in now for r in before),repr(added));j.check("complete_saved_table_delta",len(after_all)==len(before_all)+1 and all(row in after_all for row in before_all),f"before={len(before_all)} after={len(after_all)}");j.check("only_saved_talk_changed",changed_tables(initial,after)=={"saved_talk"},repr(changed_tables(initial,after)))
 j.emit()
if __name__=="__main__":main()

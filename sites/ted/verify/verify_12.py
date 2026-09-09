#!/usr/bin/env python3
import json
from verify_lib import Judge, changed_tables, check_common, contains_all, final_answer, load_run, login_submitted_as, parse_args, resolve_db, saved_snapshot, submitted_from_path, table_snapshot, visited_in_order
TASK_ID="TED--12";EMAIL="alice.j@test.com"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check("login_as_alice",login_submitted_as(t,EMAIL),EMAIL);j.check("ordered_account_flow",visited_in_order(t,[("/login",{}),("/account",{})]),"login then account");j.check("remove_submitted",submitted_from_path(t,"/account","/account"),"remove form submitted")
 initial=resolve_db(a.initial_db,a.container,"instance_seed");after=resolve_db(a.after_db,a.container,"instance");j.check("databases_readable",bool(initial and after),f"initial={initial} after={after}")
 if initial and after:
  before=saved_snapshot(initial,EMAIL);now=saved_snapshot(after,EMAIL);now_ids={r['id'] for r in now};removed=[r for r in before if r['id'] not in now_ids]
  before_all=table_snapshot(initial,"saved_talk");after_all=table_snapshot(after,"saved_talk")
  non_ai=len(removed)==1 and "ai" not in {v.casefold() for v in json.loads(removed[0]['topics_json'])};j.check("one_non_ai_talk_removed",non_ai and len(now)==len(before)-1 and all(r in before for r in now),repr(removed));j.check("complete_saved_table_delta",len(after_all)==len(before_all)-1 and all(row in before_all for row in after_all),f"before={len(before_all)} after={len(after_all)}");j.check("answer_removed_title",len(removed)==1 and contains_all(answer,(removed[0]['title'],)),repr(answer));j.check("only_saved_talk_changed",changed_tables(initial,after)=={"saved_talk"},repr(changed_tables(initial,after)))
 j.emit()
if __name__=="__main__":main()

#!/usr/bin/env python3
from verify_lib import SEED_EMAILS, Judge, changed_tables, check_common, clicked_transition, contains_all, final_answer, load_run, parse_args, resolve_db, row_dicts, submitted_from_path, table_snapshot, user_snapshot, visited_in_order
TASK_ID="TED--16";SLUG="peter-steinberger-how-i-created-openclaw-the-breakthrough-ai-agent";PATH=f"/talks/{SLUG}";TITLE="How I created OpenClaw, the breakthrough AI agent"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check("ordered_register_save_confirm",visited_in_order(t,[("/register",{}),("/account",{}),("/search",{"q":"OpenClaw"}),(PATH,{}),("/account",{})]),"register, search, detail, account");j.check("registration_submitted",submitted_from_path(t,"/register","/account"),"registration form submitted");j.check("clicked_openclaw_result",clicked_transition(t,"/search",PATH),"detail opened from search");j.check("save_submitted",submitted_from_path(t,PATH,PATH),"save submitted")
 initial=resolve_db(a.initial_db,a.container,"instance_seed");after=resolve_db(a.after_db,a.container,"instance");j.check("databases_readable",bool(initial and after),f"initial={initial} after={after}")
 if initial and after:
  before=user_snapshot(initial);now=user_snapshot(after);before_ids={r['id'] for r in before};new_users=[r for r in now if r['id'] not in before_ids]
  saved=[]
  if len(new_users)==1:saved=row_dicts(after,"SELECT t.slug,t.title,s.note FROM saved_talk s JOIN talk t ON t.id=s.talk_id WHERE s.user_id=?",(new_users[0]['id'],))
  before_saved=table_snapshot(initial,"saved_talk");after_saved=table_snapshot(after,"saved_talk")
  j.check("one_new_nonseed_user",len(new_users)==1 and new_users[0]['email'] not in SEED_EMAILS and len(now)==len(before)+1 and all(r in now for r in before),repr(new_users));j.check("new_user_saved_only_openclaw",len(saved)==1 and saved[0]['slug']==SLUG and len(after_saved)==len(before_saved)+1 and all(row in after_saved for row in before_saved),repr(saved));j.check("only_user_and_saved_changed",changed_tables(initial,after)=={"user","saved_talk"},repr(changed_tables(initial,after)));j.check("answer_exact_saved_title",contains_all(answer,(TITLE,)),repr(answer))
 j.emit()
if __name__=="__main__":main()

#!/usr/bin/env python3
from verify_lib import Judge, affirmative_contains, check_common, check_read_only, clicked_transition, contains_any, final_answer, has_number, load_run, number_bound_in_comparison, parse_args, visited_in_order
TASK_ID='Ohio State University--15';W='/athletics/ohio-state-buckeyes-wrestling';F='/athletics/ohio-state-buckeyes-fencing'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('athletics_then_both_details',visited_in_order(t,[('/athletics',{}),(W,{})]) and visited_in_order(t,[('/athletics',{}),(F,{})]),'listing before details');j.check('clicked_both_teams',clicked_transition(t,'/athletics',W) and clicked_transition(t,'/athletics',F),'visible team links used');j.check('wrestling_titles_bound',number_bound_in_comparison(answer,8,('wrestling',)),repr(answer));j.check('fencing_titles_bound',number_bound_in_comparison(answer,2,('fencing',)),repr(answer));j.check('winner_and_difference',affirmative_contains(answer,'wrestling') and contains_any(answer,('more','higher')) and has_number(answer,6),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

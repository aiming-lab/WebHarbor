#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, final_answer, load_run, parse_args, text_bound_in_comparison, visited_in_order
TASK_ID='Ohio State University--14';F='/athletics/ohio-state-buckeyes-football';B='/athletics/ohio-state-buckeyes-mens-basketball'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('athletics_then_both_details',visited_in_order(t,[('/athletics',{}),(F,{})]) and visited_in_order(t,[('/athletics',{}),(B,{})]),'listing before details');j.check('clicked_both_teams',clicked_transition(t,'/athletics',F) and clicked_transition(t,'/athletics',B),'visible team links used');j.check('football_venue_bound',text_bound_in_comparison(answer,'Ohio Stadium',('football',)),repr(answer));j.check('basketball_venue_bound',text_bound_in_comparison(answer,'Value City Arena',('basketball',)),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

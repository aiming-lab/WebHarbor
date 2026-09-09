#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID='Ohio State University--2';F='/athletics/ohio-state-buckeyes-football';W='/athletics/ohio-state-buckeyes-wrestling'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('athletics_then_both_details',visited_in_order(t,[('/athletics',{}),(F,{})]) and visited_in_order(t,[('/athletics',{}),(W,{})]),'listing precedes details');j.check('clicked_both_teams',clicked_transition(t,'/athletics',F) and clicked_transition(t,'/athletics',W),'visible team links used');j.check('answer_big_ten_both',contains_all(answer,('football','wrestling','Big Ten')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

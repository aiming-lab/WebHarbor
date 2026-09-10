#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID='Ohio State University--10';PATH='/athletics/ohio-state-buckeyes-wrestling'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('ordered_wrestling_navigation',visited_in_order(t,[('/athletics',{}),(PATH,{})]) and clicked_transition(t,'/athletics',PATH),'athletics to wrestling');j.check('answer_coach_and_venue',contains_all(answer,('Tom Ryan','Covelli Center')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID='Ohio State University--3';PATH='/athletics/ohio-state-buckeyes-football'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('ordered_football_navigation',visited_in_order(t,[('/athletics',{}),(PATH,{})]) and clicked_transition(t,'/athletics',PATH),'athletics listing to football');j.check('answer_coach_and_record',contains_all(answer,('Ryan Day','11-2')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

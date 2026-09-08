#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID='Ohio State University--13';PATH='/departments/department-of-mathematics'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('ordered_math_navigation',visited_in_order(t,[('/departments',{}),(PATH,{})]) and clicked_transition(t,'/departments',PATH),'departments to Mathematics');j.check('answer_chair_and_location',contains_all(answer,('James Cogdell','100 Mathematics Building')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

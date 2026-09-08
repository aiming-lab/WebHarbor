#!/usr/bin/env python3
from verify_lib import Judge, affirmative_contains, check_common, check_read_only, contains_any, final_answer, has_number, load_run, number_bound_in_comparison, parse_args, visited_path
TASK_ID='Ohio State University--8'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('opened_academics',visited_path(t,'/academics'),'required=/academics');j.check('engineering_count_bound',number_bound_in_comparison(answer,8000,('Engineering',)),repr(answer));j.check('fisher_count_bound',number_bound_in_comparison(answer,4500,('Fisher',)),repr(answer));j.check('difference_and_winner',has_number(answer,3500) and affirmative_contains(answer,'Engineering') and contains_any(answer,('more','higher')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

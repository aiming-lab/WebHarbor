#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, final_answer, has_number, load_run, number_bound_in_comparison, parse_args, visited_path
TASK_ID='Ohio State University--7'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('opened_about',visited_path(t,'/about'),'required=/about');j.check('undergraduate_bound',number_bound_in_comparison(answer,46820,('undergraduate','undergrads')),repr(answer));j.check('graduate_bound',number_bound_in_comparison(answer,14000,('graduate','graduate students')),repr(answer));j.check('exact_difference',has_number(answer,32820),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

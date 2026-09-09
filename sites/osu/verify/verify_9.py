#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, contains_word, final_answer, has_number, load_run, parse_args, visited_query
TASK_ID='Ohio State University--9'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('engineering_filter',visited_query(t,'/programs',{'college':'engineering'}),'college=engineering');j.check('answer_all_types',all(contains_word(answer,value) for value in ('BS','MS','PhD')) and has_number(answer,3),repr(answer));j.check('no_extra_degree_types',not any(contains_word(answer,value) for value in ('BA','MA','MBA','JD','MD','MPH','PharmD','DVM','OD')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

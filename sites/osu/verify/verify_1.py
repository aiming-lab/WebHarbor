#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, contains_all, final_answer, has_number, load_run, parse_args, visited_path
TASK_ID='Ohio State University--1'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('opened_about',visited_path(t,'/about'),'required=/about');j.check('answer_varsity_sports',has_number(answer,36) and contains_all(answer,('varsity','sports')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

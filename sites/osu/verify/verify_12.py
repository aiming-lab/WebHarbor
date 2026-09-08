#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, contains_word, final_answer, has_number, load_run, parse_args, visited_in_order
TASK_ID='Ohio State University--12';PATH='/programs/juris-doctor-jd'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('ordered_jd_search',visited_in_order(t,[('/programs',{'q':'Juris Doctor'}),(PATH,{})]) and clicked_transition(t,'/programs',PATH),'program search to JD');j.check('answer_jd_details',contains_word(answer,'JD') and has_number(answer,90) and has_number(answer,3) and contains_all(answer,('credits','years')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

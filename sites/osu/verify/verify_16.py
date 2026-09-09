#!/usr/bin/env python3
from verify_lib import Judge, affirmative_contains, check_common, check_read_only, clicked_transition, contains_all, contains_word, final_answer, load_run, parse_args, visited_in_order, visited_query
TASK_ID='Ohio State University--16';PATH='/programs/master-of-business-administration-mba'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('mba_filter',visited_query(t,'/programs',{'degree':'MBA'}),'degree=MBA');j.check('ordered_mba_navigation',visited_in_order(t,[('/programs',{'degree':'MBA'}),(PATH,{})]) and clicked_transition(t,'/programs',PATH),'filtered programs to MBA');j.check('answer_mba_details',contains_all(answer,('April 1','credits')) and contains_word(answer,'60') and contains_word(answer,'GRE') and affirmative_contains(answer,'not required'),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

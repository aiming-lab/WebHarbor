#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, has_number, load_run, parse_args, visited_in_order
TASK_ID='Ohio State University--4';PATH='/news/ohio-state-sets-record-for-research-expenditures-at-13-billion'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('ordered_news_search',visited_in_order(t,[('/search',{'q':'research expenditures'}),(PATH,{})]) and clicked_transition(t,'/search',PATH),'search to exact article');j.check('answer_amount_date',has_number(answer,1.3) and contains_all(answer,('billion','September','23','2024')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

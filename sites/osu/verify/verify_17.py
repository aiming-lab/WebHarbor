#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID='Ohio State University--17';PATH='/news/ohio-state-researchers-develop-breakthrough-cancer-immunotherapy';TITLE='Ohio State Researchers Develop Breakthrough Cancer Immunotherapy'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('ordered_cancer_search',visited_in_order(t,[('/search',{'q':'cancer research'}),(PATH,{})]) and clicked_transition(t,'/search',PATH),'search to exact article');j.check('answer_title_author',contains_all(answer,(TITLE,'Jody Sheridan')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

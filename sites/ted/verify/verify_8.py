#!/usr/bin/env python3
from verify_lib import Judge, affirmative_contains, check_common, check_read_only, clicked_transition, contains_any, final_answer, load_run, number_bound_in_comparison, parse_args, visited_path
TASK_ID="TED--8";A="/talks/alexi-pappas-why-i-love-my-bad-days";D="/talks/debbie-millman-you-got-what-you-wanted-now-what"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check("opened_both_from_search",visited_path(t,A) and visited_path(t,D) and clicked_transition(t,"/search",A) and clicked_transition(t,"/search",D),"both detail links opened from searches");j.check("alexi_duration_bound",number_bound_in_comparison(answer,5,("Alexi","bad days")),repr(answer));j.check("debbie_duration_bound",number_bound_in_comparison(answer,8,("Debbie","wanted")),repr(answer));j.check("alexi_identified_shorter",affirmative_contains(answer,"Alexi") and contains_any(answer,("shorter","less time")),repr(answer));check_read_only(j,a);j.emit()
if __name__=="__main__":main()

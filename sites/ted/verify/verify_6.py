#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID="TED--6";PATH="/talks/kimiko-hirata-a-cheat-sheet-for-accelerating-clean-energy"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check("ordered_clean_energy_search",visited_in_order(t,[("/search",{"q":"clean energy"}),(PATH,{})]),"search before detail");j.check("clicked_kimiko_result",clicked_transition(t,"/search",PATH),"detail opened from search");j.check("answer_exact_event",contains_all(answer,("TED Countdown Summit 2025",)),repr(answer));check_read_only(j,a);j.emit()
if __name__=="__main__":main()

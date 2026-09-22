#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID="TED--14";PATH="/talks/riyad-joucka-reimagining-traditional-architecture-for-modern-needs"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check("ordered_architecture_search",visited_in_order(t,[("/search",{"q":"architecture 3D printing"}),(PATH,{})]),"search before detail");j.check("clicked_riyad_result",clicked_transition(t,"/search",PATH),"detail opened from search");j.check("answer_speaker",contains_all(answer,("Riyad Joucka",)),repr(answer));check_read_only(j,a);j.emit()
if __name__=="__main__":main()

#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_any, final_answer, has_number, load_run, parse_args, visited_in_order
TASK_ID="TED--0"; PATH="/talks/anil-seth-why-ai-is-unlikely-to-become-conscious"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID)
 j.check("ordered_ai_search_to_talk",visited_in_order(t,[("/search",{"q":"AI"}),(PATH,{})]),"AI search before detail")
 j.check("clicked_anil_result",clicked_transition(t,"/search",PATH),"detail opened from search")
 j.check("answer_duration",has_number(answer,15) and contains_any(answer,("minute","minutes")),repr(answer));check_read_only(j,a);j.emit()
if __name__=="__main__":main()

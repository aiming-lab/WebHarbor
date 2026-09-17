#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID="TED--5";PATH="/talks/malala-yousafzai-what-i-got-wrong-about-changing-the-world";TITLE="What I got wrong about changing the world"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check("ordered_malala_search",visited_in_order(t,[("/search",{"q":"Malala Yousafzai"}),(PATH,{})]),"search before detail");j.check("clicked_malala_result",clicked_transition(t,"/search",PATH),"detail opened from search");j.check("answer_exact_title",contains_all(answer,(TITLE,)),repr(answer));check_read_only(j,a);j.emit()
if __name__=="__main__":main()

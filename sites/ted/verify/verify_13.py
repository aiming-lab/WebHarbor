#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID="TED--13";PATH="/talks/qian-janice-wang-the-art-and-science-of-wine-tasting"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check("ordered_science_topic_flow",visited_in_order(t,[("/topics",{}),("/talks",{"topic":"science"}),(PATH,{})]),"topics, science listing, detail");j.check("clicked_science_and_talk",clicked_transition(t,"/topics","/talks") and clicked_transition(t,"/talks",PATH),"visible links used");j.check("answer_title_and_speaker",contains_all(answer,("The art and science of wine tasting","Qian Janice Wang")),repr(answer));check_read_only(j,a);j.emit()
if __name__=="__main__":main()

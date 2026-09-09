#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order, visited_query
TASK_ID="TED--11";PATH="/talks/maya-higa-the-wildlife-sanctuary-you-can-visit-from-anywhere";FILTERS={"event":"TED2026","max_minutes":"10"}
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check("exact_listing_filters",visited_query(t,"/talks",FILTERS),repr(FILTERS));j.check("ordered_filter_to_detail",visited_in_order(t,[("/talks",FILTERS),(PATH,{})]),"filtered listing before detail");j.check("clicked_maya_result",clicked_transition(t,"/talks",PATH),"detail opened from listing");j.check("answer_exact_title",contains_all(answer,("The wildlife sanctuary you can visit from anywhere",)),repr(answer));check_read_only(j,a);j.emit()
if __name__=="__main__":main()

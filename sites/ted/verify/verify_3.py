#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID="TED--3";PLAYLIST="/playlists/climate-nature-conservation";MAYA="/talks/maya-higa-the-wildlife-sanctuary-you-can-visit-from-anywhere";ROSE="/talks/rose-b-simpson-debbie-millman-how-to-invite-creativity-into-your-life";TARGET="/talks/elsaphan-njora-conservation-a-love-story"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID)
 j.check("ordered_playlist_inspection",visited_in_order(t,[("/playlists",{}),(PLAYLIST,{}),(MAYA,{}),(ROSE,{}),(TARGET,{})]),"playlist and first three details in order")
 j.check("clicked_playlist_and_talks",clicked_transition(t,"/playlists",PLAYLIST) and all(clicked_transition(t,PLAYLIST,p) for p in (MAYA,ROSE,TARGET)),"visible playlist links used")
 j.check("answer_exact_title",contains_all(answer,("Conservation: a love story",)),repr(answer));check_read_only(j,a);j.emit()
if __name__=="__main__":main()

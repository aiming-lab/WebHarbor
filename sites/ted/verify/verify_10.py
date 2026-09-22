#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_in_order
TASK_ID="TED--10";PLAYLIST="/playlists/ai-and-society";PATH="/talks/neal-kumar-katyal-what-really-won-the-trillion-dollar-supreme-court-case"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check("ordered_playlist_to_talk",visited_in_order(t,[("/playlists",{}),(PLAYLIST,{}),(PATH,{})]),"playlists, named playlist, detail");j.check("clicked_playlist_and_talk",clicked_transition(t,"/playlists",PLAYLIST) and clicked_transition(t,PLAYLIST,PATH),"visible links used");j.check("answer_title_and_speaker",contains_all(answer,("What really won the trillion-dollar Supreme Court case","Neal Kumar Katyal")),repr(answer));check_read_only(j,a);j.emit()
if __name__=="__main__":main()

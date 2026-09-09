#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, contains_all, final_answer, load_run, parse_args, visited_path
TASK_ID="TED--17"
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check("opened_events",visited_path(t,"/events"),"events page visited");j.check("answer_event_month_year",contains_all(answer,("TEDNext 2025","November 2025")),repr(answer));check_read_only(j,a);j.emit()
if __name__=="__main__":main()

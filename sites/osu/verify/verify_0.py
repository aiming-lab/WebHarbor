#!/usr/bin/env python3
from verify_lib import Judge, check_common, check_read_only, clicked_transition, contains_all, final_answer, load_run, parse_args, visited_path
TASK_ID='Ohio State University--0'
def main():
 a=parse_args();t=load_run(a.run_dir);j=Judge(TASK_ID);answer=final_answer(t);check_common(j,t,TASK_ID);j.check('opened_academics',visited_path(t,'/academics'),'required=/academics');j.check('used_academics_link',clicked_transition(t,'/','/academics'),'home to academics click');j.check('answer_fisher_dean',contains_all(answer,('Fisher College of Business','Anil Makhija')),repr(answer));check_read_only(j,a);j.emit()
if __name__=='__main__':main()

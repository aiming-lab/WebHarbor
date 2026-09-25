"""Current coherent task checks; source facts remain outside agent-facing tasks."""
import re
from verify_lib import *

def fact(judge, answer, name, *patterns):
    text = normalize_text(answer)
    ok = all(re.search(pattern, text, re.I) for pattern in patterns)
    judge.check(name, ok, 'required facts and relationships')

def paths(judge, traj, *values):
    for value in values:
        check_visited_path(judge, traj, 'visited_' + value, value)


import bcrypt

def check_password_hash(value, password):
    try:
        return bcrypt.checkpw(password.encode(), value.encode())
    except (ValueError, TypeError):
        return False

def run_checks(judge, traj, initial_db, after_db):
    i = int(judge.task_id.rsplit('--', 1)[1]); answer = final_answer(traj)
    check_trajectory_identity(judge, traj, judge.task_id)
    if i == 10:
        paths(judge, traj, '/news-and-events/news/november-2025-hire-a-veteran-month-events', '/contact-us')
        before = db_query(initial_db, 'SELECT id FROM contact_messages');ids = {r['id'] for r in before}
        rows = [r for r in db_query(after_db, 'SELECT * FROM contact_messages') if r['id'] not in ids]
        judge.check('one_inquiry', len(rows) == 1, str(len(rows)))
        if rows:
            r=rows[0]
            judge.check('inquiry_identity', r['name'] == 'Alex Morgan' and r['email'] == 'alex.morgan@example.com' and r['subject'] == 'Career fair accessibility', 'requested sender and subject')
            fact(judge, r['message'], 'inquiry_details', r'moaa', r'(?:december|dec\.?) 4', r'(?:caption|subtitl)')
        fact(judge, answer, 'event_and_confirmation', r'moaa virtual career fair', r'(?:december|dec\.?) 4', r'(?:sent|submitted)')
    elif i == 11:
        check_signed_in_as(judge, traj, 'alice.j@test.com')
        paths(judge, traj, '/help-center/common-questions', '/account/change-password', '/account/profile')
        u=user_by_email(after_db, 'alice.j@test.com')
        judge.check('new_password', check_password_hash(u['password_hash'], 'Nursing2026!'), 'requested password saved')
        login_steps=[s for s in traj.get('steps', []) if '/account/login' in str(s.get('url', '')) and s.get('action') in INPUT_ACTIONS and 'Nursing2026!' in str(s.get('params',{}))]
        judge.check('signed_back_in', bool(login_steps), 'new password used in login form')
        fact(judge, answer, 'password_rules', r'8.{0,6}20', r'number|digit', r'symbol', r'upper', r'lower')
    elif i == 16:
        check_signed_in_as(judge, traj, 'david.k@test.com')
        paths(judge, traj, '/account/career-plan')
        judge.check('scholarship_help', navigated_to_path_any(traj, ['/help-center/common-questions', '/help-center/education']), 'scholarship help page')
        old={r['id'] for r in db_query(initial_db, 'SELECT id FROM career_plan_tasks')}
        rows=[r for r in db_query(after_db, 'SELECT * FROM career_plan_tasks') if r['id'] not in old]
        judge.check('one_milestone', len(rows) == 1, str(len(rows)))
        if rows:
            r=rows[0];judge.check('milestone_owner_date', r['user_id'] == 4 and str(r['deadline']) == '2026-10-15' and not r['done'], 'David upcoming task')
            fact(judge, r['description'], 'scholarship_criteria', r'scholarship', r'major', r'grade', r'zip|postal', r'gpa', r'college')
        fact(judge, answer, 'milestone_confirmation', r'scholarship', r'2026-10-15|october 15,? 2026')

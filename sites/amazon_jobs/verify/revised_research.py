"""Additional research checks for the revised application tasks."""
import re
from urllib.parse import urlsplit, parse_qs
from verify_lib import affirms, final_answer, navigated_job, shot_at, step_urls
from reviewed_contract import CONTRACT

def check_research(j, number, traj):
    spec = CONTRACT['revised'].get(str(number), {})
    if spec.get('kind') == 'alert':
        wanted = {'base_query': spec['query'], 'loc_keyword': spec['location']}
        def matches(url):
            u = urlsplit(url); q = parse_qs(u.query, keep_blank_values=True)
            return u.path == '/search' and all(q.get(k, [''])[0].casefold() == v.casefold() for k,v in wanted.items())
        # Confirmation must follow creation, rather than merely reusing the earlier research search.
        steps = traj.get('steps', []); alerts = [i for i,s in enumerate(steps) if urlsplit(s.get('url','')).path == '/applicant/job-alerts']
        j.check('alert_matching_search', bool(alerts) and any(matches(s.get('url','')) for s in steps[min(alerts)+1:]), 'Open matching jobs for the newly created alert')
    if number not in [16,22,23]:
        return
    job, company, city = {16:('10555689','Amazon.com Services LLC','Seattle'),22:('10555688','ADCI - Maharashtra','Pune'),23:('10498057','Amazon Commercial Services Pty Ltd','Sydney')}[number]
    final = final_answer(traj)
    j.check('role_details', navigated_job(traj, job) and shot_at(traj, '/jobs/'+job)[0], job)
    j.check('role_company', affirms(final, company), company)
    if number != 22:
        j.check('role_city', affirms(final, city), city)
    else:
        for title,status in [('EC2 Nitro Team','Interview'),('AI Runtime','Under review'),('Humorphic Labs','Submitted')]:
            clause = next((part for part in re.split(r'[;\n]+',final) if title.casefold() in part.casefold()), '')
            j.check('application_status_'+title, affirms(clause,status), title+' '+status)
    if number in [22,23]:
        steps=traj.get('steps',[]); detail=[i for i,s in enumerate(steps) if '/jobs/'+job in s.get('url','')]
        j.check('return_to_applications', bool(detail) and any(urlsplit(s.get('url','')).path == '/applicant/dashboard/applications' for s in steps[max(detail)+1:]), 'Return to applications after inspecting role')

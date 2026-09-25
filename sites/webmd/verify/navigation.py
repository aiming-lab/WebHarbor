"""Task-specific observed navigation. Paths, visible content, and order all matter."""
from evidence import normalized

ARTICLES = {
    0: 'fall-asleep-faster', 1: 'rsv-vaccine-adults-50s',
    2: 'meal-prep-90-minute-system', 3: 'hydration-how-much-water',
    5: 'melatonin-evidence', 10: 'gout-attacks-prevention', 16: 'gout-attacks-prevention',
}
DRUGS = {4: 'tamsulosin', 6: 'warfarin', 7: 'levothyroxine', 8: 'sumatriptan', 9: 'apixaban'}


def navigation_ok(e, task):
    groups = []
    if task in (0, 1, 2):
        section, topic = [('well-being', 'Sleep'), ('news', 'Research & Approvals'), ('diet-weight', 'Food & Recipes')][task]
        groups.append(e.at('/section/' + section, topic, query={'topic': topic}))
    if task in (3, 4, 5):
        queries = {3: ('water', 'hydration'), 4: ('flomax',), 5: ('melatonin',)}[task]
        groups.append([p for p in e.at('/search', 'Search results') if any(q in normalized(' '.join(p[2].get('q', []))) for q in queries)])
    if task in (8, 9, 10, 11):
        slug, title = {8: ('migraine', 'Migraine'), 9: ('atrial-fibrillation', 'Atrial Fibrillation'), 10: ('gout', 'Gout'), 11: ('vertigo-bppv', 'Vertigo (BPPV)')}[task]
        groups.append(e.at('/condition/' + slug, title, 'Treatments'))
    if task in (16, 17, 18):
        groups.append(e.at('/login', 'Log In to WebMD'))
    if task in ARTICLES:
        slug = ARTICLES[task]
        a = next(a for a in e.initial['articles'] if a['slug'] == slug)
        groups.append(e.at('/articles/' + slug, a['title'], 'Medically reviewed by'))
    if task in DRUGS:
        slug = DRUGS[task]
        groups.append(e.at('/drug/' + slug, slug, 'Dosage', 'Interactions'))
    if task == 5:
        groups.append(e.at('/authors/steven-marsh-pharmd', 'Steven Marsh', 'PharmD, BCPS'))
    if task in (12, 13):
        selected = ['Dizziness', 'Fatigue', 'Heart palpitations', 'Shortness of breath'] if task == 12 else ['Fever', 'Frequent urination', 'Painful urination']
        winner = 'Atrial Fibrillation' if task == 12 else 'Urinary Tract Infection (UTI)'
        n = len(selected)
        results = []
        for p in e.at('/symptom-checker', 'Possible Matches', 'Based on your selected symptoms:', winner, f'{n} of {n} symptoms match'):
            picked = p[3].split('based on your selected symptoms:', 1)[1].split('ranked by', 1)[0].strip(' .')
            if picked == normalized(', '.join(selected)):
                # Ensure the expected winner is the first result, not another
                # matching condition somewhere further down the result list.
                result = p[3].split('each condition shares.', 1)
                if len(result) == 2 and result[1].strip().startswith(normalized(winner)):
                    results.append(p)
        groups.append(results)
    if task == 14:
        groups.append(e.at('/authors/lucia-ferreira-md', 'Lucia Ferreira', 'Board-Certified Gastroenterology', 'Medically reviewed by'))
    if task == 15:
        groups.extend([e.at('/register', 'Create Your WebMD Account'), e.at('/account', 'Jordan Rivera', 'jordan.rivera@example.com', 'Log Out')])
    if task == 16:
        groups.append(e.saved_page('alice.j@test.com', after=True))
    if task == 17:
        # Check observed state transitions; /logout is a redirect, not a page.
        groups.extend([
            e.at('/account', 'Your password has been updated.', 'bob.m@test.com'),
            e.at('/', 'You have been logged out.', 'Log In'),
            e.at('/login', 'Log In to WebMD'),
            e.at('/account', 'Bob Martinez', 'bob.m@test.com', 'Log Out'),
        ])
    if task == 18:
        groups.append(e.saved_page('carol.w@test.com'))
    if task == 19:
        # Either comparison order is valid.
        return bool(e.at('/drug/atorvastatin', 'Atorvastatin', 'Used For') and
                    e.at('/drug/rosuvastatin', 'Rosuvastatin', 'Used For'))
    return bool(groups) and e.ordered(groups)

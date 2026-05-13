"""Health check module for OSU mirror site."""


def health_check(app, db, College, Program):
    """Return health status dict."""
    try:
        with app.app_context():
            college_count = College.query.count()
            program_count = Program.query.count()
            return {
                'ok': True,
                'site': 'osu',
                'colleges': college_count,
                'programs': program_count,
            }
    except Exception as e:
        return {'ok': False, 'error': str(e)}

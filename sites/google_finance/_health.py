"""Per-site health probe (called by control_server)."""


def health():
    from app import Instrument, NewsArticle, app
    with app.app_context():
        return {'ok': Instrument.query.count() > 0,
                'site': 'google_finance',
                'instruments': Instrument.query.count(),
                'news': NewsArticle.query.count()}

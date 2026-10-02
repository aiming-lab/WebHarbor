"""Per-site health probe (called by control_server)."""


def health():
    try:
        from app import (AdminProceeding, Company, FastAnswer, Filing,
                          FormIndex, FtsDoc, InvestorAlert, LitRelease,
                          PressRelease, TradingSuspension, User)
        counts = {
            'companies': Company.query.count(),
            'filings': Filing.query.count(),
            'press_releases': PressRelease.query.count(),
            'lit_releases': LitRelease.query.count(),
            'admin_proceedings': AdminProceeding.query.count(),
            'trading_suspensions': TradingSuspension.query.count(),
            'fts_docs': FtsDoc.query.count(),
            'fast_answers': FastAnswer.query.count(),
            'investor_alerts': InvestorAlert.query.count(),
            'form_index': FormIndex.query.count(),
            'users': User.query.count(),
        }
        return {'ok': all(v > 0 for v in counts.values()),
                'site': 'sec', 'counts': counts}
    except Exception as exc:  # pragma: no cover
        return {'ok': False, 'site': 'sec', 'error': str(exc)}

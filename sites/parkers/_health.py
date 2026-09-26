"""Per-site health probe for the Parkers mirror (called via /_health).

Reports live DB counts so the control plane can see the site is serving
seeded data. Must be imported *within* the app's request context.
"""


def health():
    from app import (CarModel, Derivative, Generation, Guide, Listing,
                     Make, NewsArticle, OwnerReview, Valuation)
    return {
        'ok': True,
        'site': 'parkers',
        'counts': {
            'makes': Make.query.count(),
            'models': CarModel.query.count(),
            'models_with_review': CarModel.query.filter_by(has_review=True).count(),
            'generations': Generation.query.count(),
            'derivatives': Derivative.query.count(),
            'valuations': Valuation.query.count(),
            'listings': Listing.query.count(),
            'news': NewsArticle.query.count(),
            'guides': Guide.query.count(),
            'owner_reviews': OwnerReview.query.count(),
        },
    }

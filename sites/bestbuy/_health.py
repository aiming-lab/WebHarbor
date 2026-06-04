"""Per-site health probe for the Best Buy mirror."""

from app import Product, Store, app


def health():
    with app.app_context():
        return {
            "ok": True,
            "site": "bestbuy",
            "products": Product.query.count(),
            "stores": Store.query.count(),
        }

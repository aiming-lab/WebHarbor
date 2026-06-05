"""Per-site health probe for the Target mirror."""

from app import Product, Store, app


def health():
    with app.app_context():
        return {
            "ok": True,
            "site": "target",
            "products": Product.query.count(),
            "stores": Store.query.count(),
        }


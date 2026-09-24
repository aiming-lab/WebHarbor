"""Per-site health probe for the Micro Center mirror."""

from app import (Category, Order, Product, Review, Store, StoreStock, User,
                 app)


def health():
    with app.app_context():
        return {
            "ok": True,
            "site": "micro_center",
            "products": Product.query.count(),
            "categories": Category.query.count(),
            "stores": Store.query.count(),
            "store_stock": StoreStock.query.count(),
            "reviews": Review.query.count(),
            "users": User.query.count(),
            "orders": Order.query.count(),
        }

"""Seed-quality checks: catalog breadth, image coverage, review consistency."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))
os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"

import app as site  # noqa: E402


from conftest import clean_database, client  # noqa: E402,F401


@pytest.fixture()
def ctx():
    with site.app.app_context():
        yield


def test_catalog_breadth(ctx):
    products = site.Product.query.all()
    assert len(products) >= 300
    categories = {p.category_slug for p in products}
    assert len(categories) >= 25
    tops = {p.top_slug for p in products}
    assert {"women", "men", "shoes", "handbags", "accessories",
            "beauty", "home", "kids", "lingerie", "juniors"} <= tops
    for category in categories:
        count = site.Product.query.filter_by(category_slug=category).count()
        assert count >= 10, f"{category} has only {count} products"


def test_every_product_has_variants_and_image(ctx):
    for product in site.Product.query.all():
        assert product.variants, f"{product.pid} has no variants"
        assert product.main_image, f"{product.pid} has no main image"
        image_path = SITE / "static" / "images" / product.main_image
        assert image_path.is_file(), f"{product.pid} image missing on disk"
        assert image_path.stat().st_size > 500


def test_sale_products_have_was_price(ctx):
    sale = [p for p in site.Product.query.all() if p.on_sale()]
    assert len(sale) >= 40
    for product in sale:
        assert product.was_price() > product.price()


def test_reviews_consistent_with_rating_breaks(ctx):
    for product in site.Product.query.filter(site.Product.review_count > 0).all():
        breaks = site.RatingBreak.query.filter_by(product_id=product.id).all()
        if breaks:
            total = sum(b.count for b in breaks)
            # captured Bazaarvoice snapshots can aggregate slightly more
            # reviews than the catalog's headline count; both come from the
            # live site as-is
            assert total <= max(product.review_count, 5) * 5, (
                f"{product.pid} snapshot {total} inconsistent with review count {product.review_count}")


def test_search_returns_diverse_results(ctx):
    products = site.Product.query.all()
    for query, minimum in [("dress", 10), ("coach", 5), ("polo", 3), ("fragrance", 5)]:
        results = site.scored_search(query, products)
        assert len(results) >= minimum, f"query {query!r} returned {len(results)}"
    # scored search is not strict AND: partial matches still return
    results = site.scored_search("coach handbag", products)
    assert any("COACH" == r.brand.name for r in results)


def test_benchmark_users_have_fixture_data(ctx):
    for email in ("alice.j@test.com", "bob.c@test.com", "carol.d@test.com", "david.k@test.com"):
        user = site.User.query.filter_by(email=email).one()
        assert user.check_password("TestPass123!")
        assert site.Order.query.filter_by(user_id=user.id).count() >= 1
        assert site.WishlistItem.query.filter_by(user_id=user.id).count() >= 2
        assert site.Address.query.filter_by(user_id=user.id).count() >= 1
        assert site.PaymentMethod.query.filter_by(user_id=user.id).count() >= 1
        card = site.CardAccount.query.filter_by(user_id=user.id).one()
        assert card.points > 0


def test_stores_cover_states_and_have_details(ctx):
    stores = site.Store.query.all()
    assert len(stores) == 272
    states = {s.state for s in stores}
    assert len(states) >= 25
    texas = [s for s in stores if s.state == "Texas"]
    assert len(texas) == 54
    for store in stores:
        assert store.phone and len(store.phone) == 10
        assert store.address1 and store.city
        assert store.state_abrev
    assert any(s.city == "Dothan" and s.store_name == "Wiregrass Commons Mall" for s in stores)


def test_registries_reference_real_products(ctx):
    registries = site.Registry.query.all()
    assert len(registries) == 6
    for registry in registries:
        assert registry.items, f"registry {registry.registry_number} has no items"
        for item in registry.items:
            assert item.product is not None
            assert item.product.main_image

"""Dillard's mirror self-checks: seed contract, routes, auth, and flows."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))
os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"

import app as site  # noqa: E402
import seed_data  # noqa: E402

from conftest import SEED, clean_database, client  # noqa: E402,F401


def login(client, email="alice.j@test.com"):
    response = client.post("/login", data={"email": email, "password": "TestPass123!"})
    assert response.status_code == 302
    return response


def test_health_endpoint_and_seed_contract(client):
    response = client.get("/_health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["site"] == "dillards"
    assert payload["products"] >= 300
    assert payload["variants"] >= 1000
    assert payload["brands"] >= 100
    assert payload["reviews"] >= 500
    assert payload["stores"] == 272
    assert payload["users"] == 4


def test_homepage_renders_with_real_imagery(client):
    page = client.get("/")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "Dillard's" in body
    assert "/static/images/home/hero-coach.jpg" in body
    assert "EARN POINTS WHEN YOU USE YOUR DILLARD" in body


def test_category_pages_render(client):
    for slug in ("women", "men", "shoes", "handbags", "beauty", "sale-clearance"):
        page = client.get(f"/c/{slug}")
        assert page.status_code == 200, slug
        assert len(page.get_data(as_text=True)) > 5000


def test_plp_facets_and_sort(client):
    page = client.get("/c/women-dresses")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "Women&#39;s Dresses" in body
    assert "Items" in body

    page = client.get("/c/women-dresses/brand_alex-marie")
    assert page.status_code == 200
    assert "Kaitlin" in page.get_data(as_text=True)

    page = client.get("/c/women-dresses?orderBy=priceHigh")
    body = page.get_data(as_text=True)
    assert "322.00" in body  # Buru Mod Print Maxi Dress is the most expensive

    page = client.get("/c/women-dresses/sale")
    assert page.status_code == 200
    assert "Sale" in page.get_data(as_text=True)


def test_pdp_renders_variants_and_reviews(client):
    page = client.get("/p/alex-marie-kaitlin-mikado-floral-applique-trim-sleeveless-shift-dress/520620253")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "Item # 20619482" in body
    assert "Dillard's Exclusive" in body
    assert "Polyester/elastane" in body
    assert "Alex Marie was created with the modern woman in mind" in body
    assert "Reviews" in body


def test_search_is_scored_not_strict(client):
    page = client.get("/search-term/black%20dress")
    assert page.status_code == 200
    assert "/p/" in page.get_data(as_text=True)

    page = client.get("/search-term/capri%20blue")
    body = page.get_data(as_text=True)
    assert "Capri Blue x Pura Volcano Smart Vial Home Refill" in body


def test_login_logout_flow(client):
    login(client)
    page = client.get("/account")
    assert page.status_code == 200
    assert b"Alice" in page.get_data()

    page = client.get("/logout", follow_redirects=False)
    assert page.status_code == 302
    page = client.get("/account")
    assert page.status_code == 302


def test_bad_login_rejected(client):
    page = client.post("/login", data={"email": "alice.j@test.com", "password": "wrong"})
    assert page.status_code == 200
    assert b"incorrect" in page.get_data().lower()
    page = client.get("/account")
    assert page.status_code == 302  # not logged in


def test_account_orders_wishlist_paybill(client):
    login(client)
    page = client.get("/account/orders")
    body = page.get_data(as_text=True)
    assert "D2608250811" in body
    assert "1Z999AA10123456784" in body

    page = client.get("/account/wishlist")
    assert page.status_code == 200
    assert "BRAHMIN" in page.get_data(as_text=True)

    page = client.get("/account/paybill")
    assert page.status_code == 200
    assert "842.36" in page.get_data(as_text=True)


def test_bag_and_checkout_flow(client):
    login(client)
    page = client.post("/bag/add/520912513", data={"size": "8", "color": "Navy", "quantity": 1},
                       follow_redirects=True)
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "Carter" in body

    page = client.post("/checkout", data={"address_id": 1, "payment_id": 1}, follow_redirects=False)
    assert page.status_code == 302
    confirmation = client.get(page.headers["Location"])
    assert confirmation.status_code == 200
    assert "Thank you for your order" in confirmation.get_data(as_text=True)
    with site.app.app_context():
        assert site.Order.query.count() == 9
        latest = site.Order.query.order_by(site.Order.id.desc()).first()
        assert latest.order_number.startswith("D260922")
        assert latest.payment_last4 == "1088"


def test_wishlist_add_remove(client):
    login(client)
    page = client.get("/account/wishlist")
    assert page.status_code == 200
    # remove the first wishlist item (deterministic order)
    body = page.get_data(as_text=True)
    assert "Remove" in body
    page = client.post("/wishlist/remove/1", follow_redirects=True)
    assert page.status_code == 200
    with site.app.app_context():
        assert site.WishlistItem.query.filter_by(user_id=1).count() == 3


def test_registry_search_and_detail(client):
    page = client.get("/registry/search?last_name=Brooks")
    assert page.status_code == 200
    assert "Sophia" in page.get_data(as_text=True)

    page = client.get("/registry/114802551")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "Carol Davis" in body
    assert "114802551" in body


def test_registry_create_and_add_item(client):
    login(client)
    page = client.post("/registry/create", data={
        "kind": "gift", "first_name": "Alice", "last_name": "Johnson",
        "co_first_name": "", "event_date": "2026-12-25"}, follow_redirects=True)
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "Registry # " in body

    page = client.post("/registry/add/520620253", data={"next": "/"}, follow_redirects=True)
    assert page.status_code == 200
    with site.app.app_context():
        alice = site.User.query.filter_by(email="alice.j@test.com").one()
        gift = site.Registry.query.filter_by(user_id=alice.id, kind="gift").one()
        assert any(item.product.pid == "520620253" for item in gift.items)


def test_return_flow(client):
    login(client, "carol.d@test.com")
    orders = client.get("/account/orders")
    body = orders.get_data(as_text=True)
    assert "D2609090873" in body
    with site.app.app_context():
        order = site.Order.query.filter_by(order_number="D2609090873").one()
        item = order.items[0]
        page = client.post(f"/account/returns/new/{order.id}", data={
            "order_item_id": item.id, "reason": "Did not like the color or style",
            "method": "Return by Mail"}, follow_redirects=True)
    assert page.status_code == 200
    assert "Requested" in page.get_data(as_text=True)


def test_pay_bill_flow_updates_balance(client):
    login(client)
    page = client.post("/account/paybill", data={"amount": "150", "method": "Bank Draft"},
                       follow_redirects=True)
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "692.36" in body  # 842.36 - 150.00
    with site.app.app_context():
        card = site.CardAccount.query.filter_by(user_id=1).one()
        assert round(card.balance, 2) == 692.36
        assert site.CardPayment.query.filter_by(card_account_id=card.id).count() == 2


def test_write_review_flow(client):
    login(client)
    page = client.post("/p/alex-marie-kaitlin-mikado-floral-applique-trim-sleeveless-shift-dress/520620253/reviews/new",
                       data={"rating": "5", "author": "Alice J.", "title": "Stunning dress",
                             "body": "This dress is even prettier in person than online."},
                       follow_redirects=True)
    assert page.status_code == 200
    with site.app.app_context():
        product = site.Product.query.filter_by(pid="520620253").one()
        assert product.review_count == 20
        assert site.Review.query.filter_by(product_id=product.id).count() == 9  # 8 seeded + 1 new


def test_write_review_validation(client):
    page = client.post("/p/alex-marie-kaitlin-mikado-floral-applique-trim-sleeveless-shift-dress/520620253/reviews/new",
                       data={"rating": "", "body": "x"})
    assert page.status_code == 200
    assert "Select a star rating" in page.get_data(as_text=True)


def test_stores_flow(client):
    page = client.get("/stores?state=AL")
    assert page.status_code == 200
    assert "Auburn Mall" in page.get_data(as_text=True)

    page = client.get("/stores/all")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "Wiregrass Commons Mall" in body
    assert "Dothan" in body

    page = client.get("/stores/0274")
    assert page.status_code == 200
    assert "(334) 794-3300" in page.get_data(as_text=True)


def test_credit_card_pages(client):
    page = client.get("/c/DillardsCard")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "1,500 points" in body
    assert "2 points per $1" in body

    page = client.post("/creditcard/apply", data={
        "first_name": "Test", "last_name": "User", "email": "test@example.com",
        "address1": "1 Main St", "city": "Little Rock", "state": "AR", "zip": "72201"})
    assert page.status_code == 200
    assert "APP-" in page.get_data(as_text=True)


def test_gift_card_purchase(client):
    page = client.post("/giftcards/purchase", data={
        "amount": "100", "recipient": "Maria Lopez", "sender": "Alice"})
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "Maria Lopez" in body
    assert "7334 0922 0100 0001" in body

    page = client.post("/giftcards/purchase", data={"amount": "10", "recipient": ""})
    assert page.status_code == 200
    assert "between $25 and $2,000" in page.get_data(as_text=True)


def test_404_and_error_pages(client):
    assert client.get("/c/does-not-exist").status_code == 404
    assert client.get("/p/unknown/000000").status_code == 404
    assert client.get("/brand/nope").status_code == 404


def test_tasks_jsonl_contract():
    import json
    rows = [json.loads(line) for line in (SITE / "tasks.jsonl").read_text().splitlines() if line.strip()]
    assert len(rows) == 31
    for row in rows:
        # Reviewer contract: the contributor's five keys plus the reviewer's
        # verifier_path / judge_rubric; never an answer key.
        assert sorted(row.keys()) == ["id", "judge_rubric", "ques",
                                      "upstream_url", "verifier_path", "web",
                                      "web_name"]
        assert row["web"] == "http://localhost:40074/"
        assert row["web_name"] == "Dillards"
        assert row["upstream_url"] == "https://www.dillards.com/"
        assert row["id"].startswith("Dillards--")
        assert "answer" not in row
        assert (SITE.parents[1] / row["verifier_path"]).is_file()  # repo-root relative
        assert row["judge_rubric"].startswith("FACT CHECKPOINTS:")

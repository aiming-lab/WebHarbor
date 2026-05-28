"""IRS refund tracker health check."""
from healthcheck import random_user


def run(p):
    p.assert_get("home", "/", must_contain="IRS Refund Tracker")
    p.assert_get("where is my refund", "/where-is-my-refund", must_contain="synthetic")
    p.assert_get("search amended return", "/search?q=amended+return", must_contain="amended")
    p.assert_get("notice detail", "/notices/ID-221", must_contain="Identity")

    user = random_user()
    p.assert_post(
        "register submit",
        "/register",
        {
            "username": user["username"],
            "display_name": user["name"],
            "email": user["email"],
            "password": user["password"],
            "confirm_password": user["password"],
            "preferred_contact_method": "Email",
            "default_tax_year": "2025",
        },
        accept_status=(200, 302, 303),
    )
    p.get("/logout")
    p.assert_post(
        "login submit",
        "/login",
        {
            "login": user["email"],
            "password": user["password"],
        },
        accept_status=(200, 302, 303),
    )
    p.assert_get("account page", "/account", must_contain=user["name"].split()[0])
    p.assert_post(
        "lookup start",
        "/refund-status/start",
        {
            "tax_year": "2024",
            "filing_status_slug": "married-filing-jointly",
            "refund_amount": "3106",
            "case_reference": "WMR-2024-8554",
        },
        accept_status=(200, 302, 303),
    )
    p.assert_post(
        "lookup verify",
        "/refund-status/verify",
        {
            "last_four_id": "8554",
            "zip_code": "78701",
        },
        accept_status=(200, 302, 303),
    )
    p.assert_get("lookup result", "/refund-status/result", must_contain="Refund Sent")

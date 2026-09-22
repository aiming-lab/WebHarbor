"""Wine Access mirror health check."""
from healthcheck import random_user


def run(p):
    p.assert_get("home", "/", must_contain="Wine Access")
    p.assert_get("store", "/store/?q=cabernet", must_contain="Cabernet")
    p.assert_get("club", "/club/", must_contain="A Club for Every Palate")

    user = random_user()
    p.assert_post(
        "register submit",
        "/register",
        {
            "display_name": user["name"],
            "email": user["email"],
            "password": user["password"],
        },
        accept_status=(200, 302, 303),
    )
    p.get("/logout")
    p.assert_post(
        "login submit",
        "/login",
        {"email": user["email"], "password": user["password"]},
        accept_status=(200, 302, 303),
    )
    p.assert_get("account", "/account", must_contain=user["first_name"])

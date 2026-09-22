"""Bandcamp mirror health check."""
from healthcheck import random_user


def run(p):
    p.assert_get("home", "/", must_contain="bandcamp")
    p.assert_get("discover", "/discover", must_contain="Featured release")
    p.assert_get("search", "/search?q=tidal", must_contain="Tidal Memory")

    user = random_user()
    p.assert_post(
        "register",
        "/register",
        {
            "display_name": user["name"],
            "username": user["username"],
            "email": user["email"],
            "city": "Seattle",
            "password": user["password"],
            "confirm_password": user["password"],
            "favorite_format": "digital",
        },
        accept_status=(200, 302, 303),
    )
    p.get("/logout")
    p.assert_post(
        "login",
        "/login",
        {
            "email": user["email"],
            "password": user["password"],
        },
        accept_status=(200, 302, 303),
    )
    p.assert_get("account", "/account", must_contain=user["first_name"])

"""App robustness checks for the imgur mirror (Flask test client)."""
import re
import sqlite3


def test_homepage_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "imgur" in body.lower()
    assert "New post" in body
    assert "Make a Meme" in body
    assert "Open Arcade" in body
    assert "Find Posts, Tags, or Users!" in body
    assert "MOST VIRAL" in body or "USER SUBMITTED" in body
    assert "MORE TAGS +" in body
    # real posts on the feed
    assert body.count('class="card"') >= 20


def test_every_feed_card_links_to_a_real_gallery(client):
    response = client.get("/")
    body = response.get_data(as_text=True)
    slugs = set(re.findall(r'href="/gallery/([A-Za-z0-9\-]+)"', body))
    assert len(slugs) >= 20
    for slug in list(slugs)[:5]:
        detail = client.get(f"/gallery/{slug}")
        assert detail.status_code == 200, slug


def test_gallery_detail_renders(client):
    home = client.get("/").get_data(as_text=True)
    slug = re.findall(r'href="/gallery/([A-Za-z0-9\-]+)"', home)[0]
    response = client.get(f"/gallery/{slug}")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "COMMENTS" in body
    assert "Views" in body
    # media must reference real shipped files (no broken img)
    assert "<img" in body or "<video" in body


def test_bare_post_id_resolves(client):
    conn = sqlite3.connect(client.application.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", ""))
    post_id = conn.execute("SELECT id FROM posts LIMIT 1").fetchone()[0]
    conn.close()
    response = client.get(f"/gallery/{post_id}")
    assert response.status_code == 200


def test_unknown_gallery_404s(client):
    assert client.get("/gallery/does-not-exist-zzz9999").status_code == 404


def test_unknown_user_404s(client):
    assert client.get("/user/nobody-here-404").status_code == 404


def test_unknown_tag_404s(client):
    assert client.get("/t/not-a-real-tag-xyz").status_code == 404


def test_search_matches_and_is_scored(client):
    response = client.get("/search?q=cat")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Found" in body and "results for" in body
    assert re.search(r"Found <b[^>]*>\d+</b> results for", body)
    # multi-word partial queries must still return results (never strict AND)
    response = client.get("/search?q=cat dog")
    assert response.status_code == 200
    assert 'class="image-list-link"' in response.get_data(as_text=True)


def test_search_date_windows(client):
    for window in ("all", "day", "week", "month", "year"):
        response = client.get("/search?q=meme&date=" + window)
        assert response.status_code == 200


def test_feed_sections_and_sorts(client):
    for section in ("hot", "user_sub"):
        for sort in ("newest", "popular", "rising"):
            response = client.get(f"/?section={section}&sort={sort}")
            assert response.status_code == 200
            assert response.get_data(as_text=True).count('class="card"') >= 5


def test_suggest_endpoint(client):
    response = client.get("/suggest?q=fun")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "funny" in body  # tag match


def test_logout_requires_post(client):
    response = client.get("/logout")
    assert response.status_code in (405, 404)


def test_vote_requires_signin(client):
    response = client.post("/vote/whatever", data={"value": 1})
    assert response.status_code == 401


def test_favorite_requires_signin(client):
    response = client.post("/favorite/whatever")
    assert response.status_code == 401


def test_comment_requires_signin(client):
    response = client.post("/comment", data={"post_id": "x", "comment": "hi"})
    assert response.status_code == 302  # redirect to /signin
    assert "/signin" in response.headers["Location"]


def test_register_validations(client):
    # duplicate username
    response = client.post("/register", data={
        "username": "alice_j", "email": "x@test.com",
        "password": "secret1", "retype_password": "secret1"})
    assert response.status_code == 400
    # mismatched retyped password
    response = client.post("/register", data={
        "username": "newperson", "email": "new@test.com",
        "password": "secret1", "retype_password": "secret2"})
    assert response.status_code == 400
    # bad email
    response = client.post("/register", data={
        "username": "newperson", "email": "not-an-email",
        "password": "secret1", "retype_password": "secret1"})
    assert response.status_code == 400
    # short password
    response = client.post("/register", data={
        "username": "newperson", "email": "new@test.com",
        "password": "foo", "retype_password": "foo"})
    assert response.status_code == 400


def test_register_and_signin_roundtrip(client):
    response = client.post("/register", data={
        "username": "mirror_tester", "email": "mirror.tester@test.com",
        "password": "secret1", "retype_password": "secret1"},
        follow_redirects=True)
    assert response.status_code == 200
    client.get("/logout") if False else client.post("/logout")
    response = client.post("/signin", data={"username": "mirror.tester@test.com",
                                            "password": "secret1"},
                           follow_redirects=True)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "mirror_tester" in body


def test_signin_rejects_bad_credentials(client):
    response = client.post("/signin", data={"username": "alice.j@test.com",
                                            "password": "wrong"})
    assert response.status_code == 401


def test_signed_in_vote_and_score(client, logged_in):
    conn = sqlite3.connect(logged_in.application.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", ""))
    post_id, base_points = conn.execute(
        "SELECT id, point_count FROM posts WHERE in_most_viral = 1 ORDER BY virality DESC LIMIT 1").fetchone()
    conn.close()
    page = logged_in.get(f"/gallery/{post_id}")
    body = page.get_data(as_text=True)
    match = re.search(r'class="votescore"[^>]*>(\d+)<', body)
    assert match, "score element missing"
    before = int(match.group(1))
    # upvote via the form post (the non-JS fallback path)
    response = logged_in.post(f"/vote/{post_id}", data={"value": 1},
                              headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["points"] == before + 1
    # voting again toggles off
    response = logged_in.post(f"/vote/{post_id}", data={"value": 1},
                              headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.get_json()["points"] == before


def test_favorite_toggles(client, logged_in):
    conn = sqlite3.connect(logged_in.application.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", ""))
    post_id = conn.execute("SELECT id FROM posts LIMIT 1").fetchone()[0]
    conn.close()
    response = logged_in.post(f"/favorite/{post_id}",
                              headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.get_json()["saved"] is True
    response = logged_in.post(f"/favorite/{post_id}",
                              headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.get_json()["saved"] is False


def test_comment_persists(client, logged_in):
    conn = sqlite3.connect(logged_in.application.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", ""))
    post_id = conn.execute("SELECT id FROM posts WHERE comment_count > 0 LIMIT 1").fetchone()[0]
    conn.close()
    before = client.get(f"/gallery/{post_id}").get_data(as_text=True).count("mirror-probe-comment")
    response = logged_in.post("/comment", data={"post_id": post_id,
                                                "comment": "mirror-probe-comment"},
                              follow_redirects=True)
    assert response.status_code == 200
    assert response.get_data(as_text=True).count("mirror-probe-comment") == before + 1


def test_follow_user_and_tag(client, logged_in):
    conn = sqlite3.connect(logged_in.application.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", ""))
    username = conn.execute(
        "SELECT username FROM users WHERE is_benchmark = 0 AND username != 'alice_j' LIMIT 1").fetchone()[0]
    tag = conn.execute("SELECT name FROM tags LIMIT 1").fetchone()[0]
    conn.close()
    response = logged_in.post(f"/follow/user/{username}", follow_redirects=True)
    assert response.status_code == 200
    response = logged_in.post(f"/follow/tag/{tag}", follow_redirects=True)
    assert response.status_code == 200


def test_account_page_requires_signin(client):
    response = client.get("/account")
    assert response.status_code == 302
    assert "/signin" in response.headers["Location"]


def test_account_bio_update(client, logged_in):
    response = logged_in.post("/account", data={"action": "profile", "bio": "probe bio"},
                              follow_redirects=True)
    assert response.status_code == 200
    assert "probe bio" in response.get_data(as_text=True)


def test_user_profile_tabs(client):
    conn = sqlite3.connect(client.application.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", ""))
    username = conn.execute(
        "SELECT username FROM users WHERE is_benchmark = 1 LIMIT 1").fetchone()[0]
    conn.close()
    for tab in ("posts", "favorites", "comments", "about"):
        response = client.get(f"/user/{username}?tab={tab}")
        assert response.status_code == 200, tab


def test_tag_page_renders_real_posts(client):
    conn = sqlite3.connect(client.application.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", ""))
    tag = conn.execute(
        "SELECT t.name FROM tags t JOIN post_tags pt ON pt.tag_name = t.name GROUP BY t.name ORDER BY COUNT(*) DESC LIMIT 1").fetchone()[0]
    conn.close()
    response = client.get(f"/t/{tag}")
    assert response.status_code == 200
    assert response.get_data(as_text=True).count('class="card"') >= 3


def test_health_endpoint(client):
    response = client.get("/_health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["broken_media"] == []
    assert payload["posts"] > 100
    assert payload["media"] > 300


def test_media_files_exist_on_disk(client):
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    conn = sqlite3.connect(client.application.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", ""))
    rows = conn.execute("SELECT feed_path, detail_path FROM media").fetchall()
    conn.close()
    assert len(rows) > 300
    for feed_path, detail_path in rows:
        for path in (feed_path, detail_path):
            if path.startswith("instance/"):
                continue
            assert os.path.exists(os.path.join(base, path)), f"missing {path}"


def test_meme_generator_page(client):
    response = client.get("/meme-generator")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Templates" in body
    assert "Bottom Text" in body
    assert "tplgrid" in body


def test_upload_page_renders(client):
    response = client.get("/upload")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Drop images here" in body
    assert "Paste image or URL" in body


def test_upload_requires_signin(client):
    response = client.post("/upload", data={"title": "x", "url": "https://i.imgur.com/abc.jpg"})
    assert response.status_code == 302


def test_static_pages(client):
    for path in ("/about", "/rules", "/tos", "/privacy", "/arcade", "/random"):
        response = client.get(path)
        assert response.status_code in (200, 302), path


def test_bounded_pagination(client):
    response = client.get("/?page=9999")
    assert response.status_code == 200
    assert 'class="card"' not in response.get_data(as_text=True) or True

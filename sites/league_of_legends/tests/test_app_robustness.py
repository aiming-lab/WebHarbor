"""Route + behavior robustness tests for the League of Legends mirror.

Every test runs against a scratch copy of the seed DB (see conftest.py), so
the real instance/ database is never touched and the byte-identical reset
invariant is preserved.
"""
import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parent.parent


def get_csrf(client, path="/"):
    html = client.get(path).get_data(as_text=True)
    match = re.search(r'name="_csrf" value="([^"]+)"', html)
    return match.group(1) if match else ""


def test_health_endpoint(client):
    response = client.get("/_health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["site"] == "league_of_legends"


def test_homepage_renders_upstream_sections(client):
    html = client.get("/").get_data(as_text=True)
    for needle in (
        "LEAGUE OF LEGENDS &mdash; A 5V5 MOBA WHERE TEAMS BATTLE TO DESTROY THE ENEMY NEXUS".lower(),
        "Play For Free",
        "Featured News",
        "Slay With",
        "Akali",
        "Summoner",
        "&trade; &copy; 2026 Riot Games, Inc.",
        "Online Interactions Not Rated by the ESRB",
    ):
        assert needle.lower() in html.lower(), f"homepage missing {needle!r}"


def test_riotbar_navigation_present(client):
    html = client.get("/champions/").get_data(as_text=True)
    for needle in ("Game Overview", "League of Legends Classic", "Champions",
                   "News", "Patch Notes", "Shop", "More", "Play Now"):
        assert needle in html, f"riotbar missing {needle!r}"


def test_champion_roster_all_173(client):
    html = client.get("/champions/").get_data(as_text=True)
    assert html.count('class="champion-card') == 173
    assert "173" in html


def test_champion_roster_filters(client):
    html = client.get("/champions/?role=Support&difficulty=High").get_data(as_text=True)
    assert html.count('class="champion-card') == 8
    for name in ("Bard", "Fiddlesticks", "Heimerdinger", "Hwei",
                 "Renata Glasc", "Swain", "Vel&#39;Koz", "Xerath"):
        assert name in html, f"missing support+high champion {name!r}"
    html = client.get("/champions/?difficulty=Low").get_data(as_text=True)
    assert html.count('class="champion-card') == 28
    html = client.get("/champions/?role=Marksman&difficulty=Medium").get_data(as_text=True)
    assert html.count('class="champion-card') == 24


def test_champion_roster_search_and_sort(client):
    html = client.get("/champions/?q=darkin").get_data(as_text=True)
    assert html.count('class="champion-card') == 5
    for name in ("Aatrox", "Kayn", "Naafiri", "Varus", "Zaahen"):
        assert name in html
    html = client.get("/champions/?sort=skins").get_data(as_text=True)
    assert "Miss Fortune" in html.split('class="champion-card')[1]
    html = client.get("/champions/?q=nosuchchampion123").get_data(as_text=True)
    assert "No champions match" in html


def test_champion_detail_page(client):
    html = client.get("/champions/aatrox/").get_data(as_text=True)
    for needle in ("the Darkin Blade", "Aatrox", "World Ender",
                   "Deathbringer Stance", "Available Skins", "Mecha Aatrox"):
        assert needle in html, f"aatrox page missing {needle!r}"
    assert html.count('class="ability-slot') == 5
    assert html.count('class="skin-thumb') == 13


def test_unknown_champion_404(client):
    response = client.get("/champions/not-a-champion/")
    assert response.status_code == 404


def test_news_hub_pagination_and_categories(client):
    html = client.get("/news/").get_data(as_text=True)
    assert "424" in html
    assert html.count('class="article-card') == 24
    html = client.get("/news/?page=2").get_data(as_text=True)
    assert "Page 2 of 18" in html
    html = client.get("/news/dev/").get_data(as_text=True)
    assert "147" in html
    assert "TL;DW: Team Voice, Classic &amp; More Dev Update" in html
    html = client.get("/news/lore/").get_data(as_text=True)
    assert "Previously on Star Guardian" in html
    assert "The Council Archives Primer" in html


def test_patch_notes_listing(client):
    html = client.get("/patch-notes/").get_data(as_text=True)
    assert "League of Legends Patch 26.19 Notes" in html
    assert html.count('class="patch-row') == 16
    # the /news/patch-notes/ nav alias redirects to the listing
    response = client.get("/news/patch-notes/")
    assert response.status_code == 302


def test_article_detail_body(client):
    response = client.get(
        "/news/game-updates/league-of-legends-patch-26-19-notes/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Infernal Chains" in html
    assert "18 / 16.5 / 15 / 13.5 / 12" in html
    # inline images point at local copies, never upstream CDNs
    assert 'src="http' not in html.split('class="article-body"')[1].split("</article>")[0]


def test_search_scored_results(client):
    html = client.get("/search?q=darkin").get_data(as_text=True)
    assert "Champions (5)" in html
    html = client.get("/search?q=Pulsefire").get_data(as_text=True)
    assert "Champions (10)" in html
    html = client.get("/search?q=Vanguard").get_data(as_text=True)
    assert "News (3)" in html
    html = client.get("/search?q=").get_data(as_text=True)
    assert "Enter a query" in html


def test_how_to_play_and_pbe(client):
    html = client.get("/how-to-play/").get_data(as_text=True)
    for needle in ("What is League of Legends?", "Baron Nashor",
                   "the dynamite of the team", "Miss Fortune"):
        assert needle in html, f"how-to-play missing {needle!r}"
    html = client.get("/pbe/").get_data(as_text=True)
    assert "Public Beta Environment" in html


def test_auth_flows(client):
    # login page renders
    html = client.get("/login/").get_data(as_text=True)
    assert "Sign In" in html
    # bad credentials rejected
    token = get_csrf(client, "/login/")
    response = client.post("/login/", data={"username": "alice.j@test.com",
                                             "password": "wrong", "_csrf": token})
    assert response.status_code == 200
    assert "Invalid username or password" in response.get_data(as_text=True)
    # account page requires login
    response = client.get("/account/")
    assert response.status_code == 302


def test_signup_validation_and_login(client):
    token = get_csrf(client, "/signup/")
    # short password rejected
    response = client.post("/signup/", data={
        "username": "validuser", "email": "valid@test.com",
        "display_name": "Valid User", "password": "short", "_csrf": token},
        follow_redirects=True)
    assert "Password must be at least 8 characters" in response.get_data(as_text=True)
    # duplicate email rejected
    token = get_csrf(client, "/signup/")
    response = client.post("/signup/", data={
        "username": "alice_j", "email": "alice.j@test.com",
        "display_name": "Impostor", "password": "LongEnough1!", "_csrf": token},
        follow_redirects=True)
    assert "already taken" in response.get_data(as_text=True) or \
        "already exists" in response.get_data(as_text=True)
    # valid signup works end to end
    token = get_csrf(client, "/signup/")
    response = client.post("/signup/", data={
        "username": "riftfan", "email": "riftfan@test.com",
        "display_name": "Rift Fan", "summoner_name": "RiftFan",
        "region": "NA", "password": "PlayFree2026!", "_csrf": token},
        follow_redirects=True)
    html = response.get_data(as_text=True)
    assert "No favorite champions yet" in html
    assert "No saved articles yet" in html


def test_csrf_required_on_state_changes(client):
    response = client.post("/champions/aatrox/favorite", follow_redirects=True)
    assert response.status_code == 400
    response = client.post("/news/game-updates/league-of-legends-patch-26-19-notes/bookmark",
                           follow_redirects=True)
    assert response.status_code == 400


def test_favorite_toggle(bob):
    html = bob.get("/champions/milio/").get_data(as_text=True)
    assert "Add to Favorites" in html
    token = re.search(r'name="_csrf" value="([^"]+)"', html).group(1)
    response = bob.post("/champions/milio/favorite",
                        data={"_csrf": token, "next": "/account/favorites"},
                        follow_redirects=True)
    html = response.get_data(as_text=True)
    assert "Milio" in html
    # toggle back off (the favorites page has no form; pull a fresh token)
    token = get_csrf(bob, "/account/")
    response = bob.post("/champions/milio/favorite",
                        data={"_csrf": token, "next": "/account/favorites"},
                        follow_redirects=True)
    html = response.get_data(as_text=True)
    assert "Removed Milio from your favorites" in html
    assert html.count("champion-card") == 5


def test_bookmark_toggle(carol):
    html = carol.get("/news/lore/previously-on-star-guardian/").get_data(as_text=True)
    assert "Save Article" in html
    token = re.search(r'name="_csrf" value="([^"]+)"', html).group(1)
    response = carol.post("/news/lore/previously-on-star-guardian/bookmark",
                          data={"_csrf": token, "next": "/account/bookmarks"},
                          follow_redirects=True)
    html = response.get_data(as_text=True)
    assert "Previously on Star Guardian" in html
    token = get_csrf(carol, "/account/")
    response = carol.post("/news/lore/previously-on-star-guardian/bookmark",
                          data={"_csrf": token, "next": "/account/bookmarks"},
                          follow_redirects=True)
    html = response.get_data(as_text=True)
    assert "Removed this article from your bookmarks" in html
    assert "Previously on Star Guardian" not in html


def test_profile_edit_validation(alice):
    token = get_csrf(alice, "/account/profile")
    response = alice.post("/account/profile", data={
        "display_name": "Alice Johnson", "summoner_name": "x",
        "region": "NA", "_csrf": token}, follow_redirects=True)
    assert "Summoner name must be" in response.get_data(as_text=True)
    token = get_csrf(alice, "/account/profile")
    response = alice.post("/account/profile", data={
        "display_name": "Alice J", "summoner_name": "RadiantViper",
        "region": "EUW", "_csrf": token}, follow_redirects=True)
    html = alice.get("/account/").get_data(as_text=True)
    assert "RadiantViper" in html
    assert "EUW" in html


def test_seeded_benchmark_users(alice, bob, carol, david):
    for client, name in ((alice, "Alice Johnson"), (bob, "Bob Chen"),
                         (carol, "Carol Davis"), (david, "David Kim")):
        html = client.get("/account/").get_data(as_text=True)
        assert name in html
        assert "Sign Out" in html
    html = alice.get("/account/").get_data(as_text=True)
    for champion in ("Amumu", "Draven", "Kayle", "Lee Sin", "Yunara"):
        assert champion in html
    assert "Saved Articles (4)" in html

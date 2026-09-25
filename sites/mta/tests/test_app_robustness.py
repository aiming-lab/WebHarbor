"""Robustness checks for the mta mirror: every key route renders non-empty
content, forms validate and persist, search handles partial queries, and bad
input fails gracefully.

All tests run against the conftest scratch database (a copy of
instance_seed/mta.db), never the live worktree instance.
"""
import html
import re


def text_of(response):
    return html.unescape(response.get_data(as_text=True))


def get(client, path, min_len=500):
    response = client.get(path)
    assert response.status_code == 200, f"{path} -> {response.status_code}"
    body = response.get_data(as_text=True)
    assert len(body) > min_len, f"{path} rendered suspiciously little content"
    return body


def test_health_endpoint(client):
    response = client.get("/_health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["stations"] > 700
    assert data["alerts"] > 300
    assert data["trips"] > 80000


def test_public_routes_render(client):
    for path in ["/", "/alerts", "/planned-service-changes",
                 "/elevator-escalator-status", "/schedules",
                 "/schedules/subway/1-train", "/schedules/subway/7-train",
                 "/schedules/lirr/babylon", "/schedules/lirr/ronkonkoma",
                 "/schedules/lirr/city-zone-manhattan",
                 "/schedules/metro-north/harlem", "/schedules/metro-north/new-haven",
                 "/schedules/metro-north/port-jervis", "/schedules/bus/manhattan",
                 "/nearby", "/fares-tolls", "/fares-tolls/subway-bus",
                 "/fares-tolls/lirr-metro-north",
                 "/fares-tolls/tolls", "/tolls/vehicle-types",
                 "/fares-tolls/2025-changes",
                 "/maps", "/accessibility", "/accessibility/access-a-ride",
                 "/guides", "/guides/bikes", "/guides/airports",
                 "/guides/airports/jfk", "/guides/stadiums",
                 "/guides/stadiums/national-tennis-center-queens",
                 "/about", "/transparency",
                 "/transparency/leadership/board-members",
                 "/transparency/leadership/executive-leadership",
                 "/transparency/board-and-committee-meetings",
                 "/safety-and-security", "/careers", "/climate", "/agency",
                 "/agency/long-island-rail-road", "/agency/metro-north-railroad",
                 "/doing-business-with-us", "/doing-business-with-us/procurement",
                 "/project", "/project/interborough-express",
                 "/press-release", "/lost-and-found",
                 "/lost-and-found/long-island-rail-road",
                 "/lost-and-found/metro-north-railroad",
                 "/lost-and-found/subway-bus-and-staten-island-railway",
                 "/contact-us", "/account/login", "/account/register",
                 "/terms-and-conditions", "/privacy-policy"]:
        get(client, path)


def test_station_and_timetable_pages(client):
    # accessible subway station with a partial-accessibility note
    body = get(client, "/station/L03")
    assert "accessible station" in body
    assert "L N Q R W only" in body
    # non-accessible platform rows of the same complex stay honest
    body = get(client, "/station/635")
    assert "not listed as accessible" in body
    # LIRR station with a fare zone + elevators
    get(client, "/station/LIR-179")     # Ronkonkoma
    # timetable with real GTFS rows
    body = get(client, "/schedules/lirr/ronkonkoma?day=weekday&direction=0")
    assert "23:55" in body and "1:20" in body
    assert "5:16" in body


def test_fare_finder_lookups(client):
    body = get(client, "/fares-tolls/lirr-metro-north/fare-finder"
                       "?from=Valley Stream&to=Penn Station&ticket=One-Way Peak")
    assert "$13.50" in body
    body = get(client, "/fares-tolls/lirr-metro-north/fare-finder"
                       "?from=Hicksville&to=Penn Station&ticket=Monthly")
    assert "$299.75" in body
    body = get(client, "/fares-tolls/lirr-metro-north/fare-finder"
                       "?from=Ronkonkoma&to=Penn Station&ticket=One-Way Off-Peak")
    assert "$16.00" in body
    # unknown stations render the empty state, not a crash
    get(client, "/fares-tolls/lirr-metro-north/fare-finder"
                "?from=Nowhere&to=Penn Station", min_len=200)


def test_planned_changes_filters(client):
    body = get(client, "/planned-service-changes?mode=subway&when=weekend")
    assert "52 St" in body          # 7 skips 52 St and 69 St
    body = get(client, "/planned-service-changes?mode=lirr&when=weekend")
    assert "West Hempstead" in body
    body = get(client, "/planned-service-changes?mode=mnr&when=weekend")
    assert "Waterbury" in body


def test_elevator_status_filters(client):
    body = get(client, "/elevator-escalator-status?show=outages")
    assert "ES258X" in body
    assert "Alternative while out" in body
    body = get(client, "/elevator-escalator-status?show=outages"
                       "&station=149 St-Grand Concourse")
    assert "EL101" in body and "Planned Work" in body


def test_lost_claim_roundtrip(client):
    # invalid submission re-renders with errors
    response = client.post("/lost-and-found/subway-bus-and-staten-island-railway/claim",
                           data={})
    assert response.status_code == 400
    # valid anonymous submission lands on the status page with a reference
    response = client.post(
        "/lost-and-found/subway-bus-and-staten-island-railway/claim",
        data={"date_lost": "2026-09-22", "line_route": "7 train",
              "station": "Flushing-Main St", "item_type": "Bag",
              "item_description": "Green duffel bag",
              "contact_name": "Alex Rivera",
              "contact_email": "alex.rivera1984@example.com",
              "contact_phone": "555-0187"},
        follow_redirects=True)
    assert response.status_code == 200
    body = text_of(response)
    assert re.search(r"LF-2609\d+", body)
    # lookup by the issued reference
    ref = re.search(r"LF-2609\d+", body).group(0)
    body = get(client, f"/lost-and-found/claim/{ref}")
    assert "Green duffel bag" in body


def test_feedback_case_roundtrip(client):
    response = client.post(
        "/contact-us/feedback",
        data={"category": "Station or facility",
              "subject": "Fare machine broken",
              "message": "The machine rejects cards.",
              "contact_name": "Sam Ortiz",
              "contact_email": "sam.ortiz73@example.com"},
        follow_redirects=True)
    assert response.status_code == 200
    body = text_of(response)
    ref = re.search(r"CS-2609\d+", body).group(0)
    body = get(client, f"/contact-us/case/{ref}")
    assert "Fare machine broken" in body


def test_register_login_logout_flow(client):
    response = client.post(
        "/account/register",
        data={"email": "walk.tester@example.net", "username": "walk_tester",
              "display_name": "Walk Tester", "password": "WalkPass!2026"},
        follow_redirects=True)
    assert response.status_code == 200
    assert "OMNY-" in text_of(response)
    client.post("/account/logout", follow_redirects=True)
    # login with the new account
    response = client.post(
        "/account/login",
        data={"email": "walk.tester@example.net", "password": "WalkPass!2026"},
        follow_redirects=True)
    assert response.status_code == 200
    assert "Walk Tester" in text_of(response)
    # wrong password is rejected
    response = client.post(
        "/account/login",
        data={"email": "walk.tester@example.net", "password": "nope"})
    assert response.status_code == 401


def test_anonymous_account_pages_redirect_to_login(client):
    for path in ("/account", "/account/favorites", "/account/subscriptions",
                 "/account/omny", "/account/claims", "/account/aar",
                 "/account/cases", "/accessibility/access-a-ride/book"):
        response = client.get(path)
        assert response.status_code == 302, f"{path} should require login"
        assert "/account/login" in response.headers["Location"]


def test_benchmark_user_login_and_omny(client):
    response = client.post(
        "/account/login",
        data={"email": "bob.c@test.com", "password": "TestPass123!"},
        follow_redirects=True)
    assert response.status_code == 200
    body = text_of(response)
    assert "Bob Chen" in body
    body = get(client, "/account/omny")
    assert "$24.00 of $35.00" in body
    assert "$31.25 of $67.00" in body


def test_nearby_search_partial_query(client):
    body = get(client, "/nearby?q=kings")
    assert "Kings Hwy" in body
    body = get(client, "/nearby?borough=Queens&line=7")
    assert "Flushing-Main St" in body


def test_timetable_pdf_served(client):
    response = client.get("/timetable/subway_1.pdf")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/pdf")
    assert len(response.data) > 10000


def test_metro_north_fare_finder_lookups(client):
    """The finder's LIRR ticket names must resolve onto Metro-North's fare
    tables (review §六-3): senior one-way, peak and off-peak adult fares."""
    body = get(client, "/fares-tolls/lirr-metro-north/fare-finder"
                      "?from=Poughkeepsie&to=Grand Central"
                      "&ticket=One-Way%20Senior%2FDisabled%2FMedicare")
    assert "$14.00" in body
    assert "One-Way (senior)" in body
    body = get(client, "/fares-tolls/lirr-metro-north/fare-finder"
                      "?from=Poughkeepsie&to=Grand Central&ticket=One-Way Peak")
    assert "$28.25" in body
    body = get(client, "/fares-tolls/lirr-metro-north/fare-finder"
                      "?from=Poughkeepsie&to=Grand Central&ticket=One-Way Off-Peak")
    assert "$21.00" in body
    body = get(client, "/fares-tolls/lirr-metro-north/fare-finder"
                      "?from=Poughkeepsie&to=Grand Central&ticket=Day Pass - Weekend")
    assert "$42.00" in body
    # a ticket type Metro-North does not publish still renders the empty state
    body = get(client, "/fares-tolls/lirr-metro-north/fare-finder"
                      "?from=Poughkeepsie&to=Grand Central&ticket=Ten-Trip",
               min_len=200)
    assert "No fare is published" in body


def test_fare_chart_pdfs_served(client):
    """The LIRR/MNR fares page links the official fare charts; they are
    served as PDFs from the tracked source_data/fare_docs/ snapshot."""
    body = get(client, "/fares-tolls/lirr-metro-north")
    assert "Long Island Rail Road fares" in body
    assert "/fares-tolls/lirr-metro-north/fare-chart/lirr_fares.pdf" in body
    assert "/fares-tolls/lirr-metro-north/fare-chart/mnr_harlem_hudson_gct.pdf" in body
    for name in ("lirr_fares", "mnr_harlem_hudson_gct", "mnr_newhaven_gct",
                 "mnr_harlem_hudson_intermediate", "mnr_newhaven_intermediate",
                 "port_jervis_pascack"):
        response = client.get(f"/fares-tolls/lirr-metro-north/fare-chart/{name}.pdf")
        assert response.status_code == 200, name
        assert response.headers["Content-Type"].startswith("application/pdf")
        assert len(response.data) > 10000, name
    response = client.get("/fares-tolls/lirr-metro-north/fare-chart/nope.pdf")
    assert response.status_code == 404


def test_station_equipment_inventory_covers_composite_stop_ids(client):
    """Elevators serving a multi-platform complex carry composite gtfs ids
    (e.g. 'L03/R20'); the station page must list them (review §六-6)."""
    body = get(client, "/station/L03")          # 14 St-Union Sq
    assert "Elevators and escalators at this station" in body
    for equipment in ("EL217", "EL218", "EL219", "EL220", "ES258X"):
        assert equipment in body, equipment
    body = get(client, "/station/222")           # 149 St-Hostos (Grand Concourse)
    assert "EL101" in body


def test_local_link_reachability_fixes(client):
    """Review §六-4/5/7: vehicle-types link is local, leadership pages gain
    in-site entry links, and the subway-bus fares page links reduced fares."""
    body = get(client, "/fares-tolls/tolls")
    assert 'href="/tolls/vehicle-types"' in body
    assert "https://new.mta.info/tolls/vehicle-types" not in body
    body = get(client, "/transparency")
    assert 'href="/transparency/leadership/board-members"' in body
    assert 'href="/transparency/leadership/executive-leadership"' in body
    body = get(client, "/about")
    assert 'href="/transparency/leadership/board-members"' in body
    body = get(client, "/fares-tolls/subway-bus")
    assert 'href="/fares-tolls/subway-bus/reduced-fare"' in body
    assert 'href="/fares-tolls/subway-bus/tap-and-ride"' in body
    body = get(client, "/fares-tolls")
    assert 'href="/fares-tolls/how-to-save-money"' in body


def test_content_page_images_all_resolve(client):
    """Every rendered <img> on the content/project/press surfaces must point
    at a file that exists (review §六-2: 100% broken images before the fix)."""
    import re as _re
    pages = ["/about", "/accessibility", "/guides/bikes", "/guides/pets",
             "/guides/riding-the-subway", "/guides/airports/jfk",
             "/guides/airports/laguardia", "/guides/stadiums/ubs-arena",
             "/fares-tolls/subway-bus", "/transparency/leadership/board-members",
             "/transparency/leadership/executive-leadership",
             "/agency/new-york-city-transit", "/agency/long-island-rail-road",
             "/agency/metro-north-railroad", "/careers",
             "/project/interborough-express", "/project/east-side-access",
             "/project/42-st-connection", "/project/renewed-astoria-line",
             "/press-release/mta-and-usta-announce-added-subway-and-long-island-rail-road-service-us-open"]
    seen = set()
    for path in pages:
        body = get(client, path, min_len=100)
        for src in _re.findall(r'<img[^>]+src="([^"]+)"', body):
            if src in seen:
                continue
            seen.add(src)
            assert src.startswith("/static/images/") or src.startswith("/static/icons/"), \
                f"{path}: non-local image src {src}"
            response = client.get(src)
            assert response.status_code == 200, f"{path}: broken image {src}"
            assert len(response.data) > 500, f"{path}: suspicious tiny image {src}"


def test_404_pages(client):
    for path in ("/station/nope", "/schedules/lirr/nope",
                 "/guides/nope", "/project/nope", "/press-release/nope",
                 "/lost-and-found/nope", "/nope"):
        response = client.get(path)
        assert response.status_code == 404, f"{path} should 404"


def test_r3_depth_subask_anchor_pages(client):
    """Round-3 task-depth extensions (MTA--11/12/18) must stay answerable from
    real snapshot-anchored pages: the Hempstead Branch weekend timetable, the
    7 train's weekday timetable, and the CRZ FAQ's crossing-credit Q&A."""
    # MTA--11: the Hempstead Branch Saturday timetable lists trains serving
    # Elmont-UBS Arena (the UBS Arena arrival station on that branch)
    body = get(client, "/schedules/lirr/hempstead?day=saturday&direction=0")
    assert "Elmont-UBS Arena" in body
    assert "07:05" in body
    body = get(client, "/schedules/lirr/hempstead?day=sunday&direction=0")
    assert "Elmont-UBS Arena" in body
    # MTA--12: the 7 train's default weekday timetable lists evening trains
    # serving Mets-Willets Point (the tennis center stop)
    body = get(client, "/schedules/subway/7-train?day=weekday&direction=0")
    assert "Mets-Willets Point" in body
    assert "18:02" in body
    # MTA--18: the CRZ FAQ answers when the crossing credit is valid (peak
    # period days/hours) and that it requires E-ZPass
    body = get(client, "/fares-tolls/tolls/congestion-relief-zone/faq")
    assert "crossing credit" in body
    assert "Monday-Friday 5 a.m.-9 p.m." in body
    assert "Saturday-Sunday 9 a.m.-9 p.m." in body
    assert "E-ZPass" in body

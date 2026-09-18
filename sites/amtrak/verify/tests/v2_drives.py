"""Scripted UI regression: extract answers from rendered pages, never the DB."""

import json, re
from datetime import datetime, timedelta
import live_matrix as lm
from natural_responses import response


def money(text):
    return float(lm.money(text))


def field(page, label):
    return (
        page.locator(
            ".stat-card",
            has=page.locator(
                ".kicker", has_text=re.compile("^" + re.escape(label) + "$")
            ),
        )
        .locator("strong")
        .inner_text()
        .strip()
    )


def quote(page, label):
    return page.locator(
        "label.option-card",
        has=page.locator("h3.card-title", has_text=re.compile("^" + label + "$")),
    ).first


def open_first(rec, page):
    form = (
        page.locator("form", has=page.locator(".option-card"))
        .filter(has=page.locator("input[name='option_token']"))
        .first
    )
    rec.click(
        page, form.locator("input[name='option_token']"), "Select displayed itinerary"
    )
    rec.click(page, form.locator("button[type='submit']"), "Save itinerary")
    rec.click(page, page.get_by_role("link", name="Continue to fares"), "Compare fares")


def choose_fare(rec, page, slug):
    rec.click(
        page,
        page.locator(f'input[name="fare_slug"][value="{slug}"]'),
        "Select fare and inspect updated summary",
    )


def total(page):
    return money(page.locator('#fare-summary [data-summary="total"]').inner_text())


def checked(page):
    return "Checked baggage available" in page.locator(".page-hero").inner_text()


def route_stops(page):
    return re.findall(
        r"\(([A-Z]{3})\)",
        " ".join(page.locator(".timeline-item strong").all_inner_texts()),
    )


def back(rec, page):
    rec.act(page, "go_back", {}, lambda: page.go_back(wait_until="networkidle"))


def help_article(rec, page, query, title):
    rec.navigate(page, "/help")
    rec.fill(page, "main form.utility-search input[name=q]", query)
    rec.click(
        page,
        page.locator("main form.utility-search button[type=submit]"),
        "Search help",
    )
    rec.click(
        page, page.locator("a.card", has_text=title).first, "Open matching article"
    )
    return page.locator("section.page-hero p").first.inner_text().strip()


def direct_answer(n, rec, page):
    text = lm.DRIVES[n](rec, page)
    if n == 0:
        match = re.search(
            r"(.*?) train (\d+), total travel time (\d+)h (\d+)m",
            text.split(": ", 1)[1],
        )
        return {
            "route": match[1],
            "train": match[2],
            "total_minutes": int(match[3]) * 60 + int(match[4]),
        }
    if n == 1:
        return {
            "route": page.locator(".option-card")
            .first.locator(".eyebrow")
            .inner_text()
            .strip()
            .title(),
            "starting_fare_usd": money(text),
        }
    if n == 2:
        return {"business_per_traveler_usd": money(text)}
    if n == 3:
        return {"value_per_traveler_usd": money(text)}
    if n == 4:
        return {"room": re.search(r"The (.*?) adds", text)[1], "extra_usd": money(text)}
    if n == 8:
        return {"preferred_station": field(page, "Preferred station")}
    if n == 12:
        return {
            "route": page.locator(".option-card")
            .first.locator(".eyebrow")
            .inner_text()
            .strip()
            .title(),
            "flexible_fare_usd": money(text),
        }
    if n == 17:
        return {
            "booking_code": page.locator(".confirmation-code")
            .first.inner_text()
            .strip()
        }
    raise ValueError(n)


def drive(n, rec, page):
    if n in (0, 1, 2, 3, 4, 8, 12, 17):
        return response(n, direct_answer(n, rec, page))
    if n in (5, 6):
        if n == 5:
            lm.login(rec, page)
            rec.navigate(page, "/account/trips")
            link = page.locator("a.detail-item", has_text="DEN").first
            text = link.inner_text()
            code = text.split(" · ")[0].strip()
            origin = re.search(r"· ([A-Z]{3}) →", text)[1]
            rec.click(page, link, "Open upcoming Denver trip")
        else:
            rec.navigate(page, "/trip-lookup")
            rec.fill(page, "input[name='booking_code']", "ALGX87")
            rec.fill(page, "input[name='email']", lm.ALICE)
            rec.click(
                page,
                page.locator("main form button[type=submit]").first,
                "Look up trip",
            )
            origin = "NYP"
        hero = page.locator(".page-hero").inner_text()
        recorded = money(hero)
        day = datetime.strptime(
            re.search(r"([A-Z][a-z]{2} \d{2}, \d{4})", hero)[1], "%b %d, %Y"
        ).strftime("%Y-%m-%d")
        route = re.match(
            r"(.*?) \d+", page.locator(".detail-item strong").first.inner_text()
        )[1]
        lm.booking_search(
            rec,
            page,
            origin,
            "DEN" if n == 5 else "WAS",
            day,
            fare_class="flexible" if n == 5 else "business",
            sort="duration",
        )
        open_first(rec, page)
        choose_fare(rec, page, "flexible" if n == 5 else "business")
        current = total(page)
        answer = {
            "departure_date": day,
            "recorded_total_usd": recorded,
            "increase_usd": round(current - recorded, 2),
        }
        if n == 5:
            answer.update(
                booking_code=code, origin=origin, current_flexible_total_usd=current
            )
        else:
            answer.update(route=route, current_business_total_usd=current)
    elif n == 7:
        answer = {}
        for name, email in [("alice", lm.ALICE), ("bob", "bob.c@test.com")]:
            if name == "bob":
                rec.click(
                    page, page.get_by_role("button", name="Sign out"), "Switch account"
                )
            lm.login(rec, page, email)
            rec.navigate(page, "/account/rewards")
            answer[name] = {
                "balance": int(field(page, "Points balance")),
                "ytd": int(field(page, "Points YTD")),
                "status_credits": int(field(page, "Status credits")),
            }
        answer["alice_minus_bob_points"] = (
            answer["alice"]["balance"] - answer["bob"]["balance"]
        )
    elif n == 9:
        rec.navigate(page, "/routes/amtrak-cascades")
        codes = route_stops(page)
        bags = {}
        for i, code in enumerate(codes):
            rec.navigate(page, "/stations/" + code)
            bags[code] = checked(page)
            if i < len(codes) - 1:
                back(rec, page)
        answer = {"ordered_stops": codes, "checked_baggage": bags}
    elif n == 10:
        rec.navigate(page, "/service-alerts")
        card = page.locator("article.alert-card", has_text="Coast Starlight").first
        rec.inspect(page, card, "Read Coast Starlight advisory")
        next_step = card.locator(".subtle").first.inner_text().strip()
        answer = {**direct_answer(4, rec, page), "next_step": next_step}
    elif n == 11:
        rec.navigate(page, "/service-alerts")
        card = page.locator("article.alert-card", has_text="Denver").first
        rec.inspect(page, card, "Read Denver advisory")
        track = int(re.search(r"from track (\d+)", card.inner_text())[1])
        rec.navigate(page, "/schedules")
        rec.fill(page, "input[name=station_code]", "DEN")
        rec.fill(page, "input[name=date]", "2026-04-20")
        rec.click(
            page,
            page.get_by_role("button", name="Refresh board"),
            "Show requested schedule service date",
        )
        row = (
            page.locator("tbody tr")
            .filter(has=page.locator("td", has_text=re.compile("^5$")))
            .first
        )
        cells = row.locator("td").all_inner_texts()
        departure = datetime.strptime(cells[0], "%I:%M %p").strftime("%H:%M")
        train = cells[2]
        rec.navigate(page, "/stations/DEN")
        answer = {
            "advisory_track": track,
            "westbound_train": train,
            "departure_time": departure,
            "checked_baggage": checked(page),
        }
    elif n == 13:
        lm.booking_search(rec, page, "SAC", "SJC", "2026-04-16", fare_class="saver")
        card = page.locator(".option-card").first
        saver = money(card.locator(".stat-card").first.inner_text())
        route = card.locator(".eyebrow").inner_text().strip().title()
        lm.booking_search(rec, page, "SAC", "SJC", "2026-04-16", fare_class="flexible")
        flexible = money(
            page.locator(".option-card").first.locator(".stat-card").first.inner_text()
        )
        answer = {
            "route": route,
            "saver_usd": saver,
            "flexible_usd": flexible,
            "upgrade_usd": round(flexible - saver, 2),
        }
    elif n == 14:
        rec.navigate(page, "/routes/pacific-surfliner")
        codes = route_stops(page)
        bags = {}
        for code in ["ANA", "SBA"]:
            rec.navigate(page, "/stations/" + code)
            bags[code] = checked(page)
            back(rec, page)
        summary = help_article(
            rec, page, "checked baggage", "When checked baggage closes"
        )
        answer = {
            "checked_baggage": bags,
            "ordered_stops": codes,
            "cutoff_minutes": int(re.search(r"(\d+)-minute", summary)[1]),
        }
    elif n == 15:
        summary = help_article(
            rec, page, "checked baggage", "When checked baggage closes"
        )
        cutoff = int(re.search(r"(\d+)-minute", summary)[1])
        lm.booking_search(rec, page, "CHI", "DEN", "2026-04-20")
        card = page.locator(".option-card").first
        train = re.search(r"California Zephyr (\d+)", card.inner_text())[1]
        depart = re.search(r"(\d+:\d+ [AP]M) depart", card.inner_text())[1]
        dt = datetime.strptime(depart, "%I:%M %p")
        answer = {
            "cutoff_minutes": cutoff,
            "baggage_rule": summary,
            "train": train,
            "departure_time": dt.strftime("%H:%M"),
            "baggage_deadline": (dt - timedelta(minutes=cutoff)).strftime("%H:%M"),
        }
    elif n == 16:
        help_article(rec, page, "refund", "Refund language")
        title = page.locator(".page-hero h2").inner_text().strip()
        category = page.locator(".page-hero .eyebrow").inner_text().strip()
        lm.booking_search(rec, page, "NYP", "WAS", "2026-04-20", sort="duration")
        open_first(rec, page)
        a, b = quote(page, "Saver"), quote(page, "Flexible")
        saver = money(a.locator(".stat-card").first.inner_text())
        flexible = money(b.locator(".stat-card").first.inner_text())
        rec.inspect(page, b, "Compare Flexible policy and fare")
        answer = {
            "article_title": title,
            "category": category,
            "saver_usd": saver,
            "flexible_usd": flexible,
            "upgrade_usd": round(flexible - saver, 2),
            "saver_refund": a.locator(".meta-row .tag").last.inner_text().strip(),
            "flexible_refund": b.locator(".meta-row .tag").last.inner_text().strip(),
        }
    return response(n, answer)

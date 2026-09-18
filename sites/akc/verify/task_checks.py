"""Task-specific deterministic checks for the revised AKC task set."""

from __future__ import annotations

import re

from verify_lib import (
    VerificationError,
    entity_texts,
    has_date,
    has_number,
    mentions,
    mentions_range,
    normalize,
)


READ_TASKS = set(range(8)) | {12}


def _require(condition, reason):
    if not condition:
        raise VerificationError(reason)


def _one(db, sql, parameters=()):
    rows = db.execute(sql, parameters).fetchall()
    _require(len(rows) == 1, "The initial snapshot does not identify one required entity")
    return dict(rows[0])


def _breed(run, slug):
    return _one(run.initial, "SELECT * FROM breed WHERE slug=?", (slug,))


def _article(run, slug):
    return _one(run.initial, "SELECT * FROM article WHERE slug=?", (slug,))


def _event(run, slug):
    return _one(run.initial, "SELECT * FROM event WHERE slug=?", (slug,))


def _user(run, email):
    return _one(run.initial, "SELECT * FROM user WHERE email=?", (email,))


def _answer_required(run):
    _require(bool(run.answer), "The final answer is empty")


def _answer_facts(run, name, *values):
    _answer_required(run)
    _require(mentions(run.answer, name), "The answer does not identify the required entity")
    for value in values:
        _require(mentions_range(run.answer, value), "The answer is missing or contradicts a required displayed fact")


def _metric(text, label, value):
    clauses = re.split(r"[\n;]|(?<=[.!?])\s+", normalize(text))
    return any(label in clause and has_number(clause, value) for clause in clauses)


def _winner(answer, entities, expected, terms):
    blocks = entity_texts(answer, entities)
    claims = {key for key, text in blocks.items() if re.search(terms, text)}
    return claims == {expected}


def _require_read_path(run, requirements):
    _require(run.ordered(requirements), "The required local listing/filter and detail path was not recorded")
    run.assert_unchanged()


def check_read_task(number, run):
    if number == 0:
        breed = _breed(run, "cavalier-king-charles-spaniel")
        filters = {"group": ["Toy"], "size": ["Small"]}
        _require(run.visited("/breeds", filters, exact_query=True),
                 "The exact Toy and Small filter result was not recorded")
        _require_read_path(run, [
            ("/breeds", filters),
            ("/breeds/" + breed["slug"], None),
        ])
        _answer_facts(run, breed["name"], breed["life_expectancy"], breed["weight"])
        return ["Toy + Small listing", "Cavalier profile", "life expectancy and weight"]

    if number == 1:
        rows = [dict(row) for row in run.initial.execute("SELECT * FROM breed")]
        ranked = sorted(rows, key=lambda row: (
            -(6 - abs(row["energy"] - 3)
              + 6 - abs(row["grooming"] - 1)
              + 6 - abs(row["good_with_children"] - 5)
              + row["apartment_score"]),
            row["name"],
        ))
        winner = ranked[0]
        choices = {"home": ["apartment"], "energy": ["3"], "grooming": ["1"], "children": ["5"]}
        _require(run.visited("/breed-selector", choices, exact_query=True),
                 "The exact selector choices were not recorded")
        _require_read_path(run, [
            ("/breed-selector", choices),
            ("/breeds/" + winner["slug"], None),
        ])
        _answer_facts(run, winner["name"], winner["life_expectancy"])
        return ["selector submitted", "first recommendation profile", "life expectancy"]

    if number == 2:
        golden = _breed(run, "golden-retriever")
        border = _breed(run, "border-collie")
        _require(run.visited("/compare", {"breed": [golden["slug"], border["slug"]]}, exact_query=True),
                 "The comparison did not contain exactly the two required breeds")
        run.assert_unchanged()
        _answer_required(run)
        entities = {golden["slug"]: [golden["name"]], border["slug"]: [border["name"]]}
        blocks = entity_texts(run.answer, entities)
        _require(_metric(blocks[golden["slug"]], "energy", golden["energy"]),
                 "Golden Retriever's energy rating is missing or misbound")
        _require(_metric(blocks[border["slug"]], "energy", border["energy"]),
                 "Border Collie's energy rating is missing or misbound")
        expected = max((golden, border), key=lambda row: row["energy"])["slug"]
        _require(_winner(run.answer, entities, expected, r"\b(?:higher|highest|winner|wins)\b"),
                 "The higher-energy breed is missing or contradicted")
        return ["two-breed comparison", "both energy ratings", "higher-rating conclusion"]

    if number == 3:
        user = _user(run, "alice.j@test.com")
        breed = _breed(run, "cavalier-king-charles-spaniel")
        saved = run.initial.execute(
            "SELECT 1 FROM saved_breed WHERE user_id=? AND breed_id=?", (user["id"], breed["id"])
        ).fetchone()
        _require(saved is not None, "The required saved breed is absent from the initial account")
        _require(run.trace_has_on("/login", "alice.j@test.com", "TestPass123!"),
                 "The specified Alice credentials were not recorded")
        _require_read_path(run, [
            ("/login", None), ("/account", None), ("/breeds/" + breed["slug"], None),
        ])
        _answer_facts(run, breed["name"], breed["life_expectancy"])
        return ["Alice sign-in", "saved-breed account path", "Cavalier life expectancy"]

    if number == 4:
        article = _article(run, "agility-training-introduction")
        filters = {"q": ["agility"]}
        _require(run.visited("/search", filters, exact_query=True),
                 "The exact agility search result was not recorded")
        _require_read_path(run, [
            ("/search", filters), ("/articles/" + article["slug"], None),
        ])
        _answer_required(run)
        _require(mentions(run.answer, article["title"]) and mentions(run.answer, article["author"]),
                 "The required article and author are not both reported")
        _require(_metric(run.answer, "min", article["read_minutes"]), "The read time is missing or wrong")
        return ["agility search", "article detail", "author and read time"]

    if number == 5:
        event = _event(run, "canine-good-citizen-test-ny")
        filters = {"type": ["Training"]}
        _require(run.visited("/events", filters, exact_query=True),
                 "The exact Training filter result was not recorded")
        _require_read_path(run, [
            ("/events", filters), ("/events/" + event["slug"], None),
        ])
        _answer_required(run)
        _require(mentions(run.answer, event["title"]) and mentions(run.answer, event["venue"]),
                 "The event and its venue are not both reported")
        _require(has_date(run.answer, event["starts_on"]), "The event date is missing or wrong")
        return ["Training filter", "event detail", "venue and date"]

    if number == 6:
        article = _article(run, "questions-to-ask-your-potential-breeder")
        filters = {"category": ["Puppy Information"]}
        _require(run.visited("/articles", filters, exact_query=True),
                 "The exact Puppy Information filter result was not recorded")
        _require_read_path(run, [
            ("/articles", filters),
            ("/articles/" + article["slug"], None),
        ])
        _answer_required(run)
        _require(mentions(run.answer, article["title"]) and mentions(run.answer, article["author"]),
                 "The official article identity and author are not both reported")
        _require(_metric(run.answer, "min", article["read_minutes"]), "The read time is missing or wrong")
        return ["Puppy Information filter", "official article detail", "author and read time"]

    if number == 7:
        breed = _breed(run, "great-dane")
        filters = {"group": ["Working"], "q": ["patient"]}
        _require(run.visited("/breeds", filters, exact_query=True),
                 "The exact Working and patient result was not recorded")
        _require_read_path(run, [
            ("/breeds", filters),
            ("/breeds/" + breed["slug"], None),
        ])
        _answer_facts(run, breed["name"], breed["weight"], breed["life_expectancy"])
        return ["Working + patient listing", "Great Dane profile", "weight and life expectancy"]

    if number == 12:
        slugs = ["cavalier-king-charles-spaniel", "papillon", "shih-tzu"]
        breeds = [_breed(run, slug) for slug in slugs]
        _require(run.visited("/compare", {"breed": slugs}, exact_query=True),
                 "The comparison did not contain exactly the three required breeds")
        run.assert_unchanged()
        _answer_required(run)
        entities = {breed["slug"]: [breed["name"]] for breed in breeds}
        blocks = entity_texts(run.answer, entities)
        for breed in breeds:
            _require(_metric(blocks[breed["slug"]], "trainability", breed["trainability"]),
                     "A trainability rating is missing or misbound")
        expected = max(breeds, key=lambda row: row["trainability"])["slug"]
        _require(_winner(run.answer, entities, expected, r"\b(?:higher|highest|winner|wins|most trainable)\b"),
                 "The highest-trainability breed is missing or contradicted")
        return ["three-breed comparison", "all trainability ratings", "highest-rating conclusion"]

    raise VerificationError("Unsupported read task")


def _require_credentials(run, email, password):
    _require(run.trace_has_on("/login", email, password),
             "The specified account credentials were not recorded on the login page")


def _one_added(change):
    _require(len(change["before"]) == 0 and len(change["after"]) == 1,
             "Expected exactly one inserted row and no removed row")
    return change["after"][0]


def check_state_task(number, run):
    _answer_required(run)

    if number == 8:
        user = _user(run, "alice.j@test.com")
        event = _event(run, "puppy-training-webinar")
        _require_credentials(run, user["email"], "TestPass123!")
        _require(run.trace_has_on("/events/" + event["slug"], "Scout", "Canine Good Citizen"),
                 "The requested dog name and class were not recorded")
        _require(run.interaction_on("/events/" + event["slug"]),
                 "No event registration interaction was recorded")
        _require(run.ordered([
            ("/login", None), ("/account", None), ("/events/" + event["slug"], None),
            ("/account", None),
        ]), "The signed-in registration path and confirmation page were not recorded")
        row = _one_added(run.only_change("event_registration"))
        expected = {"user_id": user["id"], "event_id": event["id"],
                    "dog_name": "Scout", "class_name": "Canine Good Citizen"}
        _require(all(row.get(key) == value for key, value in expected.items()),
                 "The inserted event registration does not match the task")
        _require(mentions(run.answer, "Scout") and mentions(run.answer, event["title"]),
                 "The final answer does not confirm the requested registration")
        return ["Alice sign-in", "Puppy Training Webinar form", "exact Scout registration delta"]

    if number == 9:
        user = _user(run, "alice.j@test.com")
        _require_credentials(run, user["email"], "TestPass123!")
        _require(run.trace_has_on("/account", "Low"), "The Low activity selection was not recorded")
        _require(run.ordered([("/login", None), ("/account", None)]),
                 "The Alice account path was not recorded")
        _require(run.interaction_on("/account"), "No account-profile interaction was recorded")
        change = run.only_change("user")
        _require(len(change["before"]) == 1 and len(change["after"]) == 1,
                 "Expected exactly one updated user row")
        before, after = change["before"][0], change["after"][0]
        _require(before.get("id") == user["id"] and after.get("id") == user["id"],
                 "The wrong account was updated")
        differing = {key for key in before if before.get(key) != after.get(key)}
        _require(differing == {"activity_level"} and before["activity_level"] != "Low"
                 and after["activity_level"] == "Low",
                 "Only Alice's activity level may change to Low")
        _require(mentions(run.answer, "Low"), "The final answer does not confirm Low activity")
        return ["Alice sign-in", "profile form", "activity-only exact delta"]

    if number == 10:
        user = _user(run, "bob.c@test.com")
        breed = _breed(run, "whippet")
        _require_credentials(run, user["email"], "TestPass123!")
        _require(run.ordered([
            ("/login", None), ("/account", None), ("/breeds/" + breed["slug"], None),
        ]), "The Bob account and Whippet detail path were not recorded")
        _require(run.interaction_on("/breeds/" + breed["slug"]), "No save interaction was recorded")
        row = _one_added(run.only_change("saved_breed"))
        _require(row.get("user_id") == user["id"] and row.get("breed_id") == breed["id"],
                 "The saved breed row belongs to the wrong account or breed")
        _require(mentions(run.answer, breed["name"]), "The final answer does not confirm Whippet")
        return ["Bob sign-in", "Whippet detail action", "exact saved-breed delta"]

    if number == 11:
        fields = {
            "display_name": "Morgan Reed",
            "username": "morgan_reed",
            "email": "morgan.r@test.com",
            "household": "House with yard",
            "activity_level": "High",
            "experience": "Experienced owner",
        }
        _require(run.trace_has_on("/register", *fields.values(), "TrailDog42!"),
                 "One or more specified registration values were not recorded")
        _require(run.interaction_on("/register"), "No registration-form interaction was recorded")
        _require(run.ordered([("/register", None), ("/account", None)]),
                 "The registration and resulting account pages were not recorded")
        row = _one_added(run.only_change("user"))
        _require(all(row.get(key) == value for key, value in fields.items()),
                 "The inserted owner profile does not match every specified field")
        password_hash = row.get("password_hash")
        _require(isinstance(password_hash, str) and password_hash and password_hash != "TrailDog42!"
                 and ":" in password_hash, "The password was not stored as a supported hash")
        _require(mentions(run.answer, "Morgan Reed"), "The final answer does not confirm the new profile")
        return ["registration form", "exact Morgan profile delta", "hashed password"]

    raise VerificationError("Unsupported state task")

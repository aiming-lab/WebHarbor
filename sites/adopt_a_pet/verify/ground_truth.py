#!/usr/bin/env python3
"""Frozen Adopt-a-Pet catalog used as verifier ground truth.

The values below are a transcription of ``PETS`` / ``SHELTERS`` / ``USERS`` in
``sites/adopt_a_pet/app.py`` at the reviewed commit. Every verifier fails closed
(``snapshot_contract_invalid``) when the supplied initial SQLite snapshot no
longer matches this table, so a silent catalog edit can never make a verifier
grade against stale truth. The agent-facing ``tasks.jsonl`` never carries any
of these values.
"""
from __future__ import annotations

PET_FIELDS = (
    "id", "slug", "name", "species", "breed", "secondary_breed", "sex", "age_group",
    "age_months", "size", "color", "city", "state", "postal", "fee",
    "house_trained", "good_dogs", "good_cats", "good_children", "shelter_id",
)

_PET_ROWS = [
    # id slug     name      species breed                        secondary            sex      age      mo  size    color             city           st  postal  fee ht gd gc gk shelter
    (1,  "sirius",  "Sirius",  "Dog", "Chihuahua",                 "Terrier",           "Male",   "Senior", 108, "Small",  "Tan",             "Scottsdale",   "AZ", "85251", 175, 1, 1, 1, 0, 1),
    (2,  "waymo",   "Waymo",   "Dog", "American Pit Bull Terrier", "Mixed Breed",       "Male",   "Adult",   24, "Large",  "Gray",            "Phoenix",      "AZ", "85004", 225, 1, 1, 0, 1, 2),
    (3,  "casper",  "Casper",  "Cat", "Colorpoint Shorthair",      None,                "Male",   "Adult",   48, "Medium", "Cream",           "Mesa",         "AZ", "85201", 125, 1, 0, 1, 1, 1),
    (4,  "neo",     "Neo",     "Cat", "Domestic Shorthair",        None,                "Male",   "Kitten",   7, "Small",  "Black",           "Scottsdale",   "AZ", "85250", 110, 1, 1, 1, 1, 2),
    (5,  "amba",    "Amba",    "Cat", "Domestic Mediumhair",       None,                "Female", "Kitten",   5, "Small",  "Tabby",           "Arizona City", "AZ", "85123",  95, 1, 1, 1, 1, 1),
    (6,  "cinders", "Cinders", "Cat", "Domestic Shorthair",        None,                "Female", "Adult",   85, "Medium", "Tortoiseshell",   "Sedona",       "AZ", "86336", 120, 1, 0, 1, 0, 2),
    (7,  "arno",    "Arno",    "Dog", "German Shepherd Dog",       "Mixed Breed",       "Male",   "Adult",   43, "Large",  "Black and Tan",   "Casa Grande",  "AZ", "85122", 200, 1, 1, 0, 1, 1),
    (8,  "batman",  "Batman",  "Dog", "Chihuahua",                 "Yorkshire Terrier", "Male",   "Adult",   36, "Small",  "Black",           "Tucson",       "AZ", "85701", 165, 1, 1, 1, 0, 2),
    (9,  "horus",   "Horus",   "Dog", "Pointer",                   "Labrador Retriever","Male",   "Young",   16, "Large",  "White and Black", "Phoenix",      "AZ", "85006", 210, 1, 1, 0, 1, 1),
    (10, "luna",    "Luna",    "Dog", "Beagle",                    None,                "Female", "Young",   14, "Medium", "Tricolor",        "New York",     "NY", "10011", 250, 1, 1, 1, 1, 3),
    (11, "milo",    "Milo",    "Cat", "Maine Coon",                None,                "Male",   "Adult",   38, "Large",  "Orange",          "New York",     "NY", "10003", 150, 1, 0, 1, 1, 3),
    (12, "daisy",   "Daisy",   "Dog", "Golden Retriever",          None,                "Female", "Adult",   30, "Large",  "Golden",          "Seattle",      "WA", "98109", 275, 1, 1, 1, 1, 4),
    (13, "pepper",  "Pepper",  "Cat", "Domestic Shorthair",        None,                "Female", "Young",   13, "Small",  "Black and White", "Seattle",      "WA", "98101", 130, 1, 1, 1, 0, 4),
    (14, "archie",  "Archie",  "Dog", "Australian Shepherd",       None,                "Male",   "Young",   18, "Medium", "Merle",           "Austin",       "TX", "78704", 240, 1, 1, 0, 1, 5),
    (15, "ruby",    "Ruby",    "Dog", "Boxer",                     "Mixed Breed",       "Female", "Adult",   42, "Large",  "Fawn",            "Austin",       "TX", "78702", 215, 1, 1, 0, 0, 5),
    (16, "olive",   "Olive",   "Cat", "Siamese",                   None,                "Female", "Adult",   27, "Medium", "Seal Point",      "Miami",        "FL", "33130", 145, 1, 0, 1, 1, 6),
    (17, "teddy",   "Teddy",   "Dog", "Poodle",                    "Mixed Breed",       "Male",   "Senior",  96, "Small",  "White",           "Miami",        "FL", "33133", 185, 1, 1, 1, 1, 6),
    (18, "winston", "Winston", "Dog", "Chihuahua",                 "Mixed Breed",       "Male",   "Adult",   60, "Small",  "Tan",             "Tempe",        "AZ", "85281", 230, 1, 1, 1, 0, 2),
    (19, "yuki",    "Yuki",    "Dog", "Chihuahua",                 "Mixed Breed",       "Female", "Senior", 120, "Small",  "Cream",           "Glendale",     "AZ", "85301", 205, 1, 0, 1, 1, 1),
    (20, "zorro",   "Zorro",   "Dog", "Chihuahua",                 "Terrier",           "Male",   "Adult",   72, "Small",  "Black",           "Prescott",     "AZ", "86301", 220, 1, 1, 0, 0, 2),
]
PETS: list[dict] = [dict(zip(PET_FIELDS, row)) for row in _PET_ROWS]

SHELTER_FIELDS = ("id", "name", "city", "state", "phone", "email")
_SHELTER_ROWS = [
    (1, "Desert Paws Rescue",   "Phoenix",    "AZ", "602-555-0141", "hello@desertpaws.test"),
    (2, "Happy Tails Alliance", "Scottsdale", "AZ", "480-555-0128", "adopt@happytails.test"),
    (3, "City Friends Shelter", "New York",   "NY", "212-555-0164", "pets@cityfriends.test"),
    (4, "Pacific Animal Haven", "Seattle",    "WA", "206-555-0119", "info@pacifichaven.test"),
    (5, "Lone Star Companions", "Austin",     "TX", "512-555-0182", "team@lonestar.test"),
    (6, "Sunshine Pet Rescue",  "Miami",      "FL", "305-555-0136", "adopt@sunshine.test"),
]
SHELTERS: list[dict] = [dict(zip(SHELTER_FIELDS, row)) for row in _SHELTER_ROWS]

USER_FIELDS = ("id", "email", "name")
_USER_ROWS = [
    (1, "alice.j@test.com",   "Alice Johnson"),
    (2, "bob.smith@test.com", "Bob Smith"),
    (3, "carol.w@test.com",   "Carol Williams"),
    (4, "david.b@test.com",   "David Brown"),
]
USERS: list[dict] = [dict(zip(USER_FIELDS, row)) for row in _USER_ROWS]
BENCHMARK_PASSWORD = "TestPass123!"

# (favorite.id, user.id, pet.id) -- alice.j has luna favorited in the seed.
SEED_FAVORITES: list[tuple[int, int, int]] = [(1, 1, 10)]

BLOG_TITLES = [
    "What to know about pet adoption paperwork",
    "Why is there an adoption fee?",
    "Bringing home your newly adopted dog",
    "Make pet adoption less scary",
    "Am I ready for a cat?",
    "Things to consider before adopting",
]


def pet(slug: str) -> dict:
    for row in PETS:
        if row["slug"] == slug:
            return row
    raise KeyError(slug)


def pet_by_id(pet_id: int) -> dict:
    for row in PETS:
        if row["id"] == int(pet_id):
            return row
    raise KeyError(pet_id)


def shelter(shelter_id: int) -> dict:
    for row in SHELTERS:
        if row["id"] == int(shelter_id):
            return row
    raise KeyError(shelter_id)


def user(email: str) -> dict:
    for row in USERS:
        if row["email"] == email.lower():
            return row
    raise KeyError(email)


def breeds(row: dict) -> list[str]:
    return [row["breed"]] + ([row["secondary_breed"]] if row["secondary_breed"] else [])


def search(location: str = "", species: str = "", breed: str = "", sex: str = "",
           age: str = "", size: str = "") -> list[dict]:
    """Re-implementation of app.search() ranking over the frozen catalog (used by
    tests and by the README to document candidate sets; never by a verdict)."""
    import re

    lookup = {"arizona": "AZ", "new york": "New York NY", "washington": "WA", "texas": "TX", "florida": "FL"}
    query = lookup.get(location.lower(), location)

    def score(q: str, text: str) -> int:
        terms = set(re.findall(r"[a-z0-9]+", q.lower()))
        tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
        return len(terms & tokens)

    ranked = []
    for row in PETS:
        s = score(query, f"{row['city']} {row['state']} {row['postal']}") if query else 1
        if s and (not species or row["species"] == species) \
                and (not breed or breed.lower() in " ".join(breeds(row)).lower()) \
                and (not sex or row["sex"] == sex) and (not age or row["age_group"] == age) \
                and (not size or row["size"] == size):
            ranked.append((s, row["name"], row))
    return [item[2] for item in sorted(ranked, key=lambda item: (-item[0], item[1]))]

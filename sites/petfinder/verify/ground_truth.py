"""Frozen grading facts for the reviewed Petfinder tasks."""

FILTERS = {
    0: {"species": "Dog", "location": "New York, NY", "age": "Adult", "size": "Large", "good_with_children": "1"},
    1: {"species": "Cat", "location": "Chicago, IL", "age": "Young", "size": "Small", "good_with_cats": "1"},
    2: {"species": "Rabbit", "location": "Seattle, WA", "age": "Adult", "size": "Small", "good_with_children": "1"},
    7: {"species": "Dog", "location": "Chicago, IL", "age": "Senior"},
}

DETAILS = {
    0: "/pets/milo-labrador-mix",
    1: "/pets/luna-domestic-shorthair",
    2: "/pets/nori-rabbit",
    3: "/pets/nori-rabbit",
}

CHECKLIST_ITEMS = [
    "Choose a veterinarian and save the clinic number",
    "Set up a quiet room with food, water, and a comfortable bed",
    "Check fences, windows, plants, and household hazards",
]

INQUIRY_MESSAGE = "I have a quiet home and would like to meet Nori."

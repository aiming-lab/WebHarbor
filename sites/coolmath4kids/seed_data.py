"""Seed data for the Coolmath4Kids mirror.

TEASERS / MANIPULATIVES / LESSON_ORDER mirror the upstream site's content
(captured 2026-09-26). seed_database()/seed_benchmark_users() are both
idempotent — gated on the whole function, not per-row.
"""
from __future__ import annotations

from datetime import datetime, timedelta

TEASERS = [
    {"slug": "penny-triangle", "title": "Penny Triangle",
     "blurb": "Can you move just THREE pennies & flip this triangle upside down?"},
    {"slug": "toothpick-squares", "title": "Toothpick Squares",
     "blurb": "Can you move just TWO toothpicks and create SEVEN squares?"},
    {"slug": "connect-dots", "title": "Connect the Dots",
     "blurb": "Can you connect the dots using 4 lines?"},
    {"slug": "how-many-triangles", "title": "How Many Triangles",
     "blurb": "How many triangles can you find?"},
    {"slug": "handshake-puzzle", "title": "Handshake Puzzle",
     "blurb": "If each person shakes hands with every other person exactly once..."},
    {"slug": "family-photo", "title": "Family Photo",
     "blurb": "How small can this family be?"},
    {"slug": "pascals-triangle", "title": "Pascal's Triangle",
     "blurb": "What number goes in the blank?"},
    {"slug": "planting-trees", "title": "Planting Trees",
     "blurb": "Can you make the right layout?"},
    {"slug": "painted-cube", "title": "The Painted Cube",
     "blurb": "How many of the little cubes get painted?"},
    {"slug": "sticky-shapes", "title": "Sticky Shapes",
     "blurb": "Can you find which symbols match up with the numbers?"},
    {"slug": "find-numbers-4", "title": "Find the Numbers",
     "blurb": "Solve this multiplication problem."},
]

MANIPULATIVES = [
    {"slug": "ten-frame", "title": "Ten Frame",
     "about": "Ten Frame is an online mathematical manipulative that helps students develop basic number sense through the composition and decomposition of numbers within 5, 10, 20 and beyond. Ten Frame helps students understand counting, addition and subtraction. Most importantly, it allows them to practice mental math and to \"subitize\" -- instantly see how many of something there is."},
    {"slug": "base-ten-blocks", "title": "Base Ten Blocks",
     "about": "Base Ten Blocks (also known as \"Base 10 Blocks\" and \"Place Value Blocks\") is an online mathematical manipulative that helps students learn addition, subtraction, number sense, place value and counting. It lets them investigate how to regroup and solve calculations with ease."},
    {"slug": "number-line", "title": "Number Line",
     "about": "Number Line is an online mathematical manipulative that helps students develop greater flexibility in mental arithmetic as they actively construct mathematical meaning, number sense, and understandings of number relationships."},
    {"slug": "pattern-blocks", "title": "Pattern Blocks",
     "about": "Pattern Blocks is an online mathematical manipulative that helps students develop spatial reasoning. As students become more familiar with composition and decomposition of shapes, they start to recognize \"patterns,\" which is one of the most important concepts of early geometry."},
]

LESSON_ORDER = {
    "addition": ["how-addition-works", "yardstick-addition", "place-value-review",
                 "adding-numbers-within-100", "adding-numbers-within-100-regrouping",
                 "adding-numbers-within-1000", "scratch-addition"],
    "subtraction": ["how-subtraction-works", "yardstick-subtraction", "fact-families",
                    "place-value-review", "subtracting-numbers-within-100",
                    "subtracting-numbers-within-100-regrouping",
                    "subtracting-numbers-within-1000"],
    "multiplication": ["equal-groups", "lattice-multiplication"],
    "division": ["division-introduction", "standard-algorithm"],
    "fractions": ["what-are-fractions", "mixed-numbers", "magic-1",
                  "equivalent-fractions-part-1", "equivalent-fractions-part-2",
                  "simplifying-fractions", "improper-fractions",
                  "compare-fractions-equal-denominator", "compare-fractions-equal-numerator",
                  "add-fractions-denominators", "subtract-fractions-denominators",
                  "adding-and-subtracting-fractions-different-denominators",
                  "adding-and-subtracting-fractions-whole-and-mixed-numbers",
                  "multiplying-fractions", "multiplication-fractions-and-whole-numbers",
                  "dividing-fractions", "division-fractions-and-whole-numbers"],
}

BENCHMARK_USERS = [
    {"username": "alice_j", "email": "alice.j@test.com", "display_name": "Alice Johnson"},
    {"username": "bob_c", "email": "bob.c@test.com", "display_name": "Bob Chen"},
    {"username": "carol_d", "email": "carol.d@test.com", "display_name": "Carol Davis"},
    {"username": "david_k", "email": "david.k@test.com", "display_name": "David Kim"},
]
BENCHMARK_PASSWORD = "TestPass123!"


def seed_benchmark_data(db, bcrypt, reference: datetime):
    """Create the 4 benchmark users with pre-existing progress data."""
    from app import (Certificate, Favorite, GamePlay, QuizAttempt, User)

    def make_user(u):
        return User(username=u["username"], email=u["email"],
                    display_name=u["display_name"],
                    password_hash=bcrypt.generate_password_hash(BENCHMARK_PASSWORD).decode(),
                    created_at=reference - timedelta(days=30))

    alice = make_user(BENCHMARK_USERS[0])
    bob = make_user(BENCHMARK_USERS[1])
    carol = make_user(BENCHMARK_USERS[2])
    david = make_user(BENCHMARK_USERS[3])
    db.session.add_all([alice, bob, carol, david])
    db.session.flush()

    import json as _json

    def attempt(user, op, rng_label, questions, answers, op_minutes, token, status="complete"):
        correct = sum(1 for q, a in zip(questions, answers) if a == q[2])
        total = len(questions)
        a = QuizAttempt(token=token,
                        user_id=user.id, operation=op, range_label=rng_label,
                        total_questions=total, time_per_question="Unlimited",
                        status=status, questions=_json.dumps(questions),
                        answers=_json.dumps(answers),
                        elapsed_ms=_json.dumps([2400 + (i % 5) * 300 for i in range(total)]),
                        correct_count=correct,
                        score_pct=round(correct / total * 100, 1),
                        avg_seconds=2.4,
                        created_at=reference - timedelta(minutes=op_minutes),
                        completed_at=reference - timedelta(minutes=op_minutes))
        db.session.add(a)
        return a

    # Alice: strong addition, good multiplication
    a1 = attempt(alice, "Addition", "0-10",
                 [[3, 4, 7], [2, 5, 7], [6, 3, 9], [4, 4, 8], [1, 8, 9], [5, 5, 10], [7, 2, 9], [0, 6, 6], [3, 3, 6], [4, 6, 10]],
                 [7, 7, 9, 8, 9, 10, 9, 6, 6, 10], 60, "seed-alice-addition-1")
    a2 = attempt(alice, "Multiplication", "0-10",
                 [[3, 4, 12], [5, 6, 30], [2, 7, 14], [8, 3, 24], [4, 4, 16], [6, 6, 36], [7, 2, 14], [9, 1, 9], [5, 5, 25], [3, 3, 9]],
                 [12, 30, 14, 24, 16, 30, 14, 9, 25, 9], 30, "seed-alice-multiplication-1")
    db.session.flush()
    db.session.add(Certificate(user_id=alice.id, attempt_id=a1.id, person_name="Alice Johnson",
                               theme="mathgirl", operation="Addition", range_label="0-10",
                               correct=10, total=10,
                               issued_at=reference - timedelta(days=1)))
    db.session.add_all([
        Favorite(user_id=alice.id, game_slug="grand-prix-multiplication", created_at=reference - timedelta(days=5)),
        Favorite(user_id=alice.id, game_slug="alien-addition", created_at=reference - timedelta(days=4)),
        Favorite(user_id=alice.id, game_slug="tugboat-addition", created_at=reference - timedelta(days=3)),
    ])
    db.session.add(GamePlay(user_id=alice.id, game_slug="grand-prix-multiplication",
                            facts_total=10, facts_correct=9, position=1,
                            duration_seconds=71.5, created_at=reference - timedelta(days=2)))

    # Bob: subtraction focus, one certificate
    b1 = attempt(bob, "Subtraction", "0-10",
                 [[9, 4, 5], [7, 2, 5], [10, 3, 7], [8, 8, 0], [6, 1, 5], [5, 5, 0], [9, 6, 3], [4, 2, 2], [10, 7, 3], [3, 1, 2]],
                 [5, 5, 7, 0, 5, 0, 3, 2, 3, 2], 45, "seed-bob-subtraction-1")
    b2 = attempt(bob, "Subtraction", "0-5",
                 [[5, 2, 3], [4, 1, 3], [5, 5, 0], [3, 2, 1], [2, 0, 2], [4, 3, 1], [5, 1, 4], [1, 1, 0], [3, 0, 3], [5, 4, 1]],
                 [3, 3, 0, 1, 2, 1, 4, 0, 3, 1], 120, "seed-bob-subtraction-2")
    db.session.flush()
    db.session.add(Certificate(user_id=bob.id, attempt_id=b1.id, person_name="Bob Chen",
                               theme="mathninja", operation="Subtraction", range_label="0-10",
                               correct=10, total=10,
                               issued_at=reference - timedelta(days=2)))
    db.session.add_all([
        Favorite(user_id=bob.id, game_slug="island-chase", created_at=reference - timedelta(days=6)),
        Favorite(user_id=bob.id, game_slug="minus-mission", created_at=reference - timedelta(days=5)),
    ])
    db.session.add(GamePlay(user_id=bob.id, game_slug="island-chase",
                            facts_total=10, facts_correct=8, position=2,
                            duration_seconds=84.0, created_at=reference - timedelta(days=3)))

    # Carol: division practice, below certificate threshold on first try
    c1 = attempt(carol, "Division", "1-10",
                 [[8, 2, 4], [9, 3, 3], [10, 5, 2], [6, 6, 1], [7, 1, 7], [12, 4, 3], [20, 10, 2], [8, 8, 1], [15, 5, 3], [6, 2, 3]],
                 [4, 3, 2, 1, 7, 3, 2, 1, 3, 2], 90, "seed-carol-division-1")
    attempt(carol, "Division", "1-5",
            [[5, 1, 5], [10, 2, 5], [15, 3, 5], [20, 4, 5], [25, 5, 5], [6, 2, 3], [8, 4, 2], [9, 3, 3], [12, 4, 3], [10, 5, 2]],
            [5, 5, 5, 5, 5, 3, 2, 3, 3, 2], 150, "seed-carol-division-2")
    db.session.add_all([
        Favorite(user_id=carol.id, game_slug="drag-race-division", created_at=reference - timedelta(days=7)),
        Favorite(user_id=carol.id, game_slug="demolition-division", created_at=reference - timedelta(days=6)),
        Favorite(user_id=carol.id, game_slug="math-fisher", created_at=reference - timedelta(days=1)),
    ])
    db.session.add(GamePlay(user_id=carol.id, game_slug="demolition-division",
                            facts_total=10, facts_correct=6, position=3,
                            duration_seconds=95.5, created_at=reference - timedelta(days=4)))

    # David: multiplication tables, mixed results
    attempt(david, "Multiplication", "1's",
            [[1, 5, 5], [1, 8, 8], [1, 3, 3], [1, 10, 10], [1, 7, 7], [1, 2, 2], [1, 9, 9], [1, 4, 4], [1, 6, 6], [1, 0, 0]],
            [5, 8, 3, 10, 7, 2, 9, 4, 6, 0], 200, "seed-david-multiplication-1")
    d1 = attempt(david, "Multiplication", "7's",
                 [[7, 3, 21], [7, 4, 28], [7, 6, 42], [7, 8, 56], [7, 2, 14], [7, 9, 63], [7, 5, 35], [7, 7, 49], [7, 10, 70], [7, 1, 7]],
                 [21, 28, 42, 54, 14, 63, 35, 49, 70, 7], 240, "seed-david-multiplication-2")
    db.session.add_all([
        Favorite(user_id=david.id, game_slug="meteor-multiplication", created_at=reference - timedelta(days=8)),
        Favorite(user_id=david.id, game_slug="tractor-multiplication", created_at=reference - timedelta(days=2)),
    ])
    db.session.add(GamePlay(user_id=david.id, game_slug="meteor-multiplication",
                            facts_total=10, facts_correct=7, position=2,
                            duration_seconds=88.5, created_at=reference - timedelta(days=5)))

    db.session.commit()

"""Idempotent seed for the Merriam-Webster mirror.

Runs at every container boot and every /reset/merriam_webster. Each seed
function early-returns on a populated DB so that re-seeding is a no-op and the
byte-identical reset invariant holds (a bare commit on a populated DB still
bumps SQLite metadata).
"""
import json
from datetime import date, timedelta

from _seed_content import WORDS, THESAURUS, WORD_OF_THE_DAY, QUIZZES

# Fixed reference date so WORD_OF_THE_DAY rows are deterministic across boots
# and resets (using date.today() would make the seed DB differ day to day).
WOTD_ANCHOR = date(2025, 1, 15)


def seed_database(db, Word, ThesaurusEntry, WordOfTheDay, Quiz):
    if Word.query.count() > 0:
        return

    for w in WORDS:
        db.session.add(Word(
            headword=w['headword'],
            slug=w['slug'],
            pos=w['pos'],
            pronunciation=w['pronunciation'],
            syllables=w.get('syllables', ''),
            first_known_use=w.get('first_known_use', ''),
            etymology=w.get('etymology', ''),
            definitions_json=json.dumps(w['definitions'], ensure_ascii=False),
            synonyms_json=json.dumps(w.get('synonyms', []), ensure_ascii=False),
            difficulty=w.get('difficulty', 'common'),
        ))

    for t in THESAURUS:
        db.session.add(ThesaurusEntry(
            headword=t['headword'],
            slug=t['slug'],
            pos=t.get('pos', ''),
            short_def=t.get('short_def', ''),
            synonyms_json=json.dumps(t.get('synonyms', []), ensure_ascii=False),
            antonyms_json=json.dumps(t.get('antonyms', []), ensure_ascii=False),
        ))

    for w in WORD_OF_THE_DAY:
        feature_date = WOTD_ANCHOR - timedelta(days=w['feature_offset'])
        db.session.add(WordOfTheDay(
            feature_date=feature_date,
            headword=w['headword'],
            pos=w.get('pos', ''),
            pronunciation=w.get('pronunciation', ''),
            definition=w.get('definition', ''),
            did_you_know=w.get('did_you_know', ''),
            examples_json=json.dumps(w.get('examples', []), ensure_ascii=False),
        ))

    for qz in QUIZZES:
        db.session.add(Quiz(
            title=qz['title'],
            slug=qz['slug'],
            description=qz.get('description', ''),
            difficulty=qz.get('difficulty', 'easy'),
            questions_json=json.dumps(qz['questions'], ensure_ascii=False),
        ))

    db.session.commit()
    print(f"Seeded {len(WORDS)} words, {len(THESAURUS)} thesaurus entries, "
          f"{len(WORD_OF_THE_DAY)} WOTD, {len(QUIZZES)} quizzes.")


# The primary benchmark account. Login-flow tasks reference this one; the
# others exist so account-listing pages aren't trivially single-row.
PRIMARY_ACCOUNT = {'email': 'alice.j@test.com', 'username': 'alicej',
                   'name': 'Alice Johnson', 'password': 'TestPass123!'}

BENCHMARK_USERS = [
    PRIMARY_ACCOUNT,
    {'email': 'bob.smith@test.com', 'username': 'bobsmith',
     'name': 'Bob Smith', 'password': 'TestPass123!'},
    {'email': 'carol.w@test.com', 'username': 'carolw',
     'name': 'Carol Williams', 'password': 'TestPass123!'},
    {'email': 'david.b@test.com', 'username': 'davidb',
     'name': 'David Brown', 'password': 'TestPass123!'},
]


# Words the primary account already has in its list at reset time, so that
# "view/clean up my saved words" disambiguation tasks have ≥2 ambiguous items.
PRIMARY_SAVED_SLUGS = ['eloquent', 'curiosity', 'harmony']


def seed_benchmark_users(db, User, bcrypt, Word=None, SavedWord=None):
    if User.query.filter_by(email='alice.j@test.com').first():
        return
    for u in BENCHMARK_USERS:
        user = User(email=u['email'], username=u['username'], name=u['name'])
        user.password_hash = bcrypt.generate_password_hash(
            u['password']).decode('utf-8')
        db.session.add(user)
    db.session.commit()

    if Word is not None and SavedWord is not None:
        alice = User.query.filter_by(email='alice.j@test.com').first()
        for slug in PRIMARY_SAVED_SLUGS:
            w = Word.query.filter_by(slug=slug).first()
            if w:
                db.session.add(SavedWord(user_id=alice.id, word_id=w.id))
        db.session.commit()
    print(f"Seeded {len(BENCHMARK_USERS)} benchmark users.")

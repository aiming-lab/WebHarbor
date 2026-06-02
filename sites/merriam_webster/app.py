#!/usr/bin/env python3
"""Merriam-Webster mirror — Flask application.

Routes + SQLAlchemy models for an offline mirror of merriam-webster.com.
Runtime data comes entirely from instance/merriam_webster.db (seeded from
instance_seed/merriam_webster.db at boot). No JSON read at request time.
"""
import os
import re
import json
import random
from datetime import datetime, date

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from sqlalchemy import or_, func

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'merriam-webster-mirror-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'merriam_webster.db')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your account.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)

STOPWORDS = {'a', 'an', 'the', 'of', 'to', 'in', 'on', 'for', 'and', 'or',
             'is', 'are', 'be', 'with', 'as', 'by', 'at', 'from'}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    saved_words = db.relationship('SavedWord', backref='user', lazy=True,
                                  cascade='all, delete-orphan')
    search_history = db.relationship('SearchHistory', backref='user',
                                     lazy=True, cascade='all, delete-orphan')
    quiz_scores = db.relationship('QuizScore', backref='user', lazy=True,
                                  cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class Word(db.Model):
    __tablename__ = 'words'
    id = db.Column(db.Integer, primary_key=True)
    headword = db.Column(db.String(120), nullable=False, index=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    pos = db.Column(db.String(40), default='')            # noun, verb, ...
    pronunciation = db.Column(db.String(120), default='')  # MW respelling
    syllables = db.Column(db.String(120), default='')      # se·ren·dip·i·ty
    first_known_use = db.Column(db.String(200), default='')
    etymology = db.Column(db.Text, default='')
    # definitions: JSON list of {sense_num, text, examples:[str]}
    definitions_json = db.Column(db.Text, default='[]')
    # related synonyms shown on the dictionary page (slugs)
    synonyms_json = db.Column(db.Text, default='[]')
    difficulty = db.Column(db.String(20), default='common')  # common|advanced
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    saved_by = db.relationship('SavedWord', backref='word', lazy=True,
                               cascade='all, delete-orphan')

    def get_definitions(self):
        try:
            return json.loads(self.definitions_json or '[]')
        except Exception:
            return []

    def get_synonyms(self):
        try:
            return json.loads(self.synonyms_json or '[]')
        except Exception:
            return []

    def all_examples(self):
        out = []
        for d in self.get_definitions():
            out.extend(d.get('examples') or [])
        return out


class ThesaurusEntry(db.Model):
    __tablename__ = 'thesaurus_entries'
    id = db.Column(db.Integer, primary_key=True)
    headword = db.Column(db.String(120), nullable=False, index=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    pos = db.Column(db.String(40), default='')
    short_def = db.Column(db.Text, default='')
    synonyms_json = db.Column(db.Text, default='[]')
    antonyms_json = db.Column(db.Text, default='[]')

    def get_synonyms(self):
        try:
            return json.loads(self.synonyms_json or '[]')
        except Exception:
            return []

    def get_antonyms(self):
        try:
            return json.loads(self.antonyms_json or '[]')
        except Exception:
            return []


class WordOfTheDay(db.Model):
    __tablename__ = 'word_of_the_day'
    id = db.Column(db.Integer, primary_key=True)
    feature_date = db.Column(db.Date, unique=True, nullable=False, index=True)
    headword = db.Column(db.String(120), nullable=False)
    pos = db.Column(db.String(40), default='')
    pronunciation = db.Column(db.String(120), default='')
    definition = db.Column(db.Text, default='')
    did_you_know = db.Column(db.Text, default='')
    examples_json = db.Column(db.Text, default='[]')

    def get_examples(self):
        try:
            return json.loads(self.examples_json or '[]')
        except Exception:
            return []


class SavedWord(db.Model):
    __tablename__ = 'saved_words'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('words.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SearchHistory(db.Model):
    __tablename__ = 'search_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    term = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default='')
    difficulty = db.Column(db.String(20), default='easy')
    # questions: JSON list of {q, choices:[str], answer_index, explanation}
    questions_json = db.Column(db.Text, default='[]')

    def get_questions(self):
        try:
            return json.loads(self.questions_json or '[]')
        except Exception:
            return []


class QuizScore(db.Model):
    __tablename__ = 'quiz_scores'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

class RegisterForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=120)])
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm Password',
                            validators=[DataRequired(), EqualTo('password')])


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


# ---------------------------------------------------------------------------
# Search helpers (token-overlap scoring, not strict AND)
# ---------------------------------------------------------------------------

def _tokens(q):
    return [t.lower() for t in re.findall(r'[a-z0-9]+', q.lower())
            if t not in STOPWORDS and len(t) >= 2]


def _score_word(w, tokens):
    hay = ' '.join([
        w.headword.lower(), w.pos.lower(),
        ' '.join(d.get('text', '') for d in w.get_definitions()).lower(),
    ])
    score = 0
    for t in tokens:
        if w.headword.lower() == t:
            score += 5
        elif w.headword.lower().startswith(t):
            score += 3
        elif t in hay:
            score += 1
    return score


def search_words(q):
    tokens = _tokens(q)
    if not tokens:
        return []
    exact = Word.query.filter(Word.headword.ilike(q.strip())).all()
    partial = Word.query.filter(
        or_(Word.headword.ilike(f'%{tokens[0]}%'),
            Word.definitions_json.ilike(f'%{tokens[0]}%'))
    ).limit(60).all()
    seen = {w.id for w in exact}
    combined = exact + [w for w in partial if w.id not in seen]
    min_req = max(1, len(tokens) // 2)
    scored = [(s, w) for w in combined
              if (s := _score_word(w, tokens)) >= min_req]

    # Synonym-aware recall: if the query matches a thesaurus headword, surface
    # dictionary entries for its synonyms too. A search for "happy" should
    # then return its near-synonyms (elated, cheerful, ...) as related hits,
    # so a definition-fragment search has real distractors instead of one hit.
    syn_words = []
    if scored:
        thes = ThesaurusEntry.query.filter(
            ThesaurusEntry.headword.ilike(q.strip())).first()
        if thes:
            scored_ids = {w.id for _, w in scored}
            for syn in thes.get_synonyms():
                w = Word.query.filter(func.lower(Word.headword) == syn.lower()).first()
                if w and w.id not in scored_ids:
                    syn_words.append(w)
                    scored_ids.add(w.id)

    scored.sort(key=lambda x: (-x[0], x[1].headword))
    return [w for _, w in scored] + syn_words


def todays_wotd():
    """Return today's WOTD, falling back to a deterministic rotation so the
    homepage always has one even on dates with no explicit row."""
    today = date.today()
    w = WordOfTheDay.query.filter_by(feature_date=today).first()
    if w:
        return w
    rows = WordOfTheDay.query.order_by(WordOfTheDay.id).all()
    if not rows:
        return None
    return rows[today.toordinal() % len(rows)]


# ---------------------------------------------------------------------------
# Routes — core
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    wotd = todays_wotd()
    trending = Word.query.order_by(func.random()).limit(8).all()
    browse = Word.query.order_by(Word.headword).limit(12).all()
    return render_template('index.html', wotd=wotd, trending=trending,
                           browse=browse)


@app.route('/dictionary/<slug>')
def word_detail(slug):
    word = Word.query.filter_by(slug=slug).first_or_404()
    if current_user.is_authenticated:
        db.session.add(SearchHistory(user_id=current_user.id,
                                     term=word.headword))
        db.session.commit()
    is_saved = False
    if current_user.is_authenticated:
        is_saved = SavedWord.query.filter_by(
            user_id=current_user.id, word_id=word.id).first() is not None
    prev_w = (Word.query.filter(Word.headword < word.headword)
              .order_by(Word.headword.desc()).limit(4).all())
    next_w = (Word.query.filter(Word.headword > word.headword)
              .order_by(Word.headword.asc()).limit(4).all())
    nearby = list(reversed(prev_w)) + [word] + next_w
    thes = ThesaurusEntry.query.filter(
        func.lower(ThesaurusEntry.headword) == word.headword.lower()).first()
    return render_template('word_detail.html', word=word, is_saved=is_saved,
                           nearby=nearby, thes=thes)


@app.route('/thesaurus/<slug>')
def thesaurus_detail(slug):
    entry = ThesaurusEntry.query.filter_by(slug=slug).first()
    if not entry:
        entry = ThesaurusEntry.query.filter(
            ThesaurusEntry.headword.ilike(slug.replace('-', ' '))).first()
    if not entry:
        abort(404)
    word = Word.query.filter(
        func.lower(Word.headword) == entry.headword.lower()).first()
    return render_template('thesaurus_detail.html', entry=entry, word=word)


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    stype = request.args.get('type', 'dictionary')
    if not q:
        return render_template('search.html', q='', results=[],
                               thes_results=[], stype=stype)

    exact = Word.query.filter(Word.headword.ilike(q)).first()
    if exact and stype == 'dictionary':
        if current_user.is_authenticated:
            db.session.add(SearchHistory(user_id=current_user.id, term=q))
            db.session.commit()
        return redirect(url_for('word_detail', slug=exact.slug))

    results = search_words(q)
    thes_results = ThesaurusEntry.query.filter(
        ThesaurusEntry.headword.ilike(f'%{q}%')).limit(10).all()

    if current_user.is_authenticated:
        db.session.add(SearchHistory(user_id=current_user.id, term=q))
        db.session.commit()
    return render_template('search.html', q=q, results=results,
                           thes_results=thes_results, stype=stype)


@app.route('/autocomplete')
@csrf.exempt
def autocomplete():
    q = request.args.get('q', '').strip().lower()
    if len(q) < 2:
        return jsonify([])
    words = Word.query.filter(Word.headword.ilike(f'{q}%')).limit(8).all()
    return jsonify([w.headword for w in words])


@app.route('/word-of-the-day')
@app.route('/word-of-the-day/<slug>')
def word_of_the_day(slug=None):
    if slug:
        wotd = WordOfTheDay.query.filter(
            func.lower(WordOfTheDay.headword) == slug.lower()).first_or_404()
    else:
        wotd = todays_wotd()
        if not wotd:
            abort(404)
    recent = (WordOfTheDay.query
              .filter(WordOfTheDay.id != wotd.id)
              .order_by(WordOfTheDay.feature_date.desc()).limit(6).all())
    return render_template('wotd.html', wotd=wotd, recent=recent)


# ---------------------------------------------------------------------------
# Routes — games & quizzes
# ---------------------------------------------------------------------------

@app.route('/games-quizzes')
def games_quizzes():
    quizzes = Quiz.query.all()
    return render_template('games_index.html', quizzes=quizzes)


@app.route('/quiz/<slug>')
def quiz_detail(slug):
    quiz = Quiz.query.filter_by(slug=slug).first_or_404()
    return render_template('quiz.html', quiz=quiz,
                           questions=quiz.get_questions())


@app.route('/quiz/<slug>/submit', methods=['POST'])
def quiz_submit(slug):
    quiz = Quiz.query.filter_by(slug=slug).first_or_404()
    questions = quiz.get_questions()
    score = 0
    review = []
    for i, qq in enumerate(questions):
        picked = request.form.get(f'q{i}')
        correct = qq.get('answer_index')
        ok = picked is not None and int(picked) == correct
        if ok:
            score += 1
        review.append({
            'q': qq.get('q'),
            'choices': qq.get('choices', []),
            'picked': int(picked) if picked is not None else None,
            'answer_index': correct,
            'explanation': qq.get('explanation', ''),
            'correct': ok,
        })
    total = len(questions)
    if current_user.is_authenticated:
        db.session.add(QuizScore(user_id=current_user.id, quiz_id=quiz.id,
                                 score=score, total=total))
        db.session.commit()
    return render_template('quiz_result.html', quiz=quiz, score=score,
                           total=total, review=review)


# ---------------------------------------------------------------------------
# Routes — auth & account
# ---------------------------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            flash('That email is already registered.', 'error')
        elif User.query.filter_by(username=form.username.data).first():
            flash('That username is taken.', 'error')
        else:
            u = User(email=form.email.data.lower(),
                     username=form.username.data, name=form.name.data)
            u.set_password(form.password.data)
            db.session.add(u)
            db.session.commit()
            login_user(u)
            flash('Welcome to Merriam-Webster!', 'success')
            return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        ident = form.email.data.strip().lower()
        user = (User.query.filter_by(email=ident).first()
                or User.query.filter(func.lower(User.username) == ident).first())
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/account')
@login_required
def account():
    saved = (SavedWord.query.filter_by(user_id=current_user.id)
             .order_by(SavedWord.created_at.desc()).all())
    history = (SearchHistory.query.filter_by(user_id=current_user.id)
               .order_by(SearchHistory.created_at.desc()).limit(20).all())
    scores = (QuizScore.query.filter_by(user_id=current_user.id)
              .order_by(QuizScore.created_at.desc()).limit(10).all())
    return render_template('account.html', saved=saved, history=history,
                           scores=scores)


@app.route('/account/saved-words/<int:sw_id>/remove', methods=['POST'])
@login_required
def remove_saved(sw_id):
    sw = SavedWord.query.filter_by(id=sw_id, user_id=current_user.id).first_or_404()
    db.session.delete(sw)
    db.session.commit()
    flash('Removed from your saved words.', 'info')
    return redirect(url_for('account'))


@app.route('/words/<int:word_id>/save', methods=['POST'])
@login_required
def save_word(word_id):
    word = db.session.get(Word, word_id)
    if not word:
        abort(404)
    existing = SavedWord.query.filter_by(user_id=current_user.id,
                                         word_id=word.id).first()
    if not existing:
        db.session.add(SavedWord(user_id=current_user.id, word_id=word.id))
        db.session.commit()
        flash(f'Saved "{word.headword}" to your words.', 'success')
    return redirect(request.referrer or url_for('word_detail', slug=word.slug))


@app.route('/_health')
def health():
    return {'ok': True, 'site': 'merriam_webster',
            'words': Word.query.count()}


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


@app.context_processor
def inject_globals():
    return {'current_year': datetime.now().year}


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

from seed_data import seed_database, seed_benchmark_users  # noqa: E402

with app.app_context():
    db.create_all()
    seed_database(db, Word, ThesaurusEntry, WordOfTheDay, Quiz)
    seed_benchmark_users(db, User, bcrypt, Word, SavedWord)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

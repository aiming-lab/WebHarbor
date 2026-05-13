#!/usr/bin/env python3
"""Ohio State University mirror — Flask application."""
import os
import re
from datetime import datetime
from math import ceil

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, abort, g)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from wtforms import StringField, PasswordField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'osu-mirror-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'osu.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_TIME_LIMIT'] = None

os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to continue.'
login_manager.login_message_category = 'info'
csrf = CSRFProtect(app)

PER_PAGE = 20

# ─── Helpers ──────────────────────────────────────────────────────────────────

def slugify(text):
    if not text:
        return ''
    s = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
    s = re.sub(r'[\s]+', '-', s.strip().lower())
    return s

# ─── Models ───────────────────────────────────────────────────────────────────

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False, default='')
    role = db.Column(db.String(30), default='student')
    bio = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookmarks = db.relationship('Bookmark', backref='user', lazy=True,
                                cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)


class College(db.Model):
    __tablename__ = 'colleges'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default='')
    dean = db.Column(db.String(150), default='')
    founded_year = db.Column(db.Integer, default=1870)
    undergrad_count = db.Column(db.Integer, default=1000)
    grad_count = db.Column(db.Integer, default=500)
    campus = db.Column(db.String(100), default='Columbus')

    departments = db.relationship('Department', backref='college', lazy=True)
    programs = db.relationship('Program', backref='college', lazy=True)
    research_centers = db.relationship('ResearchCenter', backref='college', lazy=True)


class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    college_id = db.Column(db.Integer, db.ForeignKey('colleges.id'), nullable=False)
    description = db.Column(db.Text, default='')
    chair = db.Column(db.String(150), default='')
    phone = db.Column(db.String(30), default='')
    location = db.Column(db.String(200), default='')

    faculty = db.relationship('Faculty', backref='department', lazy=True)
    programs = db.relationship('Program', backref='department', lazy=True)


class Program(db.Model):
    __tablename__ = 'programs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(300), unique=True, nullable=False, index=True)
    degree_type = db.Column(db.String(20), default='BA')
    college_id = db.Column(db.Integer, db.ForeignKey('colleges.id'), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    description = db.Column(db.Text, default='')
    requirements = db.Column(db.Text, default='')
    units = db.Column(db.Integer, default=120)
    duration_years = db.Column(db.Float, default=4.0)
    application_deadline = db.Column(db.String(80), default='')
    is_online = db.Column(db.Boolean, default=False)
    gre_required = db.Column(db.Boolean, default=False)


class NewsArticle(db.Model):
    __tablename__ = 'news_articles'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(300), unique=True, nullable=False, index=True)
    category = db.Column(db.String(50), default='Campus Life')
    author = db.Column(db.String(150), default='OSU News Staff')
    published_date = db.Column(db.DateTime, default=datetime.utcnow)
    content = db.Column(db.Text, default='')
    summary = db.Column(db.Text, default='')
    tags = db.Column(db.String(500), default='')
    view_count = db.Column(db.Integer, default=0)
    featured = db.Column(db.Boolean, default=False)


class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, default='')
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=True)
    location = db.Column(db.String(300), default='')
    building = db.Column(db.String(200), default='')
    campus = db.Column(db.String(100), default='Columbus')
    category = db.Column(db.String(50), default='Lecture')
    organizer = db.Column(db.String(200), default='')
    registration_required = db.Column(db.Boolean, default=False)
    cost = db.Column(db.String(50), default='Free')


class ResearchCenter(db.Model):
    __tablename__ = 'research_centers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(300), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default='')
    director = db.Column(db.String(150), default='')
    college_id = db.Column(db.Integer, db.ForeignKey('colleges.id'), nullable=True)
    focus_areas = db.Column(db.String(500), default='')
    url = db.Column(db.String(300), default='')
    founded_year = db.Column(db.Integer, default=2000)


class Faculty(db.Model):
    __tablename__ = 'faculty'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), default='Professor')
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    email = db.Column(db.String(120), default='')
    office = db.Column(db.String(200), default='')
    phone = db.Column(db.String(30), default='')
    research_interests = db.Column(db.String(500), default='')
    bio = db.Column(db.Text, default='')
    is_emeritus = db.Column(db.Boolean, default=False)


class AthleticTeam(db.Model):
    __tablename__ = 'athletic_teams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    sport = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(20), default='Men')
    conference = db.Column(db.String(100), default='Big Ten')
    coach = db.Column(db.String(150), default='')
    home_venue = db.Column(db.String(200), default='')
    national_titles = db.Column(db.Integer, default=0)
    recent_record = db.Column(db.String(50), default='')


class Bookmark(db.Model):
    __tablename__ = 'bookmarks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_type = db.Column(db.String(50), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── Forms ────────────────────────────────────────────────────────────────────

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(3, 80)])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(2, 150)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(8, 100)])
    confirm = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])

class ProfileForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(2, 150)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=1000)])

class BookmarkForm(FlaskForm):
    item_type = StringField('Type', validators=[DataRequired()])
    item_id = StringField('ID', validators=[DataRequired()])
    note = TextAreaField('Note', validators=[Optional(), Length(max=500)])

# ─── Login Manager ────────────────────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ─── Context Processors ───────────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    return {
        'now': datetime.utcnow(),
        'colleges': College.query.order_by(College.name).all(),
    }

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    featured_news = NewsArticle.query.filter_by(featured=True).order_by(
        NewsArticle.published_date.desc()).limit(6).all()
    if len(featured_news) < 3:
        featured_news = NewsArticle.query.order_by(
            NewsArticle.published_date.desc()).limit(6).all()
    upcoming_events = Event.query.filter(
        Event.start_datetime >= datetime.utcnow()
    ).order_by(Event.start_datetime).limit(4).all()
    recent_research = ResearchCenter.query.limit(4).all()
    stats = {
        'fulbright_rank': 1,
        'undergrad_majors': 200,
        'grad_programs': 278,
        'varsity_sports': 36,
        'faculty_count': 7000,
        'undergrad_count': 46820,
        'grad_count': 14000,
        'degree_programs': 500,
        'buckeython_raised': 13,
        'extension_offices': 88,
        'campuses': 6,
        'research_expenditure': 1.3,
    }
    return render_template('index.html',
                           featured_news=featured_news,
                           upcoming_events=upcoming_events,
                           recent_research=recent_research,
                           stats=stats)


@app.route('/news')
def news():
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '')
    featured = request.args.get('featured', '')
    page = request.args.get('page', 1, type=int)

    query = NewsArticle.query
    if q:
        query = query.filter(
            db.or_(
                NewsArticle.title.ilike(f'%{q}%'),
                NewsArticle.summary.ilike(f'%{q}%'),
                NewsArticle.content.ilike(f'%{q}%'),
                NewsArticle.tags.ilike(f'%{q}%'),
            ))
    if category:
        query = query.filter(NewsArticle.category == category)
    if featured == '1':
        query = query.filter(NewsArticle.featured == True)

    query = query.order_by(NewsArticle.published_date.desc())
    total = query.count()
    articles = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
    total_pages = ceil(total / PER_PAGE) if total else 1

    categories = ['Research', 'Campus Life', 'Faculty', 'Student', 'Athletics',
                  'Science', 'Health']
    return render_template('news.html',
                           articles=articles,
                           total=total,
                           page=page,
                           total_pages=total_pages,
                           categories=categories,
                           current_category=category,
                           q=q,
                           featured=featured)


@app.route('/news/<slug>')
def news_article(slug):
    article = NewsArticle.query.filter_by(slug=slug).first_or_404()
    article.view_count = (article.view_count or 0) + 1
    db.session.commit()
    related = NewsArticle.query.filter(
        NewsArticle.category == article.category,
        NewsArticle.id != article.id
    ).order_by(NewsArticle.published_date.desc()).limit(3).all()
    return render_template('news_article.html', article=article, related=related)


@app.route('/academics')
def academics():
    colleges = College.query.order_by(College.name).all()
    total_programs = Program.query.count()
    total_depts = Department.query.count()
    return render_template('academics.html',
                           colleges=colleges,
                           total_programs=total_programs,
                           total_depts=total_depts)


@app.route('/programs')
def programs():
    q = request.args.get('q', '').strip()
    college_slug = request.args.get('college', '')
    degree = request.args.get('degree', '')
    online = request.args.get('online', '')
    page = request.args.get('page', 1, type=int)

    query = Program.query
    if q:
        query = query.filter(
            db.or_(
                Program.name.ilike(f'%{q}%'),
                Program.description.ilike(f'%{q}%'),
            ))
    if college_slug:
        col = College.query.filter_by(slug=college_slug).first()
        if col:
            query = query.filter(Program.college_id == col.id)
    if degree:
        query = query.filter(Program.degree_type == degree)
    if online == '1':
        query = query.filter(Program.is_online == True)

    query = query.order_by(Program.name)
    total = query.count()
    progs = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
    total_pages = ceil(total / PER_PAGE) if total else 1

    all_colleges = College.query.order_by(College.name).all()
    degree_types = ['BA', 'BS', 'MA', 'MS', 'PhD', 'MPH', 'MBA', 'JD', 'MD',
                    'PharmD', 'DVM', 'OD']
    return render_template('programs.html',
                           programs=progs,
                           total=total,
                           page=page,
                           total_pages=total_pages,
                           all_colleges=all_colleges,
                           degree_types=degree_types,
                           current_college=college_slug,
                           current_degree=degree,
                           online=online,
                           q=q)


@app.route('/programs/<slug>')
def program_detail(slug):
    program = Program.query.filter_by(slug=slug).first_or_404()
    related = Program.query.filter(
        Program.college_id == program.college_id,
        Program.id != program.id
    ).limit(4).all()
    return render_template('program_detail.html', program=program, related=related)


@app.route('/events')
def events():
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '')
    campus = request.args.get('campus', '')
    date_filter = request.args.get('date', 'upcoming')
    page = request.args.get('page', 1, type=int)
    now = datetime.utcnow()

    query = Event.query
    if q:
        query = query.filter(
            db.or_(
                Event.title.ilike(f'%{q}%'),
                Event.description.ilike(f'%{q}%'),
                Event.location.ilike(f'%{q}%'),
                Event.organizer.ilike(f'%{q}%'),
            ))
    if category:
        query = query.filter(Event.category == category)
    if campus:
        query = query.filter(Event.campus == campus)
    if date_filter == 'upcoming':
        query = query.filter(Event.start_datetime >= now)
        query = query.order_by(Event.start_datetime)
    elif date_filter == 'past':
        query = query.filter(Event.start_datetime < now)
        query = query.order_by(Event.start_datetime.desc())
    elif date_filter == 'today':
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59)
        query = query.filter(Event.start_datetime.between(today_start, today_end))
        query = query.order_by(Event.start_datetime)
    else:
        query = query.order_by(Event.start_datetime)

    total = query.count()
    evts = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
    total_pages = ceil(total / PER_PAGE) if total else 1

    categories = ['Lecture', 'Sports', 'Arts', 'Career', 'Health', 'Social', 'Virtual']
    campuses = ['Columbus', 'Lima', 'Marion', 'Mansfield', 'Newark', 'Wooster']
    return render_template('events.html',
                           events=evts,
                           total=total,
                           page=page,
                           total_pages=total_pages,
                           categories=categories,
                           campuses=campuses,
                           current_category=category,
                           current_campus=campus,
                           date_filter=date_filter,
                           q=q)


@app.route('/events/<int:event_id>')
def event_detail(event_id):
    event = db.session.get(Event, event_id)
    if event is None:
        abort(404)
    related = Event.query.filter(
        Event.category == event.category,
        Event.id != event.id,
        Event.start_datetime >= datetime.utcnow()
    ).order_by(Event.start_datetime).limit(3).all()
    return render_template('event_detail.html', event=event, related=related)


@app.route('/research')
def research():
    centers = ResearchCenter.query.order_by(ResearchCenter.name).all()
    colleges = College.query.order_by(College.name).all()
    return render_template('research.html', centers=centers, colleges=colleges)


@app.route('/research/<slug>')
def research_center(slug):
    center = ResearchCenter.query.filter_by(slug=slug).first_or_404()
    related = ResearchCenter.query.filter(
        ResearchCenter.college_id == center.college_id,
        ResearchCenter.id != center.id
    ).limit(3).all()
    return render_template('research_center.html', center=center, related=related)


@app.route('/departments')
def departments():
    all_colleges = College.query.order_by(College.name).all()
    depts_by_college = {}
    for college in all_colleges:
        depts_by_college[college] = Department.query.filter_by(
            college_id=college.id).order_by(Department.name).all()
    return render_template('departments.html', depts_by_college=depts_by_college)


@app.route('/departments/<slug>')
def department_detail(slug):
    dept = Department.query.filter_by(slug=slug).first_or_404()
    faculty_list = Faculty.query.filter_by(department_id=dept.id).order_by(Faculty.name).all()
    dept_programs = Program.query.filter_by(department_id=dept.id).all()
    return render_template('department_detail.html',
                           dept=dept,
                           faculty_list=faculty_list,
                           programs=dept_programs)


@app.route('/admissions')
def admissions():
    undergrad_programs = Program.query.filter(
        Program.degree_type.in_(['BA', 'BS'])
    ).count()
    grad_programs = Program.query.filter(
        Program.degree_type.in_(['MA', 'MS', 'PhD', 'MPH', 'MBA', 'JD', 'MD',
                                  'PharmD', 'DVM', 'OD'])
    ).count()
    online_programs = Program.query.filter_by(is_online=True).count()
    return render_template('admissions.html',
                           undergrad_programs=undergrad_programs,
                           grad_programs=grad_programs,
                           online_programs=online_programs)


@app.route('/about')
def about():
    stats = {
        'fulbright_rank': 1,
        'undergrad_majors': 200,
        'grad_programs': 278,
        'varsity_sports': 36,
        'faculty_count': 7000,
        'undergrad_count': 46820,
        'grad_count': 14000,
        'degree_programs': 500,
        'founded': 1870,
        'acres': 1665,
        'campuses': 6,
        'alumni': 600000,
        'extension_offices': 88,
        'buckeython_raised': 13,
        'research_expenditure': 1.3,
        'national_titles': 15,
    }
    return render_template('about.html', stats=stats)


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    results = {'programs': [], 'news': [], 'events': [], 'faculty': [],
               'research': [], 'athletics': []}
    total = 0
    if q:
        results['programs'] = Program.query.filter(
            db.or_(
                Program.name.ilike(f'%{q}%'),
                Program.description.ilike(f'%{q}%'),
            )).limit(10).all()
        results['news'] = NewsArticle.query.filter(
            db.or_(
                NewsArticle.title.ilike(f'%{q}%'),
                NewsArticle.summary.ilike(f'%{q}%'),
                NewsArticle.tags.ilike(f'%{q}%'),
            )).order_by(NewsArticle.published_date.desc()).limit(10).all()
        results['events'] = Event.query.filter(
            db.or_(
                Event.title.ilike(f'%{q}%'),
                Event.description.ilike(f'%{q}%'),
            )).limit(10).all()
        results['faculty'] = Faculty.query.filter(
            db.or_(
                Faculty.name.ilike(f'%{q}%'),
                Faculty.research_interests.ilike(f'%{q}%'),
                Faculty.bio.ilike(f'%{q}%'),
            )).limit(10).all()
        results['research'] = ResearchCenter.query.filter(
            db.or_(
                ResearchCenter.name.ilike(f'%{q}%'),
                ResearchCenter.description.ilike(f'%{q}%'),
                ResearchCenter.focus_areas.ilike(f'%{q}%'),
            )).limit(10).all()
        results['athletics'] = AthleticTeam.query.filter(
            db.or_(
                AthleticTeam.name.ilike(f'%{q}%'),
                AthleticTeam.sport.ilike(f'%{q}%'),
            )).limit(10).all()
        total = sum(len(v) for v in results.values())
    return render_template('search.html', q=q, results=results, total=total)


@app.route('/faculty')
def faculty():
    q = request.args.get('q', '').strip()
    dept_slug = request.args.get('dept', '')
    page = request.args.get('page', 1, type=int)

    query = Faculty.query
    if q:
        query = query.filter(
            db.or_(
                Faculty.name.ilike(f'%{q}%'),
                Faculty.research_interests.ilike(f'%{q}%'),
                Faculty.title.ilike(f'%{q}%'),
            ))
    if dept_slug:
        dept = Department.query.filter_by(slug=dept_slug).first()
        if dept:
            query = query.filter(Faculty.department_id == dept.id)

    query = query.order_by(Faculty.name)
    total = query.count()
    faculty_list = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
    total_pages = ceil(total / PER_PAGE) if total else 1

    all_depts = Department.query.order_by(Department.name).all()
    return render_template('faculty.html',
                           faculty_list=faculty_list,
                           total=total,
                           page=page,
                           total_pages=total_pages,
                           all_depts=all_depts,
                           current_dept=dept_slug,
                           q=q)


@app.route('/faculty/<slug>')
def faculty_profile(slug):
    member = Faculty.query.filter_by(slug=slug).first_or_404()
    colleagues = []
    if member.department_id:
        colleagues = Faculty.query.filter(
            Faculty.department_id == member.department_id,
            Faculty.id != member.id
        ).limit(5).all()
    return render_template('faculty_profile.html', member=member, colleagues=colleagues)


@app.route('/athletics')
def athletics():
    teams = AthleticTeam.query.order_by(AthleticTeam.sport, AthleticTeam.name).all()
    men_teams = [t for t in teams if t.gender == 'Men']
    women_teams = [t for t in teams if t.gender == 'Women']
    coed_teams = [t for t in teams if t.gender == 'Co-ed']
    return render_template('athletics.html',
                           teams=teams,
                           men_teams=men_teams,
                           women_teams=women_teams,
                           coed_teams=coed_teams)


@app.route('/athletics/<slug>')
def athletics_team(slug):
    team = AthleticTeam.query.filter_by(slug=slug).first_or_404()
    related = AthleticTeam.query.filter(
        AthleticTeam.gender == team.gender,
        AthleticTeam.id != team.id
    ).limit(4).all()
    return render_template('athletics_team.html', team=team, related=related)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash('Welcome back, Buckeye!', 'success')
            return redirect(next_page or url_for('index'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower().strip()).first():
            flash('Email already registered.', 'danger')
        elif User.query.filter_by(username=form.username.data.strip()).first():
            flash('Username already taken.', 'danger')
        else:
            user = User(
                email=form.email.data.lower().strip(),
                username=form.username.data.strip(),
                full_name=form.full_name.data.strip(),
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created! Welcome to The Ohio State University.', 'success')
            return redirect(url_for('index'))
    return render_template('register.html', form=form)


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/account')
@login_required
def account():
    bookmarks = Bookmark.query.filter_by(user_id=current_user.id).order_by(
        Bookmark.created_at.desc()).all()
    bookmark_details = []
    for bm in bookmarks:
        detail = {'bookmark': bm, 'item': None, 'title': '', 'url': '#'}
        if bm.item_type == 'program':
            item = db.session.get(Program, bm.item_id)
            if item:
                detail['item'] = item
                detail['title'] = item.name
                detail['url'] = url_for('program_detail', slug=item.slug)
        elif bm.item_type == 'news':
            item = db.session.get(NewsArticle, bm.item_id)
            if item:
                detail['item'] = item
                detail['title'] = item.title
                detail['url'] = url_for('news_article', slug=item.slug)
        elif bm.item_type == 'event':
            item = db.session.get(Event, bm.item_id)
            if item:
                detail['item'] = item
                detail['title'] = item.title
                detail['url'] = url_for('event_detail', event_id=item.id)
        elif bm.item_type == 'faculty':
            item = db.session.get(Faculty, bm.item_id)
            if item:
                detail['item'] = item
                detail['title'] = item.name
                detail['url'] = url_for('faculty_profile', slug=item.slug)
        elif bm.item_type == 'research':
            item = db.session.get(ResearchCenter, bm.item_id)
            if item:
                detail['item'] = item
                detail['title'] = item.name
                detail['url'] = url_for('research_center', slug=item.slug)
        elif bm.item_type == 'athletics':
            item = db.session.get(AthleticTeam, bm.item_id)
            if item:
                detail['item'] = item
                detail['title'] = item.name
                detail['url'] = url_for('athletics_team', slug=item.slug)
        bookmark_details.append(detail)
    return render_template('account.html', bookmark_details=bookmark_details)


@app.route('/bookmark/add', methods=['POST'])
@login_required
def bookmark_add():
    item_type = request.form.get('item_type')
    item_id = request.form.get('item_id', type=int)
    note = request.form.get('note', '')
    if item_type and item_id:
        existing = Bookmark.query.filter_by(
            user_id=current_user.id, item_type=item_type, item_id=item_id
        ).first()
        if not existing:
            bm = Bookmark(user_id=current_user.id, item_type=item_type,
                          item_id=item_id, note=note)
            db.session.add(bm)
            db.session.commit()
            flash('Saved to bookmarks.', 'success')
        else:
            flash('Already bookmarked.', 'info')
    next_url = request.form.get('next') or request.referrer or url_for('account')
    return redirect(next_url)


@app.route('/bookmark/remove', methods=['POST'])
@login_required
def bookmark_remove():
    bookmark_id = request.form.get('bookmark_id', type=int)
    if bookmark_id:
        bm = db.session.get(Bookmark, bookmark_id)
        if bm and bm.user_id == current_user.id:
            db.session.delete(bm)
            db.session.commit()
            flash('Bookmark removed.', 'info')
    return redirect(request.referrer or url_for('account'))


@app.route('/_health')
def health():
    try:
        college_count = College.query.count()
        program_count = Program.query.count()
        return jsonify({
            'ok': True,
            'site': 'osu',
            'colleges': college_count,
            'programs': program_count,
        })
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ─── Startup ──────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()
    from seed_data import seed
    seed()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=40015, debug=False)

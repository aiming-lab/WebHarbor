import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{BASE_DIR}/instance/y_combinator.db'
app.config['SECRET_KEY'] = 'webharbor-y_combinator-dev-key'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    batch = db.Column(db.String(50))
    description = db.Column(db.Text)
    full_description = db.Column(db.Text)
    website = db.Column(db.String(200))
    logo_url = db.Column(db.String(200))
    local_logo = db.Column(db.String(200))
    slug = db.Column(db.String(100), unique=True)
    founders = db.relationship('Founder', backref='company', lazy=True)

class Founder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(100))
    bio = db.Column(db.Text)
    image_url = db.Column(db.String(200))
    local_img = db.Column(db.String(200))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    companies = Company.query.limit(20).all()
    return render_template('index.html', companies=companies)

import re

STOPWORDS = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'and', 'or', 'is', 'are'}

def score_company(company, tokens):
    text = f"{company.name} {company.description or ''} {company.full_description or ''} {company.batch or ''}".lower()
    score = 0
    for token in tokens:
        if token in text:
            score += 1
            # Bonus for name match
            if token in company.name.lower():
                score += 2
    return score

@app.route('/companies')
def companies():
    q = request.args.get('q', '')
    if q:
        tokens = [t.lower() for t in re.findall(r'\w+', q) if t.lower() not in STOPWORDS]
        if not tokens:
            companies = Company.query.all()
        else:
            all_companies = Company.query.all()
            scored = []
            for c in all_companies:
                score = score_company(c, tokens)
                if score > 0:
                    scored.append((score, c))
            scored.sort(key=lambda x: x[0], reverse=True)
            companies = [c for score, c in scored]
    else:
        companies = Company.query.all()
    return render_template('companies.html', companies=companies, q=q)

@app.route('/companies/<slug>')
def company_detail(slug):
    company = Company.query.filter_by(slug=slug).first_or_404()
    return render_template('company_detail.html', company=company)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/people')
def people():
    return render_template('people.html')

# Bootstrap
with app.app_context():
    db.create_all()
    from seed_data import seed_database, seed_benchmark_users
    seed_database(db, Company, Founder)
    seed_benchmark_users(db, User, bcrypt)

if __name__ == '__main__':
    app.run(debug=True, port=40015)

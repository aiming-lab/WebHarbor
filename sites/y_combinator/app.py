import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
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
    industry = db.Column(db.String(100))
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
    slug = db.Column(db.String(100), unique=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)

class FAQ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)

class LibraryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), unique=True)
    content = db.Column(db.Text)
    url = db.Column(db.String(200))

class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), unique=True)
    date = db.Column(db.String(50))
    snippet = db.Column(db.Text)
    content = db.Column(db.Text)

class Launch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), unique=True)
    tagline = db.Column(db.Text)
    content = db.Column(db.Text)
    url = db.Column(db.String(200))

class LegalDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(200))

class StaticPage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    # Enriched data for the landing page
    in_the_room = [
        {"name": "Brian Chesky", "title": "Airbnb", "poster": "https://bookface-static.ycombinator.com/assets/ycdc/intheroomwith/brian-chesky-poster-compressed-85f52e5c8382ec6fede2dba32aaf31d46461415bbb46d2388e8c73191c7e2d86.jpg"},
        {"name": "Sam Altman", "title": "OpenAI", "poster": "https://bookface-static.ycombinator.com/assets/ycdc/intheroomwith/sam-altman-poster-compressed-623d3d19dd642d772a4d6649296a76bfb18f442cc6ecca47f792b55a4463ad40.jpg"},
        {"name": "Greg Brockman", "title": "OpenAI", "poster": "https://bookface-static.ycombinator.com/assets/ycdc/intheroomwith/greg-brockman-poster-compressed-745fb7cb848fa95ff24bad394777e3f8c3c6fbf079a5d632e3e478ef262518f1.jpg"},
        {"name": "Michael Truell", "title": "Cursor", "poster": "https://bookface-static.ycombinator.com/assets/ycdc/intheroomwith/michael-truell-poster-compressed-b0a1598fd43a294adf4789b523b55512f20d348b26905185c9d0bb59a871e8d5.jpg"},
        {"name": "Paul Graham", "title": "Y Combinator", "poster": "https://bookface-static.ycombinator.com/assets/ycdc/intheroomwith/paul-graham-poster-compressed-6a6dc8e7ec9e11953fdde71fb7df82c48c31e101a97366a75f8b05ee2068b3e6.jpg"},
        {"name": "Guillermo Rauch", "title": "Vercel", "poster": "https://bookface-static.ycombinator.com/assets/ycdc/intheroomwith/guillermo-rauch-poster-compressed-33b83d0ead08ebac6d260961c470022733ffeb636f3fc2465dc08aca72b96f95.jpg"},
        {"name": "Dylan Field", "title": "Figma", "poster": "https://bookface-static.ycombinator.com/assets/ycdc/intheroomwith/dylan-field-poster-compressed-81895505876d8cc7e6104a541294bd90d0efd75bd538ae552880738174b70a8e.jpg"},
        {"name": "Emmett Shear", "title": "Twitch", "poster": "https://bookface-static.ycombinator.com/assets/ycdc/intheroomwith/emmett-shear-poster-compressed-d8d230bf291fe6d24d63c779dbb9a082273e7746ca75db5db2d80e5ff031342c.jpg"},
        {"name": "Tony Xu", "title": "DoorDash", "poster": "https://bookface-static.ycombinator.com/assets/ycdc/intheroomwith/tony-xu-poster-compressed-6bbd3eacb27c1e86950d30ee84d2b56a473e1f57a3782a92b97fa3dd360eb895.jpg"}
    ]
    
    startup_news = [
        {"title": "Announcing the YC AI Stack", "url": "https://www.ycombinator.com/blog/the-yc-ai-student-starter-pack"},
        {"title": "Emergent Raises $70M Series B at $300M Valuation", "url": "https://techcrunch.com/2026/01/20/indian-vibe-coding-startup-emergent-raises-70m-at-300m-valuation-from-softbank-khosla-ventures/"},
        {"title": "Govdash Raises $30M Series B", "url": "https://www.govdash.com/blog/govdash-raises-30m-in-new-funding"},
        {"title": "Fleetzero Raises $43M Series A for Battery-Powered Cargo Ships", "url": "https://www.wsj.com/business/energy-oil/talk-about-range-anxietycould-giant-cargo-ships-run-on-batteries-7d258427"},
        {"title": "Deepgram Raises $130M Series C", "url": "https://deepgram.com/learn/scott-announcement-deepgram-raises-series-c"}
    ]
    
    pg_essays = [
        {"title": "Default Alive or Default Dead", "url": "https://www.paulgraham.com/aord.html"},
        {"title": "Do Things that Don’t Scale", "url": "https://www.paulgraham.com/ds.html"},
        {"title": "Be Relentlessly Resourceful", "url": "https://www.paulgraham.com/relres.html"},
        {"title": "How to Get Startup Ideas", "url": "http://www.paulgraham.com/startupideas.html"},
        {"title": "Startup = Growth", "url": "http://www.paulgraham.com/growth.html"}
    ]
    
    about_quotes = [
        {"text": "YC compresses months of growth into weeks.", "author": "Aman Mishra", "company": "Unsiloed AI", "batch": "F25", "img": "https://bookface-static.ycombinator.com/assets/ycdc/about/aman-mishra-compressed-f86a1a0caaa317ed5e8770981a0ebb253846a406837c88fe89137ed0c85a7a47.jpg"},
        {"text": "The sense of urgency is so infectious among founders that it becomes the most productive period in most people’s lives.", "author": "Adith Reddi", "company": "Riff", "batch": "S25", "img": "https://bookface-static.ycombinator.com/assets/ycdc/about/adith-reddi-compressed-1c81fcfa8ef9cf7a23b35d0c34648d1b79ab613b0fdced3ea015d23ffb984cdc.jpg"},
        {"text": "It’s a community of founders that you can’t find anywhere else.", "author": "Bishesh Khadka", "company": "Imprezia", "batch": "S25", "img": "https://bookface-static.ycombinator.com/assets/ycdc/about/bishesh-khadka-compressed-76f09ec549bbfdb8c7fa25d8ac0e943f2e3bc593cb5cc43af5b7fc5b8ad3ee9c.jpg"},
        {"text": "It feels like having the entire world at your back—from Partners to batchmates.", "author": "Justin Lee", "company": "Slope", "batch": "W22", "img": "https://bookface-static.ycombinator.com/assets/ycdc/about/justin-lee-compressed-8a1494883907779d71c48e89137ed0c85a7a47.jpg"}
    ]
    
    # Randomly select a few companies for the logo strip
    logos = Company.query.filter(Company.logo_url != None).limit(20).all()
    
    return render_template('index.html', 
                          in_the_room=in_the_room, 
                          startup_news=startup_news, 
                          pg_essays=pg_essays, 
                          about_quotes=about_quotes,
                          logos=logos)

import re
STOPWORDS = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'and', 'or', 'is', 'are'}

def score_company(company, tokens):
    founder_names = " ".join([f.name for f in company.founders])
    text = f"{company.name} {company.description or ''} {company.full_description or ''} {company.batch or ''} {founder_names}".lower()
    score = 0
    for token in tokens:
        if token in text:
            score += 1
            if token in company.name.lower():
                score += 2
            if token in founder_names.lower():
                score += 1
    return score

@app.route('/companies')
def companies():
    q = request.args.get('q', '')
    batch = request.args.get('batch', '')
    industry = request.args.get('industry', '')
    
    query = Company.query
    
    if batch:
        query = query.filter_by(batch=batch)
    if industry:
        query = query.filter(Company.industry.ilike(f'%{industry}%'))
        
    if q:
        tokens = [t.lower() for t in re.findall(r'\w+', q) if t.lower() not in STOPWORDS]
        if not tokens:
            companies = query.all()
        else:
            all_companies = query.all()
            scored = []
            for c in all_companies:
                score = score_company(c, tokens)
                if score > 0:
                    scored.append((score, c))
            scored.sort(key=lambda x: x[0], reverse=True)
            companies = [c for score, c in scored]
    else:
        companies = query.all()
        
    # Get distinct batches and industries for filters
    all_batches = sorted(list(set([c.batch for c in Company.query.all() if c.batch])), reverse=True)
    all_industries = sorted(list(set([c.industry for c in Company.query.all() if c.industry])))
    
    return render_template('companies.html', companies=companies, q=q, current_batch=batch, current_industry=industry, all_batches=all_batches, all_industries=all_industries)

@app.route('/companies/<slug>')
def company_detail(slug):
    company = Company.query.filter_by(slug=slug).first_or_404()
    return render_template('company_detail.html', company=company)

@app.route('/founders')
def founders():
    all_founders = Founder.query.all()
    return render_template('founders.html', founders=all_founders)

@app.route('/founders/<slug>')
def founder_detail(slug):
    founder = Founder.query.filter_by(slug=slug).first_or_404()
    return render_template('founder_detail.html', founder=founder)

@app.route('/library')
def library():
    items = LibraryItem.query.all()
    return render_template('library.html', items=items)

@app.route('/library/<slug>')
def library_detail(slug):
    item = LibraryItem.query.filter_by(slug=slug).first_or_404()
    return render_template('detail_page.html', item=item, type='Library')

@app.route('/blog')
def blog():
    posts = BlogPost.query.all()
    return render_template('blog.html', posts=posts)

@app.route('/blog/<slug>')
def blog_detail(slug):
    item = BlogPost.query.filter_by(slug=slug).first_or_404()
    return render_template('detail_page.html', item=item, type='Blog')

@app.route('/launches')
def launches():
    items = Launch.query.all()
    return render_template('launches.html', launches=items)

@app.route('/launches/<slug>')
def launch_detail(slug):
    item = Launch.query.filter_by(slug=slug).first_or_404()
    return render_template('detail_page.html', item=item, type='Launch')

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

@app.route('/faq')
def faq():
    faqs = FAQ.query.all()
    return render_template('faq.html', faqs=faqs)

@app.route('/apply')
def apply():
    return render_template('apply.html')

@app.route('/people')
def people():
    # YC Staff are those who don't have a company_id OR have a specific bio/title indicating YC role
    staff = Founder.query.filter((Founder.company_id == None) | (Founder.title.ilike('%Partner%')) | (Founder.title.ilike('%CEO%')) | (Founder.title.ilike('%YC%'))).all()
    return render_template('people.html', founders=staff)

@app.route('/investors')
def investors():
    page = StaticPage.query.filter_by(slug='investors').first()
    return render_template('investors.html', page=page)

@app.route('/rfs')
def rfs():
    page = StaticPage.query.filter_by(slug='rfs').first()
    return render_template('rfs.html', page=page)

@app.route('/documents')
def documents():
    docs = LegalDocument.query.all()
    return render_template('documents.html', docs=docs)

@app.route('/<page_slug>')
def static_page(page_slug):
    page = StaticPage.query.filter_by(slug=page_slug).first()
    if page:
        return render_template('static_page.html', page=page)
    if page_slug == 'hn':
        return render_template('hn_mock.html')
    return redirect(url_for('index'))

# Bootstrap
with app.app_context():
    db.create_all()
    from seed_data import seed_database, seed_benchmark_users, seed_extra_sections, seed_deep_sections, seed_ultra_sections
    seed_database(db, Company, Founder)
    seed_benchmark_users(db, User, bcrypt)
    seed_extra_sections(db, FAQ, LibraryItem, BlogPost)
    seed_deep_sections(db, Founder, Launch, LegalDocument)
    seed_ultra_sections(db, StaticPage)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=40016)

"""Deterministic Adopt-a-Pet mirror with search, accounts, favorites and applications."""
import os,re,secrets
from functools import wraps
from urllib.parse import quote_plus,urlsplit
from flask import Flask,abort,flash,redirect,render_template,request,session,url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.security import check_password_hash,generate_password_hash
BASE_DIR=os.path.dirname(os.path.abspath(__file__)); app=Flask(__name__,instance_path=os.path.join(BASE_DIR,'instance'))
app.config.update(SECRET_KEY=os.environ.get('ADOPT_A_PET_SECRET_KEY') or secrets.token_hex(32),SQLALCHEMY_DATABASE_URI='sqlite:///adopt_a_pet.db',SQLALCHEMY_TRACK_MODIFICATIONS=False,MAX_CONTENT_LENGTH=256*1024,WTF_CSRF_TIME_LIMIT=None); db=SQLAlchemy(app); csrf=CSRFProtect(app)
@event.listens_for(Engine,'connect')
def _sqlite_foreign_keys(connection,_record):
 cursor=connection.cursor(); cursor.execute('PRAGMA foreign_keys=ON'); cursor.close()
class User(db.Model):
 id=db.Column(db.Integer,primary_key=True); email=db.Column(db.String(120),unique=True,nullable=False); name=db.Column(db.String(80),nullable=False); password_hash=db.Column(db.String(255),nullable=False)
class Shelter(db.Model):
 id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120),unique=True,nullable=False); city=db.Column(db.String(60),nullable=False); state=db.Column(db.String(2),nullable=False); phone=db.Column(db.String(20),nullable=False); email=db.Column(db.String(120),nullable=False)
class Pet(db.Model):
 id=db.Column(db.Integer,primary_key=True); slug=db.Column(db.String(120),unique=True,nullable=False); name=db.Column(db.String(60),nullable=False); species=db.Column(db.String(20),nullable=False); breed=db.Column(db.String(100),nullable=False); secondary_breed=db.Column(db.String(100)); sex=db.Column(db.String(10),nullable=False); age_group=db.Column(db.String(20),nullable=False); age_months=db.Column(db.Integer,nullable=False); size=db.Column(db.String(20),nullable=False); color=db.Column(db.String(40),nullable=False); city=db.Column(db.String(60),nullable=False); state=db.Column(db.String(2),nullable=False); postal=db.Column(db.String(10),nullable=False); fee=db.Column(db.Integer,nullable=False); image=db.Column(db.String(100),nullable=False); description=db.Column(db.Text,nullable=False); house_trained=db.Column(db.Boolean,nullable=False); good_dogs=db.Column(db.Boolean,nullable=False); good_cats=db.Column(db.Boolean,nullable=False); good_children=db.Column(db.Boolean,nullable=False); shelter_id=db.Column(db.Integer,db.ForeignKey('shelter.id'),nullable=False); shelter=db.relationship(Shelter,backref='pets')
class Favorite(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); pet_id=db.Column(db.Integer,db.ForeignKey('pet.id'),nullable=False); __table_args__=(db.UniqueConstraint('user_id','pet_id'),)
class Application(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); pet_id=db.Column(db.Integer,db.ForeignKey('pet.id'),nullable=False); housing=db.Column(db.String(30),nullable=False); experience=db.Column(db.Text,nullable=False); phone=db.Column(db.String(20),nullable=False); status=db.Column(db.String(20),default='Submitted',nullable=False); __table_args__=(db.UniqueConstraint('user_id','pet_id'),)
class PetAlert(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); species=db.Column(db.String(20),nullable=False); breed=db.Column(db.String(80),nullable=False); postal=db.Column(db.String(10),nullable=False); radius=db.Column(db.Integer,nullable=False)
HOUSING_OPTIONS=('Own home','Rent with permission','Other')
SPECIES_OPTIONS=('Dog','Cat')
RADIUS_OPTIONS=(10,25,50,100)
USERS=[('alice.j@test.com','Alice Johnson'),('bob.smith@test.com','Bob Smith'),('carol.w@test.com','Carol Williams'),('david.b@test.com','David Brown')]
SHELTERS=[('Desert Paws Rescue','Phoenix','AZ','602-555-0141','hello@desertpaws.test'),('Happy Tails Alliance','Scottsdale','AZ','480-555-0128','adopt@happytails.test'),('City Friends Shelter','New York','NY','212-555-0164','pets@cityfriends.test'),('Pacific Animal Haven','Seattle','WA','206-555-0119','info@pacifichaven.test'),('Lone Star Companions','Austin','TX','512-555-0182','team@lonestar.test'),('Sunshine Pet Rescue','Miami','FL','305-555-0136','adopt@sunshine.test')]
PETS=[
('sirius','Sirius','Dog','Chihuahua','Terrier','Male','Senior',108,'Small','Tan','Scottsdale','AZ','85251',175,'pet-01.avif',True,True,True,False),('waymo','Waymo','Dog','American Pit Bull Terrier','Mixed Breed','Male','Adult',24,'Large','Gray','Phoenix','AZ','85004',225,'pet-02.avif',True,True,False,True),('casper','Casper','Cat','Colorpoint Shorthair',None,'Male','Adult',48,'Medium','Cream','Mesa','AZ','85201',125,'pet-03.avif',True,False,True,True),('neo','Neo','Cat','Domestic Shorthair',None,'Male','Kitten',7,'Small','Black','Scottsdale','AZ','85250',110,'pet-04.avif',True,True,True,True),('amba','Amba','Cat','Domestic Mediumhair',None,'Female','Kitten',5,'Small','Tabby','Arizona City','AZ','85123',95,'pet-05.avif',True,True,True,True),('cinders','Cinders','Cat','Domestic Shorthair',None,'Female','Adult',85,'Medium','Tortoiseshell','Sedona','AZ','86336',120,'pet-06.avif',True,False,True,False),('arno','Arno','Dog','German Shepherd Dog','Mixed Breed','Male','Adult',43,'Large','Black and Tan','Casa Grande','AZ','85122',200,'pet-07.avif',True,True,False,True),('batman','Batman','Dog','Chihuahua','Yorkshire Terrier','Male','Adult',36,'Small','Black','Tucson','AZ','85701',165,'pet-08.avif',True,True,True,False),('horus','Horus','Dog','Pointer','Labrador Retriever','Male','Young',16,'Large','White and Black','Phoenix','AZ','85006',210,'pet-09.avif',True,True,False,True),
('luna','Luna','Dog','Beagle',None,'Female','Young',14,'Medium','Tricolor','New York','NY','10011',250,'article-23c4acda83eaf8ae.avif',True,True,True,True),('milo','Milo','Cat','Maine Coon',None,'Male','Adult',38,'Large','Orange','New York','NY','10003',150,'article-67613dbc6f5d35e7.avif',True,False,True,True),('daisy','Daisy','Dog','Golden Retriever',None,'Female','Adult',30,'Large','Golden','Seattle','WA','98109',275,'article-7df82ed295140b9e.avif',True,True,True,True),('pepper','Pepper','Cat','Domestic Shorthair',None,'Female','Young',13,'Small','Black and White','Seattle','WA','98101',130,'article-d481e062963ebb2d.avif',True,True,True,False),('archie','Archie','Dog','Australian Shepherd',None,'Male','Young',18,'Medium','Merle','Austin','TX','78704',240,'article-d2d957768d445381.avif',True,True,False,True),('ruby','Ruby','Dog','Boxer','Mixed Breed','Female','Adult',42,'Large','Fawn','Austin','TX','78702',215,'article-87c08b41dcca022d.avif',True,True,False,False),('olive','Olive','Cat','Siamese',None,'Female','Adult',27,'Medium','Seal Point','Miami','FL','33130',145,'rehome.avif',True,False,True,True),('teddy','Teddy','Dog','Poodle','Mixed Breed','Male','Senior',96,'Small','White','Miami','FL','33133',185,'rehome-mobile.avif',True,True,True,True),('winston','Winston','Dog','Chihuahua','Mixed Breed','Male','Adult',60,'Small','Tan','Tempe','AZ','85281',230,'pet-10.avif',True,True,True,False),('yuki','Yuki','Dog','Chihuahua','Mixed Breed','Female','Senior',120,'Small','Cream','Glendale','AZ','85301',205,'pet-11.avif',True,False,True,True),('zorro','Zorro','Dog','Chihuahua','Terrier','Male','Adult',72,'Small','Black','Prescott','AZ','86301',220,'pet-12.avif',True,True,False,False)]
def seed_benchmark_users():
 if User.query.first(): return
 for email,name in USERS: db.session.add(User(email=email,name=name,password_hash=generate_password_hash('TestPass123!')))
 db.session.commit()
def seed_database():
 if Pet.query.first(): return
 for row in SHELTERS: db.session.add(Shelter(name=row[0],city=row[1],state=row[2],phone=row[3],email=row[4]))
 db.session.flush(); shelters=Shelter.query.all()
 for i,p in enumerate(PETS):
  shelter_index=(i%2 if p[11]=='AZ' else {'NY':2,'WA':3,'TX':4,'FL':5}[p[11]])
  db.session.add(Pet(slug=p[0],name=p[1],species=p[2],breed=p[3],secondary_breed=p[4],sex=p[5],age_group=p[6],age_months=p[7],size=p[8],color=p[9],city=p[10],state=p[11],postal=p[12],fee=p[13],image=p[14],description=f'{p[1]} is an affectionate {p[6].lower()} {p[2].lower()} who enjoys companionship, gentle play, and a comfortable place to relax.',house_trained=p[15],good_dogs=p[16],good_cats=p[17],good_children=p[18],shelter_id=shelters[shelter_index].id))
 db.session.commit()
def seed_user_state():
 if Favorite.query.first() or Application.query.first() or PetAlert.query.first(): return
 alice=User.query.filter_by(email='alice.j@test.com').first(); db.session.add(Favorite(user_id=alice.id,pet_id=Pet.query.filter_by(slug='luna').first().id)); db.session.commit()
with app.app_context(): os.makedirs(app.instance_path,exist_ok=True);db.create_all();seed_benchmark_users();seed_database();seed_user_state()
def user():
 raw=session.get('user_id')
 if isinstance(raw,bool) or not isinstance(raw,int): return None   # a forged cookie must not reach the ORM
 return db.session.get(User,raw)
@app.context_processor
def ctx(): return {'current_user':user()}
def required(fn):
 @wraps(fn)
 def w(*a,**k):
  if not user(): flash('Log in to continue.');return redirect(url_for('login',next=request.path))
  return fn(*a,**k)
 return w
def score(q,text):
 terms=set(re.findall(r'[a-z0-9]+',q.lower()));tokens=set(re.findall(r'[a-z0-9]+',text.lower()));return len(terms&tokens)
def bounded_text(value,field,maximum,required=True,minimum=0):
 """Trimmed form value plus an error string; SQLite does not enforce VARCHAR widths, so the app must."""
 text=(value or '').strip()
 if required and not text: return text,f'Enter your {field}.'
 if len(text)>maximum: return text,f'{field.capitalize()} must be {maximum} characters or fewer.'
 if len(text)<minimum and text: return text,f'{field.capitalize()} must be at least {minimum} characters.'
 if any(ord(c)<32 for c in text): return text,f'{field.capitalize()} contains unsupported control characters.'
 return text,None
def one_of(value,field,options):
 text=(value or '').strip()
 return text,(None if text in options else f'Choose a valid {field}.')
def bounded_int(value,field,options):
 text=(value or '').strip()
 if not text.isdigit() or int(text) not in options: return 0,f'Choose a valid {field}.'
 return int(text),None
def internal_path(target):
 """Only same-site relative paths may be redirect targets (no scheme, host or protocol-relative //)."""
 if not target: return None
 parts=urlsplit(target)
 if parts.scheme or parts.netloc or not target.startswith('/') or target.startswith('//'): return None
 return target
def safe_referrer():
 """The Referer header is attacker-controlled; only bounce back to this host."""
 parts=urlsplit(request.referrer or '')
 if parts.netloc and parts.netloc!=request.host: return None
 return internal_path(parts.path+(('?'+parts.query) if parts.query else ''))
@app.route('/')
def index(): return render_template('index.html',pets=Pet.query.order_by(Pet.id).limit(6).all())
@app.route('/search')
def search():
 q=request.args.get('location','').strip(); lookup={'arizona':'AZ','new york':'New York NY','washington':'WA','texas':'TX','florida':'FL'}.get(q.lower(),q); species=request.args.get('species',''); breed=request.args.get('breed',''); sex=request.args.get('sex',''); age=request.args.get('age',''); size=request.args.get('size',''); page=max(1,request.args.get('page',1,type=int)); ranked=[]
 for p in Pet.query.all():
  s=score(lookup,f'{p.city} {p.state} {p.postal}') if lookup else 1
  if s and (not species or p.species==species) and (not breed or breed.lower() in (p.breed+' '+(p.secondary_breed or '')).lower()) and (not sex or p.sex==sex) and (not age or p.age_group==age) and (not size or p.size==size): ranked.append((s,p.name,p))
 ranked=[x[2] for x in sorted(ranked,key=lambda x:(-x[0],x[1]))]
 base_qs='&'.join(f'{quote_plus(k)}={quote_plus(v)}' for k,v in request.args.items(multi=True) if k!='page')  # never re-emit page: the first value wins, so a duplicate freezes pagination
 return render_template('search.html',pets=ranked[(page-1)*6:page*6],total=len(ranked),page=page,q=q,filters=request.args,base_qs=base_qs,per_page=6)
@app.route('/pet/<slug>')
def pet(slug):
 p=Pet.query.filter_by(slug=slug).first_or_404();fav=bool(user() and Favorite.query.filter_by(user_id=user().id,pet_id=p.id).first());return render_template('pet.html',pet=p,favorite=fav)
@app.route('/favorite/<slug>',methods=['POST'])
@required
def favorite(slug):
 p=Pet.query.filter_by(slug=slug).first_or_404();f=Favorite.query.filter_by(user_id=user().id,pet_id=p.id).first()
 if f: db.session.delete(f);flash(f'Removed {p.name} from favorites.')
 else: db.session.add(Favorite(user_id=user().id,pet_id=p.id));flash(f'{p.name} was added to favorites.')
 db.session.commit();return redirect(safe_referrer() or url_for('pet',slug=slug))
@app.route('/apply/<slug>',methods=['GET','POST'])
@required
def apply(slug):
 p=Pet.query.filter_by(slug=slug).first_or_404()
 if request.method=='POST':
  phone,e1=bounded_text(request.form.get('phone'),'phone number',20)
  housing,e2=one_of(request.form.get('housing'),'housing option',HOUSING_OPTIONS)
  experience,e3=bounded_text(request.form.get('experience'),'pet experience',2000,minimum=15)
  error=e1 or e2 or e3
  if error: return render_template('apply.html',pet=p,error=error),400
  old=Application.query.filter_by(user_id=user().id,pet_id=p.id).first()
  if old: flash('You already applied for this pet.')
  else: db.session.add(Application(user_id=user().id,pet_id=p.id,housing=housing,experience=experience,phone=phone));db.session.commit();return render_template('application_done.html',pet=p)
 return render_template('apply.html',pet=p)
@app.route('/alerts',methods=['GET','POST'])
@required
def alerts():
 if request.method=='POST':
  species,e1=one_of(request.form.get('species'),'pet type',SPECIES_OPTIONS)
  breed,e2=bounded_text(request.form.get('breed'),'breed',80,required=False)
  postal,e3=bounded_text(request.form.get('postal'),'postal code',10)
  radius,e4=bounded_int(request.form.get('radius'),'distance',RADIUS_OPTIONS)
  if not e3 and not re.fullmatch(r'\d{5}',postal): e3='Enter a five-digit postal code.'
  error=e1 or e2 or e3 or e4
  if error: return render_template('alerts.html',error=error),400
  db.session.add(PetAlert(user_id=user().id,species=species,breed=breed,postal=postal,radius=radius));db.session.commit();flash('New Pet Alert created.');return redirect(url_for('account'))
 return render_template('alerts.html')
@app.route('/account')
@required
def account():
 favs=db.session.query(Pet).join(Favorite,Favorite.pet_id==Pet.id).filter(Favorite.user_id==user().id).all();apps=db.session.query(Application,Pet).join(Pet,Pet.id==Application.pet_id).filter(Application.user_id==user().id).all();return render_template('account.html',favorites=favs,applications=apps,alerts=PetAlert.query.filter_by(user_id=user().id).all())
@app.route('/shelters')
def shelters():
 q=request.args.get('q','');items=[s for s in Shelter.query.order_by(Shelter.state,Shelter.city,Shelter.name).all() if not q or score(q,f'{s.name} {s.city} {s.state}')];return render_template('shelters.html',shelters=items,q=q)
@app.route('/shelter/<int:id>')
def shelter(id): return render_template('shelter.html',shelter=db.session.get(Shelter,id) or abort(404))
@app.route('/breeds')
def breeds(): return render_template('breeds.html',dogs=sorted({p.breed for p in Pet.query.filter_by(species='Dog')}),cats=sorted({p.breed for p in Pet.query.filter_by(species='Cat')}))
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  u=User.query.filter_by(email=request.form.get('email','').lower().strip()).first()
  if u and check_password_hash(u.password_hash,request.form.get('password','')):session['user_id']=u.id;flash('Welcome back!');return redirect(internal_path(request.args.get('next')) or url_for('account'))
  flash('Email or password is incorrect.')
 return render_template('login.html')
@app.route('/register',methods=['GET','POST'])
def register():
 if request.method=='POST':
  email,e1=bounded_text(request.form.get('email','').lower(),'email address',120)
  name,e2=bounded_text(request.form.get('name'),'name',80)
  password=request.form.get('password','')
  # deliberately not email_validator: it rejects RFC 6761 special-use TLDs, and this offline
  # mirror's own benchmark accounts are @test.com / @example.test addresses.
  if not e1 and not re.fullmatch(r"[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+",email): e1='Enter a valid email address.'
  error=e1 or e2
  if error: return render_template('register.html',error=error),400
  if User.query.filter_by(email=email).first():flash('An account already exists for that email.')
  elif len(password)<8:flash('Password must be at least 8 characters.')
  elif len(password)>256:flash('Password must be 256 characters or fewer.')
  else:u=User(email=email,name=name,password_hash=generate_password_hash(password));db.session.add(u);db.session.commit();session['user_id']=u.id;return redirect(url_for('account'))
 return render_template('register.html')
@app.route('/logout',methods=['POST'])
def logout():session.clear();return redirect(url_for('index'))
@app.route('/blog')
def blog(): return render_template('blog.html')
@app.route('/_health')
def health():return {'ok':True,'site':'adopt_a_pet'}
@app.errorhandler(400)
def bad_request(_e):return render_template('400.html'),400
@app.errorhandler(404)
def not_found(_e):return render_template('404.html'),404
@app.errorhandler(413)
def too_large(_e):return render_template('400.html'),413
@app.errorhandler(500)
def server_error(_e):db.session.rollback();return render_template('500.html'),500
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))

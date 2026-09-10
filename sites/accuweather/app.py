"""Deterministic, interaction-complete AccuWeather mirror."""
import os, re
from datetime import datetime
from functools import wraps
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
app=Flask(__name__,instance_path=os.path.join(BASE_DIR,"instance"))
app.config.update(SECRET_KEY="accuweather-local-benchmark",SQLALCHEMY_DATABASE_URI="sqlite:///accuweather.db",SQLALCHEMY_TRACK_MODIFICATIONS=False)
db=SQLAlchemy(app)

class User(db.Model):
 id=db.Column(db.Integer,primary_key=True); email=db.Column(db.String(120),unique=True,nullable=False); name=db.Column(db.String(80),nullable=False); password_hash=db.Column(db.String(255),nullable=False); unit=db.Column(db.String(1),default="F",nullable=False)
class Location(db.Model):
 id=db.Column(db.Integer,primary_key=True); slug=db.Column(db.String(100),unique=True,nullable=False); city=db.Column(db.String(80),nullable=False); region=db.Column(db.String(80),nullable=False); country=db.Column(db.String(80),nullable=False); postal=db.Column(db.String(20),nullable=False); temp=db.Column(db.Integer,nullable=False); realfeel=db.Column(db.Integer,nullable=False); condition=db.Column(db.String(80),nullable=False); icon=db.Column(db.String(2),nullable=False); humidity=db.Column(db.Integer,nullable=False); wind=db.Column(db.Integer,nullable=False); visibility=db.Column(db.Integer,nullable=False); pressure=db.Column(db.Float,nullable=False); uv=db.Column(db.Integer,nullable=False); air_quality=db.Column(db.Integer,nullable=False)
class Forecast(db.Model):
 id=db.Column(db.Integer,primary_key=True); location_id=db.Column(db.Integer,db.ForeignKey("location.id"),nullable=False); day_index=db.Column(db.Integer,nullable=False); label=db.Column(db.String(30),nullable=False); high=db.Column(db.Integer,nullable=False); low=db.Column(db.Integer,nullable=False); condition=db.Column(db.String(80),nullable=False); icon=db.Column(db.String(2),nullable=False); precip=db.Column(db.Integer,nullable=False); location=db.relationship(Location,backref="forecasts")
class Hourly(db.Model):
 id=db.Column(db.Integer,primary_key=True); location_id=db.Column(db.Integer,db.ForeignKey("location.id"),nullable=False); hour_index=db.Column(db.Integer,nullable=False); label=db.Column(db.String(20),nullable=False); temp=db.Column(db.Integer,nullable=False); condition=db.Column(db.String(80),nullable=False); icon=db.Column(db.String(2),nullable=False); precip=db.Column(db.Integer,nullable=False); location=db.relationship(Location,backref="hourly")
class SavedLocation(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False); location_id=db.Column(db.Integer,db.ForeignKey("location.id"),nullable=False); __table_args__=(db.UniqueConstraint("user_id","location_id"),)
class Alert(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False); location_id=db.Column(db.Integer,db.ForeignKey("location.id"),nullable=False); alert_type=db.Column(db.String(30),nullable=False); enabled=db.Column(db.Boolean,default=True,nullable=False); __table_args__=(db.UniqueConstraint("user_id","location_id","alert_type"),)

USERS=[("alice.j@test.com","Alice Johnson"),("bob.smith@test.com","Bob Smith"),("carol.w@test.com","Carol Williams"),("david.b@test.com","David Brown")]
LOCATIONS=[
("new-york-ny","New York","New York","United States","10007",79,82,"Partly sunny","03",61,9,10,29.92,5,42),("phoenix-az","Phoenix","Arizona","United States","85001",104,115,"Sunny","01",18,7,12,29.75,10,58),("seattle-wa","Seattle","Washington","United States","98101",66,65,"Cloudy","07",73,6,9,30.08,3,24),("miami-fl","Miami","Florida","United States","33101",88,99,"Mostly cloudy","06",76,12,8,29.88,7,36),("chicago-il","Chicago","Illinois","United States","60601",72,71,"Showers","12",70,14,7,29.86,2,31),("boston-ma","Boston","Massachusetts","United States","02108",75,76,"Mostly sunny","02",55,11,10,30.01,6,28),("austin-tx","Austin","Texas","United States","78701",96,103,"Sunny","01",38,10,11,29.81,9,49),("denver-co","Denver","Colorado","United States","80202",84,82,"Partly sunny","03",27,13,15,30.04,8,45),("portland-or","Portland","Oregon","United States","97205",69,68,"Cloudy","07",67,5,10,30.11,3,22),("portland-me","Portland","Maine","United States","04101",70,69,"Mostly cloudy","06",64,8,10,30.02,4,20),("springfield-il","Springfield","Illinois","United States","62701",76,77,"Partly sunny","03",59,10,10,29.91,5,33),("springfield-ma","Springfield","Massachusetts","United States","01103",73,73,"Showers","12",69,7,8,29.98,3,25),("springfield-mo","Springfield","Missouri","United States","65806",81,84,"Mostly sunny","02",53,9,11,29.89,6,39),("san-francisco-ca","San Francisco","California","United States","94102",65,64,"Cloudy","07",75,12,10,30.05,3,18),("los-angeles-ca","Los Angeles","California","United States","90012",78,79,"Mostly sunny","02",49,6,12,29.96,7,41),("atlanta-ga","Atlanta","Georgia","United States","30303",86,91,"Partly sunny","03",58,8,9,29.94,6,46),("nashville-tn","Nashville","Tennessee","United States","37219",84,88,"Mostly cloudy","06",61,7,10,29.93,5,38),("new-orleans-la","New Orleans","Louisiana","United States","70112",89,100,"Showers","12",75,9,7,29.87,4,44),("london-gb","London","England","United Kingdom","SW1A",63,62,"Cloudy","07",72,10,8,30.10,2,21),("toronto-ca","Toronto","Ontario","Canada","M5H",70,69,"Partly sunny","03",62,11,10,29.99,4,29)]

def seed_benchmark_users():
 if User.query.first(): return
 for email,name in USERS: db.session.add(User(email=email,name=name,password_hash=generate_password_hash("TestPass123!")))
 db.session.commit()
def seed_database():
 if Location.query.first(): return
 for row in LOCATIONS:
  loc=Location(slug=row[0],city=row[1],region=row[2],country=row[3],postal=row[4],temp=row[5],realfeel=row[6],condition=row[7],icon=row[8],humidity=row[9],wind=row[10],visibility=row[11],pressure=row[12],uv=row[13],air_quality=row[14]); db.session.add(loc); db.session.flush()
  icons=[loc.icon,"02","03","06","12","07","01"]; conditions=[loc.condition,"Mostly sunny","Partly sunny","Mostly cloudy","Showers","Cloudy","Sunny"]
  for i,label in enumerate(["Today","Thu","Fri","Sat","Sun","Mon","Tue"]): db.session.add(Forecast(location_id=loc.id,day_index=i,label=label,high=loc.temp+(i%3)-2,low=loc.temp-12-(i%4),condition=conditions[i],icon=icons[i],precip=(i*17+loc.id*3)%71))
  for i in range(12):
   hour=(12+i)%24; label="Now" if i==0 else datetime.strptime(str(hour),"%H").strftime("%-I %p"); db.session.add(Hourly(location_id=loc.id,hour_index=i,label=label,temp=loc.temp+(3-abs(i-4)),condition=conditions[i%7],icon=icons[i%7],precip=(i*11+loc.id)%66))
 db.session.commit()
def seed_preferences():
 if SavedLocation.query.first() or Alert.query.first(): return
 alice=User.query.filter_by(email="alice.j@test.com").first()
 for slug in ("new-york-ny","boston-ma"): db.session.add(SavedLocation(user_id=alice.id,location_id=Location.query.filter_by(slug=slug).first().id))
 db.session.commit()
with app.app_context():
 os.makedirs(app.instance_path,exist_ok=True); db.create_all(); seed_benchmark_users(); seed_database(); seed_preferences()

def current_user(): return db.session.get(User,session.get("user_id")) if session.get("user_id") else None
@app.context_processor
def shared(): return {"current_user":current_user(),"unit":session.get("unit",current_user().unit if current_user() else "F")}
def login_required(fn):
 @wraps(fn)
 def wrapped(*a,**k):
  if not current_user(): flash("Please sign in to continue."); return redirect(url_for("login",next=request.path))
  return fn(*a,**k)
 return wrapped
def display_temp(value): return round((value-32)*5/9) if session.get("unit",current_user().unit if current_user() else "F")=="C" else value
app.jinja_env.globals.update(display_temp=display_temp)
def scored_locations(query):
 terms=set(re.findall(r"[a-z0-9]+",query.lower())); ranked=[]
 for loc in Location.query.all():
  fields=[loc.city,loc.region,loc.country,loc.postal]; score=sum(len(terms&set(re.findall(r"[a-z0-9]+",f.lower())))*w for f,w in zip(fields,[5,3,1,6]))
  if score: ranked.append((score,loc.city,loc.region,loc))
 return [x[3] for x in sorted(ranked,key=lambda x:(-x[0],x[1],x[2]))]

@app.route("/")
def index(): return render_template("index.html",location=Location.query.filter_by(slug="new-york-ny").first(),cities=Location.query.limit(8).all())
@app.route("/search")
def search():
 q=request.args.get("q","").strip(); return render_template("search.html",query=q,locations=scored_locations(q) if q else [])
@app.route("/weather/<slug>")
def weather(slug):
 loc=Location.query.filter_by(slug=slug).first_or_404(); saved=bool(current_user() and SavedLocation.query.filter_by(user_id=current_user().id,location_id=loc.id).first()); return render_template("weather.html",location=loc,saved=saved)
@app.route("/hourly/<slug>")
def hourly(slug): return render_template("hourly.html",location=Location.query.filter_by(slug=slug).first_or_404())
@app.route("/daily/<slug>")
def daily(slug): return render_template("daily.html",location=Location.query.filter_by(slug=slug).first_or_404())
@app.route("/radar/<slug>")
def radar(slug): return render_template("radar.html",location=Location.query.filter_by(slug=slug).first_or_404())
@app.route("/air-quality/<slug>")
def air_quality(slug): return render_template("air_quality.html",location=Location.query.filter_by(slug=slug).first_or_404())
@app.route("/save/<slug>",methods=["POST"])
@login_required
def save_location(slug):
 loc=Location.query.filter_by(slug=slug).first_or_404(); old=SavedLocation.query.filter_by(user_id=current_user().id,location_id=loc.id).first()
 if old: db.session.delete(old); flash(f"Removed {loc.city} from saved locations.")
 else: db.session.add(SavedLocation(user_id=current_user().id,location_id=loc.id)); flash(f"Saved {loc.city}.")
 db.session.commit(); return redirect(request.referrer or url_for("weather",slug=slug))
@app.route("/alerts/<slug>",methods=["GET","POST"])
@login_required
def alerts(slug):
 loc=Location.query.filter_by(slug=slug).first_or_404()
 if request.method=="POST":
  selected=set(request.form.getlist("alert_type")); Alert.query.filter_by(user_id=current_user().id,location_id=loc.id).delete()
  for kind in sorted(selected): db.session.add(Alert(user_id=current_user().id,location_id=loc.id,alert_type=kind,enabled=True))
  db.session.commit(); flash("Alert preferences updated.")
 active={a.alert_type for a in Alert.query.filter_by(user_id=current_user().id,location_id=loc.id).all()}; return render_template("alerts.html",location=loc,active=active)
@app.route("/account")
@login_required
def account():
 saved=db.session.query(Location).join(SavedLocation,SavedLocation.location_id==Location.id).filter(SavedLocation.user_id==current_user().id).all(); return render_template("account.html",saved=saved)
@app.route("/settings",methods=["GET","POST"])
@login_required
def settings():
 if request.method=="POST":
  unit=request.form.get("unit")
  if unit in {"F","C"}: current_user().unit=unit; session["unit"]=unit; db.session.commit(); flash("Units updated.")
 return render_template("settings.html")
@app.route("/units/<unit>",methods=["POST"])
def units(unit):
 if unit in {"F","C"}: session["unit"]=unit
 return redirect(request.referrer or url_for("index"))
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  user=User.query.filter_by(email=request.form.get("email","").lower().strip()).first()
  if user and check_password_hash(user.password_hash,request.form.get("password","")): session["user_id"]=user.id; session["unit"]=user.unit; flash("Welcome back."); return redirect(request.args.get("next") or url_for("account"))
  flash("Email or password is incorrect.")
 return render_template("login.html")
@app.route("/register",methods=["GET","POST"])
def register():
 if request.method=="POST":
  email=request.form.get("email","").lower().strip()
  if User.query.filter_by(email=email).first(): flash("An account already exists for that email.")
  elif len(request.form.get("password",""))<8: flash("Password must be at least 8 characters.")
  else:
   user=User(email=email,name=request.form.get("name","Weather fan").strip(),password_hash=generate_password_hash(request.form["password"])); db.session.add(user); db.session.commit(); session["user_id"]=user.id; return redirect(url_for("account"))
 return render_template("register.html")
@app.route("/logout",methods=["POST"])
def logout(): session.clear(); return redirect(url_for("index"))
@app.route("/about")
def about(): return render_template("static_page.html",title="About AccuWeather",copy="We provide local weather forecasts and severe weather information for communities around the world.")
@app.route("/privacy")
def privacy(): return render_template("static_page.html",title="Privacy Statement",copy="Your privacy choices and account preferences are available here.")
@app.route("/_health")
def health(): return {"ok":True,"site":"accuweather"}
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)

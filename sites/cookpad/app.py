#!/usr/bin/env python3
"""Cookpad mirror for WebHarbor."""
import os
import re
import json
import random
import string
import hashlib
import shutil
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (Flask, render_template, request, redirect, url_for, flash,
                   jsonify, abort, session)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         current_user, login_required)
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
SITE_SLUG = "cookpad"
SITE_NAME = "Cookpad"
SITE_PORT = 40040
BENCHMARK_PASSWORD = "TestPass123!"
BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
SEED_DIR = BASE_DIR / "instance_seed"
STATIC_DIR = BASE_DIR / "static"
IMAGE_DIR = STATIC_DIR / "images"
RUNTIME_DB_PATH = Path(os.environ.get('COOKPAD_DATABASE', str(INSTANCE_DIR / 'cookpad.db')))
SEED_DB_PATH = SEED_DIR / "cookpad.db"


def _ensure_dirs() -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


_ensure_dirs()

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config['SECRET_KEY'] = 'cookpad-demo-session-key'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{RUNTIME_DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


def slugify(value):
    cleaned = []
    for char in (value or "").lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != '-':
            cleaned.append('-')
    return ''.join(cleaned).strip('-')

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    display_name = db.Column(db.String(100), default='')
    bio = db.Column(db.Text, default='')
    location = db.Column(db.String(100), default='')
    avatar_url = db.Column(db.String(300), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Relationships
    reviews = db.relationship('Review', backref='author', lazy=True, cascade='all, delete-orphan')
    recipe_box = db.relationship('RecipeBoxItem', backref='user', lazy=True, cascade='all, delete-orphan')
    meal_plans = db.relationship('MealPlanItem', backref='user', lazy=True, cascade='all, delete-orphan')
    shopping_lists = db.relationship('ShoppingList', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, default='')
    image = db.Column(db.String(300), default='')
    parent_type = db.Column(db.String(50), default='meal')  # meal, ingredient, cuisine
    display_order = db.Column(db.Integer, default=0)
    recipes = db.relationship('Recipe', backref='category', lazy=True)


class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text, default='')
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    cuisine = db.Column(db.String(100), default='')
    image = db.Column(db.String(300), default='')
    prep_time = db.Column(db.String(50), default='')
    cook_time = db.Column(db.String(50), default='')
    total_time = db.Column(db.String(50), default='')
    additional_time = db.Column(db.String(50), default='')
    servings = db.Column(db.String(20), default='')
    yield_amount = db.Column(db.String(100), default='')
    calories = db.Column(db.Integer, default=0)
    ingredients_json = db.Column(db.Text, default='[]')
    instructions_json = db.Column(db.Text, default='[]')
    nutrition_json = db.Column(db.Text, default='{}')
    tags_json = db.Column(db.Text, default='[]')
    gallery_json = db.Column(db.Text, default='[]')
    is_featured = db.Column(db.Boolean, default=False)
    is_editors_pick = db.Column(db.Boolean, default=False)
    avg_rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    author_name = db.Column(db.String(100), default='Cookpad Community')
    # Task-driven filter columns
    prep_time_mins = db.Column(db.Integer, default=0)
    cook_time_mins = db.Column(db.Integer, default=0)
    total_time_mins = db.Column(db.Integer, nullable=True)
    ingredient_count = db.Column(db.Integer, default=0)
    dietary_tags_json = db.Column(db.Text, default='[]')  # vegan, vegetarian, gluten-free, etc.
    dish_type = db.Column(db.String(50), default='')  # main, dessert, breakfast, appetizer, salad, soup
    meal_type = db.Column(db.String(50), default='')  # breakfast, lunch, dinner, snack
    cooking_method = db.Column(db.String(80), default='')  # baked, grilled, slow cooker, etc.
    main_ingredient = db.Column(db.String(80), default='')  # chicken, beef, fish, etc.
    occasion = db.Column(db.String(100), default='')
    season = db.Column(db.String(50), default='')
    feature_tags = db.Column(db.Text, default='[]')  # kebab-case keywords for filter matching
    latest_review_text = db.Column(db.Text, default='')
    storage_instructions = db.Column(db.Text, default='')
    primary_seasoning = db.Column(db.String(120), default='')
    max_oven_temp = db.Column(db.Integer, default=0)  # e.g. 425 for apple pie
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    source_url = db.Column(db.Text, nullable=False, default='')
    source_author_url = db.Column(db.Text, default='')
    source_comments_json = db.Column(db.Text, default='[]')
    save_count = db.Column(db.Integer, nullable=True)
    source_comment_count = db.Column(db.Integer, nullable=True)
    # Relationships
    reviews = db.relationship('Review', backref='recipe', lazy=True, cascade='all, delete-orphan')
    recipe_box_items = db.relationship('RecipeBoxItem', backref='recipe', lazy=True, cascade='all, delete-orphan')

    def get_ingredients(self):
        try:
            return json.loads(self.ingredients_json)
        except:
            return []

    def get_instructions(self):
        try:
            return [text.replace('\\n', '\n') for text in json.loads(self.instructions_json)]
        except:
            return []

    def get_nutrition(self):
        try:
            return json.loads(self.nutrition_json)
        except:
            return {}

    def get_tags(self):
        try:
            return json.loads(self.tags_json)
        except:
            return []

    def get_gallery(self):
        try:
            return json.loads(self.gallery_json)
        except:
            return []

    def get_dietary_tags(self):
        try:
            return json.loads(self.dietary_tags_json)
        except:
            return []

    def get_feature_tags(self):
        try:
            return json.loads(self.feature_tags)
        except:
            return []


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), default='')
    body = db.Column(db.Text, default='')
    helpful_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RecipeBoxItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MealPlanItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    day = db.Column(db.String(20), nullable=False)  # monday, tuesday, etc.
    meal_type = db.Column(db.String(20), nullable=False)  # breakfast, lunch, dinner, snack
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    recipe = db.relationship('Recipe', lazy=True)


class ShoppingList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), default='Shopping List')
    items_json = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_items(self):
        try:
            return json.loads(self.items_json)
        except:
            return []

    def set_items(self, items):
        self.items_json = json.dumps(items)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

@app.context_processor
def utility_processor():
    def recipe_box_count():
        if current_user.is_authenticated:
            return RecipeBoxItem.query.filter_by(user_id=current_user.id).count()
        return 0

    def is_in_recipe_box(recipe_id):
        if current_user.is_authenticated:
            return RecipeBoxItem.query.filter_by(
                user_id=current_user.id, recipe_id=recipe_id).first() is not None
        return False

    def pagination_url(page):
        from urllib.parse import urlencode
        args = request.args.to_dict()
        args['page'] = page
        return request.path + '?' + urlencode(args)
    return dict(recipe_box_count=recipe_box_count, is_in_recipe_box=is_in_recipe_box,
                pagination_url=pagination_url)


def source_author_slug(recipe):
    """Different Cookpad accounts can share a display name."""
    identities = db.session.query(Recipe.source_author_url).filter_by(
        author_name=recipe.author_name).distinct().count()
    suffix = '-' + recipe.source_author_url.rstrip('/').split('/')[-1] if identities > 1 else ''
    return slugify(recipe.author_name) + suffix


app.jinja_env.filters['author_slug'] = source_author_slug
app.jinja_env.filters['from_json'] = json.loads


# ---------------------------------------------------------------------------
# Routes 鈥?Static Pages
# ---------------------------------------------------------------------------


from catalog_routes import register_catalog
register_catalog(app, db, Recipe, Category, render_template, request, slugify)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=request.form.get('remember'))
            flash('Welcome back!', 'success')
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/') or next_page.startswith('//'):
                next_page = url_for('index')
            return redirect(next_page)
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if not username or not email or not password:
            flash('All fields are required.', 'danger')
        elif password != confirm:
            flash('Passwords do not match.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
        else:
            user = User(username=username, email=email, display_name=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created! Welcome to Cookpad.', 'success')
            return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Routes 鈥?User Profile / Account
# ---------------------------------------------------------------------------

@app.route('/account')
@login_required
def account():
    saved_count = RecipeBoxItem.query.filter_by(user_id=current_user.id).count()
    review_count = Review.query.filter_by(user_id=current_user.id).count()
    meal_plans = MealPlanItem.query.filter_by(user_id=current_user.id).all()
    shopping_lists = ShoppingList.query.filter_by(user_id=current_user.id).all()
    return render_template('account.html', saved_count=saved_count,
                           review_count=review_count, meal_plans=meal_plans,
                           shopping_lists=shopping_lists)


@app.route('/account/edit', methods=['GET', 'POST'])
@login_required
def account_edit():
    if request.method == 'POST':
        current_user.display_name = request.form.get('display_name', '').strip()
        current_user.bio = request.form.get('bio', '').strip()
        current_user.location = request.form.get('location', '').strip()
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('account'))
    return render_template('account_edit.html')


@app.route('/account/password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')
        if not current_user.check_password(current_pw):
            flash('Current password is incorrect.', 'danger')
        elif new_pw != confirm_pw:
            flash('New passwords do not match.', 'danger')
        elif len(new_pw) < 6:
            flash('Password must be at least 6 characters.', 'danger')
        else:
            current_user.set_password(new_pw)
            db.session.commit()
            flash('Password changed successfully.', 'success')
            return redirect(url_for('account'))
    return render_template('change_password.html')


@app.route('/account/delete', methods=['POST'])
@login_required
def delete_account():
    user = User.query.get(current_user.id)
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash('Your account has been deleted.', 'info')
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Routes 鈥?Saved recipes
# ---------------------------------------------------------------------------

@app.route('/recipe-box')
@app.route('/favorites')
@login_required
def recipe_box():
    items = RecipeBoxItem.query.filter_by(user_id=current_user.id).order_by(
        RecipeBoxItem.created_at.desc(), RecipeBoxItem.id.desc()).all()
    recipes = [item.recipe for item in items]
    return render_template('recipe_box.html', recipes=recipes, items=items)


@app.route('/api/recipe-box/toggle', methods=['POST'])
@login_required
def toggle_recipe_box():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(success=False, message='Expected a JSON object'), 400
    recipe_id = data.get('recipe_id')
    if not recipe_id:
        return jsonify(success=False, message='Missing recipe_id'), 400
    Recipe.query.get_or_404(recipe_id)
    existing = RecipeBoxItem.query.filter_by(
        user_id=current_user.id, recipe_id=recipe_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        count = RecipeBoxItem.query.filter_by(user_id=current_user.id).count()
        return jsonify(success=True, saved=False, count=count, message='Removed from saved recipes')
    else:
        item = RecipeBoxItem(user_id=current_user.id, recipe_id=recipe_id)
        db.session.add(item)
        db.session.commit()
        count = RecipeBoxItem.query.filter_by(user_id=current_user.id).count()
        return jsonify(success=True, saved=True, count=count, message='Saved to your Cookpad box')


@app.route('/recipe-box/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_recipe_box(item_id):
    item = RecipeBoxItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash('Recipe removed from your box.', 'info')
    return redirect(url_for('recipe_box'))


@app.route('/recipe-box/save/<int:recipe_id>', methods=['POST'])
@login_required
def save_to_recipe_box(recipe_id):
    """Form-POST endpoint to save a recipe to the recipe box (agent-friendly)."""
    recipe = Recipe.query.get_or_404(recipe_id)
    existing = RecipeBoxItem.query.filter_by(
        user_id=current_user.id, recipe_id=recipe_id).first()
    if not existing:
        item = RecipeBoxItem(user_id=current_user.id, recipe_id=recipe_id)
        db.session.add(item)
        db.session.commit()
        flash(f'"{recipe.title}" saved to your Cookpad box.', 'success')
    else:
        flash(f'"{recipe.title}" is already saved in your Cookpad box.', 'info')
    next_page = request.form.get('next') or url_for('recipe_box')
    if not next_page.startswith('/') or next_page.startswith('//'):
        next_page = url_for('recipe_box')
    return redirect(next_page)


@app.route('/recipe-box/note/<int:item_id>', methods=['POST'])
@login_required
def update_recipe_box_note(item_id):
    """Form-POST endpoint to update the note on a saved recipe."""
    item = RecipeBoxItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    item.notes = request.form.get('notes', '').strip()
    db.session.commit()
    flash('Note updated.', 'success')
    return redirect(url_for('recipe_box'))


# ---------------------------------------------------------------------------
# Routes 鈥?Meal Planner
# ---------------------------------------------------------------------------

@app.route('/meal-plan')
@login_required
def meal_plan():
    items = MealPlanItem.query.filter_by(user_id=current_user.id).all()
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    meals = ['breakfast', 'lunch', 'dinner', 'snack']
    plan = {}
    for day in days:
        plan[day] = {}
        for meal in meals:
            plan[day][meal] = None
    for item in items:
        plan[item.day][item.meal_type] = item
    all_recipes = Recipe.query.order_by(Recipe.title).all()
    return render_template('meal_plan.html', plan=plan, days=days, meals=meals,
                           all_recipes=all_recipes)


@app.route('/api/meal-plan/add', methods=['POST'])
@login_required
def add_to_meal_plan():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(success=False, message='Expected a JSON object'), 400
    recipe_id = data.get('recipe_id')
    day = data.get('day')
    meal_type = data.get('meal_type')
    if not recipe_id or day not in {'monday','tuesday','wednesday','thursday','friday','saturday','sunday'} or meal_type not in {'breakfast','lunch','dinner','snack'}:
        return jsonify(success=False, message='Missing fields'), 400
    Recipe.query.get_or_404(recipe_id)
    # Remove existing item for this slot
    MealPlanItem.query.filter_by(
        user_id=current_user.id, day=day, meal_type=meal_type).delete()
    item = MealPlanItem(user_id=current_user.id, recipe_id=recipe_id,
                        day=day, meal_type=meal_type)
    db.session.add(item)
    db.session.commit()
    return jsonify(success=True, message='Added to meal plan')


@app.route('/api/meal-plan/remove', methods=['POST'])
@login_required
def remove_from_meal_plan():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(success=False, message='Expected a JSON object'), 400
    day = data.get('day')
    meal_type = data.get('meal_type')
    MealPlanItem.query.filter_by(
        user_id=current_user.id, day=day, meal_type=meal_type).delete()
    db.session.commit()
    return jsonify(success=True, message='Removed from meal plan')


@app.route('/meal-plan/clear', methods=['POST'])
@login_required
def clear_meal_plan():
    MealPlanItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('Meal plan cleared.', 'info')
    return redirect(url_for('meal_plan'))


@app.route('/meal-plan/add', methods=['POST'])
@login_required
def add_to_meal_plan_form():
    """Form-POST endpoint to add a recipe to the meal plan (agent-friendly)."""
    recipe_id = request.form.get('recipe_id', type=int)
    day = request.form.get('day', '').strip().lower()
    meal_type = request.form.get('meal_type', '').strip().lower()
    if not recipe_id or day not in {'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'} or meal_type not in {'breakfast', 'lunch', 'dinner', 'snack'}:
        flash('Please select a recipe, day, and meal type.', 'danger')
        return redirect(url_for('meal_plan'))
    recipe = Recipe.query.get_or_404(recipe_id)
    MealPlanItem.query.filter_by(
        user_id=current_user.id, day=day, meal_type=meal_type).delete()
    item = MealPlanItem(user_id=current_user.id, recipe_id=recipe_id,
                        day=day, meal_type=meal_type)
    db.session.add(item)
    db.session.commit()
    flash(f'"{recipe.title}" added to {day.capitalize()} {meal_type}.', 'success')
    return redirect(url_for('meal_plan'))


@app.route('/meal-plan/remove', methods=['POST'])
@login_required
def remove_from_meal_plan_form():
    """Form-POST endpoint to remove a slot from the meal plan (agent-friendly)."""
    day = request.form.get('day', '').strip().lower()
    meal_type = request.form.get('meal_type', '').strip().lower()
    MealPlanItem.query.filter_by(
        user_id=current_user.id, day=day, meal_type=meal_type).delete()
    db.session.commit()
    flash(f'{day.capitalize()} {meal_type} cleared.', 'info')
    return redirect(url_for('meal_plan'))


# ---------------------------------------------------------------------------
# Routes 鈥?Shopping List
# ---------------------------------------------------------------------------

@app.route('/shopping-list')
@login_required
def shopping_list():
    lists = ShoppingList.query.filter_by(user_id=current_user.id).order_by(
        ShoppingList.created_at.desc()).all()
    all_recipes = Recipe.query.order_by(Recipe.title).all()
    return render_template('shopping_list.html', lists=lists, all_recipes=all_recipes)


@app.route('/shopping-list/create', methods=['POST'])
@login_required
def create_shopping_list():
    name = request.form.get('name', 'Shopping List').strip()
    if not name or len(name) > 200:
        flash('Enter a list name of 1–200 characters.', 'danger')
        return redirect(url_for('shopping_list'))
    sl = ShoppingList(user_id=current_user.id, name=name)
    db.session.add(sl)
    db.session.commit()
    flash('Shopping list created.', 'success')
    return redirect(url_for('shopping_list'))


@app.route('/api/shopping-list/<int:list_id>/add', methods=['POST'])
@login_required
def add_to_shopping_list(list_id):
    sl = ShoppingList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(success=False, message='Expected a JSON object'), 400
    recipe_id = data.get('recipe_id')
    if recipe_id:
        recipe = Recipe.query.get_or_404(recipe_id)
        items = sl.get_items()
        for ing in recipe.get_ingredients():
            if ing not in items:
                items.append(ing)
        sl.set_items(items)
        db.session.commit()
        return jsonify(success=True, message=f'Added {recipe.title} ingredients',
                       count=len(items))
    item = data.get('item', '').strip()
    if item:
        items = sl.get_items()
        items.append(item)
        sl.set_items(items)
        db.session.commit()
        return jsonify(success=True, count=len(items))
    return jsonify(success=False), 400


@app.route('/api/shopping-list/<int:list_id>/remove', methods=['POST'])
@login_required
def remove_from_shopping_list(list_id):
    sl = ShoppingList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(success=False, message='Expected a JSON object'), 400
    index = data.get('index')
    items = sl.get_items()
    if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(items):
        items.pop(index)
        sl.set_items(items)
        db.session.commit()
    return jsonify(success=True, count=len(items))


@app.route('/shopping-list/<int:list_id>/delete', methods=['POST'])
@login_required
def delete_shopping_list(list_id):
    sl = ShoppingList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    db.session.delete(sl)
    db.session.commit()
    flash('Shopping list deleted.', 'info')
    return redirect(url_for('shopping_list'))


@app.route('/shopping-list/<int:list_id>/add-recipe', methods=['POST'])
@login_required
def add_recipe_to_shopping_list(list_id):
    """Form-POST endpoint to add a recipe's ingredients to a shopping list (agent-friendly)."""
    sl = ShoppingList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    recipe_id = request.form.get('recipe_id', type=int)
    if not recipe_id:
        flash('No recipe selected.', 'danger')
        return redirect(url_for('shopping_list'))
    recipe = Recipe.query.get_or_404(recipe_id)
    items = sl.get_items()
    added = 0
    for ing in recipe.get_ingredients():
        if ing not in items:
            items.append(ing)
            added += 1
    sl.set_items(items)
    db.session.commit()
    flash(f'Added {added} ingredient(s) from "{recipe.title}" to "{sl.name}".', 'success')
    return redirect(url_for('shopping_list'))


@app.route('/shopping-list/<int:list_id>/add-item', methods=['POST'])
@login_required
def add_item_to_shopping_list(list_id):
    """Form-POST endpoint to add a custom item to a shopping list (agent-friendly)."""
    sl = ShoppingList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    item = request.form.get('item', '').strip()
    if not item:
        flash('Please enter an item.', 'danger')
        return redirect(url_for('shopping_list'))
    items = sl.get_items()
    items.append(item)
    sl.set_items(items)
    db.session.commit()
    flash(f'"{item}" added to "{sl.name}".', 'success')
    return redirect(url_for('shopping_list'))


@app.route('/shopping-list/<int:list_id>/remove-item', methods=['POST'])
@login_required
def remove_item_from_shopping_list(list_id):
    """Form-POST endpoint to remove an item by index from a shopping list (agent-friendly)."""
    sl = ShoppingList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    index = request.form.get('index', type=int)
    items = sl.get_items()
    if index is not None and 0 <= index < len(items):
        removed = items.pop(index)
        sl.set_items(items)
        db.session.commit()
        flash(f'"{removed}" removed.', 'info')
    return redirect(url_for('shopping_list'))


# ---------------------------------------------------------------------------
# Routes 鈥?Reviews
# ---------------------------------------------------------------------------


def initialize_database():
    """Restore only an absent runtime; normal startup never writes either DB.

    Saved recipes, plans and lists are user-owned state, not initialization
    sentinels. Removing their rows must survive /restart and must never cause
    the immutable reset fixture to be regenerated from live state.
    """
    if RUNTIME_DB_PATH.exists():
        return
    if os.environ.get('COOKPAD_SEED_BUILD') == '1':
        return
    if not SEED_DB_PATH.is_file():
        raise RuntimeError(
            'Cookpad seed database is missing. Fetch the reviewed assets before '
            'starting this site; runtime startup does not generate benchmark data.'
        )
    shutil.copy2(SEED_DB_PATH, RUNTIME_DB_PATH)


with app.app_context():
    initialize_database()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', SITE_PORT))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)

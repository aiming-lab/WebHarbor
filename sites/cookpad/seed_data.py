"""Explicit deterministic seed build, never imported by runtime startup.

Usage: python seed_data.py --output /new/path/cookpad.db
The destination must not exist. Never overwrites a runtime or seed.
"""
import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent
COLLECTIONS = [
    ('breakfast','Breakfast','Pancakes and waffles from home cooks.'),
    ('baking','Banana bread','Banana breads from the Cookpad snapshot.'),
    ('soups','Miso soups','Miso soups and bases, with source ingredient lists.'),
    ('japanese','Japanese-inspired','Japanese and Japanese-inspired home cooking.'),
    ('tofu','Tofu','Recipes featuring tofu; not all are vegetarian.'),
    ('desserts','Desserts','Cookies, brownies and sweet treats.'),
    ('dinner','Dinner','Lasagna and other dinner ideas.'),
    ('pork','Pork','Pork recipes from the Cookpad community.'),
    ('meal-prep','Meal Prep','Recipes explicitly presented as meal-prep ideas.'),
    ('seafood','Salmon','Salmon dishes from home cooks.'),
]
QUERY_COLLECTION = {'pancakes':'breakfast','waffles':'breakfast','banana bread':'baking',
    'miso soup':'soups','Japanese eggplant':'japanese','tofu':'tofu',
    'chocolate chip cookies':'desserts','brownies':'desserts','lasagna':'dinner',
    'pork':'pork','meal prep chicken':'dinner','salmon':'seafood'}
MEAL_PREP = {'25797934','25038367'}
BENCHMARK_USERS = [('alice.j','Alice Johnson'),('bob.c','Bob Chen'),
                   ('carol.d','Carol Davis'),('david.k','David Kim')]
SAVED = [[26400824,335275,26394567,26469106,26438226],
         [367685,350361,25142876,25797934,26311602],
         [365027,25794736,17110323,26273739,26132817],
         [26504420,24605590,26200218,26425750,25797934]]


def minutes(value):
    match = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', value or '')
    if not match:
        return None
    hours, mins, seconds = (int(x or 0) for x in match.groups())
    return hours*60 + mins + seconds/60


def build(output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    os.environ['COOKPAD_SEED_BUILD'] = '1'
    os.environ['COOKPAD_DATABASE'] = str(output)
    from app import app, db, Category, Recipe, User, RecipeBoxItem, MealPlanItem, ShoppingList
    records = json.loads((BASE_DIR/'source_catalog.json').read_text())
    with app.app_context():
        db.create_all()
        for number,(slug,name,description) in enumerate(COLLECTIONS,1):
            db.session.add(Category(id=number,slug=slug,name=name,description=description,display_order=number))
        db.session.flush()
        categories = {c.slug:c.id for c in Category.query.all()}
        for record in sorted(records,key=lambda r:int(r['source_id'])):
            source = record['recipe']
            time = minutes(source.get('totalTime'))
            bookmark = next((x['userInteractionCount'] for x in source.get('interactionStatistic',[])
                             if x.get('interactionType','').endswith('/BookmarkAction')),None)
            collection = 'meal-prep' if record['source_id'] in MEAL_PREP else QUERY_COLLECTION[record['discovered_via'][0]]
            db.session.add(Recipe(id=int(record['source_id']),slug='cookpad-'+record['source_id'],
                title=source['name'],description=source.get('description',''),
                category_id=categories[collection],cuisine=source.get('recipeCuisine',''),
                image='/'+record['image_path'],total_time_mins=time,
                total_time=(f'{time:g} minutes' if time is not None else ''),
                servings=str(source.get('recipeYield') or ''),
                ingredients_json=json.dumps(source['recipeIngredient'],ensure_ascii=False),
                instructions_json=json.dumps([s['text'] for s in source['recipeInstructions']],ensure_ascii=False),
                author_name=source['author']['name'].strip(),source_url=record['source_url'],
                source_author_url=source['author'].get('url',''),
                source_comments_json=json.dumps(source.get('comment',[]),ensure_ascii=False),
                save_count=bookmark,source_comment_count=source.get('commentCount'),
                ingredient_count=len(source['recipeIngredient']),
                created_at=datetime.fromisoformat(source.get('datePublished','2000-01-01')[:10])))
        db.session.flush()
        # Fixed demo-only hash for TestPass123!, not a real account credential.
        password_hash = '$2b$12$YlyoMQZ9VI.X9PM9BNTcEevaLx/zuPWklMHgKR2VOlF6RST2aO8vi'
        for user_id,(username,name) in enumerate(BENCHMARK_USERS,1):
            db.session.add(User(id=user_id,username=username,email=username+'@test.com',display_name=name,
                               password_hash=password_hash,created_at=datetime(2026,1,1)))
            for offset,recipe_id in enumerate(SAVED[user_id-1]):
                db.session.add(RecipeBoxItem(user_id=user_id,recipe_id=recipe_id,notes='',
                    created_at=datetime(2026,1,1)+timedelta(days=offset)))
            recipe_id = SAVED[user_id-1][0]
            db.session.add(MealPlanItem(user_id=user_id,recipe_id=recipe_id,day='monday',
                                       meal_type='breakfast',created_at=datetime(2026,1,1)))
            db.session.add(MealPlanItem(user_id=user_id,recipe_id=SAVED[user_id-1][2],day='sunday',
                                       meal_type='dinner',created_at=datetime(2026,1,1)))
            name = ['Weekly Groceries','Weeknight Dinners','Weekend Baking','Sunday Meal Prep'][user_id-1]
            ingredients = db.session.get(Recipe,recipe_id).get_ingredients()[:6]
            db.session.add(ShoppingList(user_id=user_id,name=name,items_json=json.dumps(ingredients),created_at=datetime(2026,1,1)))
        db.session.commit()
        db.session.remove()
        print(f'Built {len(records)} sourced recipes and four synthetic demo accounts: {output}')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    build(parser.parse_args().output)

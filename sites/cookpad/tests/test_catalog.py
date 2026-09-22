"""Routes and assets against an isolated mutable fixture, not the preview."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from PIL import Image

SITE=Path(__file__).resolve().parents[1]
TEMP=tempfile.TemporaryDirectory()
RUNTIME=Path(TEMP.name)/'cookpad.db'
shutil.copy2(SITE/'instance_seed/cookpad.db',RUNTIME)
os.environ['COOKPAD_DATABASE']=str(RUNTIME)
sys.path.insert(0,str(SITE))
from app import app,db

class CatalogueTests(unittest.TestCase):
    def setUp(self):
        with app.app_context():db.session.remove();db.engine.dispose()
        shutil.copy2(SITE/'instance_seed/cookpad.db',RUNTIME)
        self.client=app.test_client()
    def token(self,path='/login'):
        html=self.client.get(path).text
        return re.search(r'name="csrf_token" value="([^"]+)"',html)[1]
    def login(self):
        return self.client.post('/login',data=dict(email='alice.j@test.com',password='TestPass123!',csrf_token=self.token()))
    def test_sixty_real_photos_and_exact_source_fields(self):
        from app import Recipe
        records=json.loads((SITE/'source_catalog.json').read_text())
        self.assertEqual(len(records),60)
        with app.app_context():
            self.assertEqual(Recipe.query.count(),60)
            for record in records:
                r=db.session.get(Recipe,int(record['source_id']));s=record['recipe']
                self.assertEqual(r.title,s['name']);self.assertEqual(r.author_name,s['author']['name'].strip())
                self.assertEqual(r.get_ingredients(),s['recipeIngredient'])
                self.assertEqual(json.loads(r.instructions_json),[x['text'] for x in s['recipeInstructions']])
                image=SITE/record['image_path']
                self.assertEqual(r.image,'/'+record['image_path'])
                self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(),record['image_sha256'])
                with Image.open(image) as im:im.verify()
                self.assertTrue(r.source_url.startswith('https://cookpad.com/'))
    def test_search_is_relevant_and_literal_wildcards_do_not_match_all(self):
        html=self.client.get('/search?q=banana+bread').text
        self.assertIn('5 recipes',html);self.assertNotIn('Homemade Pancakes',html)
        self.assertIn('No matching recipes',self.client.get('/search?q=%25').text)
    def test_unknown_time_is_not_zero_or_time_filter_candidate(self):
        html=self.client.get('/category/meal-prep?max_time=60').text
        self.assertIn('Marx Meal Prep',html);self.assertNotIn('Chicken Teriyaki',html)
        self.assertIn('Not provided by the author',self.client.get('/recipe/cookpad-25038367').text)
    def test_every_recipe_and_collection_renders(self):
        from app import Recipe,Category
        with app.app_context():
            paths=['/recipe/'+r.slug for r in Recipe.query]+['/category/'+c.slug for c in Category.query]
        for path in paths:self.assertEqual(self.client.get(path).status_code,200,path)
    def test_authenticated_pages_and_csrf(self):
        self.assertEqual(self.login().status_code,302)
        for path in ['/recipe-box','/meal-plan','/shopping-list','/account','/account/edit','/account/password']:
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.assertEqual(self.client.post('/api/meal-plan/add',json={}).status_code,400)
    def test_owner_guard_and_invalid_meal_are_noops(self):
        self.login();before=RUNTIME.read_bytes();token=self.token('/shopping-list')
        r=self.client.post('/shopping-list/2/add-item',data=dict(item='intruder',csrf_token=token))
        self.assertEqual(r.status_code,404)
        r=self.client.post('/meal-plan/add',data=dict(recipe_id=365027,day='noday',meal_type='breakfast',csrf_token=token))
        self.assertEqual(r.status_code,302);self.assertEqual(RUNTIME.read_bytes(),before)
    def test_bad_json_and_nonexistent_recipe_do_not_write(self):
        self.login();before=RUNTIME.read_bytes();token=self.token('/shopping-list');headers={'X-CSRFToken':token}
        self.assertEqual(self.client.post('/api/meal-plan/add',json=[],headers=headers).status_code,400)
        self.assertEqual(self.client.post('/api/recipe-box/toggle',json={'recipe_id':99999999},headers=headers).status_code,404)
        self.assertEqual(RUNTIME.read_bytes(),before)
    def test_login_returns_to_local_recipe(self):
        token=self.token('/login?next=/recipe/cookpad-365027')
        r=self.client.post('/login?next=/recipe/cookpad-365027',data=dict(email='alice.j@test.com',password='TestPass123!',csrf_token=token))
        self.assertEqual(r.location,'/recipe/cookpad-365027')

    def test_same_named_authors_remain_separate_accounts(self):
        pancakes=self.client.get('/authors/christina-116531125').text
        waffles=self.client.get('/authors/christina-3000087').text
        self.assertIn('Homemade Pancakes',pancakes)
        self.assertNotIn('Easy Waffles',pancakes)
        self.assertIn('Easy Waffles',waffles)
        self.assertNotIn('Homemade Pancakes',waffles)
        self.assertEqual(self.client.get('/authors/christina').status_code,404)

if __name__=='__main__':unittest.main()

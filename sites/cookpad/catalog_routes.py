"""Catalogue handlers; all runtime content comes from the local SQLite DB."""
from urllib.parse import urlsplit


def register_catalog(app, db, Recipe, Category, render_template, request, slugify):
    def ordered(query, sort):
        if sort == 'time':
            return query.order_by(Recipe.total_time_mins.is_(None), Recipe.total_time_mins, Recipe.id)
        if sort == 'name':
            return query.order_by(Recipe.title, Recipe.id)
        return query.order_by(Recipe.save_count.desc().nullslast(), Recipe.title, Recipe.id)

    def listing(category=None, author=None, author_source=None):
        query = Recipe.query
        text = request.args.get('q', '').strip()
        if text:
            for word in text.split():
                escaped = word.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                pattern = '%' + escaped + '%'
                query = query.filter(db.or_(Recipe.title.ilike(pattern, escape='\\'),
                                           Recipe.ingredients_json.ilike(pattern, escape='\\')))
        if category:
            query = query.filter_by(category_id=category.id)
        category_slug = request.args.get('category', '')
        if category_slug:
            selected = Category.query.filter_by(slug=category_slug).first_or_404()
            query = query.filter_by(category_id=selected.id)
        if author:
            query = query.filter_by(author_name=author, source_author_url=author_source)
        maximum = request.args.get('max_time', type=int)
        if maximum is not None:
            query = query.filter(Recipe.total_time_mins.is_not(None), Recipe.total_time_mins <= maximum)
        sort = request.args.get('sort', 'saved')
        page = max(1, request.args.get('page', 1, type=int))
        recipes = ordered(query, sort).paginate(page=page, per_page=12, error_out=False)
        return render_template('listing.html', recipes=recipes, query=text, sort=sort,
                               selected_category=category_slug, max_time=maximum,
                               category=category, author=author,
                               categories=Category.query.order_by(Category.display_order).all())

    @app.route('/')
    @app.route('/home')
    def index():
        categories = Category.query.order_by(Category.display_order).all()
        return render_template('index.html', categories=categories,
                               popular=ordered(Recipe.query, 'saved').limit(8).all(),
                               latest=Recipe.query.order_by(Recipe.created_at.desc(), Recipe.id).limit(8).all())

    @app.route('/search')
    @app.route('/recipes')
    def search():
        return listing()

    app.add_url_rule('/all-recipes', 'all_recipes', search)

    @app.route('/categories')
    def categories_page():
        return render_template('categories.html', categories=Category.query.order_by(Category.display_order).all())

    @app.route('/category/<slug>')
    def category_page(slug):
        return listing(category=Category.query.filter_by(slug=slug).first_or_404())

    @app.route('/recipe/<slug>')
    def recipe_detail(slug):
        recipe = Recipe.query.filter_by(slug=slug).first_or_404()
        related = Recipe.query.filter(Recipe.category_id == recipe.category_id, Recipe.id != recipe.id).limit(3).all()
        return render_template('recipe_detail.html', recipe=recipe, related=related)

    @app.route('/authors/<slug>')
    def author_page(slug):
        identities = db.session.query(Recipe.author_name, Recipe.source_author_url).distinct().all()
        matches = [(name, source) for name, source in identities
                   if slug == slugify(name) + '-' + source.rstrip('/').split('/')[-1]
                   or slug == slugify(name)]
        if len(matches) != 1:
            from flask import abort
            abort(404)
        return listing(author=matches[0][0], author_source=matches[0][1])

    @app.route('/help')
    def help_center():
        text = request.args.get('q', '').strip().lower()
        articles = [a for a in HELP_ARTICLES if not text or all(
            token in (a['title']+' '+a['body']).lower() for token in text.split())]
        return render_template('help.html', articles=articles, query=text)

    @app.route('/help/<slug>')
    def help_article(slug):
        from flask import abort
        article = next((a for a in HELP_ARTICLES if a['slug'] == slug), None)
        if article is None:
            abort(404)
        return render_template('help_article.html', article=article)

    @app.route('/about')
    def about():
        return render_template('about.html')

    @app.route('/api/search')
    def api_search():
        from flask import jsonify
        text = request.args.get('q', '').strip()
        recipes = Recipe.query.filter(Recipe.title.ilike('%'+text+'%')).limit(6).all() if text else []
        return jsonify(results=[dict(id=r.id,title=r.title,slug=r.slug,image=r.image) for r in recipes])


HELP_ARTICLES = [
    dict(slug='saving-recipes', title='Save recipes and add a note',
         summary='Keep recipes in your collection, with personal cooking notes.',
         body='Sign in and choose Save recipe on a recipe page. Open Saved Recipes to add a note about ingredient substitutions, pantry reminders, or meal-prep timing. Choose Save Note to keep it. Removing a saved recipe also removes its personal note. These changes are local to this offline mirror; they do not change your real Cookpad account.', keywords=['saved recipes','notes','substitutions']),
    dict(slug='shopping-list-overview', title='Create a shopping list from a recipe',
         summary='Collect recipe ingredients or add your own items.',
         body='Sign in and open Shopping List. Enter a list name and choose Create List. Select a recipe to add its complete ingredient list, or enter a custom item. Ingredients keep their source wording; duplicate identical lines are added only once. You can remove items individually. Shopping lists are local to this mirror: grocery ordering and delivery are not available.', keywords=['shopping','ingredients','grocery']),
    dict(slug='meal-plan-basics', title='Plan meals for the week',
         summary='Choose a recipe for a day and meal slot.',
         body='Sign in and open Meal Plan. Each day has breakfast, lunch, dinner and snack slots. Choose a recipe and Add or Replace it. Replacing a meal changes only that slot. Meal plans are local to this offline mirror and do not send reminders or order groceries.', keywords=['meal plan','weekly','dinner']),
    dict(slug='source-data', title='Recipe sources and missing information',
         summary='Understand the saved Cookpad snapshot and its limits.',
         body='Recipe photos, authors, ingredient lists and instructions come from the linked Cookpad recipe. Cooking times, serving sizes, saves and comments are shown only when present in that source snapshot. An unknown time is not zero and is excluded when you apply a maximum-time filter. Saves are bookmarks, not star ratings or written reviews. Curated collections are local navigation groups. Demo accounts, saved lists and meal plans are synthetic benchmark state.', keywords=['sources','time','saves']),
]

"""Deterministic seed helpers for the Cookpad WebHarbor mirror."""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

from app import (
    Category,
    MealPlanItem,
    Recipe,
    RecipeBoxItem,
    Review,
    ShoppingList,
    User,
    app,
    db,
    seed_benchmark_users,
    seed_database,
)


RNG = random.Random(20260605)
EXPECTED_COUNTS = {
    "users": 4,
    "recipes": 180,
    "reviews": 120,
    "recipe_box": 60,
    "meal_plan": 24,
}

AUTHOR_PROFILES = [
    ("Mika Tanaka", "Tokyo-born weeknight recipe writer who loves one-pan comfort food."),
    ("Sofia Delgado", "Home baker focused on approachable desserts and pantry swaps."),
    ("Jordan Lee", "Meal-prep enthusiast building flavorful lunch boxes for busy weekdays."),
    ("Nina Patel", "Vegetarian cook sharing family favorites with quick ingredient lists."),
    ("Owen Brooks", "Weekend cook behind slow-cooker soups and cozy dinners."),
    ("Avery Chen", "Fan of noodle bowls, bento ideas, and flexible fridge-friendly meals."),
    ("Maya Robinson", "Community cook specializing in skillet breakfasts and brunch plates."),
    ("Kei Sato", "Recipe creator who turns market produce into low-fuss seasonal dishes."),
]

CUISINE_SLUGS = [
    "japanese",
    "korean",
    "thai",
    "indian",
    "mediterranean",
    "vegetarian",
    "vegan",
    "gluten-free",
    "comfort-food",
    "meal-prep",
]

ADDITIONAL_CATEGORIES = [
    ("Japanese Home Cooking", "japanese", "Community favorites like donburi, curry, soups, and bento sides.", "cuisine", 15),
    ("Korean Kitchen", "korean", "Savory bowls, braises, and pantry-friendly Korean comfort recipes.", "cuisine", 16),
    ("Thai Favorites", "thai", "Noodle bowls, coconut curries, and bright herb-packed dinners.", "cuisine", 17),
    ("Indian Weeknight", "indian", "Simple dal, rice, and skillet meals you can repeat all week.", "cuisine", 18),
    ("Mediterranean", "mediterranean", "Olive oil, grains, seafood, and vegetable-forward recipes.", "cuisine", 19),
    ("Vegetarian", "vegetarian", "Vegetable-led mains, soups, and satisfying meatless lunches.", "meal", 20),
    ("Vegan", "vegan", "Plant-based bowls, noodles, snacks, and desserts.", "meal", 21),
    ("Gluten-Free", "gluten-free", "Recipes with clear substitutions and pantry-safe ingredient choices.", "meal", 22),
    ("Meal Prep", "meal-prep", "Batch-cook lunches, sauces, and make-ahead dinner plans.", "meal", 23),
    ("Comfort Food", "comfort-food", "Cozy braises, baked pasta, and shareable weekend favorites.", "meal", 24),
]

TITLE_PATTERNS = [
    "{main} {style} Bowl",
    "{style} {main} Skillet",
    "{main} and {veg} {style}",
    "{style} {veg} Noodles",
    "{veg} {style} Soup",
    "{main} {veg} Bento",
    "{style} Rice with {main}",
    "{veg} and {main} Plate",
]

MAIN_INGREDIENTS = [
    "Chicken",
    "Salmon",
    "Tofu",
    "Mushroom",
    "Eggplant",
    "Shrimp",
    "Beef",
    "Pork",
    "Chickpea",
    "Spinach",
    "Udon",
    "Soba",
]

VEGETABLES = [
    "Tomato",
    "Broccoli",
    "Eggplant",
    "Carrot",
    "Cabbage",
    "Sweet Potato",
    "Zucchini",
    "Scallion",
    "Corn",
    "Bell Pepper",
    "Snow Pea",
    "Pumpkin",
]

STYLES = [
    "Miso Butter",
    "Soy Ginger",
    "Chili Crisp",
    "Sesame Garlic",
    "Herb Roasted",
    "Coconut Curry",
    "Lemon Pepper",
    "Honey Tamari",
    "Creamy Tomato",
    "Weeknight Pantry",
]

REVIEW_SNIPPETS = [
    "Loved how easy this was to prep after work.",
    "Great balance of flavor and pantry-friendly ingredients.",
    "Added extra scallions and will absolutely make it again.",
    "Perfect for leftovers and lunch boxes the next day.",
    "The instructions were clear and the timing felt realistic.",
    "My family asked for this again before the plates were cleared.",
]


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "-":
            chars.append("-")
    return "".join(chars).strip("-")


def _counts_ok() -> bool:
    return (
        User.query.count() >= EXPECTED_COUNTS["users"]
        and Recipe.query.count() >= EXPECTED_COUNTS["recipes"]
        and Review.query.count() >= EXPECTED_COUNTS["reviews"]
        and RecipeBoxItem.query.count() >= EXPECTED_COUNTS["recipe_box"]
        and MealPlanItem.query.count() >= EXPECTED_COUNTS["meal_plan"]
    )


def _ensure_extra_categories() -> None:
    for name, slug, description, parent_type, order in ADDITIONAL_CATEGORIES:
        if Category.query.filter_by(slug=slug).first():
            continue
        db.session.add(
            Category(
                name=name,
                slug=slug,
                description=description,
                parent_type=parent_type,
                display_order=order,
            )
        )
    db.session.flush()


def _recipe_payload(index: int, category: Category) -> dict[str, object]:
    style = STYLES[index % len(STYLES)]
    main = MAIN_INGREDIENTS[index % len(MAIN_INGREDIENTS)]
    veg = VEGETABLES[index % len(VEGETABLES)]
    title = TITLE_PATTERNS[index % len(TITLE_PATTERNS)].format(main=main, style=style, veg=veg)
    slug = _slugify(f"{title}-{category.slug}-{index + 1}")
    prep = 10 + (index % 6) * 5
    cook = 12 + (index % 7) * 6
    total = prep + cook
    author_name, _ = AUTHOR_PROFILES[index % len(AUTHOR_PROFILES)]
    cuisine_label = category.name if category.parent_type == "cuisine" else category.slug.replace("-", " ").title()
    tags = [
        category.slug,
        CUISINE_SLUGS[index % len(CUISINE_SLUGS)],
        "weeknight" if index % 2 == 0 else "weekend",
        "meal-prep" if index % 3 == 0 else "quick",
        "vegetarian" if main in {"Tofu", "Chickpea", "Mushroom", "Spinach"} else "protein",
    ]
    ingredients = [
        f"2 cups {main.lower()}",
        f"1 cup sliced {veg.lower()}",
        "2 tablespoons olive oil",
        "2 cloves garlic",
        "1 tablespoon soy sauce",
        "1 teaspoon sea salt",
    ]
    instructions = [
        f"Prep the {main.lower()} and {veg.lower()} while heating a skillet over medium heat.",
        f"Cook the base with the {style.lower()} seasoning until glossy and fragrant.",
        "Finish with a quick simmer, taste for balance, and serve warm.",
    ]
    return {
        "title": title,
        "slug": slug,
        "description": f"A deterministic Cookpad-style {cuisine_label.lower()} recipe built for search, saves, meal plans, and step-by-step cooking tasks.",
        "category_id": category.id,
        "cuisine": cuisine_label,
        "image": "/static/images/placeholder.svg",
        "prep_time": f"{prep} mins",
        "cook_time": f"{cook} mins",
        "total_time": f"{total} mins" if total < 60 else f"{total // 60} hr {total % 60} mins",
        "additional_time": "",
        "servings": str(2 + (index % 4)),
        "yield_amount": f"{2 + (index % 4)} servings",
        "calories": 320 + (index % 6) * 35,
        "ingredients_json": json.dumps(ingredients),
        "instructions_json": json.dumps(instructions),
        "nutrition_json": json.dumps({"protein_g": 18 + index % 10, "carbs_g": 22 + index % 12, "fat_g": 12 + index % 7}),
        "tags_json": json.dumps(tags),
        "gallery_json": json.dumps([]),
        "is_featured": index % 18 == 0,
        "is_editors_pick": index % 11 == 0,
        "avg_rating": round(4.1 + (index % 8) * 0.1, 1),
        "review_count": 18 + (index % 20) * 7,
        "author_name": author_name,
        "prep_time_mins": prep,
        "cook_time_mins": cook,
        "total_time_mins": total,
        "ingredient_count": len(ingredients),
        "dietary_tags_json": json.dumps([tag for tag in tags if tag in {"vegetarian", "vegan", "gluten-free"}]),
        "dish_type": "main" if index % 4 else "soup",
        "meal_type": "dinner" if index % 3 else "lunch",
        "cooking_method": "skillet" if index % 2 else "stovetop",
        "main_ingredient": main.lower(),
        "occasion": "Weeknight Favorite" if index % 2 else "Batch Cook",
        "season": ["spring", "summer", "fall", "winter"][index % 4],
        "feature_tags": json.dumps(tags),
        "latest_review_text": REVIEW_SNIPPETS[index % len(REVIEW_SNIPPETS)],
        "storage_instructions": "Store in an airtight container for up to 3 days.",
        "primary_seasoning": style,
        "max_oven_temp": 0,
    }


def _ensure_recipe_volume() -> None:
    categories = Category.query.order_by(Category.display_order.asc(), Category.id.asc()).all()
    current = Recipe.query.count()
    needed = max(0, EXPECTED_COUNTS["recipes"] - current)
    for index in range(needed):
        category = categories[index % len(categories)]
        payload = _recipe_payload(index + current, category)
        if Recipe.query.filter_by(slug=payload["slug"]).first():
            continue
        db.session.add(Recipe(**payload))
    db.session.flush()


def _ensure_review_volume() -> None:
    current_count = Review.query.count()
    if current_count >= EXPECTED_COUNTS["reviews"]:
        return
    needed = EXPECTED_COUNTS["reviews"] - current_count
    users = User.query.order_by(User.id.asc()).all()
    recipes = Recipe.query.order_by(Recipe.id.asc()).all()
    created = 0
    for index, recipe in enumerate(recipes):
        if Review.query.filter_by(recipe_id=recipe.id).count() >= 2:
            continue
        for offset in range(2):
            user = users[(index + offset) % len(users)]
            if Review.query.filter_by(recipe_id=recipe.id, user_id=user.id).first():
                continue
            db.session.add(
                Review(
                    user_id=user.id,
                    recipe_id=recipe.id,
                    rating=4 + ((index + offset) % 2),
                    title=f"{recipe.title} recipe note",
                    body=REVIEW_SNIPPETS[(index + offset) % len(REVIEW_SNIPPETS)],
                    helpful_count=3 + (index % 8),
                )
            )
            created += 1
            if created >= needed:
                return


def _ensure_recipe_box_volume() -> None:
    users = User.query.order_by(User.id.asc()).all()
    recipes = Recipe.query.order_by(Recipe.avg_rating.desc(), Recipe.id.asc()).limit(80).all()
    for index, recipe in enumerate(recipes):
        user = users[index % len(users)]
        if RecipeBoxItem.query.filter_by(user_id=user.id, recipe_id=recipe.id).first():
            continue
        db.session.add(
            RecipeBoxItem(
                user_id=user.id,
                recipe_id=recipe.id,
                notes="Saved for a deterministic Cookpad benchmark flow.",
            )
        )
        if RecipeBoxItem.query.count() >= EXPECTED_COUNTS["recipe_box"]:
            break


def _ensure_meal_plans() -> None:
    users = User.query.order_by(User.id.asc()).all()
    recipes = Recipe.query.order_by(Recipe.total_time_mins.asc(), Recipe.id.asc()).limit(40).all()
    day_labels = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    meal_labels = ["breakfast", "lunch", "dinner", "snack"]
    for user_index, user in enumerate(users):
        for offset in range(6):
            recipe = recipes[(user_index * 6 + offset) % len(recipes)]
            day = day_labels[(user_index + offset) % len(day_labels)]
            meal = meal_labels[(user_index + offset) % len(meal_labels)]
            if MealPlanItem.query.filter_by(user_id=user.id, recipe_id=recipe.id, day=day, meal_type=meal).first():
                continue
            db.session.add(
                MealPlanItem(
                    user_id=user.id,
                    recipe_id=recipe.id,
                    day=day,
                    meal_type=meal,
                )
            )


def _ensure_shopping_lists() -> None:
    users = User.query.order_by(User.id.asc()).all()
    for user_index, user in enumerate(users):
        shopping_list = ShoppingList.query.filter_by(user_id=user.id).first()
        if shopping_list:
            continue
        recipe = Recipe.query.order_by(Recipe.id.asc()).offset(user_index * 3).first()
        items = recipe.get_ingredients()[:6] if recipe else ["olive oil", "garlic", "soy sauce", "greens"]
        shopping_list = ShoppingList(user_id=user.id, name=f"{user.display_name.split()[0]}'s Cookpad List")
        shopping_list.set_items(items)
        db.session.add(shopping_list)


def ensure_seed_data(force: bool, runtime_db_path: Path, seed_db_path: Path, image_root: Path) -> None:
    image_root.mkdir(parents=True, exist_ok=True)

    if force or not _counts_ok():
        db.drop_all()
        db.create_all()
        seed_database()
        seed_benchmark_users()
        _ensure_extra_categories()
        _ensure_recipe_volume()
        _ensure_review_volume()
        _ensure_recipe_box_volume()
        _ensure_meal_plans()
        _ensure_shopping_lists()
        db.session.commit()
        db.session.remove()
        if runtime_db_path.exists():
            seed_db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(runtime_db_path, seed_db_path)
        return

    if runtime_db_path.exists() and not seed_db_path.exists():
        seed_db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(runtime_db_path, seed_db_path)


if __name__ == "__main__":
    with app.app_context():
        ensure_seed_data(
            force=not Path("instance_seed/cookpad.db").exists(),
            runtime_db_path=Path("instance/cookpad.db"),
            seed_db_path=Path("instance_seed/cookpad.db"),
            image_root=Path("static/images"),
        )

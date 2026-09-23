#!/usr/bin/env python3
"""Deterministic verifier for Allrecipes task Allrecipes--15.

dessert <30 min prep, chocolate, >=4 stars + ingredients + steps

Checks (deterministic first, no LLM):
   1. run-package gate (trajectory + screenshots + non-empty answer)
   2. trajectory opened a /recipe/<slug> page from the qualifying set
   3. the answer names the qualifying recipe it opened
   4. the answer states the recipe's on-page facts required by the task
Input/Output: see verify_lib.run / Judge.emit.
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (run, opened_recipe, opened_page, mentions_title,
                        mentions_number, mentions_time, keyword_hit, keyword_hits,
                        mentions_any, nutrition_hits)

# Ground truth frozen from the mirror's own pages (rating/review counts, info
# bar times, ingredient and direction text as rendered on the recipe pages).
GROUND_TRUTH = [
    {
        "slug": "5-minute-chocolate-mug-cake",
        "title": "5-Minute Chocolate Mug Cake",
        "avg_rating": "4.2",
        "review_count": 118,
        "ingredients": [
            "chocolate chips",
            "heavy cream",
            "butter",
            "sugar",
            "vanilla extract",
            "eggs",
            "salt"
        ],
        "steps": [
            "melt chocolate with butter",
            "whip eggs with sugar",
            "fold chocolate mixture into eggs",
            "chill or serve immediately"
        ]
    },
    {
        "slug": "almond-flour-gluten-free-brownies",
        "title": "Almond Flour Gluten-Free Brownies",
        "avg_rating": "4.3",
        "review_count": 86,
        "ingredients": [
            "gluten-free flour",
            "cocoa powder",
            "sugar",
            "butter",
            "eggs",
            "vanilla",
            "baking powder",
            "salt",
            "chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "award-winning-soft-chocolate-chip-cookies",
        "title": "Award-Winning Soft Chocolate Chip Cookies",
        "avg_rating": "5.0",
        "review_count": 271,
        "ingredients": [
            "butter",
            "white sugar",
            "brown sugar",
            "eggs",
            "vanilla extract",
            "all-purpose flour",
            "baking soda",
            "salt",
            "semisweet chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "black-bean-vegan-brownies",
        "title": "Black Bean Vegan Brownies",
        "avg_rating": "4.2",
        "review_count": 127,
        "ingredients": [
            "flour",
            "cocoa powder",
            "sugar",
            "vegan butter",
            "almond milk",
            "vanilla",
            "baking powder",
            "salt",
            "vegan chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "chewy-chocolate-chip-cookies",
        "title": "Chewy Chocolate Chip Cookies",
        "avg_rating": "4.9",
        "review_count": 1759,
        "ingredients": [
            "butter",
            "white sugar",
            "brown sugar",
            "eggs",
            "vanilla extract",
            "all-purpose flour",
            "baking soda",
            "salt",
            "semisweet chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "chocolate-chip-cookies",
        "title": "Chocolate Chip Cookies",
        "avg_rating": "4.8",
        "review_count": 2108,
        "ingredients": [
            "butter",
            "white sugar",
            "brown sugar",
            "eggs",
            "vanilla extract",
            "all-purpose flour",
            "baking soda",
            "hot water",
            "salt",
            "semisweet chocolate chips",
            "walnuts"
        ],
        "steps": [
            "preheat oven to 350 degrees",
            "cream together butter white sugar",
            "beat in eggs one at",
            "dissolve baking soda in hot"
        ]
    },
    {
        "slug": "chocolate-chunk-gluten-free-brownies",
        "title": "Chocolate Chunk Gluten-Free Brownies",
        "avg_rating": "4.2",
        "review_count": 113,
        "ingredients": [
            "gluten-free flour",
            "cocoa powder",
            "sugar",
            "butter",
            "eggs",
            "vanilla",
            "baking powder",
            "salt",
            "chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "chocolate-chunk-vegan-brownies",
        "title": "Chocolate Chunk Vegan Brownies",
        "avg_rating": "4.7",
        "review_count": 54,
        "ingredients": [
            "flour",
            "cocoa powder",
            "sugar",
            "vegan butter",
            "almond milk",
            "vanilla",
            "baking powder",
            "salt",
            "vegan chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "classic-vegan-chocolate-chip-cookies",
        "title": "Classic Vegan Chocolate Chip Cookies",
        "avg_rating": "4.8",
        "review_count": 337,
        "ingredients": [
            "flour",
            "vegan butter",
            "brown sugar",
            "maple syrup",
            "vanilla",
            "baking soda",
            "salt",
            "vegan chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "coconut-flour-gluten-free-brownies",
        "title": "Coconut Flour Gluten-Free Brownies",
        "avg_rating": "4.6",
        "review_count": 28,
        "ingredients": [
            "gluten-free flour",
            "cocoa powder",
            "sugar",
            "butter",
            "eggs",
            "vanilla",
            "baking powder",
            "salt",
            "chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "easy-chocolate-dessert-parfait",
        "title": "Easy Chocolate Dessert Parfait",
        "avg_rating": "4.5",
        "review_count": 89,
        "ingredients": [
            "chocolate pudding",
            "whipped cream",
            "chocolate sandwich cookies",
            "mini chocolate chips",
            "syrup for drizzling"
        ],
        "steps": [
            "spoon a layer of chocolate",
            "top with crushed cookies",
            "repeat the layers finishing",
            "drizzle with chocolate syrup"
        ]
    },
    {
        "slug": "easy-chocolate-truffles",
        "title": "Easy Chocolate Truffles",
        "avg_rating": "4.8",
        "review_count": 103,
        "ingredients": [
            "chocolate chips",
            "heavy cream",
            "butter",
            "sugar",
            "vanilla extract",
            "eggs",
            "salt"
        ],
        "steps": [
            "melt chocolate with butter",
            "whip eggs with sugar",
            "fold chocolate mixture into eggs",
            "chill or serve immediately"
        ]
    },
    {
        "slug": "flourless-vegan-chocolate-chip-cookies",
        "title": "Flourless Vegan Chocolate Chip Cookies",
        "avg_rating": "4.1",
        "review_count": 104,
        "ingredients": [
            "flour",
            "vegan butter",
            "brown sugar",
            "maple syrup",
            "vanilla",
            "baking soda",
            "salt",
            "vegan chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "gluten-free-vegan-brownies",
        "title": "Gluten-Free Vegan Brownies",
        "avg_rating": "4.7",
        "review_count": 120,
        "ingredients": [
            "flour",
            "cocoa powder",
            "sugar",
            "vegan butter",
            "almond milk",
            "vanilla",
            "baking powder",
            "salt",
            "vegan chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "highly-rated-chocolate-chip-cookies",
        "title": "Highly Rated Chocolate Chip Cookies",
        "avg_rating": "4.0",
        "review_count": 76,
        "ingredients": [
            "butter",
            "white sugar",
            "brown sugar",
            "eggs",
            "vanilla",
            "flour",
            "baking soda",
            "salt",
            "chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "no-bake-chocolate-dessert-squares",
        "title": "No-Bake Chocolate Dessert Squares",
        "avg_rating": "4.7",
        "review_count": 206,
        "ingredients": [
            "graham cracker crumbs",
            "butter",
            "dark chocolate chips",
            "sweetened condensed milk",
            "vanilla extract",
            "walnuts"
        ],
        "steps": [
            "combine graham cracker crumbs",
            "melt chocolate with sweetened condensed",
            "stir in vanilla pour over",
            "refrigerate at least 1 hour"
        ]
    },
    {
        "slug": "quick-chocolate-dessert-cups",
        "title": "Quick Chocolate Dessert Cups",
        "avg_rating": "4.6",
        "review_count": 142,
        "ingredients": [
            "dark chocolate chips",
            "heavy cream",
            "powdered sugar",
            "vanilla extract",
            "berries",
            "Chocolate shavings"
        ],
        "steps": [
            "melt the chocolate chips",
            "whip the cream with sugar",
            "fold the whipped cream into",
            "spoon into serving cups top"
        ]
    },
    {
        "slug": "ultimate-vegan-chocolate-chip-cookies",
        "title": "Ultimate Vegan Chocolate Chip Cookies",
        "avg_rating": "4.7",
        "review_count": 168,
        "ingredients": [
            "flour",
            "vegan butter",
            "brown sugar",
            "maple syrup",
            "vanilla",
            "baking soda",
            "salt",
            "vegan chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    },
    {
        "slug": "vegan-oatmeal-chocolate-chip-cookies",
        "title": "Vegan Oatmeal Chocolate Chip Cookies",
        "avg_rating": "4.9",
        "review_count": 80,
        "ingredients": [
            "flour",
            "vegan butter",
            "brown sugar",
            "maple syrup",
            "vanilla",
            "baking soda",
            "salt",
            "vegan chocolate chips"
        ],
        "steps": [
            "prepare ingredients as listed",
            "follow the standard cooking method",
            "serve and enjoy"
        ]
    }
]

def body(j, traj, ans):
    slugs = [r["slug"] for r in GROUND_TRUTH]
    opened = opened_recipe(traj, slugs)
    j.check("opened_qualifying_recipe_detail", bool(opened),
            f"opened={[s for s in opened]}")
    named = [r for r in GROUND_TRUTH
            if r["slug"] in opened and mentions_title(ans, r["title"])]
    j.check("answer_names_opened_recipe", bool(named),
            f"named={[r['title'] for r in named]}")
    best = [r for r in named
            if keyword_hits(ans, r["ingredients"]) >= 4 and keyword_hits(ans, r["steps"]) >= 2]
    j.check("answer_states_recipe_facts", bool(best),
            f"facts_ok={[r['title'] for r in best]}")

if __name__ == "__main__":
    run("Allrecipes--15", body)

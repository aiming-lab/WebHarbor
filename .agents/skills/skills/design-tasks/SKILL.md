---
name: design-tasks
description: "Phase 2: Design 15-20 benchmark tasks for a WebHarbor mirror site and write them into sites/<site>/tasks.jsonl (one JSON object per line, WebVoyager-compatible schema). Tasks must cover the site's full functional breadth (search, browse, cart, checkout, account management, etc.) and include tasks that frontier models cannot easily solve. Use after clone-website to define what the environment must support."
---

# Design Tasks — Benchmark Task Construction

## When to use

- After Phase 1 (clone-website) to define the task set
- When enriching an existing site with new tasks
- When adapting tasks from WebVoyager / Online-Mind2Web to a mirror

## Output format: `sites/<site>/tasks.jsonl`

WebHarbor uses the WebVoyager schema, one JSON object per line:

```jsonl
{"web_name": "Amazon", "id": "Amazon--0", "ques": "Search an Xbox Wireless controller with green color and rated above 4 stars.", "web": "http://localhost:40001/", "upstream_url": "https://www.amazon.com/"}
{"web_name": "Amazon", "id": "Amazon--1", "ques": "Search for women's golf polos in M size, priced between 50 to 75 dollars, and save the lowest-priced result.", "web": "http://localhost:40001/", "upstream_url": "https://www.amazon.com/"}
```

Required fields:
- `web_name` — display name of the site (PascalCase, e.g. `"Amazon"`, `"BBC News"`)
- `id` — unique task ID, format `<web_name>--<index>`
- `ques` — the natural-language task instruction the agent will see
- `web` — local mirror URL, `http://localhost:<port>/`
- `upstream_url` — the real-site URL the mirror clones (for reference)

## Design principles

### 1. Functional breadth

Tasks must cover the site's FULL feature surface, not just one flow. Example for an Amazon-like site:

| Category | Example task |
|---|---|
| Search & filter | "Find a wireless mouse under $30 with 4+ stars" |
| Product detail | "What is the battery life of the Sony WH-1000XM5?" |
| Cart & checkout | "Add the cheapest USB-C hub to your cart and proceed to checkout" |
| Account | "Change the shipping address to 123 Main St, Denver, CO" |
| Order history | "Find the tracking number for your most recent order" |
| Payment | "Add a new Visa card ending in 4242" |
| Reviews | "How many 1-star reviews does the Kindle Paperwhite have?" |
| Comparison | "Which laptop has more RAM: MacBook Air or ThinkPad X1?" |

Aim for ≥3 distinct functional areas with 4-6 tasks each.

### 2. Difficulty spectrum

- **Easy** (2-3 steps): "Find the customer service phone number"
- **Medium** (4-6 steps): "Search for hiking boots, filter by size 10, find one under $100"
- **Hard** (7+ steps): "Compare 3 laptops by price, RAM, and battery life, then add the best value to cart"
- **Frontier-challenging**: multi-step reasoning, visual comparison, disambiguation

At least 3-5 tasks should require ≥5 steps.

### 3. Disambiguation tasks

Tasks where the user has multiple items and the agent must ask for clarification:

**Good** (forces clarification):
- "Cancel my recent order" (user has 2+ orders)
- "Remove a saved recipe" (user has 5 recipes — which one?)
- "Complete checkout" (user has 2+ payment cards)
- "Export my papers" (multiple formats: BibTeX, EndNote, RIS)

**Bad** (agent can guess):
- "Add a recipe to Recipe Box" (any item works)
- "Buy headphones" (any model works)

### 4. Ground truth

The expected answer must be verifiable against the DB. WebHarbor's grounded
truth checks live in the evaluation harness, not in `tasks.jsonl`. The
mirror DB must contain a single unambiguous answer for each task (modulo
disambiguation tasks).

## Task sources

### Adapt from existing benchmarks
If the site appears in WebVoyager or Online-Mind2Web, copy those tasks
verbatim into `tasks.jsonl` and verify they work against your mirror.

### LLM-generated
Prompt an LLM:

```
Design 20 benchmark tasks for a local mirror of {website}. The mirror supports
{list routes and capabilities}. Use this format (one JSON object per line):

{"web_name": "<Name>", "id": "<Name>--<i>", "ques": "<task>", "web": "http://localhost:<port>/", "upstream_url": "<real_url>"}

Tasks must:
1. Cover ≥5 distinct functional areas
2. Range from 2-step (easy) to 7+ step (hard)
3. Include 3+ multi-step reasoning tasks
4. Have specific, verifiable answers
5. Include 2+ disambiguation tasks
```

### Manual design
Browse the real site and design tasks based on real user workflows.

## Verification

For each task in `tasks.jsonl`, hand-walk it through the mirror to confirm:
- The natural search query for the task returns at least 6 results
- The correct answer exists in the DB
- The answer is NOT visible at the search-result level (must require detail page)
- For disambiguation tasks, the user has ≥2 ambiguous items

## Next step

Proceed to **evolve-env** (Phase 3) to evolve the environment to support all tasks.

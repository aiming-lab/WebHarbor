---
name: evolve-env
description: "Phase 3: Task-driven environment evolution. Feed tasks.jsonl to a coding agent and evolve sites/<site>/ to support each task — add routes, templates, seed data, form handlers on demand. Watch for and fix common agent pitfalls: task info leaks, superficial completion, and insufficient distractors. The byte-identical reset invariant must still hold after every change."
---

# Evolve Environment — Task-Driven Evolution

## When to use

- After Phase 2 (design-tasks) when `sites/<site>/tasks.jsonl` is defined
- When evolving an existing mirror to support new, harder tasks

## Process

### Drive the browser with Playwright — NOT curl

Every "walk the task", "use the site", "submit the form" step in this skill **must** be done by driving a real Chromium via Playwright. `curl`, `requests`, Flask's `test_client`, and reading templates by eye all miss JS, client-side validation, route guards, hidden CSRF fields, async redirects, and the actual rendered DOM the agent will see. The whole point of WebHarbor is multimodal browser interaction — verify it that way.

Minimum recipe (use the `agent_demo/` env which already has Playwright + Chromium installed via `uv sync`):

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("http://localhost:41000/")        # use ALT ports of your test container
    page.fill('input[name="q"]', "guardians of the galaxy 3")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    page.screenshot(path="/tmp/check_search.png", full_page=True)
    print(page.title(), page.url)
    print(page.content()[:3000])                # rendered DOM — search this for leaks
    browser.close()
```

Capture at least one screenshot per task / per verification check. `curl` is fine **only** for control-plane endpoints (`/health`, `/reset`, `/reset-all`) and bare HTTP-200 sweeps; never for interactive verification.

### Step 1: Walk each task through the mirror

For each task in `sites/<site>/tasks.jsonl`:

1. Open the mirror locally (`./scripts/build.sh && docker run ...`)
2. Walk the task in a real Chromium via Playwright (see the recipe above); save a screenshot at each step
3. If you can complete it, great. If not, identify what's missing:
   - Missing routes? (e.g. no `/checkout` page)
   - Missing templates? (e.g. no review submission form)
   - Missing seed data? (e.g. only 2 products match the query)
   - Missing form handlers? (e.g. POST submits but doesn't persist)

### Step 2: Extend the mirror

Make changes in `sites/<site>/`:

- **New routes** → add to `app.py`
- **New templates** → add to `templates/`
- **New seed data** → extend `seed_data.py` (with idempotent gates!)
- **New form handlers** → add POST routes with proper validation

Use `Edit` / `Write` for changes — don't `sed`. Path references must go
through `BASE_DIR = os.path.dirname(os.path.abspath(__file__))`.

### Step 3: Re-seed and verify

After any DB-affecting change:

```bash
# 1. Stop test container (don't touch user's working container on :40000-40014)
docker stop wh-test 2>/dev/null || true

# 2. Rebuild
./scripts/build.sh webharbor:dev

# 3. Run on alt ports
docker run -d --rm --name wh-test \
  -p 8201:8101 -p 41000-41014:40000-40014 webharbor:dev

# 4. Reset your site and confirm byte-identity
curl -X POST http://localhost:8201/reset/<your_site>
docker exec wh-test md5sum \
  /opt/WebSyn/<your_site>/instance/<your_site>.db \
  /opt/WebSyn/<your_site>/instance_seed/<your_site>.db
# the two md5s MUST match
```

If byte-identity fails: a seed function isn't idempotent. Gate the whole
function (not per-row). See `seed-database` skill for details.

## Common agent pitfalls

Coding agents consistently produce three categories of problems. Check each:

### Pitfall A: Task information leak

The agent makes the task trivially easy by exposing the answer.

Examples:
- Task "find a 10x zoom camera" → product named "Canon ELPH 360 (12x Zoom)"
- Task "how many courses in X?" → heading shows `<p>4 courses</p>`
- Task "find the cheapest laptop" → only one laptop in the DB
- Task "what's the role of feature X?" → page literally says "The role of X is..."

**Detect**: drive the task's natural search query in Playwright, capture `page.content()` (the rendered DOM) and a full-page screenshot of the search results page, then grep that DOM for the answer string. If the answer appears there without clicking a detail page, it's a leak. Reading the Jinja template by eye is NOT a substitute — client-side JS may inject the answer.

**Fix**: see the `harden-env` skill for systematic de-leaking.

### Pitfall B: Superficial completion

Pages that pass automated checks but fail under real interaction.

Signs:
- Forms with fields that don't validate or don't persist to DB
- Search returns only exact string matches (fails on "Boston Celtic")
- Checkout always succeeds without address/payment validation
- Placeholder text ("Lorem ipsum", "Description coming soon")
- Broken `<img>` tags or colored rectangles

**Detect**: drive the site through Playwright (see recipe above). Submit empty forms, submit malformed input, search partial queries ("Boston Celtic"), browse 5+ detail pages, log in then reload. Confirm persistence by re-`goto`-ing the page and grepping the rendered DOM. Reading routes / templates statically does NOT count.

**Fix**: implement scored token-overlap search (not strict AND), validate
forms, persist state. See `_health.py` patterns in existing sites for examples.

### Pitfall C: Insufficient distractors

The DB only contains items satisfying task constraints.

Example:
- Task "buy an iPhone 17" → DB has only iPhones, no Samsung/Pixel/OnePlus

**Detect**: run the search query for each task. Count full matches vs near
misses. If >50% are full matches, you need more distractors.

**Fix**: seed diverse items that share the category but differ in
attributes. See `harden-env` for the systematic recipe.

## Seed data guidelines

- Use `@test.com` for all test user emails
- Seed 4 benchmark users: `alice.j@test.com`, `bob.c@test.com`,
  `carol.d@test.com`, `david.k@test.com` with password `TestPass123!`
- Give each pre-existing cart/bookmark/order data for auth-gated tasks
- After ANY DB change, regenerate `instance_seed/<site>.db` (run the site
  once locally, then `cp instance/<site>.db instance_seed/<site>.db`)
- Verify byte-identical reset before opening a PR

## Output

After Phase 3:
- Every task in `tasks.jsonl` is hand-verified to work end-to-end
- The mirror has no obvious leaks, broken forms, or empty pages
- Byte-identical reset passes
- All 15 sites still return 200

## Next step

Proceed to **harden-env** (Phase 4) for systematic de-leaking and difficulty hardening.

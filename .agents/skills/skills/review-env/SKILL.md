---
name: review-env
description: "Review pipeline for WebHarbor mirror PRs. Systematically verify visual fidelity, functional depth, byte-identical reset, and task quality of a submitted mirror site. Catches agent shortcuts (answer leaks, single-item catalogs, broken forms, placeholder images) that automated checks miss. Use when reviewing a GitHub PR + paired HF assets PR."
---

# Review Environment — Quality Verification Pipeline

## When to use

- Reviewing a GitHub PR that adds or modifies a website mirror
- Auditing an existing mirror for quality issues
- Verifying that hardening fixes actually resolved the problems

## Prerequisites

- The PR contributor has completed Phases 1-5 (clone → design → evolve → harden → seed)
- There is a paired PR on the HF dataset (`ChilleD/WebHarbor`)
- `.assets-revision` in the GitHub PR points to a real HF merge SHA

## Pipeline overview

### Step 1: Check out and build

```bash
gh pr checkout <pr-number>
./scripts/fetch_assets.sh             # pull the pinned HF revision
./scripts/build.sh webharbor:dev
docker run -d --rm --name wh-review \
  -p 8201:8101 -p 41000-41014:40000-40014 webharbor:dev
```

Confirm the new/changed site is on the expected port (40000 + index).

### Step 2: The mechanical checks (5 minutes)

Run the same Pre-PR checks the contributor was supposed to run.

```bash
# 1. all 15 sites return 200
for p in $(seq 41000 41014); do
  curl -so /dev/null -w "$p:%{http_code}\n" http://localhost:$p/
done

# 2. control plane healthy
curl -s http://localhost:8201/health | python3 -m json.tool | head

# 3. byte-identical reset on the touched site
curl -X POST http://localhost:8201/reset/<site>
docker exec wh-review md5sum \
  /opt/WebSyn/<site>/instance/<site>.db \
  /opt/WebSyn/<site>/instance_seed/<site>.db
# md5s MUST match

# 4. parallel reset still works for everyone
time curl -X POST http://localhost:8201/reset-all
```

If any of these fail, request changes; don't bother with the deeper review yet.

### Drive review with Playwright — NOT curl

Steps 3, 4, and 5 below MUST be performed by driving a real Chromium via Playwright. `curl | grep` and Flask `test_client` are not acceptable for visual / functional / task-quality review — they miss JS-rendered cards, client-side validation, async loads, and the actual DOM the benchmark agent will see. Use the `agent_demo/` env (it already has Playwright + Chromium installed via `uv sync`):

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("http://localhost:41001/")          # the site under review, alt port
    page.wait_for_load_state("networkidle")
    page.screenshot(path="/tmp/home.png", full_page=True)
    page.fill('input[name="q"]', "iphone")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    page.screenshot(path="/tmp/search.png", full_page=True)
    print(page.content()[:3000])                   # grep this for answer leaks
    browser.close()
```

Save every screenshot you capture; they go into the review comment as evidence. `curl` is only for control-plane endpoints (`/health`, `/reset`, `/reset-all`) and HTTP-200 sweeps.

### Step 3: Visual fidelity (10 min)

Open the mirror at `http://localhost:41000+i/` (via Playwright `page.goto` — see recipe above) and the real website side by side.

| Check | What to verify |
|---|---|
| Homepage layout | Header, nav, hero, cards, footer match the real site |
| Navigation | All top-level links work, no 404s |
| Real images | Product/article/profile images are real (not placeholders, not colored rectangles) |
| Detail pages | Open 5+ random detail pages; layout matches, content populated |
| Typography | Fonts and colors close to original (not pixel-perfect, but same brand feel) |
| Responsive | Resize to 768px — layout adapts, no overflow |

Capture side-by-side screenshots for your review comment.

### Step 4: Functional depth (15 min)

Actually drive the site through Playwright — `page.fill` / `page.click` / `page.reload` / `page.content()`. Capture a screenshot for each check below.

| Check | How to test |
|---|---|
| Login | `alice.j@test.com` / `TestPass123!` → redirects to account, shows user name |
| Register | Create a new account, can log back in |
| Search | Try 3+ queries including multi-word ("Boston Celtic players") |
| Browse | Click 3+ categories; pages load with populated content |
| CRUD: add | Cart/bookmark/favorite an item; reload page; it persists |
| CRUD: remove | Remove the item; count updates, item gone |
| Forms | Submit review/contact/checkout; validates input, persists to DB |
| Account edit | Change display name; persists after reload |

### Step 5: Task quality audit (the most important part, 20-30 min)

For EACH task in `sites/<site>/tasks.jsonl`:

#### Solvability
- Can you actually complete the task using only the mirror's UI?
- Does the expected answer exist in the environment?

#### Answer-leak detection
Perform the task's natural search query. Check:
- Answer NOT visible in search result titles/cards
- Answer NOT pre-computed in headings or callout boxes
- Answer requires clicking into a detail page
- Count-based answers don't have count labels visible

If you solve the task from the search-results page alone, it's a **leak**.

#### Distractor check
On the search results for each task's query:
- ≥6 total results
- ≤50% are full matches (satisfy ALL task constraints)
- Near-miss items exist (match category, fail one constraint)
- Results come from multiple sub-categories

If every result satisfies the task, the catalog is **too narrow**.

#### Difficulty assessment
- ≥3 tasks require ≥5 agent actions
- ≥2 tasks involve multi-step reasoning or comparison
- ≥1 task would challenge a frontier model (GPT-4o / Claude)
- No task solvable by clicking the first result

### Step 6: Common agent pitfalls

Based on 15+ mirror reviews:

| # | Issue | Quick check |
|---|---|---|
| 1 | Task constraint values in product/item names | Search each constraint term, see if it appears in card titles |
| 2 | Single-item catalog for task targets | Count unique items matching each task category |
| 3 | Strict-AND search | Search a multi-word query ("Boston Celtic") — must return results |
| 4 | Placeholder images | Scroll listing pages, spot-check 10 items |
| 5 | Forms that don't validate | Submit empty form, submit malformed email |
| 6 | Pre-sorted results revealing answer | Check if answer is always at position #1 |
| 7 | Inconsistent specs across fields | Compare specs table vs description vs features on a detail page |
| 8 | Missing auth-gated features | Log in, try cart/checkout/bookmarks/order-history |
| 9 | Count labels next to lists agent should count | Look for "N items", "N results", "N courses" |
| 10 | Cross-imports between sites | Grep for `from sites.<other>` (sites must be isolated) |

### Step 7: Asset PR check

Verify the paired HuggingFace PR is real:

```bash
cat .assets-revision
# revision: <some-sha>

# go to https://huggingface.co/datasets/ChilleD/WebHarbor/commit/<sha>
# confirm: that commit exists, is merged, and contains the expected assets
```

If `.assets-revision` doesn't match a real HF merge SHA, request changes.

### Step 8: Submit review

Leave a structured comment on the PR:

```markdown
## Review: <site_name>

### Mechanical checks: PASS / FAIL
- [x] All 15 sites return 200
- [x] Control plane healthy
- [x] Byte-identical reset (md5 match)
- [x] Parallel reset <10s
- [x] HF revision SHA verified

### Visual fidelity: PASS / FAIL
- [x] Layout matches real site
- [x] Real images, no placeholders
- [ ] Footer links broken → /about returns 404

### Functional depth: PASS / FAIL
- [x] Auth flows work
- [x] Search returns scored results
- [ ] Checkout form doesn't validate payment

### Task quality: PASS / FAIL
- Task 3: LEAK — "iPhone 17 Pro" appears in search card title
- Task 7: TOO EASY — only 2 results match the query
- Task 12: GOOD — requires 6-step comparison

### Required fixes before approval:
1. De-leak task 3: strip "Pro" from product card title
2. Add 10+ distractor phones for task 7
3. Fix /about 404
4. Add payment validation in checkout

### Screenshots:
[attach side-by-side and issue screenshots]
```

## Reviewer authorship

Reviewing **5 environments** with thorough checklist reports earns a spot
on the final paper's author list. Quality matters: a review that says
"looks good" without evidence doesn't count.

## Teardown

```bash
docker stop wh-review
```

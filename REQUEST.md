I want to contribute a new website mirror to WebHarbor.

        Target site: https://www.ycombinator.com     # e.g. https://www.target-site.com/
        Site slug:   y_combinator         # e.g. target_site (lowercase, snake_case)
        
        Follow the WebHarbor contribution pipeline end-to-end using the local skills under .claude/skills/. Specifically:
        
        Phase 1 — Use the `clone-website` skill:
          - Run ./scripts/new_site.py <SLUG> to scaffold sites/<SLUG>/
          - Register the site in websyn_start.sh, control_server.py, Dockerfile
          - Scrape structure, harvest real assets (no placeholders), build the Flask + SQLAlchemy app
          - Replicate the frontend with Jinja2 templates matching the original site
          - Seed an initial idempotent DB (seed_database + seed_benchmark_users with alice.j@test.com et al.)
        
        Phase 2 — Use the `design-tasks` skill:
          - Write 15-20 benchmark tasks to sites/<SLUG>/tasks.jsonl
          - Cover the site's full functional breadth (search, browse, cart, checkout, account, etc.)
          - Include 3-5 hard tasks that require multi-step reasoning
          - Use the WebVoyager schema: {web_name, id, ques, web, upstream_url}
        
        Phase 3 — Use the `evolve-env` skill:
          - Manually walk through each task; extend the mirror to support it
          - Detect and fix task info leaks, superficial completion, insufficient distractors
        
        Phase 4 — Use the `harden-env` skill:
          - Audit every task against the 4 hardening dimensions (de-leak / distractors / catalog breadth / cross-field consistency)
          - Check the 13 known leak archetypes
          - Re-verify byte-identical reset
        
        Phase 5 — Use the `seed-database` skill:
          - Confirm all seed_*() functions are idempotent at the function level
          - Stabilize instance_seed/<SLUG>.db (boot-and-freeze cycle until md5 matches)
          - Implement scored token-overlap search if not already
        
        Verification (after each phase and at the end):
          ./scripts/build.sh webharbor:dev
          docker run -d --rm --name wh-test -p 8201:8101 -p 41000-41014:40000-40014 webharbor:dev
          curl -X POST http://localhost:8201/reset/<SLUG>
          docker exec wh-test md5sum /opt/WebSyn/<SLUG>/instance/<SLUG>.db /opt/WebSyn/<SLUG>/instance_seed/<SLUG>.db
          # the two md5s MUST match
        
        Stop before opening the PR. Print a summary of:
          - Files added / modified
          - Number of seeded rows per major model
          - Tasks count in tasks.jsonl
          - Byte-identical reset confirmation
          - Anything that needs human review or fixing
          - Detailed steps how to finally submit the PR (HuggingFace assets PR + GitHub PR + .assets-revision bump) 
        
        
        DO NOT STOP UNLESS YOU FINISH ALL THE STEPS. THE WHOLE TASK CAN BE HOURS OF WORK, SO BE PATIENT AND PERSISTENT. IF YOU ENCOUNTER AN ERROR, FIX IT AND KEEP GOING.
        
        I will review your output and then drive the PR submission myself (HuggingFace assets PR + GitHub PR + .assets-revision bump)

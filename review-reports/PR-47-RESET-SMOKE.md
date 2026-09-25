# Review of PR #47: reset and smoke verification

Reviewer-owned continuation of [PR #47](https://github.com/aiming-lab/WebHarbor/pull/47)
by @Lxr-max / XuanRui LI. The contributor commit and later reviewer fixes remain in history.

## Current synchronization — 2026-09-25

- Upstream main: `b3275d75fdfcfea6ca142ddd59e20b7e4cb3d454`.
- Pre-sync candidate: `d660caf15e58d6ce08cc32a976c54fcc5ff7e1af`.
- Current registry: 94 sites, ports 40000–40093.

The main branch now authenticates its control endpoints. The checker reads
`WEBSYN_CONTROL_TOKEN` from the environment and sends a bearer header to `/health`,
`/reset/<site>`, and `/reset-all`. It never sends that header to site homepages and
rejects authenticated redirects. Invalid token values fail with structured output
before any request; an incorrect token cannot produce reset or DB-parity success.

The existing DB-source and reset semantics remain: `--docker-container` reads the
running deployment, `--db-root` reads an explicit host tree, and no source means
parity `SKIP`. A failed reset also skips parity. Registry and filesystem errors
remain structured; homepage redirects may succeed when they reach an actual page.

Usage moved to [docs/reset-smoke.md](../docs/reset-smoke.md); the root README matches upstream.
A local variable rename and test assertions remove pre-existing type-check errors.

## Current validation

```bash
python3.12 -B -m unittest discover -s scripts -p 'test_check_reset_smoke.py' -v
pyright scripts/check_reset_smoke.py scripts/test_check_reset_smoke.py
ruff check scripts/check_reset_smoke.py scripts/test_check_reset_smoke.py
python3.12 -B scripts/check_site_registry.py
```

- **30/30 tests PASS**, including the 26 existing tests and four new authentication tests
  with subcases. The authentication tests exercise actual loopback HTTP servers.
- Positive checks cover per-site/global reset authentication and no header on the homepage.
- Negative checks cover cross-endpoint redirects, short/non-ASCII/header-injection tokens,
  and HTTP 401 with no false reset/parity success.
- Pyright: 0 errors; Ruff lint: PASS; upstream registry check: all 94 sites consistent.
- Reviewer-delta whitespace/conflict checks: PASS.

The tests were first executed without the authentication implementation and failed;
they pass after the scoped compatibility repair.

## Evidence scope and limits

The earlier independent review returned 14/14 PASS for the changed branches at `d660caf`;
that historical result does not certify the new authentication delta. A fresh independent
review of that delta remains a follow-up; no new blind-review PASS is claimed here.
Earlier live-container evidence covered two representative sites. The current tests use
loopback HTTP and temporary files, plus injected Docker boundaries for existing tests;
no full 94-site live smoke, Docker build, or container launch was performed this round.

There is no site/runtime, task, verifier, Dockerfile, or asset delta against current main.
No HF PR is needed. Podman and remote Docker daemons remain untested. A `--db-root`
verdict concerns only the supplied root; homepage smoke checks status, not page content.
Final approval and merge remain with the maintainer.

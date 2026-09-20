# Cookpad integration review — 2026-09-18

## History and scope

This continuation preserves the actual heads of original PR [#52](https://github.com/aiming-lab/WebHarbor/pull/52)
(`85362cff012b5684224234c917b97d99f0a0f38d`) and reviewer PR
[#78](https://github.com/aiming-lab/WebHarbor/pull/78)
(`2d0570eba69e9f7db05be09b81a9d4fdc971e562`), followed by repair commit
`c12c5e7`. The original head was not an ancestor of the rebased reviewer branch;
explicit normal merges preserve both contributions and attribution.

The 180-entry partly fabricated catalogue is replaced with 60 source-backed
Cookpad recipes, 60 corresponding main photos and two source brand images.
Source facts and unknown values are preserved; saves are not ratings.
Locally curated collections and synthetic benchmark accounts/state are disclosed.
Search, layouts, author identity, CSRF, ownership and restart behavior are fixed.
All 19 tasks, rubrics and snapshot-only verifiers are aligned with this fixture.
Task prompts remain natural-language requests without mandatory JSON output.

Cookpad is appended at index 40 / port 40040. Existing ports and unrelated site
code/assets are preserved. Runtime behavior is unchanged from the reviewed fix,
apart from the standalone default port. Integration adds an exact image inventory
gate and updates the legacy health-probe recipe URL.

## Merged HF dependencies

1. Original [HF PR #35](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/35)
   merged at `3a2f55fd31b6994edd36745a68e3991e3f0bcb45`.
2. Replacement [HF PR #99](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/99)
   merged at `5e17eadcc767a4e02541030d0f86dff25f4004f1`.

The latter is pinned as `site.cookpad` in `.assets-revision`; existing site pins
are unchanged. All unrelated dataset file blob IDs were checked unchanged.
The archive was downloaded again from its merged revision and SHA-256 verified:

```text
cookpad.tar.gz  38802e2c7898c7005c67f59973f17d9472023ce7eca5deda13476602dab85c10
cookpad.db     219f10b5e4f99751998c42e34717dcc4b57c5fa54ed624057f2b4bff322a5b20
```

## Executed validation

Runtime candidate: `2c82ddea04581c68a5cbedc0e3376847d3fbf086`.
The subsequent report-only commit does not change runtime files.

| Check | Result |
|---|---|
| Fresh pinned asset fetch into isolated integration worktree | 41 site archives validated and extracted |
| Registry, syntax, whitespace | Passed; 41 sites, ports 40000–40040 |
| Full `scripts/build.sh webharbor:pr78-integrated` | Passed; Python 3.12, 5.35 GB local image |
| Control-plane health | 41/41 alive and ready |
| Every site's homepage | 41/41 HTTP 200 |
| Cookpad UI removal followed by restart | Edit persisted; seed unchanged |
| Cookpad reset | Runtime and original seed byte-identical |
| Runtime/source/startup unit tests in integrated image | 12/12 passed |
| Verifier unit methods in integrated image | 9/9 passed |
| Official main evaluator regrade of preserved task evidence | 19/19 passed |
| Synthetic grading controls rerun against integrated fixture | 129/129 expected outcomes, no false accepts/rejects in this suite |
| Focused desktop/mobile browser regression | Seven captured states, no broken images, document overflow or browser/HTTP errors |
| Four public routes compared with reviewed preview | Identical after removing per-request CSRF values |

The image ID is
`sha256:914456b1b19a0ab3a49e7f6784d2800cf786197f4d34ad3b2cae618ff51cc2b1`.
The temporary 41-site test container was stopped; existing previews remain.

## Evidence and limits

The original corrected review contains 19 scripted Chromium task paths and GIFs:
215 recorded steps = 180 task actions + 35 viewport checks. Every path has more
than five task actions. These are known-target scripted regressions, not independent
LLM-agent attempts. Integration regrading reuses those immutable browser records;
it does not claim 19 new browser attempts. Natural-answer parsing is bounded, not
general semantic understanding. No secondary LLM judge was configured or run.

Local detailed review and dashboard: `WebHarbor-fix-pr78/.assets/reviews/pr78-fix/`
(`REPORT.md`, `ledger.json`, `runs-complete/`, `index.html`). Integration receipts,
fetch/build logs, independent verdicts and screenshots:
`WebHarbor-integrate-pr78/.assets/integration/`. Large local recordings are not
included in the source PR. Dashboard: http://localhost:43818/; preview:
http://localhost:44818/ (forward those ports when accessing remotely).

HF assets are published and merged. Docker Hub publication and deployment are
separate stages and were neither requested nor performed.

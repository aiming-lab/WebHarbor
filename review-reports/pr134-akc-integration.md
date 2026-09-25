# AKC integration: PR #40 → PR #134 → reviewed fixes

The AKC mirror now grades correctly bound facts and exact account mutations,
returns real search results, completes signed-out breed saves through login, and
labels breed traits correctly. Tasks 4 and 6 require a multi-page event plan and
a three-article reading comparison; their questions, rubrics and verifiers agree.

## History and scope

- Original contribution: #40 (`bbf9755fa83daa13e68a26cd59441e8582ae005a`).
- Reviewer continuation: #134 (`3eabda0cfe495ad94c3a374553b9eedbef83b8f9`).
- Reviewed fixes: `ffbea25` and difficulty revision `a94b45a`.
- Combined runtime candidate tested: `b1e0d7391e3e63d371a40581ab40b823b0460229`.
- Integration preserves all three histories in dependency order. Conflicts retain
  current main's shared tooling and all unrelated website code.
- AKC is appended at container port **40058**. All 58 existing ports remain stable.
  Startup registry, control-plane registry, Docker EXPOSE and all task URL ports
  agree across 59 sites. The root README changes only in its Websites table.

## Hugging Face assets

HF [#97](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/97) was
merged and independently verified. `.assets-revision` and `assets-manifest.json`
pin immutable merged revision `b9498ac48659844c7160d88845033a3fab5e1cbb`.

- AKC archive SHA-256: `a9a5f04d6bdc243b2714c5a056b31d3b134bdf8fed93a74db761f40feb301b36`.
- Seed SHA-256: `3910bdaef81e20cbdc6bd39a33c6019a56f4e2769e1b8e8001ba59b9c396b727`.
- The reviewed archive was unchanged; no archive was reformatted or repacked.
- All 61 pre-existing dataset files were preserved.
- A fresh fetch/extraction and digest verification covered the combined 59-site
  asset set. Every prior archive hash remains unchanged in the updated manifest.

## Validation

Runtime validation is scoped to AKC as requested by the user on 2026-09-22.
Unrelated site browser flows and homepages were not retested during integration.

- AKC syntax, 11 Flask tests and 23 verifier test methods pass.
- All 103 declared grading controls match expectations: 26 valid completions
  accepted and 77 invalid completions rejected. These are targeted synthetic
  controls, not a measured general grader error rate.
- Full combined Docker image build passes: `webharbor:pr134-integration`.
  Image ID: `sha256:ca6ececf4971d0b4640dec06b0839d86759a2664ae48ef6f04867cee8822a111`.
- Image source hashes match the integrated AKC code, tasks, templates and verifiers.
- AKC health and homepage pass on its registered port. Startup, dirty-state reset
  and restart preserve byte-identical seed/runtime databases.
- All 13 fresh scripted Playwright task runs against that container complete and
  pass the official deterministic evaluator. The runs record real UI actions;
  they are not autonomous LLM-agent runs. No secondary LLM judge was configured.
- Registry uniqueness, all task URL ports and preservation of existing site ports
  pass. All unrelated website source files remain identical to the starting main.
- The owned test container/network were removed. No Docker image publication or
  deployment is part of this integration.

## Evidence

Integration logs, snapshots, browser trajectories and official verdicts:
`/data/pr134-integration-evidence` in the review workspace.

The earlier [GIF dashboard](http://localhost:44988/) remains available on forwarded
port 44988. Its recordings precede integration; the integration evidence above
contains the fresh container runs. Original audit and fixed previews remain intact.

| Task | Fresh container actions | Primary verifier |
|---|---:|---|
| AKC--0 | 8 | PASS |
| AKC--1 | 12 | PASS |
| AKC--2 | 7 | PASS |
| AKC--3 | 6 | PASS |
| AKC--4 | 9 | PASS |
| AKC--5 | 6 | PASS |
| AKC--6 | 10 | PASS |
| AKC--7 | 8 | PASS |
| AKC--8 | 11 | PASS |
| AKC--9 | 7 | PASS |
| AKC--10 | 11 | PASS |
| AKC--11 | 10 | PASS |
| AKC--12 | 11 | PASS |

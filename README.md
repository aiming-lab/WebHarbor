<div align="center">

<h1>⚓ WebHarbor</h1>
<h3>Docking Real Websites for Evolving GUI Agent Environments</h3>

<p>
  <a href="https://huggingface.co/datasets/ChilleD/WebHarbor">
    <img src="https://img.shields.io/badge/🤗-Dataset-yellow.svg" alt="HuggingFace Dataset" />
  </a>
  <a href="https://docs.google.com/spreadsheets/d/1vZsrQjy9nJKze58fx4kbQtFi85NjVXIWCFyu3ShD7gk/edit?gid=0#gid=0">
    <img src="https://img.shields.io/badge/📊-Track%20Sheet-blue.svg" alt="Contribution Track Sheet" />
  </a>
  <a href="https://forms.gle/ngcD1rzAfUEphNmRA">
    <img src="https://img.shields.io/badge/📝-Request%20Form-green.svg" alt="Contribution Request Form" />
  </a>
  <a href="https://aiming-lab.github.io/webharbor.github.io/">
    <img src="https://img.shields.io/badge/🏠-Project%20Page-orange.svg" alt="WebHarbor Project Page" />
  </a>
  <a href="https://github.com/aiming-lab/WebHarbor">
    <img src="https://img.shields.io/badge/💻-Code%20Repo-black.svg" alt="WebHarbor GitHub" />
  </a>
</p>

</div>

WebHarbor docks popular websites into local, stable, Docker-based mirrors with full auth, database, and multimodal image content. Environments evolve with agent capability.


## 💡 Motivation

Live websites are noisy: reCAPTCHA, geo-blocks, network flakiness, content drift. Their most useful features sit behind login walls that benchmarks can't touch. Existing offline web environments either freeze the web into toy synthetic sites or fall back to static traces with no real interaction, which limits large-scale RL training.

WebHarbor takes a different approach. We leverage coding agent (e.g., Claude Code/CodeX) to mirror real sites into local Docker images that:

- **Stable & reproducible** — no network noise, no content drift, no geo-blocks
- **Deep features unlocked** — carts, checkouts, accounts, all fully testable
- **Evolving** — harder tasks drive richer mirrors; the environment grows with agents
- **RL-ready** — sub-second database resets between rollouts
- **Community-driven** — 30 sites today, scaling to 100+ together

## 🚀 Quickstart

One command to run all web environments:

```bash
docker run -p 8101:8101 -p 40000-40029:40000-40029 battalion7244/webharbor:latest
```

Then point your agent at `http://localhost:40000` through `http://localhost:40028` to explore 29 local mirrors of WebVoyager sites: `Allrecipes, Amazon, Apple, ArXiv, BBC News, Booking, GitHub, Google Flights, Google Maps, Google Search, Hugging Face, Wolfram Alpha, Cambridge Dictionary, Coursera, ESPN, Merriam-Webster, IKEA, Phys.org, Target, TED, Ohio State University, Rotten Tomatoes, Compass, Walmart Careers, FedEx, WebMD Doctor, Healthline, Kaggle, and NVIDIA`.

For sub-second reset between rollouts, expose the control plane and call `/reset/<site>`:

```bash
curl -X POST http://localhost:8101/reset/amazon          # one site
curl -X POST http://localhost:8101/reset-all             # all sites in parallel
```

If you prefer to build the image yourself:

```bash
git clone https://github.com/aiming-lab/WebHarbor && cd WebHarbor
./scripts/fetch_assets.sh                          # pulls static assets from ChilleD/WebHarbor on HF
./scripts/build.sh                                 # docker build -t webharbor:dev .
```

### Local NVIDIA review candidate

This branch registers **30 sites**, the 29 entries listed above; NVIDIA is the last
entry, registry index 28, container port 40028 (local review host port 48028). The
published-image quickstart above is not a claim that this review candidate has been
published or accepted.

| Site | Registry position | Container port | Local review host port |
| --- | --- | --- | --- |
| NVIDIA | 28 | 40028 | 48028 |

`websyn_start.sh`, `control_server.py`, the `Dockerfile` `EXPOSE` line and every
site's `tasks.jsonl` `web` URL agree on 30 sites and `40000-40029`;
`scripts/check_site_registry.py` (run by `scripts/check_assets.sh`) fails when they
drift.

After preparing the candidate assets and building `webharbor:dev`, the local
review deployment uses:

```bash
docker run -p 127.0.0.1:48080:8101 -p 127.0.0.1:48000-48028:40000-40029 webharbor:dev
```

NVIDIA inherits the site contribution from @KaKituken
([#55](https://github.com/aiming-lab/WebHarbor/pull/55)) and the verifier/rubric
contribution from @DEM1TASSE
([#58](https://github.com/aiming-lab/WebHarbor/pull/58)). This is file-level
integration, not a claim that either PR was merged or that the NVIDIA review has
passed.

### Asset delivery status

`.assets-revision` is pinned to `b7e605c0ec5fc47de85b09e7427162cc50e38980`, the
squash-merge commit of HF dataset PR
[#85](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/85) on the
dataset's `main`. It sits on top of PR
[#84](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/84) and PR
[#75](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/75), which
added the first reviewed NVIDIA bundle. Those PRs are merged, the pinned commit is
on `main`, and the earlier "PR not merged" and "archive rejected by the
validator" blockers are cleared:

- the pinned revision carries 31 `*.tar.gz` (one per registered site plus
  `bandcamp.tar.gz` and `drugs_com.tar.gz`, which `fetch_assets.sh` ignores for
  sites this checkout does not register);
- `nvidia.tar.gz` at that revision has 37 file members and no directory members,
  so `scripts/validate_asset_archive.py nvidia.tar.gz nvidia` prints
  `[fetch] validated 37 managed members for nvidia` and exits 0;
- `./scripts/fetch_assets.sh` at this pin extracts all 29 registered sites
  (`[fetch] done — 29 site(s) extracted into sites/`).

| Artifact | Members | Bytes | SHA-256 |
| --- | --- | --- | --- |
| `nvidia.tar.gz` at the current pin (HF PR #85) | 37 | 16,340,955 | `617a3e3740ba6706bcab786c8a5c3f9a22ecbb39eff5728ad2c12e4992cb098b` |
| previous pin's `nvidia.tar.gz` (HF PR #84, superseded) | 34 | 9,927,312 | `ee8c6ba966e7a8f7fb5ad2d7ff0134ab98e7b80d6cc77f3328217405b8b34e2f` |

PR #85 replaces five product images and adds three dedicated hero images (see
"Image and verifier follow-up" below). Its archive passes
`validate_asset_archive.py` (`validated 37 managed members`) and a clean-room
extract in which all 36 images have distinct SHA-256 values, the seed database is
byte-identical to the previous pin
(`2143c954def96cc921760ab2bea79fe119de3d73212d1b01daf6c61792c2b38d`) and every
`products.image` path resolves.

The revisions rejected in earlier rounds are kept here for the record: the older
candidate archive from HF PR #38
(`2707761e4041a492379ea227f09b3bd9ea838a02`, sha256
`89e0d0d21000bb94acaeaa329fd28a1264afa05f40834c0f3e3cee5c3a2ae9a1`) passes the
validator but carries a stale seed (the Jetson descriptions lost the kit/module
identity text, the RTX 5060 Ti is named without `16GB` and its
`recommended_psu_watts` is 550 while the page's own source note says 600 W), and a
revision with no `nvidia.tar.gz` cannot prepare this candidate at all.

### Image and verifier follow-up

HF PR #84 replaced twelve product images that were byte-identical duplicates of
another SKU (RTX 5060/5060 Ti, RTX 5070/5070 Ti, RTX 4070 SUPER/4080 SUPER) or
depicted something other than the named product. The follow-up round replaced the
remaining mismatched or near-identical assets with official NVIDIA media, so
`static/images` now holds 36 files with 36 distinct SHA-256 values and no
within-page image reuse on `/`, the two series pages or any listing:

- `geforce-rtx-5080.png` and `geforce-rtx-5090.png` use NVIDIA's own per-SKU og
  renders instead of two crops of one mirror-bundle strip;
- `geforce-rtx-5070.png`, `rtx-6000-ada.png` and `shield-tv-pro.png` now carry
  official renders, which brings every product image into a 1.77–1.90 aspect
  range;
- `static/images/heroes/*.jpg` adds three dedicated hero images, so the home hero,
  the 50-series hero and the 40-series hero no longer reuse a product-card file;
- captions state what each file shows (`dgx-b200`, `h200-tensor-core`, and the two
  family assets that share one vendor artwork).

The same round closed the 20-task audit's findings in the graders and in the site:
the T6 phrasing false negative (blocker), the unit-first spec-row phrasing, the
bare-price and single-product evidence gates, the driver-series evidence scope,
the newsletter `topic` check, the whole-catalog search scoring, the price-ordered
series grid, the leaky sort options, the `Email`/`Search` accessible-name
collisions, and the scroll-hint and footprint defects. The per-item disposition and
evidence are in `_wh_review_tools/pr107-audit/agent-{a,b,c}/summary.md`,
`_wh_review_tools/orch/integration/logs/pr107-fixall/{00-issue-list,01-disposition,02-site-reverify,06-images}.md`
and `review-reports/PR-107-FINAL-AUDIT.md`.

### Scope note: external references

Several pages render links to `nvidia.com`, `marketplace.nvidia.com` and
`store.nvidia.com` as dated source references. They are labelled as leaving the
local mirror, no route fetches them (0 external requests over 114 routes at 1440,
768, 390 and 320 px), and the site verifiers treat any navigation outside the
mirror's loopback origin as a failure, so a run that follows one fails rather than
silently grading against an unreachable page.

### Validation record for this review candidate

The commands below are the ones actually run for the review rounds; raw outputs
live under `/data/zhaoyang-user-projects/websyn/_wh_review_tools/`
(`pr107-fixes/` for the phase-1/phase-2 review, `pr107-audit/` for the 20-task
audit, `pr107-fixall/` for the follow-up round).

```bash
# site suites (the driver suite is skipped unless its explicit input/output paths are set)
python3 -B sites/nvidia/tests/test_verifiers.py --seed <seed.db> --out <new-dir>   # 316 cases
WH_CONTAINER=<container> TEST_OUT=<outside-source-dir> python3 -B -m unittest discover -s sites/nvidia/tests
#   -> 44 tests when DRIVER_TEST_INPUTS is unset (two classes skipped),
#      73 tests when it is set (29 driver cases included)
DRIVER_TEST_INPUTS=<dir-with-initial/after.db> DRIVER_TEST_OUT=<new-dir> \
  python3 -B -m unittest discover -s sites/nvidia/tests -p 'test_driver_qualifier.py'   # 29 tests
python3 -B sites/nvidia/test_ui_contract.py --output <new-dir>                     # 15 tests
python3 -B sites/nvidia/tests/test_t7_verifier.py                                   # 23 tests (parser regressions)
# verifier CLI contract and the mechanical negative-sample matrix
WH_CONTAINER=<container> TEST_OUT=<dir> python3 -B -m unittest discover -s sites/nvidia/tests -p 'test_verifier_contract.py'   # 11 tests
./scripts/check_assets.sh                                                          # exit 0, 36 inventoried assets
```

The earlier draft of this section quoted "44 unit tests pass" for the site suites;
44 is the count when the driver regression class is skipped, and that class used to
fail its own `test_other_information_task_not_relaxed` case in the PR head. Both are
fixed and the current counts are the ones listed above. The GitHub PR description
itself cannot be edited from this repository.

## 🤝 Contribute

We have built 29 high-quality mirrors covering the [WebVoyager](https://github.com/MinorJerry/WebVoyager) benchmark. The next goal is **100+ sites**, covering everything in [Online-Mind2Web](https://huggingface.co/datasets/osunlp/Online-Mind2Web). We are inviting the community to build this together.

There are two ways to join the author list:

### 🛠️ Track A — Contribute a new website

Use a coding agent to build a new mirror (frontend + backend + database + tasks). Contributing **one website** qualifies you for consideration on the final paper's author list.

1. Browse the [Contribution Track Sheet](https://docs.google.com/spreadsheets/d/1vZsrQjy9nJKze58fx4kbQtFi85NjVXIWCFyu3ShD7gk/edit?gid=0#gid=0) and pick an unclaimed site.
2. Submit the [Contribution Request Form](https://forms.gle/ngcD1rzAfUEphNmRA) to claim it. We lock the site to prevent duplicate work.
3. Follow the [Website Contribution Guide](https://aiming-lab.github.io/webharbor.github.io/guide-create.html) and [CONTRIBUTING.md](CONTRIBUTING.md) to build and open a PR. 

### 🔍 Track B — Review environments

Review submitted mirrors for visual fidelity, functional correctness, and task grounding. **Reviewing 5 environments** earns a spot on the author list.

1. Browse open [Pull Requests](https://github.com/aiming-lab/WebHarbor/pulls).
2. Check whether the submitted environment supports its proposed tasks, and whether those tasks are meaningful and challenging.
3. Follow the [Review Pipeline](https://aiming-lab.github.io/webharbor.github.io/guide-review.html) for systematic verification.

### Acknowledgement

Any other improvement — bug fixes, UI polish, data enrichment, task suggestions, or even feedback, qualifies for the paper's acknowledgement section.

## 🤗 Resources

| Name | Link |
| --- | --- |
| 🏠 WebHarbor Project Page | [WebHarbor](https://aiming-lab.github.io/webharbor.github.io/) |
| 🤗 HuggingFace Dataset | [ChilleD/WebHarbor](https://huggingface.co/datasets/ChilleD/WebHarbor) |
| 💻 WebHarbor GitHub | [Code Repo](https://github.com/aiming-lab/WebHarbor) |
| 📊 Contribution Track Sheet | [Google Sheet](https://docs.google.com/spreadsheets/d/1vZsrQjy9nJKze58fx4kbQtFi85NjVXIWCFyu3ShD7gk/edit?gid=0#gid=0) |
| 📝 Contribution Request Form | [Google Form](https://forms.gle/ngcD1rzAfUEphNmRA) |

## Citation

WebHarbor is initiated by UNC-Chapel Hill and Microsoft, with contributions from the broader community. If you have any questions, please contact us via `webharborcomm at gmail dot com` or `zhaoyang at cs dot unc dot edu`. 

```bibtex
@misc{webharbor2026,
  title        = {WebHarbor: Docking Real Websites for Evolving GUI Agent Environments},
  author       = {{WebHarbor Team and Contributors}},
  year         = {2026},
  url          = {https://aiming-lab.github.io/webharbor.github.io},
  note         = {Project website.}
}
```

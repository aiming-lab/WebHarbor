<div align="center">

## Control-plane authentication

The current source requires a bearer token of at least 32 characters for control-plane requests. Before the Docker examples below, set:

```bash
export WEBSYN_CONTROL_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
```

Pass it with `docker run -e WEBSYN_CONTROL_TOKEN`. Site browsing does not require this token; it is removed from site-process environments. Build from this checkout: previously published images may use an older registry/authentication contract.


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
- **Community-driven** — 45 sites today, scaling to 100+ together

## 🚀 Quickstart

Build this checkout to run its registered web environments (published image tags may have an older registry):

```bash
./scripts/build.sh webharbor:dev
docker run -e WEBSYN_CONTROL_TOKEN -p 8101:8101 -p 40000-40044:40000-40044 webharbor:dev
```

Then point your agent at `http://localhost:40000` through `http://localhost:40044` to explore 45 local mirrors of WebVoyager sites: `Allrecipes, Amazon, Apple, ArXiv, BBC News, Booking, GitHub, Google Flights, Google Maps, Google Search, Hugging Face, Wolfram Alpha, Cambridge Dictionary, Coursera, ESPN, Merriam-Webster, IKEA, Phys.org, Target, TED, Ohio State University, Rotten Tomatoes, Compass, Walmart Careers, FedEx, WebMD Doctor, Healthline, Kaggle, NVIDIA, UC Berkeley, B&H Photo, AccuWeather, GOV.UK, IMDb, NBA, Recreation.gov, BoardGameGeek, CarMax, BabyCenter, Amtrak, Cookpad, Craigslist, Drugs.com, Versus, and Y Combinator`.

For sub-second reset between rollouts, expose the control plane and call `/reset/<site>`:

```bash
curl -H "Authorization: Bearer $WEBSYN_CONTROL_TOKEN" -X POST http://localhost:8101/reset/amazon          # one site
curl -H "Authorization: Bearer $WEBSYN_CONTROL_TOKEN" -X POST http://localhost:8101/reset-all             # all sites in parallel
```

If you prefer to build the image yourself:

```bash
git clone https://github.com/aiming-lab/WebHarbor && cd WebHarbor
./scripts/fetch_assets.sh                          # pulls static assets from ChilleD/WebHarbor on HF
./scripts/build.sh                                 # docker build -t webharbor:dev .
```

### Site registry

This checkout registers **45 sites**. NVIDIA remains at index 28, UC Berkeley remains at index 29, B&H Photo remains at index 30, AccuWeather remains at index 31, GOV.UK remains at index 32, IMDb remains at index 33 and NBA remains at index 34. Recreation.gov remains at index 35, BoardGameGeek remains at index 36, CarMax remains at index 37, BabyCenter remains at index 38, Amtrak remains at index 39, Cookpad remains at index 40, Craigslist remains at index 41, Drugs.com remains at index 42, Versus remains at index 43, and Y Combinator is appended at index 44. Build the image from this checkout to use this registry; publishing source does not update the published Docker image automatically.

| Site | Registry position | Container port | Example local review host port |
| --- | --- | --- | --- |
| NVIDIA | 28 | 40028 | 48028 |
| UC Berkeley | 29 | 40029 | 48029 |
| B&H Photo | 30 | 40030 | 48030 |
| AccuWeather | 31 | 40031 | 48031 |
| GOV.UK | 32 | 40032 | 48032 |
| IMDb | 33 | 40033 | 48033 |
| NBA | 34 | 40034 | 48034 |
| Recreation.gov | 35 | 40035 | 48035 |
| BoardGameGeek | 36 | 40036 | 48036 |
| CarMax | 37 | 40037 | 48037 |
| BabyCenter | 38 | 40038 | 48038 |
| Amtrak | 39 | 40039 | 48039 |
| Cookpad | 40 | 40040 | 48040 |
| Craigslist | 41 | 40041 | 48041 |
| Drugs.com | 42 | 40042 | 48042 |
| Versus | 43 | 40043 | 48043 |
| Y Combinator | 44 | 40044 | 48044 |

`websyn_start.sh`, `control_server.py`, the `Dockerfile` `EXPOSE` line and every
site's `tasks.jsonl` `web` URL agree on 45 sites and `40000-40044`;
`scripts/check_site_registry.py` (run by `scripts/check_assets.sh`) fails when they
drift.

After preparing the candidate assets and building `webharbor:dev`, the local
review deployment uses:

```bash
docker run -e WEBSYN_CONTROL_TOKEN -p 127.0.0.1:48080:8101 -p 127.0.0.1:48000-48044:40000-40044 webharbor:dev
```

NVIDIA inherits the site contribution from @KaKituken
([#55](https://github.com/aiming-lab/WebHarbor/pull/55)) and the verifier/rubric
contribution from @DEM1TASSE
([#58](https://github.com/aiming-lab/WebHarbor/pull/58)). This is file-level
integration, not a claim that either PR was merged or that the NVIDIA review has
passed.

### Asset delivery status

GOV.UK is registered at index 32 / port 40032, IMDb at index 33 / port 40033 and
NBA at index 34 / port 40034 in
builds of this source revision.
The published Docker Hub image is updated in a separate release. GOV.UK's reviewed seed originated in
[HF asset PR #93](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/93).
The bundle contains 78 articles and 62 structured guidance sections. That archive
is part of the consolidated pinned dataset revision below.


The current `.assets-revision` consolidates all **45** registered sites at merged HF commit `eedc1a7f85118ab835eac38e04678fa85d141973`. All 45 archives from the previous global revision `f3ecd60ea35795eef566ee19d67140c16b200f26`—44 registered-site archives plus the unregistered Bandcamp archive—are byte-identical; merged HF PR #83 adds `y_combinator.tar.gz` (121,085,653 bytes, SHA-256 `43c666bda84680f327ce64720b2baa2f9e427acb751fe81900967f267e9176f4`). The previous revision already includes the reviewed Versus archive from HF PR #90. Drugs.com retains its 13 attributed DailyMed labels and packaging images from HF #101 with the archive-root correction from [HF #102](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/102). `assets-manifest.json` binds all selected archive hashes and the extracted tree. The unregistered Bandcamp archive is not fetched. Seed migrations and build-generated seeds remain part of the build contract.

Historical asset integration notes below describe superseded pins, not the current pin.

The previous `.assets-revision` pinned merged HF main commit
`9d67d0088a7535e455a331a823b67e3a7d666161`, containing archives for all **38**
previously registered sites. Original asset PRs #8 (Recreation.gov), #15 (CarMax),
#25 (BoardGameGeek), and #66 (AccuWeather) are merged, followed by
[CarMax photo supplement #95](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/95).
Those 38 sites do not depend on open HF PR pins. All 36 archives from the previous
global pin `2aaf9d598f3e71cddd17a4efcdfee7dd7c073337` are unchanged; the three
non-CarMax scoped bundles also retain their reviewed bytes. CarMax adds 11
source-backed model-year stock photos without changing its original files or
seed. Seven other unavailable vehicle hero images remain explicit placeholders.
At that earlier revision, the unregistered Bandcamp and Drugs.com archives were ignored by `fetch_assets.sh`.
Tracked seed migrations and build-generated seeds still run during fetch/build.

BabyCenter, the 39th site, uses the immutable merged scoped
pin `8f3437ffa3b80c606687c49a5c5bbdf158f1c9ce` from
[HF asset PR #78](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/78).
The merged archive matches the reviewed bytes and preserves all 43 pre-existing
dataset files. Other sites retain their previously validated global pin.
Its tracked idempotent seed migration corrects the week-18 excerpt during
fetch/build; the existing image/archive bytes do not require repacking.

B&H's archive contains images and external cache. The Docker build validates
its 508 declared assets and generates `instance_seed/bh_photo.db` from the tracked
catalog. No manually prepared B&H database is required for a fresh build.

The earlier pin `b7e605c0ec5fc47de85b09e7427162cc50e38980` is the squash-merge
commit of HF dataset PR
[#85](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/85) on the
dataset's `main`. It sits on top of PR
[#84](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/84) and PR
[#75](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/75), which
added the first reviewed NVIDIA bundle.

| Artifact | Members | Bytes | SHA-256 |
| --- | --- | --- | --- |
| `nvidia.tar.gz` at the current pin | 37 | 16,340,955 | `617a3e3740ba6706bcab786c8a5c3f9a22ecbb39eff5728ad2c12e4992cb098b` |
| `berkeley.tar.gz` at the current pin (HF PR #91) | 171 | 6,951,483 | `ab9d2716ae8d06540a181b5e60c37f613d87b103864b467511da546b1b173789` |
| `bh_photo.tar.gz` at the current pin (HF PR #92) | 511 | 79,658,793 | `867363d5484eb114d647e236991017992d5ac91ae3415996ad43bf654d99bd9a` |
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

We have built 30 high-quality mirrors covering the [WebVoyager](https://github.com/MinorJerry/WebVoyager) benchmark. The next goal is **100+ sites**, covering everything in [Online-Mind2Web](https://huggingface.co/datasets/osunlp/Online-Mind2Web). We are inviting the community to build this together.

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

## Reset And Smoke Checks

Use the repository reset/smoke checker to verify control-plane resets, homepage reachability, and local seed/runtime DB parity:

```bash
python scripts/check_reset_smoke.py --site amazon
python scripts/check_reset_smoke.py --control-url http://localhost:8101
python scripts/check_reset_smoke.py --json
python scripts/check_reset_smoke.py --strict
```

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

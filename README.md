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
- **Community-driven** — 16 sites today, scaling to 100+ together

## 🚀 Quickstart

One command to run all web environments:

```bash
docker run -p 8101:8101 -p 40000-40015:40000-40015 battalion7244/webharbor:latest
```

Then point your agent at `http://localhost:40000` through `http://localhost:40015` to explore 16 local mirrors of webvoyager sites: `Allrecipes, Amazon, Apple, ArXiv, BBC News, Booking, GitHub, Google Flights, Google Maps, Google Search, Hugging Face, Wolfram Alpha, Cambridge Dictionary, Coursera, ESPN, and IMDb`.

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

## 🤝 Contribute

We have built 15 high-quality mirrors covering the [WebVoyager](https://github.com/MinorJerry/WebVoyager) benchmark. The next goal is **100+ sites**, covering everything in [Online-Mind2Web](https://huggingface.co/datasets/osunlp/Online-Mind2Web). We are inviting the community to build this together.

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
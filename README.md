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
- **Community-driven** — 54 sites today, scaling to 100+ together

## 🚀 Quickstart

Build this checkout to run its registered web environments (published image tags may have an older registry):

```bash
./scripts/build.sh webharbor:dev
docker run -e WEBSYN_CONTROL_TOKEN -p 8101:8101 -p 40000-40053:40000-40053 webharbor:dev
```

Then point your agent at `http://localhost:40000` through `http://localhost:40053` to explore 54 local mirrors of WebVoyager sites: `Allrecipes, Amazon, Apple, ArXiv, BBC News, Booking, GitHub, Google Flights, Google Maps, Google Search, Hugging Face, Wolfram Alpha, Cambridge Dictionary, Coursera, ESPN, Merriam-Webster, IKEA, Phys.org, Target, TED, Ohio State University, Rotten Tomatoes, Compass, Walmart Careers, FedEx, WebMD Doctor, Healthline, Kaggle, NVIDIA, UC Berkeley, B&H Photo, AccuWeather, GOV.UK, IMDb, NBA, Recreation.gov, BoardGameGeek, CarMax, BabyCenter, Amtrak, Cookpad, Craigslist, Drugs.com, Versus, Y Combinator, PhET Interactive Simulations, Discogs, Google Finance, Bandcamp, Adopt-a-Pet, IGN, IRS Refund Tracker, WineAccess, and WebMD`.

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

### Websites

All registered websites and their default ports, in registration order from left to right across each row. A site's container port is `40000 + index` (see the `SITES` array and `BASE_PORT` in `websyn_start.sh`, and the `EXPOSE` line in the `Dockerfile`).

| Website | Default port | Website | Default port | Website | Default port |
| --- | --- | --- | --- | --- | --- |
| Allrecipes | 40000 | Amazon | 40001 | Apple | 40002 |
| ArXiv | 40003 | BBC News | 40004 | Booking | 40005 |
| GitHub | 40006 | Google Flights | 40007 | Google Maps | 40008 |
| Google Search | 40009 | Hugging Face | 40010 | Wolfram Alpha | 40011 |
| Cambridge Dictionary | 40012 | Coursera | 40013 | ESPN | 40014 |
| Merriam-Webster | 40015 | IKEA | 40016 | Phys.org | 40017 |
| Target | 40018 | TED | 40019 | Ohio State University | 40020 |
| Rotten Tomatoes | 40021 | Compass | 40022 | Walmart Careers | 40023 |
| FedEx | 40024 | WebMD Doctor | 40025 | Healthline | 40026 |
| Kaggle | 40027 | NVIDIA | 40028 | UC Berkeley | 40029 |
| B&H Photo | 40030 | AccuWeather | 40031 | GOV.UK | 40032 |
| IMDb | 40033 | NBA | 40034 | Recreation.gov | 40035 |
| BoardGameGeek | 40036 | CarMax | 40037 | BabyCenter | 40038 |
| Amtrak | 40039 | Cookpad | 40040 | Craigslist | 40041 |
| Drugs.com | 40042 | Versus | 40043 | Y Combinator | 40044 |
| PhET Interactive Simulations | 40045 | Discogs | 40046 | Google Finance | 40047 |
| Bandcamp | 40048 | Adopt-a-Pet | 40049 | IGN | 40050 |
| IRS Refund Tracker | 40051 | WineAccess | 40052 | WebMD | 40053 |
| Petfinder | 40054 | MEGA | 40055 | 4shared | 40056 |
| 9GAG | 40057 | American Kennel Club | 40058 | Best Buy | 40059 |
| YouTube | 40060 | Weather | 40061 | Amazon Jobs | 40062 |
| Cboe | 40063 | Better Business Bureau | 40064 | Birkenstock | 40065 |
| America’s Health Rankings | 40066 | American Express | 40067 | Carnival Cruise | 40068 |
| CA.gov | 40069 |  |  |  |  |

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

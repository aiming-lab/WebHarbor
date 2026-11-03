<div align="center">


<h1>⚓ WebHarbor</h1>
<h2>Docking Real Websites for Evolving GUI Agent Environments</h3>


<p>
  <a href="https://aiming-lab.github.io/WebHarbor/">
    <img src="https://img.shields.io/badge/🏠-Project%20Page-orange.svg" alt="Project Page" />
  </a>
  <a href="https://arxiv.org/abs/2611.03634">
    <img src="https://img.shields.io/badge/📄%20arXiv-2611.03634-b31b1b.svg" alt="arXiv" />
  </a>
  <a href="https://github.com/aiming-lab/WebHarbor">
    <img src="https://img.shields.io/badge/💻-Code-black.svg" alt="Code" />
  </a>
  <a href="https://huggingface.co/datasets/ChilleD/WebHarbor">
    <img src="https://img.shields.io/badge/🤗-Data%20%26%20Envs-yellow.svg" alt="Data and environments" />
  </a>
  <a href="https://huggingface.co/ChilleD/WebHarbor-4B">
    <img src="https://img.shields.io/badge/🤗-Model-blue.svg" alt="WebHarbor-4B model" />
  </a>
  <a href="https://hub.docker.com/r/wildawm/webharbor">
    <img src="https://img.shields.io/badge/🐳-Docker-2496ED.svg" alt="Docker images" />
  </a>
  <a href="https://docs.google.com/spreadsheets/d/1vZsrQjy9nJKze58fx4kbQtFi85NjVXIWCFyu3ShD7gk/edit?gid=0#gid=0">
    <img src="https://img.shields.io/badge/📊-Track%20Sheet-blue.svg" alt="Contribution Track Sheet" />
  </a>
  <a href="https://forms.gle/ngcD1rzAfUEphNmRA">
    <img src="https://img.shields.io/badge/📝-Request%20Form-green.svg" alt="Contribution Request Form" />
  </a>
</p>

</div>

WebHarbor docks **153** popular websites into local, stable, Docker-based mirrors with full auth, database, and multimodal image content, together with **3,518** tasks for evaluating and training GUI web agents. Environments evolve with agent capability. Trained solely in WebHarbor's synthetic environments and tasks, [WebHarbor-4B](https://huggingface.co/ChilleD/WebHarbor-4B) reaches a **75.8** average on WebVoyager and Online-Mind2Web, the best open-source GUI web agent at the 4B scale.

## 📣 News

- Nov 02, 2026: WebHarbor paper, code, 153 environments, 3518 tasks, and model checkpoint are released.
- May 11, 2026: We released the first 15 website environments of WebHarbor, and started the community contribution track.


## 🤗 Resources

| Name                        | Link                                                         |
| --------------------------- | ------------------------------------------------------------ |
| 🏠 WebHarbor Project Page    | [WebHarbor](https://aiming-lab.github.io/WebHarbor/)         |
| 📄 Paper                     | [arXiv:2611.03634](https://arxiv.org/abs/2611.03634)         |
| 🤗 Environments              | [ChilleD/WebHarbor](https://huggingface.co/datasets/ChilleD/WebHarbor) |
| 🤗 Tasks in Harbor format    | [ChilleD/WebHarbor-Tasks](https://huggingface.co/datasets/ChilleD/WebHarbor-Tasks) |
| 🤖 WebHarbor-4B              | [ChilleD/WebHarbor-4B](https://huggingface.co/ChilleD/WebHarbor-4B) |
| 🐳 Docker Images             | [wildawm/webharbor](https://hub.docker.com/r/wildawm/webharbor) |
| 💻 WebHarbor Code            | [Code Repo](https://github.com/aiming-lab/WebHarbor)         |
| 📊 Contribution Track Sheet  | [Google Sheet](https://docs.google.com/spreadsheets/d/1vZsrQjy9nJKze58fx4kbQtFi85NjVXIWCFyu3ShD7gk/edit?gid=0#gid=0) |
| 📝 Contribution Request Form | [Google Form](https://forms.gle/ngcD1rzAfUEphNmRA)           |


## 💡 Motivation

Live websites are noisy: reCAPTCHA, geo-blocks, network flakiness, content drift. Their most useful features sit behind login walls that benchmarks can't touch. Existing offline web environments either freeze the web into toy synthetic sites or fall back to static traces with no real interaction, which limits large-scale RL training. WebHarbor takes a different approach. We leverage coding agent (e.g., Claude Code/CodeX) to mirror real sites into local Docker images that:

- **Stable & reproducible** — no network noise, no content drift, no geo-blocks
- **Deep features unlocked** — carts, checkouts, accounts, all fully testable
- **Evolving** — harder tasks drive richer mirrors; the environment grows with agents
- **RL-ready** — sub-second database resets between rollouts
- **Community-driven** — 153 sites today

## 🚀 Quickstart

1. Run the prebuilt image with all 153 sites (about 20 GB) from [Docker Hub](https://hub.docker.com/r/wildawm/webharbor):

```bash
# required, at least 32 characters
export WEBSYN_CONTROL_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"   
docker run -e WEBSYN_CONTROL_TOKEN -p 8101:8101 -p 40000-40152:40000-40152 wildawm/webharbor:latest
```

Then point your agent at `http://localhost:40000` through `http://localhost:40152` to explore 153 local mirrors. The table below lists every site in port order. The control plane on `:8101` starts once every site is ready.

2. To build the image from scratch:

```bash
git clone https://github.com/aiming-lab/WebHarbor --depth 1 && cd WebHarbor
# pulls missing static assets from ChilleD/WebHarbor on HF, then docker build
./scripts/build.sh webharbor:dev
docker run -e WEBSYN_CONTROL_TOKEN -p 8101:8101 -p 40000-40152:40000-40152 webharbor:dev
```

3. For sub-second reset between rollouts, expose the control plane and call `/reset/<site>`:

```bash
# one site reset
curl -H "Authorization: Bearer $WEBSYN_CONTROL_TOKEN" -X POST http://localhost:8101/reset/amazon
# all sites in parallel
curl -H "Authorization: Bearer $WEBSYN_CONTROL_TOKEN" -X POST http://localhost:8101/reset-all             
```

### Docker images

All images are available on Docker Hub, [`wildawm/webharbor`](https://hub.docker.com/r/wildawm/webharbor):

| Tag                           | Contents                                                     |
| ----------------------------- | ------------------------------------------------------------ |
| `latest`, `all-v1`            | all 153 sites in one image (the quickstart above)            |
| `<site>-v1`, e.g. `amazon-v1` | one site only, for per-task evaluation and RL with [Harbor](https://github.com/harbor-framework/harbor) format. It serves the site on its registered port and ships without the verifiers |
| `<site>`                      | the newest version of that site                              |

>! ⚠️ Anonymous Docker Hub pulls are rate-limited, so run `docker login` before pulling many site images on one machine.

### Benchmark & Tasks

All 3,518 tasks are packaged as [Harbor format](https://github.com/harbor-framework/harbor) tasks in Huggingface [`ChilleD/WebHarbor-Tasks`](https://huggingface.co/datasets/ChilleD/WebHarbor-Tasks). Each task runs in its site's `<site>-v1` image and is graded by that site's verifier by default.

| Dataset | Tasks | Contents |
| --- | ---: | --- |
| `webharbor@1.0` | 3,518 | all tasks on all 153 sites |
| `webharbor-train@1.0` | 2,288 | RL training tasks on 123 sites excluding all 15 WebVoyager sites and 15 held-out sites |
| `webharbor-test@1.0` | 306 | held-out test set, two tasks per site |
| `webharbor-webvoyager@1.0` | 643 | all tasks on the 15 WebVoyager sites |
| `webharbor-unused@1.0` | 311 | tasks in no other split, on 15 held-out sites |


The agent harnesses (browser-use, OpenCode, OpenWebRL), image build files and task adapter are in [`harbor/`](harbor/README.md). To reproduce the WebHarbor-4B benchmark results, please use `OpenWebRL` GUI Web agent harness: 

```bash
uv tool install harbor==0.24.0
git clone https://github.com/aiming-lab/WebHarbor --depth 1 && cd WebHarbor/harbor

# OpenWebRL policy served behind a Chat Completions endpoint
PYTHONPATH=agents OPENAI_BASE_URL=<endpoint> OPENAI_API_KEY=<key> \
harbor run --repo https://huggingface.co/datasets/ChilleD/WebHarbor-Tasks -d webharbor-test@1.0 \
-a webharbor_agents.openwebrl:OpenWebRLWebHarbor -m openai/<model> --ak api_mode=chat_completions -y
```

The verifier gives the 0/1 reward and pass/fail verdict. To also audit every trial with an Agent Judge (agent-as-a-judge, `gpt-5.6-sol` by default), point it at an OpenAI-compatible endpoint and switch the verifier. See [`harbor/README.md`](harbor/README.md#agent-judge-agent-as-a-judge) for the options.

```bash
export WEBHARBOR_JUDGE_BASE_URL=xxxxx
export WEBHARBOR_JUDGE_API_KEY=xxxxx
# add to the harbor run command above
--verifier webharbor_agents.judge_verifier:JudgeVerifier --verifier-timeout-multiplier 8
```

To evaluate [WebHarbor-4B](https://huggingface.co/ChilleD/WebHarbor-4B) on other benchmarks such as WebVoyager, Online-Mind2Web and DeepShop, serve the model behind an OpenAI-compatible endpoint as described in its [model card](https://huggingface.co/ChilleD/WebHarbor-4B) (Serving section), then run the evaluation scripts of the [OpenWebRL](https://github.com/OpenWebRL/OpenWebRL) repository against that endpoint.

### Websites Lookup Table

All registered websites and their default ports, in registration order from left to right across each row. A site's container port is `40000 + index` (see the `SITES` array and `BASE_PORT` in `websyn_start.sh`, and the `EXPOSE` line in the `Dockerfile`).

| Website                      | Port  | Website                | Port  | Website               | Port  |
| ---------------------------- | ----- | ---------------------- | ----- | --------------------- | ----- |
| Allrecipes                   | 40000 | Amazon                 | 40001 | Apple                 | 40002 |
| ArXiv                        | 40003 | BBC News               | 40004 | Booking               | 40005 |
| GitHub                       | 40006 | Google Flights         | 40007 | Google Maps           | 40008 |
| Google Search                | 40009 | Hugging Face           | 40010 | Wolfram Alpha         | 40011 |
| Cambridge Dictionary         | 40012 | Coursera               | 40013 | ESPN                  | 40014 |
| Merriam-Webster              | 40015 | IKEA                   | 40016 | Phys.org              | 40017 |
| Target                       | 40018 | TED                    | 40019 | Ohio State University | 40020 |
| Rotten Tomatoes              | 40021 | Compass                | 40022 | Walmart Careers       | 40023 |
| FedEx                        | 40024 | WebMD Doctor           | 40025 | Healthline            | 40026 |
| Kaggle                       | 40027 | NVIDIA                 | 40028 | UC Berkeley           | 40029 |
| B&H Photo                    | 40030 | AccuWeather            | 40031 | GOV.UK                | 40032 |
| IMDb                         | 40033 | NBA                    | 40034 | Recreation.gov        | 40035 |
| BoardGameGeek                | 40036 | CarMax                 | 40037 | BabyCenter            | 40038 |
| Amtrak                       | 40039 | Cookpad                | 40040 | Craigslist            | 40041 |
| Drugs.com                    | 40042 | Versus                 | 40043 | Y Combinator          | 40044 |
| PhET Interactive Simulations | 40045 | Discogs                | 40046 | Google Finance        | 40047 |
| Bandcamp                     | 40048 | Adopt-a-Pet            | 40049 | IGN                   | 40050 |
| IRS Refund Tracker           | 40051 | WineAccess             | 40052 | WebMD                 | 40053 |
| Petfinder                    | 40054 | MEGA                   | 40055 | 4shared               | 40056 |
| 9GAG                         | 40057 | American Kennel Club   | 40058 | Best Buy              | 40059 |
| YouTube                      | 40060 | Weather                | 40061 | Amazon Jobs           | 40062 |
| Cboe                         | 40063 | Better Business Bureau | 40064 | Birkenstock           | 40065 |
| America’s Health Rankings    | 40066 | American Express       | 40067 | Carnival Cruise       | 40068 |
| CA.gov                       | 40069 | Coolmath4Kids          | 40070 | Chase                 | 40071 |
| FlightAware                  | 40072 | Chronicle Jobs         | 40073 | Dillard's             | 40074 |
| Google Shopping              | 40075 | Imgur                  | 40076 | Instructure           | 40077 |
| League of Legends            | 40078 | Healthgrades           | 40079 | Kelley Blue Book      | 40080 |
| UNIQLO                       | 40081 | Macy's Wine Shop       | 40082 | JCPenney              | 40083 |
| LandWatch                    | 40084 | Medicare.gov           | 40085 | Marriott              | 40086 |
| Megabus                      | 40087 | Michaels               | 40088 | Micro Center          | 40089 |
| OhioMeansJobs                | 40090 | Ohio.gov               | 40091 | NFL                   | 40092 |
| MTA                          | 40093 | Public Storage         | 40094 | Raising Cane’s        | 40095 |
| RE/MAX                       | 40096 | Parkers                | 40097 | Ryanair               | 40098 |
| Chess.com                    | 40099 | Porsche                | 40100 | Qatar Airways         | 40101 |
| SoundCloud                   | 40102 | Speedo                 | 40103 | SourceForge           | 40104 |
| StubHub                      | 40105 | SpotHero               | 40106 | Student.com           | 40107 |
| Statista                     | 40108 | Thumbtack              | 40109 | Ticketmaster          | 40110 |
| Trip.com                     | 40111 | The Weather Network    | 40112 | Super Lawyers         | 40113 |
| TourRadar                    | 40114 | Apartments.com         | 40115 | Eventbrite            | 40116 |
| Fandom                       | 40117 | Mayo Clinic            | 40118 | SmartAsset            | 40119 |
| U.S. DOJ                     | 40120 | CVS                    | 40121 | CBP.gov               | 40122 |
| UPS                          | 40123 | United Airlines        | 40124 | US Appliance          | 40125 |
| USCIS                        | 40126 | Tumblr                 | 40127 | Zara                  | 40128 |
| USPS                         | 40129 | Wanderlog              | 40130 | Virginia DMV          | 40131 |
| Verizon                      | 40132 | ZipRecruiter           | 40133 | Carvana               | 40134 |
| CoinMarketCap                | 40135 | Cars.com               | 40136 | Airbnb                | 40137 |
| Backcountry                  | 40138 | Disney                 | 40139 | ICLR                  | 40140 |
| Red Bull                     | 40141 | dblp                   | 40142 | Microsoft Azure       | 40143 |
| FOX Sports                   | 40144 | Samsung                | 40145 | NYSE                  | 40146 |
| University of Michigan       | 40147 | Stanford University    | 40148 | Yahoo Finance         | 40149 |
| Steam                        | 40150 | Trader Joe's           | 40151 | SEC.gov               | 40152 |

## 🤝 Contribute

**Contributions for the current paper version have been closed.**

We have built 15 high-quality mirrors covering the [WebVoyager](https://github.com/MinorJerry/WebVoyager) benchmark. The next goal is **100+ sites**, covering everything in [Online-Mind2Web](https://huggingface.co/datasets/osunlp/Online-Mind2Web). We are inviting the community to build this together.

There are two ways to join the author list:

### 🛠️ Track A — Contribute a new website

Use a coding agent to build a new mirror (frontend + backend + database + tasks). Contributing **one website** qualifies you for consideration on the final paper's author list.

1. Browse the [Contribution Track Sheet](https://docs.google.com/spreadsheets/d/1vZsrQjy9nJKze58fx4kbQtFi85NjVXIWCFyu3ShD7gk/edit?gid=0#gid=0) and pick an unclaimed site.
2. Submit the [Contribution Request Form](https://forms.gle/ngcD1rzAfUEphNmRA) to claim it. We lock the site to prevent duplicate work.
3. Follow the [Website Contribution Guide](https://aiming-lab.github.io/WebHarbor/guide-create.html) and [CONTRIBUTING.md](CONTRIBUTING.md) to build and open a PR.

### 🔍 Track B — Review environments

Review submitted mirrors for visual fidelity, functional correctness, and task grounding. **Reviewing 5 environments** earns a spot on the author list.

1. Browse open [Pull Requests](https://github.com/aiming-lab/WebHarbor/pulls).
2. Check whether the submitted environment supports its proposed tasks, and whether those tasks are meaningful and challenging.
3. Follow the [Review Pipeline](https://aiming-lab.github.io/WebHarbor/guide-review.html) for systematic verification.

### Acknowledgement

Any other improvement — bug fixes, UI polish, data enrichment, task suggestions, or even feedback are welcome. We will acknowledge all contributors in the final paper.


## Citation

WebHarbor is initiated by UNC-Chapel Hill and Microsoft, with contributions from the broader community. If you have any questions, please contact us via `webharborcomm at gmail dot com` or `zhaoyang at cs dot unc dot edu`.

```bibtex
@article{wang2026webharbordockingrealwebsites,
      title={WebHarbor: Docking Real Websites for Evolving GUI Agent Environments}, 
      author={{WebHarbor Team and Contributors}},
      year={2026},
      eprint={2611.03634},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2611.03634}, 
}
```

or

```bibtex
@article{wang2026webharbordockingrealwebsites,
      title={WebHarbor: Docking Real Websites for Evolving GUI Agent Environments}, 
      author={Zhaoyang Wang and Qianhui Wu and Boyu Gou and Demi Wang and Jiacheng Zhang and Peichun Hua and Qize Li and Shi Qiu and Yifan Jiang and Yifan Zhang and Zexu Jin and Baolin Peng and Bolin Shen and Chetan Bansal and Dehan Kong and Deren Lei and Dongshen Peng and Fengqing Jiang and Hao Cheng and Haoqing Wang and Jiaming Shan and Jicheng Wang and Jingguang Zhou and Jixuan He and Kaide Zeng and Kangyu Zhu and Lama Moukheiber and Mufan Qiu and Peng Xia and Qihan Sun and Qingwei Lin and Qiushi Sun and Ruichen Zhang and Shuqing Luo and Si Qin and Sicheng Fan and Tao Xiong and Wenlin Yao and Xinyu Zhang and Xinyue Zeng and Xuanrui Li and Xuchao Zhang and Yian Wang and Yichao Liu and Yiming Liang and Yiyang Zhou and Yizhu Jiao and Yuetai Li and Yurun Chen and Yuxuan Zhang and Zheyuan Yang and Zhiyuan Yao and Zhongyang Li and Zihao Li and Zili Wang and Jianfeng Gao and Huaxiu Yao},
      year={2026},
      eprint={2611.03634},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2611.03634}, 
}
```
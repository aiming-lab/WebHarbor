#!/usr/bin/env python3
"""Self-check suite for the BBC News grading contract (42 verifiers).

Run from the agent_demo project:

    cd agent_demo
    uv run --with pytest python -m pytest ../sites/bbc_news/verify/test_verifiers.py

The suite never touches the network, the LLM, or the database. It exercises
every verifier against SYNTHETIC run packages built from the verifier's own
hardcoded ground truth (and, for the custom-body verifiers, from the frozen
audit answers below):

  positive       a run that navigated to the qualifying page(s) and reports
                  the on-page facts -> the verifier MUST emit PASS (exit 0)
  no-op          a run that only opened the homepage with an empty answer
                  -> the verifier MUST FAIL (exit 1)
  shortcut       a correct answer but no on-site navigation for it
                  -> the verifier MUST FAIL
  wrong content  a qualifying page opened but the answer commits to wrong
                  facts / a wrong article -> the verifier MUST FAIL
  wrong page     the graded answer without ever opening a qualifying article
                  (browsing an unrelated page instead) -> the verifier MUST FAIL
  tampered run   a run package missing screenshots, or a run dir without
                  trajectory.json -> the verifier MUST FAIL

Every case runs the real verifier script as a subprocess (the same entry point
eval_judge.py uses) and asserts on both its JSON verdict and its exit code.
"""
import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

VERIFY_DIR = Path(__file__).resolve().parent
PY = sys.executable

# 1x1 transparent PNG: screenshots are required to EXIST by the run gate; their
# pixels are graded only by verify_7's optional anchored LLM checks (skipped
# under --no_llm).
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQ"
    "DwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

BASE = "http://localhost:41004"
TASK_IDS = [f"BBC News--{n}" for n in range(42)]


def art(slug):
    return f"{BASE}/article/{slug}"


def sec(path):
    return f"{BASE}{path}"


# ---------------------------------------------------------------------------
# Per-task frozen audit specs for the custom-body verifiers (and the positive
# path used for every verifier). nav = trajectory URLs, ans = final answer.
# All answers are copied from the mirror's own rendered pages.
SPECS = {
 "BBC News--0": dict(
    nav=[sec("/"), sec("/news/uk"), art("scotland-unveils-tidal-power-array-that-could-be-the-world-s-largest")],
    ans="Scotland has unveiled a 50 MW tidal stream array off the coast of Orkney — "
        "a breakthrough for its marine renewable energy industry.",
    wrong="The UK government has banned all forms of renewable energy development.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--1": dict(
    nav=[sec("/"), sec("/news/health"), art("major-study-finds-mediterranean-diet-cuts-dementia-risk-by-a-quarter")],
    ans="The latest health article reports a large European study: closely following "
        "a Mediterranean diet rich in vegetables, olive oil and fish could cut the "
        "risk of dementia by as much as 25% over a decade.",
    wrong="The latest health article is about a football match.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--2": dict(
    nav=[sec("/"), sec("/news/earth"), art("amazon-deforestation-surged-to-highest-rate-in-six-months-satellite-da")],
    ans="Amazon deforestation climbed to its highest monthly rate in six months, "
        "satellite data reveals, with ranching and mining the biggest drivers of "
        "forest loss and worsening biodiversity.",
    wrong="Deforestation in the Amazon has stopped entirely this year.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--3": dict(
    nav=[sec("/"), sec("/news/golf"), art("dp-world-tour-hero-indian-open-leaderboard-rahm-leads-on-14-with-three")],
    ans="The most recent DP World Tour tournament is the Hero Indian Open. Jon Rahm "
        "leads on -14 with three to play, and five players are tied at -10 chasing him.",
    wrong="The most recent tournament is the US Masters and two players are at -10.",
    wrong_nav=[sec("/"), sec("/news/technology"), art("apple-unveils-new-ai-chip-promising-double-the-on-device-performance")]),
 "BBC News--4": dict(
    nav=[sec("/"), sec("/news/business"), art("europe-s-economy-faces-1-trillion-climate-bill-by-2050-ecb-warns")],
    ans="The ECB warns that climate change could shave a trillion euros (€1 trillion) "
        "off the EU economy by 2050, driven by heatwaves, floods and crop failures.",
    wrong="Europe's economy will benefit greatly from climate change by 2050.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--5": dict(
    nav=[sec("/"), sec("/search?q=what+is+climate+change+a+really+simple+guide"), art("what-is-climate-change-a-really-simple-guide")],
    ans="Human activities causing climate change: burning fossil fuels like coal, oil "
        "and gas releases CO2 — the largest contributor; deforestation, intensive "
        "farming (especially cattle and rice paddies), industrial processes and "
        "transport also release greenhouse gases such as methane and nitrous oxide.",
    wrong="Climate change is caused exclusively by volcanic eruptions.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--6": dict(
    nav=[sec("/"), sec("/news/technology"), art("artificial-intelligence-eu-ai-act-the-rules-coming-into-force-in-2026")],
    ans="The top story in the Technology section is 'Artificial Intelligence: EU AI "
        "Act — the rules coming into force in 2026', about which obligations kick in "
        "first and which companies are most affected.",
    wrong="The top technology story is about a new smartphone.",
    wrong_nav=[sec("/"), sec("/news/business"), art("c70n2rjgxeyo")]),
 "BBC News--7": dict(
    nav=[sec("/"), sec("/news/business?subsection=Technology+of+Business"), art("ai-chip-shortage-drives-up-costs-for-manufacturers-worldwide")],
    ans="Under Technology of Business, the AI story 'AI chip shortage drives up costs "
        "for manufacturers worldwide' has a first picture showing a man in a computer "
        "forensics lab, holding a smartphone, surrounded by electronics workbenches.",
    wrong="The first picture shows a beach at sunset.",
    wrong_nav=[sec("/"), sec("/news/business?subsection=Technology+of+Business"), art("how-ai-is-quietly-reshaping-the-global-insurance-industry")]),
 "BBC News--8": dict(
    nav=[sec("/"), sec("/news/business"), art("uk-signs-post-brexit-trade-deal-with-india-worth-20bn-a-year")],
    ans="The UK's latest trade deal is with India: a sweeping free trade agreement "
        "worth £20bn a year to bilateral trade, cutting tariffs on whisky, cars and "
        "textiles. The article was published on 14 April 2026.",
    wrong="The UK signed a trade deal with Australia worth £5bn, published in 2025.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--9": dict(
    nav=[sec("/"), sec("/news/music"), art("taylor-swift-announces-surprise-album-during-london-show")],
    ans="Taylor Swift made the headlines in Music News: she stunned fans at her "
        "London Eras Tour stop by announcing a surprise new album due next month.",
    wrong="The musician in the headlines is Bob Dylan.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--10": dict(
    nav=[sec("/"), sec("/news/uk"), art("uk-unveils-30bn-plan-to-hit-net-zero-by-2050"),
         art("uk-government-to-ban-new-petrol-car-sales-from-2035-in-updated-plan")],
    ans="Main headlines covering the UK's plan to tackle climate change: the UK unveils "
        "a £30bn plan to hit net zero by 2050; the government will ban new petrol car "
        "sales from 2035 in its updated plan; and the climate watchdog says the plan "
        "is not yet credible.",
    wrong="The UK's climate plan is only about recycling.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--11": dict(
    nav=[sec("/"), sec("/search?q=Scottish+Premiership"),
         art("scottish-premiership-table-12-teams-celtic-hold-narrow-lead-over-range"),
         art("hibernian-2-1-st-mirren-edinburgh-side-edge-late-win-at-easter-road")],
    ans="The Scottish Premiership features 12 teams, with Celtic holding a narrow "
        "lead over Rangers. Hibernian's most recent match kicked off at 15:00 BST on "
        "Saturday, beating St Mirren 2-1 at Easter Road.",
    wrong="The Scottish Premiership has 10 teams and Hibernian played on Tuesday at noon.",
    wrong_nav=[sec("/"), sec("/news/technology"), art("apple-unveils-new-ai-chip-promising-double-the-on-device-performance")]),
 "BBC News--12": dict(
    nav=[sec("/"), sec("/news/travel"), art("vietnam-s-banh-mi-the-sandwich-that-tells-a-country-s-story")],
    ans="The picture shows a banh mi — a French baguette stuffed with Vietnamese "
        "herbs, pickles and pork — a food from Vietnam, which originated in Saigon.",
    wrong="The picture shows sushi from Japan.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--13": dict(
    nav=[sec("/"), sec("/search?q=Trump"), art("c20qv0w1j1do")],
    ans="Recent Trump news: global oil prices fluctuated ahead of US President Donald "
        "Trump's deadline for Iran to open the key Strait of Hormuz shipping route.",
    wrong="Trump won the lottery and moved to the moon.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--14": dict(
    nav=[sec("/"), sec("/news/business"), art("tech-layoffs-ripple-through-global-economy-as-250-000-jobs-cut")],
    ans="Tech layoffs have cut 250,000 jobs this year as Big Tech firms and startups "
        "slash headcount, with knock-on effects reaching supply chains, commercial "
        "property and consumer spending. Author: Natalie Sherman. Published 14 April 2026.",
    wrong="Tech layoffs cut 50 jobs. Author: John Smith. Published in 2020.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--15": dict(
    nav=[sec("/"), sec("/news/natural_wonders"), art("natural-wonders-iceland-s-vatnajokull-glacier-retreat-captured-from-the-air")],
    ans="The current Natural Wonders headline tells about Iceland's Vatnajökull "
        "glacier: a BBC Earth crew documented its retreating ice margins — up to 80 "
        "metres per year — from the air over three summers.",
    wrong="The Natural Wonders headline is about a new shopping mall in London.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--16": dict(
    nav=[sec("/"), sec("/news/business"), art("brexit-deal-update-uk-and-eu-agree-fresh-talks-on-northern-ireland-tra")],
    ans="The most recent Brexit development: the UK and EU have agreed fresh talks — "
        "reopening negotiations on post-Brexit trade arrangements for Northern Ireland "
        "— aiming to smooth paperwork for hauliers.",
    wrong="Brexit negotiations collapsed completely last week.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--17": dict(
    nav=[sec("/"), sec("/news/war")],
    ans="BBC News currently covers six war-related situations in its War & Conflict "
        "section: Ukraine, Gaza, Sudan, Yemen, Myanmar and the wider Middle East.",
    wrong="There are 3 war sections in BBC News.",
    wrong_nav=[sec("/"), sec("/news/weather")]),
 "BBC News--18": dict(
    nav=[sec("/"), sec("/news/audio"), art("best-podcasts-of-2023-bbc-sounds-picks-the-year-s-must-listens")],
    ans="BBC Sounds' best podcasts of 2023 include 'The Rest Is History' — presented "
        "by Tom Holland and Dominic Sandbrook — and the 'Global News Podcast'.",
    wrong="The best podcasts of 2023 are 'Cooking Today' and 'Garden Hour'.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--19": dict(
    nav=[sec("/"), sec("/news/athletics"), art("athletics-calendar-london-marathon-2026-elite-field-announced")],
    ans="The next earliest fixture on the athletics calendar is the 2026 TCS London "
        "Marathon, to be held on 26 April 2026.",
    wrong="The next athletics event is in December 2030.",
    wrong_nav=[sec("/"), sec("/news/technology"), art("apple-unveils-new-ai-chip-promising-double-the-on-device-performance")]),
 "BBC News--20": dict(
    nav=[sec("/"), sec("/news/green_living"), art("green-living-heat-pumps-explained-what-installers-wish-you-knew")],
    ans="The latest Green Living article explains heat pumps: badly sized systems "
        "waste money, the government's Boiler Upgrade Scheme offers up to £7,500, and "
        "installers say insulation and fabric upgrades should come first.",
    wrong="The latest Green Living article is about cheap flights.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--21": dict(
    nav=[sec("/"), sec("/news/world"), art("middle-east-crisis-gaza-ceasefire-talks-enter-critical-phase-in-cairo")],
    ans="The top headline in the World News section is 'Middle East crisis: Gaza "
        "ceasefire talks enter critical phase in Cairo' — it relates to the Middle "
        "East region, with mediators pushing a deal to pause fighting in Gaza and "
        "release hostages.",
    wrong="The top world headline is about the Australian election.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--22": dict(
    nav=[sec("/"), sec("/news/business"), art("market-data-ftse-100-closes-at-record-high-as-banks-and-miners-lead")],
    ans="The current top business story: the FTSE 100 closed at a record high, with "
        "banks and miners leading the gains — HSBC, Barclays and Lloyds led the advance.",
    wrong="The top business story is about a bakery closing down.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--23": dict(
    nav=[sec("/"), sec("/news/health"), art("major-study-finds-mediterranean-diet-cuts-dementia-risk-by-a-quarter")],
    ans="The latest health news: a major study found that closely following a "
        "Mediterranean diet could cut dementia risk by a quarter (25%) — the "
        "recommendation is a diet rich in vegetables, olive oil and fish.",
    wrong="The latest health news says chocolate cures all diseases.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--24": dict(
    nav=[sec("/"), sec("/news/science"), art("c70dr45dj1lo")],
    ans="The latest space exploration story: the Artemis II crew is returning to Earth "
        "with 'all the good stuff' from Moon discoveries aboard the Orion spacecraft, "
        "expected to splash down off the coast of San Diego.",
    wrong="Space exploration news: aliens landed in Paris.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--25": dict(
    nav=[sec("/"), sec("/news/sport"), art("premier-league-analysis-arsenal-s-title-push-hangs-on-defensive-record")],
    ans="The most recent Premier League analysis: Arsenal's title push hangs on "
        "maintaining the tightest defensive record in the league.",
    wrong="The Premier League analysis says Arsenal have already won the title.",
    wrong_nav=[sec("/"), sec("/news/technology"), art("apple-unveils-new-ai-chip-promising-double-the-on-device-performance")]),
 "BBC News--26": dict(
    nav=[sec("/"), sec("/news/asia"), art("asia-philippines-typhoon-leaves-80-dead-and-displaces-half-a-million")],
    ans="The latest Asia natural-disaster report: a typhoon in the central Philippines "
        "left at least 80 dead and displaced half a million people, worst-affected "
        "in Samar, Leyte and northern Cebu.",
    wrong="A mild breeze blew through Asia and no one noticed.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--27": dict(
    nav=[sec("/"), sec("/news/science"), art("archaeological-discovery-lost-mayan-city-uncovered-in-mexican-jungle-u")],
    ans="The most recent archaeological discovery: archaeologists using LiDAR laser "
        "scanning uncovered a sprawling lost Mayan city hidden beneath the jungle of "
        "southern Mexico, revealing plazas, pyramids and roads.",
    wrong="Archaeologists discovered a new shopping centre under the sea.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--28": dict(
    nav=[sec("/"), sec("/news/market_data")],
    ans="The Market Data section's live prices, indices and currencies come from "
        "Morningstar, updated throughout the trading day.",
    wrong="The market data comes from a random number generator.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--29": dict(
    nav=[sec("/"), sec("/news/audio"), art("new-releases-the-artificial-human-returns-for-its-third-season-on-bbc-")],
    ans="The podcast episode currently featured as the New Release is 'The Artificial "
        "Human', returning for its third season on BBC Sounds with Aleks Krotoski and "
        "Kevin Fong — Episode 1 of the new season is out now.",
    wrong="The New Release is a cooking show called 'Fry Up'.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--30": dict(
    nav=[sec("/"), sec("/news/culture"), art("film-review-the-last-horizon-is-a-stunning-and-emotional-sci-fi-epic")],
    ans="The latest film release reviewed is 'The Last Horizon' — BBC Culture calls "
        "Denis Villeneuve's film a stunning and emotional sci-fi epic, starring "
        "Florence Pugh and Mahershala Ali as astronauts on a drifting colony ship.",
    wrong="The latest film review is of a documentary about sheep.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--31": dict(
    nav=[sec("/"), sec("/news/sport"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")],
    ans="Manchester United's most recent match: they beat Liverpool 3-1 at Old "
        "Trafford, with Bruno Fernandes, Marcus Rashford and a late Rasmus Hojlund "
        "goal sealing the win.",
    wrong="Manchester United lost 0-5 at Anfield.",
    wrong_nav=[sec("/"), sec("/news/technology"), art("apple-unveils-new-ai-chip-promising-double-the-on-device-performance")]),
 "BBC News--32": dict(
    nav=[sec("/"), sec("/news/ai"), art("artificial-intelligence-eu-ai-act-the-rules-coming-into-force-in-2026")],
    ans="The top AI headline is 'EU AI Act — the rules coming into force in 2026'. "
        "The companies involved are the providers of general-purpose AI models: the "
        "GPT family, Anthropic's Claude, Google's Gemini and Meta's Llama.",
    wrong="The top AI headline is about a new coffee machine made by a startup.",
    wrong_nav=[sec("/"), sec("/news/business"), art("c70n2rjgxeyo")]),
 "BBC News--33": dict(
    nav=[sec("/"), sec("/news/world"), art("middle-east-crisis-gaza-ceasefire-talks-enter-critical-phase-in-cairo")],
    ans="The latest Middle East war situation: ceasefire negotiations between Israel "
        "and Hamas have entered a critical phase in Cairo, with mediators pushing a "
        "deal to pause fighting in Gaza and allow the release of hostages.",
    wrong="The Middle East war ended completely years ago.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--34": dict(
    nav=[sec("/"), sec("/news/travel"), art("the-specialist-five-cities-to-visit-in-2026-from-lisbon-to-kyoto")],
    ans="The SpeciaList series mentions five cities for 2026: Lisbon, Kyoto, Mexico "
        "City, Tbilisi and Cape Town.",
    wrong="The SpeciaList mentions the cities of Oz and Narnia.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--35": dict(
    nav=[sec("/"), sec("/news/asia"), art("asia-singapore-unveils-regional-quantum-computing-hub")],
    ans="The most recent Asia technological advancement: Singapore has opened a "
        "regional quantum-computing research hub in Jurong, in partnership with "
        "A*STAR and IBM Quantum.",
    wrong="Asia's latest technology story is about a new kind of sandwich.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--36": dict(
    nav=[sec("/"), sec("/news/africa"), art("africa-kenya-election-result-sparks-street-celebrations"),
         art("africa-drought-grips-the-horn-of-africa-as-un-appeals-f")],
    ans="Most of the recent Africa coverage is about politics and humanitarian "
        "crises: Kenya's election result sparked celebrations in Nairobi, drought "
        "grips the Horn of Africa as the UN appeals for aid, Nigeria's fintech boom "
        "draws record investment, and South Africa's power cuts ease after record "
        "wind generation.",
    wrong="Africa news is mostly about penguin racing.",
    wrong_nav=[sec("/"), sec("/news/health"), art("major-study-finds-mediterranean-diet-cuts-dementia-risk-by-a-quarter")]),
 "BBC News--37": dict(
    nav=[sec("/"), sec("/news/culture"), art("book-review-the-inheritance-of-summer-by-ada-clarke-is-a-quiet-masterpiece")],
    ans="The latest book review features 'The Inheritance of Summer' by Ada Clarke — "
        "a slow-burning family drama set across three decades in the English Lake "
        "District, named the best British debut of the year.",
    wrong="The latest book review is of 'War and Peace' by Charles Dickens.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--38": dict(
    nav=[sec("/"), sec("/news/weather"), art("weather-storm-kathleen-batters-ireland-and-western-scotland")],
    ans="The storm news: Storm Kathleen crossed Ireland and made landfall on the west "
        "coast of Scotland overnight — around 03:00 BST — with amber wind warnings "
        "and gusts of 93 mph recorded at Tiree.",
    wrong="A storm hit the Bahamas last year.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--39": dict(
    nav=[sec("/"), sec("/news/sport"), art("horse-racing-results-yesterday-s-meetings-cheltenham-gold-cup-had-the-")],
    ans="Yesterday's UK meetings were at Cheltenham, Kempton, Sandown, Ayr and "
        "Plumpton. Of yesterday's races, the Cheltenham Gold Cup had the highest "
        "number of runners, with 18 horses declared.",
    wrong="Yesterday's racing was won by a single horse running alone in Wales.",
    wrong_nav=[sec("/"), sec("/news/technology"), art("apple-unveils-new-ai-chip-promising-double-the-on-device-performance")]),
 "BBC News--40": dict(
    nav=[sec("/"), sec("/news/war"), art("gaza-war-mothers-and-children-among-latest-victims-of-strike-on-rafah")],
    ans="A recent war story: an overnight strike on the southern Gaza city of Rafah "
        "killed at least 23 people, including 12 children and mothers of young "
        "children, according to the Gaza Health Ministry.",
    wrong="A war story reports that nobody was hurt anywhere.",
    wrong_nav=[sec("/"), sec("/news/tennis"), art("manchester-united-3-1-liverpool-red-devils-win-old-trafford-derby")]),
 "BBC News--41": dict(
    nav=[sec("/"), sec("/news/golf"), art("women-s-majors-golf-leaderboard-minjee-lee-leads-the-field-at-pine-nee")],
    ans="In the Women's Majors leaderboard at Pine Needles, the United States has the "
        "most players in the top 20. Australia has four players in the top 20, with "
        "Minjee Lee the best-placed Australian at 1st — she leads at -6 through 54 "
        "holes.",
    wrong="Canada has the most players in the top 20 and the best Australian is 40th.",
    wrong_nav=[sec("/"), sec("/news/technology"), art("apple-unveils-new-ai-chip-promising-double-the-on-device-performance")]),
}


def make_run(root, name, steps, answer, with_screenshots=True,
             with_trajectory=True):
    d = Path(root) / name
    (d / "screenshots").mkdir(parents=True, exist_ok=True)
    if with_screenshots:
        (d / "screenshots" / "step_000.png").write_bytes(PNG)
        (d / "screenshots" / "step_001.png").write_bytes(PNG)
    if with_trajectory:
        traj = {
            "task": "synthetic", "task_id": "x",
            "start_url": steps[0].get("url", BASE + "/") if steps else BASE + "/",
            "steps": steps, "terminated": True,
            "termination_reason": "agent_done",
            "final_answer": answer,
            "final_url": steps[-1].get("url", "") if steps else "",
        }
        (d / "trajectory.json").write_text(json.dumps(traj))
    return str(d)


def nav_steps(urls):
    return [{"step": i, "url": u, "action": "click", "params": {},
             "screenshot_before": f"step_{i:03d}.png",
             "screenshot_after": f"step_{i + 1:03d}.png"}
            for i, u in enumerate(urls)]


def home_steps():
    return nav_steps([BASE + "/"])


def run_verifier(task_id, run_dir, extra=("--no_llm", "True")):
    n = task_id.split("--")[1]
    cmd = [PY, str(VERIFY_DIR / f"verify_{n}.py"), "--run_dir", run_dir]
    cmd += list(extra)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        verdict = json.loads(proc.stdout)
    except Exception:
        verdict = {"pass": False, "parse_error": proc.stdout[-400:],
                   "stderr": proc.stderr[-400:]}
    return proc.returncode, verdict


@pytest.fixture(scope="module")
def tmp_root(tmp_path_factory):
    return tmp_path_factory.mktemp("bbc_verifier_cases")


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_verifier_contract(tmp_root, task_id):
    spec = SPECS[task_id]

    # positive: qualifying navigation + on-page answer -> PASS
    pos = make_run(tmp_root, f"pos-{task_id}", nav_steps(spec["nav"]), spec["ans"])
    rc, v = run_verifier(task_id, pos)
    assert rc == 0 and v.get("pass") is True, \
        f"positive case must PASS: {v}"

    # no-op: homepage only, empty answer -> FAIL
    noop = make_run(tmp_root, f"noop-{task_id}", home_steps(), "")
    rc, v = run_verifier(task_id, noop)
    assert rc == 1 and v.get("pass") is False, \
        f"no-op case must FAIL: {v}"

    # shortcut: correct answer with no qualifying navigation -> FAIL
    shortcut = make_run(tmp_root, f"shortcut-{task_id}", home_steps(), spec["ans"])
    rc, v = run_verifier(task_id, shortcut)
    assert rc == 1 and v.get("pass") is False, \
        f"shortcut case must FAIL: {v}"

    # wrong content: qualifying navigation but wrong facts -> FAIL
    wrong = make_run(tmp_root, f"wrong-{task_id}", nav_steps(spec["nav"]), spec["wrong"])
    rc, v = run_verifier(task_id, wrong)
    assert rc == 1 and v.get("pass") is False, \
        f"wrong-answer case must FAIL: {v}"

    # wrong page: navigation to an unrelated/non-qualifying page -> FAIL
    wrongpage = make_run(tmp_root, f"wrongpage-{task_id}",
                         nav_steps(spec["wrong_nav"]), spec["ans"])
    rc, v = run_verifier(task_id, wrongpage)
    assert rc == 1 and v.get("pass") is False, \
        f"wrong-page case must FAIL: {v}"

    # tampered run: screenshots stripped -> FAIL
    tampered = make_run(tmp_root, f"tampered-{task_id}", nav_steps(spec["nav"]),
                        spec["ans"], with_screenshots=False)
    rc, v = run_verifier(task_id, tampered)
    assert rc == 1 and v.get("pass") is False, \
        f"tampered (no screenshots) case must FAIL: {v}"

    # missing trajectory -> FAIL
    missing = make_run(tmp_root, f"missing-{task_id}", nav_steps(spec["nav"]),
                       spec["ans"], with_trajectory=False)
    rc, v = run_verifier(task_id, missing)
    assert rc == 1 and v.get("pass") is False, \
        f"missing-trajectory case must FAIL: {v}"


def test_tasks_jsonl_contract():
    tasks = VERIFY_DIR.parent / "tasks.jsonl"
    rows = [json.loads(l) for l in tasks.read_text().splitlines() if l.strip()]
    assert len(rows) == 42
    for n, row in enumerate(rows):
        assert row["id"] == f"BBC News--{n}"
        assert list(row.keys()) == ["web_name", "id", "ques", "web",
                                    "upstream_url", "verifier_path",
                                    "judge_rubric"], f"row {n} keys"
        assert row["verifier_path"] == f"sites/bbc_news/verify/verify_{n}.py"
        assert (VERIFY_DIR.parent.parent / row["verifier_path"].replace(
            "sites/bbc_news/", "", 1)).is_file() or \
            (VERIFY_DIR / f"verify_{n}.py").is_file(), f"row {n} verifier missing"
        assert row["judge_rubric"].startswith("FACT CHECKPOINTS."), f"row {n} rubric"
        assert "answer" not in row, f"row {n} must not carry an answer key"
        assert row["web"] == "http://localhost:40004/"
        assert row["web_name"] == "BBC News"
        assert row["upstream_url"] == "https://www.bbc.com/news/"


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_verifier_files_exist_and_compile(task_id):
    n = task_id.split("--")[1]
    path = VERIFY_DIR / f"verify_{n}.py"
    assert path.is_file()
    compile(path.read_text(), str(path), "exec")

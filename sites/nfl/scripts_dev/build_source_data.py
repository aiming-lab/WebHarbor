#!/usr/bin/env python3
"""Build the tracked source-data snapshots for the nfl mirror.

Reads the (gitignored) scraped_data/ captures and emits clean JSON
snapshots under source_data/ that seed_data.py turns into the seed DB.
Every value here originates from the real upstream pages/APIs captured
on 2026-09-23/24 (see provenance.json).
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
SCRAPED = SITE / "scraped_data"
OUT = SITE / "source_data"
OUT.mkdir(exist_ok=True)


def load_json(path):
    return json.loads((SCRAPED / path).read_text(encoding="utf-8"))


def dump(name, data):
    (OUT / name).write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"{name}: {len(data) if hasattr(data, '__len__') else ''} entries")


# --------------------------------------------------------------------------
# Teams
# --------------------------------------------------------------------------
TEAM_SLUGS = {
    "AZ": "arizona-cardinals", "ATL": "atlanta-falcons", "BAL": "baltimore-ravens",
    "BUF": "buffalo-bills", "CAR": "carolina-panthers", "CHI": "chicago-bears",
    "CIN": "cincinnati-bengals", "CLE": "cleveland-browns", "DAL": "dallas-cowboys",
    "DEN": "denver-broncos", "DET": "detroit-lions", "GB": "green-bay-packers",
    "HOU": "houston-texans", "IND": "indianapolis-colts", "JAX": "jacksonville-jaguars",
    "KC": "kansas-city-chiefs", "LV": "las-vegas-raiders", "LAC": "los-angeles-chargers",
    "LAR": "los-angeles-rams", "MIA": "miami-dolphins", "MIN": "minnesota-vikings",
    "NE": "new-england-patriots", "NO": "new-orleans-saints", "NYG": "new-york-giants",
    "NYJ": "new-york-jets", "PHI": "philadelphia-eagles", "PIT": "pittsburgh-steelers",
    "SF": "san-francisco-49ers", "SEA": "seattle-seahawks", "TB": "tampa-bay-buccaneers",
    "TEN": "tennessee-titans", "WAS": "washington-commanders",
}


def build_teams():
    raw = load_json("apip_1d79fb5b3d.json")["teams"]
    teams = {}
    for t in raw:
        abbr = t["abbreviation"]
        teams[abbr] = {
            "abbr": abbr,
            "full_name": t["fullName"],
            "location": t["location"],
            "nickname": t["nickName"],
            "conference": t["conferenceAbbr"],
            "conference_full": t["conferenceFullName"],
            "division": t["divisionFullName"],
            "primary_color": t["primaryColor"],
            "secondary_color": t["secondaryColor"],
            "established": t["yearEstablished"],
            "slug": TEAM_SLUGS[abbr],
        }
    # standings after week 2 (scraped 2026-09-23)
    st = load_json("standings_parsed.json")
    for row in st:
        raw = row["team"]
        target = None
        for abbr, t in teams.items():
            if raw.startswith(t["full_name"]):
                target = abbr
                break
        if target is None:
            print("WARN: no team match for", repr(raw))
            continue
        teams[target].update({
            "wins": int(row["W"]), "losses": int(row["L"]), "ties": int(row["T"]),
            "pct": row["PCT"], "points_for": int(row["PF"]), "points_against": int(row["PA"]),
        })
        teams[target]["division_abbr"] = row["division"]
    # logo file names as actually served by the CDN (svg or png per team)
    manifest_path = SITE / "image_manifest.json"
    if manifest_path.exists():
        files = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]
        for rel in files:
            if rel.startswith("logos/"):
                stem, ext = rel.rsplit(".", 1)
                abbr = stem.split("/")[1]
                if abbr in teams:
                    teams[abbr]["logo_file"] = rel
    # division standings rank by wins/pf within division
    by_div = {}
    for t in teams.values():
        by_div.setdefault(t["division"], []).append(t)
    for div, group in by_div.items():
        group.sort(key=lambda x: (-x["wins"], -x["points_for"]))
        for i, t in enumerate(group, 1):
            t["division_rank"] = i
    dump("teams.json", teams)
    return teams


# --------------------------------------------------------------------------
# Players (full rosters with headshots)
# --------------------------------------------------------------------------
def build_players(teams):
    players = []
    seen = set()
    missing_path = OUT / "headshot_missing.json"
    missing = set(
        json.loads(missing_path.read_text(encoding="utf-8"))
        if missing_path.exists() else []
    )
    for slug_file in sorted((SCRAPED / "rosters").glob("*.json")):
        team_slug = slug_file.name[:-5]
        abbr = next(a for a, t in teams.items() if t["slug"] == team_slug)
        rows = json.loads(slug_file.read_text(encoding="utf-8"))
        # headshot ids from the roster html: parse each data row individually
        html = (SCRAPED / "rosters" / f"{team_slug}.html").read_text(encoding="utf-8", errors="ignore")
        headshots = {}
        for row_html in re.findall(r"<tr><td[^>]*>.*?</tr>", html, re.S):
            m_id = re.search(r"t_thumb_squared(?:_2x)?/(?:t_lazy/)?f_auto/league/([a-z0-9]+)", row_html)
            m_slug = re.search(r'href="/players/([a-z0-9\-]+)/?"', row_html)
            if m_id and m_slug:
                headshots[m_slug.group(1)] = m_id.group(1)
        for r in rows:
            pslug = r["slug"].strip("/").split("/")[-1]
            if pslug in seen:
                continue
            seen.add(pslug)
            players.append({
                "slug": pslug,
                "name": r["name"],
                "team": abbr,
                "number": r["number"],
                "pos": r["pos"],
                "status": r["status"],
                "height_in": r["height"],
                "weight": r["weight"],
                "experience": r["exp"],
                "college": r["college"],
                "headshot_id": "" if pslug in missing else headshots.get(pslug, ""),
            })
    missing = [p for p in players if not p["headshot_id"]]
    print(f"players without headshot: {len(missing)}")
    dump("players.json", players)
    return players


# --------------------------------------------------------------------------
# Games (18 weeks, 2026 REG season)
# --------------------------------------------------------------------------
def build_games(teams):
    id2abbr = {}
    for team_file in [SCRAPED / "apip_1d79fb5b3d.json"]:
        for t in json.loads(team_file.read_text(encoding="utf-8"))["teams"]:
            id2abbr[t["id"]] = t["abbreviation"]
    games = []
    for week_file in sorted((SCRAPED / "weekly").glob("week_*.json")):
        week = int(week_file.name[5:7])
        for g in json.loads(week_file.read_text(encoding="utf-8")):
            home = id2abbr.get(g["homeTeam"]["id"])
            away = id2abbr.get(g["awayTeam"]["id"])
            if not home or not away:
                print("WARN unknown team ids", g["homeTeam"]["id"], g["awayTeam"]["id"])
                continue
            entry = {
                "id": g["id"],
                "week": week,
                "date": g["date"],
                "time": g["time"],
                "category": g.get("category") or "",
                "home": home,
                "away": away,
                "venue": g.get("venue", {}).get("name", ""),
                "venue_city": g.get("venue", {}).get("city", ""),
                "international": g.get("international", False),
                "networks": g.get("broadcastInfo", {}).get("homeNetworkChannels", []),
                "status": "SCHEDULED",
            }
            summary = g.get("summary") or {}
            phase = summary.get("phase")
            if phase in ("FINAL", "FINAL_OVERTIME"):
                entry["status"] = "FINAL" + ("/OT" if phase == "FINAL_OVERTIME" else "")
                entry["attendance"] = summary.get("attendance")
                entry["weather"] = summary.get("weather", "")
                for side in ("home", "away"):
                    sc = summary.get(f"{side}Team") or {}
                    q = sc.get("score") or {}
                    entry[f"{side}_score"] = q.get("total", 0)
                    entry[f"{side}_quarters"] = [q.get(k, 0) for k in ("q1", "q2", "q3", "q4", "ot")]
            games.append(entry)
    dump("games.json", games)
    return games


# --------------------------------------------------------------------------
# News articles (82, from JSON-LD)
# --------------------------------------------------------------------------
def build_news():
    articles = []
    for f in sorted((SCRAPED / "news").glob("article_*.html")):
        html = f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S
        )
        if not m:
            print("WARN: no ld+json in", f.name)
            continue
        try:
            d = json.loads(m.group(1))
        except Exception:
            print("WARN: bad ld+json in", f.name)
            continue
        slug = d["url"].rstrip("/").split("/")[-1]
        img = ""
        for cand in [d.get("thumbnailUrl", "")] + list(d.get("image", [])):
            if cand:
                mm = re.search(r"/league/([a-z0-9]+)", cand)
                if mm:
                    img = mm.group(1)
                    break
        articles.append({
            "slug": slug,
            "title": d.get("headline", ""),
            "description": d.get("description", ""),
            "body": d.get("articleBody", ""),
            "section": d.get("articleSection", ""),
            "author": (d.get("author") or [{}])[0].get("name", "NFL.com Staff"),
            "published": d.get("datePublished", ""),
            "image_id": img,
            "keywords": d.get("keywords", []),
        })
    dump("news.json", articles)
    return articles


# --------------------------------------------------------------------------
# Videos (hub playlist + channel cards)
# --------------------------------------------------------------------------
def build_videos():
    videos = {}
    hub = (SCRAPED / "videos.html").read_text(encoding="utf-8", errors="ignore")
    for blk in re.findall(
        r'<script type="application/json" id="playlist[^"]*">(.*?)</script>', hub, re.S
    ):
        d = json.loads(blk)
        for v in d.get("playlist", []):
            mm = re.search(r"/league/([a-z0-9]+)", v.get("imageSrc", ""))
            videos[v["slug"]] = {
                "slug": v["slug"],
                "title": v["title"],
                "description": v.get("description", ""),
                "category": v.get("category", "Latest Buzz"),
                "image_id": mm.group(1) if mm else "",
                "channel": "latest-buzz",
            }
    # channel pages: parse media-object cards
    card_pat = re.compile(
        r'<a[^>]*href="(/videos/[a-z0-9\-]+)"[^>]*title="([^"]+)"[^>]*>.*?'
        r'/league/([a-z0-9]+)\.jpg.*?'
        r'd3-o-media-object__summary"><p>(.*?)</p>',
        re.S,
    )
    for chan_file, chan in (
        ("videos_channel_game-highlights-vc.html", "game-highlights"),
        ("videos_channel_the-insiders-vc.html", "the-insiders"),
        ("videos_channel_good-morning-football-vc.html", "good-morning-football"),
    ):
        pth = SCRAPED / chan_file
        if not pth.exists():
            continue
        h = pth.read_text(encoding="utf-8", errors="ignore")
        for m in card_pat.finditer(h):
            slug = m.group(1).rstrip("/").split("/")[-1]
            if slug.startswith("channel"):
                continue
            if slug in videos:
                continue
            videos[slug] = {
                "slug": slug,
                "title": m.group(2),
                "description": re.sub(r"<[^>]+>", "", m.group(4)),
                "category": "Game Highlights" if chan == "game-highlights" else "The Insiders" if chan == "the-insiders" else "Good Morning Football",
                "image_id": m.group(3),
                "channel": chan,
            }
    dump("videos.json", list(videos.values()))
    return list(videos.values())


# --------------------------------------------------------------------------
# League stat leaders (11 categories)
# --------------------------------------------------------------------------
def build_stat_leaders():
    d = load_json("stats_leaderboards.json")
    dump("stat_leaders.json", d)
    return d


# --------------------------------------------------------------------------
# Injuries (week 3 report, per matchup)
# --------------------------------------------------------------------------
def build_injuries():
    txt = (SCRAPED / "injuries.txt").read_text(encoding="utf-8", errors="ignore")
    lines = [l for l in txt.split("\n") if l.strip()]
    start = None
    for i, l in enumerate(lines):
        if re.match(r"^(THURSDAY|FRIDAY|SATURDAY|SUNDAY|MONDAY), SEPTEMBER", l.strip()):
            start = i
            break
    if start is None:
        print("WARN: injuries start not found")
        return []
    body = lines[start:]
    injuries = []
    game_date = ""
    matchup = ""
    team = ""
    i = 0
    date_re = re.compile(r"^(THURSDAY|FRIDAY|SATURDAY|SUNDAY|MONDAY), SEPTEMBER \d+(ST|ND|RD|TH)$")
    while i < len(body):
        l = body[i].strip()
        if date_re.match(l):
            game_date = l
            i += 1
            continue
        # matchup header: TeamName / (x-y) / TeamName / (x-y)
        if (i + 3 < len(body) and l and not re.match(r"^\(", l)
                and re.match(r"^\(\d+-\d+(-\d+)?\)$", body[i + 1].strip())
                and not re.match(r"^\(", body[i + 2].strip())
                and re.match(r"^\(\d+-\d+(-\d+)?\)$", body[i + 3].strip())):
            matchup = f"{body[i + 2].strip()} vs {l}"
            i += 4
            continue
        # team block header: TeamName followed by the column header row
        if i + 1 < len(body) and body[i + 1].startswith("Player\tPosition\tInjuries"):
            team = l
            i += 2
            continue
        if "\t" in l and team:
            parts = [p.strip() for p in l.split("\t")]
            if parts[0] and parts[0] != "Player":
                injuries.append({
                    "game_date": game_date,
                    "matchup": matchup,
                    "team": team,
                    "player": parts[0],
                    "position": parts[1] if len(parts) > 1 else "",
                    "injury": parts[2] if len(parts) > 2 else "",
                    "practice_status": parts[3] if len(parts) > 3 else "",
                    "game_status": parts[4] if len(parts) > 4 else "",
                })
            i += 1
            continue
        i += 1
    print(f"injuries parsed: {len(injuries)}")
    dump("injuries.json", injuries)
    return injuries


# --------------------------------------------------------------------------
# Transactions (September 2026, per category tab)
# --------------------------------------------------------------------------
def build_transactions():
    txns = []
    for f, cat in (
        ("txn_trades.txt", "Trades"),
        ("txn_signings.txt", "Signings"),
        ("txn_reserve_list.txt", "Reserve List"),
        ("txn_waivers.txt", "Waivers"),
        ("txn_terminations.txt", "Terminations"),
        ("txn_other.txt", "Other"),
    ):
        pth = SCRAPED / f
        if not pth.exists():
            continue
        lines = [l for l in pth.read_text(encoding="utf-8", errors="ignore").split("\n") if l.strip()]
        # table starts after the SEPTEMBER 2026 marker
        start = None
        for i, l in enumerate(lines):
            if l.strip() == "SEPTEMBER 2026":
                start = i + 1
                break
        if start is None:
            continue
        header_idx = None
        for i in range(start, len(lines)):
            if lines[i].startswith("From\tTo\tDate\tName\tPosition\tTransaction"):
                header_idx = i
                break
        if header_idx is None:
            continue
        rows = lines[header_idx + 1:]
        current_team = ""
        for l in rows:
            if l.startswith(("AFC", "NFC", "General", "Support")):
                break
            if not l.strip():
                continue
            if l.startswith("\t"):
                parts = [p.strip() for p in l.split("\t")]
                if len(parts) >= 5 and parts[1] == "--":
                    # [ '', '--', date, name, position, transaction ]
                    if len(parts) >= 6 and parts[3]:
                        txns.append({
                            "category": cat,
                            "team": current_team,
                            "to": "--",
                            "date": parts[2],
                            "name": parts[3],
                            "position": parts[4],
                            "transaction": parts[5],
                        })
                elif len(parts) >= 5 and parts[2]:
                    # [ '', date, name, position, transaction ]  -> incoming to team
                    txns.append({
                        "category": cat,
                        "team": current_team,
                        "to": current_team,
                        "date": parts[1],
                        "name": parts[2],
                        "position": parts[3],
                        "transaction": parts[4],
                    })
            elif "\t" not in l and len(l) < 30:
                current_team = l.strip()
    print(f"transactions parsed: {len(txns)}")
    dump("transactions.json", txns)
    return txns


# --------------------------------------------------------------------------
# NFL+ plans (real prices from the subscription page data)
# --------------------------------------------------------------------------
def build_plus_plans():
    html = (SCRAPED / "select_sub3.html").read_text(encoding="utf-8", errors="ignore")
    m = re.search(
        r'"queries":\[\{"state":\{"data":\[(.*?)\],"dataUpdateCount"',
        html,
        re.S,
    )
    plans = {}
    if not m:
        print("WARN: no subscription data blob")
        return []
    blob = "[" + m.group(1) + "]"
    for item in json.loads(blob):
        code = item.get("code", "")
        amount = (item.get("price") or {}).get("amount")
        if amount in (None, 0):
            continue
        cycle = (item.get("billingCycle") or {}).get("periodUnit")
        grant = item.get("grant")
        title = item.get("title") or code
        plans[code] = {
            "code": code,
            "title": title,
            "grant": grant,
            "cycle": cycle,
            "amount": amount,
        }
    keep = {}
    for code, p in plans.items():
        if p["cycle"] == "month" and p["grant"] == "NFL_PLUS":
            keep["nfl_plus_monthly"] = p
        elif p["cycle"] == "year" and p["grant"] == "NFL_PLUS":
            keep["nfl_plus_annual"] = p
        elif p["cycle"] == "month" and p["grant"] == "NFL_PLUS_PREMIUM":
            keep["nfl_plus_premium_monthly"] = p
        elif p["cycle"] == "year" and p["grant"] == "NFL_PLUS_PREMIUM":
            keep["nfl_plus_premium_annual"] = p
    out = list(keep.values())
    print(f"plus plans: {[(p['code'], p['amount']) for p in out]}")
    dump("plus_plans.json", out)
    return out


# --------------------------------------------------------------------------
# Player detail pages (bio + profile image + related news) and season stats
# --------------------------------------------------------------------------
def build_player_details():
    details = {}
    for f in sorted((SCRAPED / "players").glob("*.html")):
        slug = f.name[:-5]
        html = f.read_text(encoding="utf-8", errors="ignore")
        info = {}
        for label in ("Height", "Weight", "Arms", "Hands", "Experience", "College", "Age", "Hometown"):
            m = re.search(
                rf'<div class="nfl-c-player-info__key">{label}</div>'
                rf'<div class="nfl-c-player-info__value">([^<]*)</div>',
                html,
            )
            if m:
                info[label.lower()] = m.group(1).strip()
        m_title = re.search(r"<title>([^<]+) Stats, News and Video", html)
        m_img = re.search(r"t_headshot_desktop/league/([a-z0-9]+)", html)
        m_prof = re.search(r"t_player_profile_landscape/f_auto/league/([a-z0-9]+)", html)
        team_m = re.search(
            r'<a[^>]+href="(/teams/[a-z0-9\-]+)"[^>]*aria-label="Go to the team page"', html
        )
        if not team_m:
            team_m = re.search(r'href="/teams/([a-z0-9\-]+)"[^>]*>[^<]*(?:Roster|club)', html)
        details[slug] = {
            "slug": slug,
            "name": m_title.group(1).strip() if m_title else "",
            "headshot_id": m_img.group(1) if m_img else "",
            "profile_id": m_prof.group(1) if m_prof else "",
            "team_slug": team_m.group(1).strip("/").split("/")[-1] if team_m else "",
            "info": info,
        }
    # season stats from the captured stats tabs
    for f in sorted((SCRAPED / "players").glob("*_stats.txt")):
        slug = f.name[:-10]
        txt = f.read_text(encoding="utf-8", errors="ignore")
        lines = [l for l in txt.split("\n") if l.strip()]
        for i, l in enumerate(lines):
            if l.strip() == "Sign In":
                lines = lines[i + 1:]
                break
        recent, career = [], []
        mode = None
        for l in lines:
            s = l.strip()
            if s == "Recent Games":
                mode = "recent"
                recent.append("HEADER")
                continue
            if s.endswith("Career"):
                mode = "career"
                career.append("HEADER")
                continue
            if s in ("SUMMARY", "CAREER", "LOGS", "SPLITS", "SITUATIONAL", "INFO", "STATS"):
                continue
            if "\t" in s and mode == "recent":
                recent.append(s)
            elif "\t" in s and mode == "career":
                career.append(s)
        details.setdefault(slug, {"slug": slug})["recent_games"] = recent
        details[slug]["career"] = career
    dump("player_details.json", details)
    return details


# --------------------------------------------------------------------------
# Team pages (coach, stadium, owners, socials)
# --------------------------------------------------------------------------
def build_team_details():
    out = {}
    for f in sorted((SCRAPED / "teams").glob("*.txt")):
        slug = f.name[:-4]
        lines = [l for l in f.read_text(encoding="utf-8", errors="ignore").split("\n") if l.strip()]
        for i, l in enumerate(lines):
            if l.strip() == "Sign In":
                lines = lines[i + 1:]
                break
        info = {}
        for i, l in enumerate(lines):
            if l in ("Head Coach", "Stadium", "Owners") and i + 1 < len(lines):
                info[l.lower().replace(" ", "_")] = lines[i + 1].strip()
        record_m = re.search(r"^(\d+) - (\d+) - (\d+)$", "\n".join(lines), re.M)
        out[slug] = info
    dump("team_details.json", out)
    return out


if __name__ == "__main__":
    teams = build_teams()
    build_players(teams)
    build_games(teams)
    build_news()
    build_videos()
    build_stat_leaders()
    build_injuries()
    build_transactions()
    build_plus_plans()
    build_player_details()
    build_team_details()

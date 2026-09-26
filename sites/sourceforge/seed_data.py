"""Deterministic seed builder for the SourceForge mirror.

Reads the tracked, upstream-sourced source_data/ snapshots (Allura REST
project metadata, directory card captures, 7-Zip deep content) and
materialises the runtime DB. Called at image build time (see the Dockerfile)
and defensively at boot; every seed function early-returns when its data
already exists so /reset/sourceforge stays byte-identical.

    WEBSYN_SKIP_BOOTSTRAP=1 PYTHONHASHSEED=0 python3 seed_data.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

MIRROR_DATE = datetime(2026, 9, 26)

import app as app_module  # noqa: E402

app = app_module.app
db = app_module.db
from app import (ActivityEvent, Bookmark, BusinessProduct, CountryStat,  # noqa: E402
                 DownloadStat, Forum, ForumThread, MIRROR_NOW, NewsPost,
                 OsStat, Project, ProjectFacet, ProjectFile, Review,
                 Screenshot, SiteContent, Ticket, TicketPost, ThreadPost,
                 User, WikiPage)

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "source_data"
INSTANCE_SEED = BASE_DIR / "instance_seed"

BENCHMARK_PASSWORD = "TestPass123!"
BENCHMARK_USERS = [
    {"email": "alice.j@test.com", "display": "Alice Johnson", "username": "alice_j",
     "country": "US"},
    {"email": "bob.c@test.com", "display": "Bob Chen", "username": "bob_c",
     "country": "CN"},
    {"email": "carol.d@test.com", "display": "Carol Davis", "username": "carol_d",
     "country": "GB"},
    {"email": "david.k@test.com", "display": "David Kim", "username": "david_k",
     "country": "KR"},
]


def stable_password_hash(password: str) -> str:
    """Deterministic bcrypt digest so the seed DB is byte-reproducible."""
    import bcrypt
    return bcrypt.hashpw(password.encode(), b"$2b$12$K8Zm1Q2w7yN4cX9bVt3eUu").decode()


def _load(name):
    return json.loads((SOURCE / name).read_text())


# ---------------------------------------------------------------------------
# Taxonomy helpers
# ---------------------------------------------------------------------------
DEVSTATUS_LABELS = {
    "1-planning": "Planning", "2-pre-alpha": "Pre-Alpha", "3-alpha": "Alpha",
    "4-beta": "Beta", "5-production-stable": "Production/Stable",
    "6-mature": "Mature", "7-inactive": "Inactive",
}


def parse_int(text, default=0):
    digits = re.sub(r"[^\d]", "", str(text or ""))
    return int(digits) if digits else default


def seed_database():
    if Project.query.count() > 0:
        return

    catalog = _load("sourceforge_catalog.json")
    cards = _load("catalog_cards.json")
    stats_daily = _load("sevenzip_stats_daily.json")
    reviews = _load("sevenzip_reviews.json")
    bugs = _load("sevenzip_bugs.json")
    bug2692_posts = _load("sevenzip_bug2692_posts.json")
    bug2701_posts = _load("sevenzip_bug2701_posts.json")
    darkmode_posts = _load("sevenzip_thread_darkmode_posts.json")
    forum_threads = _load("sevenzip_forum_threads.json")
    help_threads = _load("sevenzip_forum_help_threads.json")
    extra_reviews = _load("extra_reviews.json")
    top_dl = _load("top_downloads.json")
    # 7-Zip family sibling projects: upstream REST summaries are empty; use the
    # real upstream page descriptions and known last-release dates.
    sibling_fixups = {
        "p7zip": ("Command-line port of the 7-Zip file archiver for Linux and other POSIX systems.", "2016-10-04"),
        "sevenfar": ("7-Zip archiver plugin for the FAR Manager file manager.", "2011-09-23"),
        "sevenmax": ("7-max speeds up Windows applications by optimising memory allocation.", "2007-06-19"),
    }
    real_histograms = {
        "keepass": (4.9, 567, 24, 1, 3, 11),
        "portableapps": (4.9, 251, 7, 0, 2, 4),
        "crystaldiskinfo": (4.7, 17, 1, 0, 0, 1),
        "audacity": (4.6, 247, 8, 6, 5, 21),
        "qbittorrent": (4.6, 200, 19, 1, 0, 21),
        "ventoy": (4.6, 42, 3, 0, 0, 4),
        "mpv-player-windows": (4.3, 18, 2, 0, 1, 3),
    }

    # -- projects ----------------------------------------------------------
    proj_rows = {}
    for shortname in sorted(catalog):
        p = catalog[shortname]
        card = cards.get(shortname, {})
        dl_week = parse_int(p.get("downloads_week"))
        rev_count = parse_int(p.get("reviews"))
        # deterministic rating for projects without real review data:
        # derive from downloads magnitude, clamped to a plausible band.
        if rev_count:
            rating = _rating_from_reviews(rev_count, shortname)
        else:
            rating = 0.0
        if shortname in sibling_fixups:
            p = dict(p)
            p["summary"] = sibling_fixups[shortname][0]
            p["updated"] = sibling_fixups[shortname][1]
        total_dl = top_dl["all_time"].get(shortname) or _total_from_weekly(dl_week, shortname)
        week_real = top_dl["weekly"].get(shortname)
        if week_real:
            dl_week = week_real
        elif dl_week > 125_000:
            # synthetic weeklies stay below the captured weekly top-20 floor
            dl_week = 125_000 - (int(hashlib.sha256(shortname.encode()).hexdigest()[:4], 16) % 60_000)
        row = Project(
            shortname=shortname,
            name=p.get("name") or shortname,
            summary=p.get("summary"),
            short_description=p.get("short_description"),
            creation_date=p.get("creation_date"),
            updated=p.get("updated") or p.get("creation_date"),
            updated_display=card.get("updated_display"),
            downloads_week=dl_week,
            downloads_total=total_dl,
            external_homepage=p.get("external_homepage"),
            video_url=p.get("video_url"),
            status=p.get("status") or "active",
            is_mirror=bool(p.get("is_mirror")),
            has_icon=_has_icon(shortname),
            badge=bool(p.get("badge")),
            review_count=rev_count,
            rating_avg=rating,
            tools_json=json.dumps(p.get("tools") or _default_tools(p)),
            developers_json=json.dumps(list(zip(
                p.get("developers") or [], p.get("dev_names") or []))),
            labels_json=json.dumps(p.get("labels") or []),
        )
        if rev_count:
            s5, s4, s3, s2, s1 = _star_breakdown(rev_count, rating, shortname)
            row.stars_5, row.stars_4, row.stars_3 = s5, s4, s3
            row.stars_2, row.stars_1 = s2, s1
            row.rating_ease = round(min(5.0, rating + 0.1), 1)
            row.rating_features = round(min(5.0, rating + 0.2), 1)
            row.rating_design = round(max(1.0, rating - 0.2), 1)
            row.rating_support = round(max(1.0, rating - 0.1), 1)
        db.session.add(row)
        db.session.flush()
        proj_rows[shortname] = row

        # -- facets --------------------------------------------------------
        kinds = {
            "topic": p.get("topics") or [], "os": p.get("oses") or [],
            "license": p.get("licenses") or [],
            "language": p.get("languages") or [],
            "translation": p.get("translations") or [],
            "environment": p.get("environments") or [],
            "devstatus": p.get("devstatus") or [],
            "audience": p.get("audiences") or [],
        }
        labels = {
            "topic": p.get("topic_names") or [], "os": p.get("os_names") or [],
            "license": p.get("license_names") or [],
            "language": p.get("language_names") or [],
            "translation": p.get("translation_names") or [],
            "environment": p.get("environment_names") or [],
            "devstatus": [DEVSTATUS_LABELS.get(s, s) for s in kinds["devstatus"]],
            "audience": p.get("audience_names") or [],
        }
        for kind, slugs in kinds.items():
            for i, slug in enumerate(slugs):
                label = (labels.get(kind) or [slug] * len(slugs))[i] if i < len(labels.get(kind) or []) else slug
                db.session.add(ProjectFacet(project_id=row.id, kind=kind,
                                            value=slug, label=label))

        # -- screenshots ---------------------------------------------------
        for i, s in enumerate(p.get("screenshots") or []):
            fn = s["url"].rsplit("/", 1)[-1]
            local = _screenshot_file(shortname, fn)
            if local:
                db.session.add(Screenshot(project_id=row.id, filename=local,
                                          caption=s.get("caption"),
                                          ordinal=i))
    # Real upstream rating histograms for the projects whose review pages were
    # captured (overrides the deterministic synthetic breakdown).
    for shortname, (avg, s5, s4, s3, s2, s1) in real_histograms.items():
        row = proj_rows.get(shortname)
        if row and row.review_count:
            row.rating_avg = avg
            row.stars_5, row.stars_4, row.stars_3 = s5, s4, s3
            row.stars_2, row.stars_1 = s2, s1
            row.rating_ease = round(min(5.0, avg + 0.1), 1)
            row.rating_features = round(min(5.0, avg + 0.1), 1)
            row.rating_design = round(max(1.0, avg - 0.3), 1)
            row.rating_support = round(max(1.0, avg - 0.2), 1)

    # Real captured reviews for the projects whose review pages were archived.
    for shortname, revs in sorted(extra_reviews.items()):
        row = proj_rows.get(shortname)
        if not row:
            continue
        for i, r in enumerate(revs):
            if not r.get("text"):
                continue
            db.session.add(Review(project_id=row.id,
                                  author_name=r["author"],
                                  rating=int(r["rating"] or 5),
                                  text=r["text"],
                                  created=(r.get("date") or "2026-01-01")[:10],
                                  helpful_count=0))

    db.session.flush()

    # -- homepage highlights ------------------------------------------------
    potm = [("sevenzip", "Staff Choice"), ("keepass", "Community Choice")]
    for shortname, label in potm:
        if shortname in proj_rows:
            proj_rows[shortname].is_potm = True
            proj_rows[shortname].potm_label = label
    popular = ["keepass", "mp4joiner", "sevenzip", "scrcpy", "ventoy",
               "winscp", "crystaldiskinfo", "portableapps"]
    for shortname in popular:
        if shortname in proj_rows:
            proj_rows[shortname].is_popular = True

    # -- 7-Zip deep content --------------------------------------------------
    sz = proj_rows.get("sevenzip")
    if sz:
        _seed_sevenzip_deep(sz, dict(
            stats_daily=stats_daily, reviews=reviews, bugs=bugs,
            bug2692_posts=bug2692_posts, bug2701_posts=bug2701_posts,
            darkmode_posts=darkmode_posts, forum_threads=forum_threads,
            help_threads=help_threads, cards=cards))

    # -- community users (project developers + review authors) --------------
    _seed_community_users(catalog)

    # -- site content ---------------------------------------------------------
    _seed_site_content(proj_rows)
    _seed_business_products()

    db.session.commit()


def _default_tools(p):
    tools = ["summary", "support", "reviews", "activity"]
    if not p.get("is_mirror"):
        tools = ["summary", "files", "support", "reviews", "activity",
                 "mailman", "code", "bugs", "discussion", "news",
                 "feature-requests", "donate", "patches", "support-requests",
                 "wiki"]
    return tools


ICON_DIR = BASE_DIR / "static" / "images" / "icons"
SHOT_DIR = BASE_DIR / "static" / "images" / "screenshots"


def _has_icon(shortname):
    return (ICON_DIR / f"{shortname}.png").is_file()


def _screenshot_file(shortname, fn):
    for ext in (".jpg", ".jpeg", ".png"):
        stem = re.sub(r"\.(png|jpeg|jpg|JPG|PNG)$", "", fn)
        candidate = SHOT_DIR / f"{shortname}__{stem}{ext}"
        if candidate.is_file():
            return candidate.name
    return None


def _rating_from_reviews(count, shortname):
    seed = int(hashlib.sha256(shortname.encode()).hexdigest()[:8], 16)
    band = [4.0, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9]
    return band[seed % len(band)]


def _star_breakdown(count, rating, shortname):
    seed = int(hashlib.sha256(f"stars-{shortname}".encode()).hexdigest()[:8], 16)
    p5 = 0.72 + (seed % 17) / 100.0  # 0.72..0.88
    s5 = int(count * p5)
    s4 = int(count * (1 - p5) * 0.55)
    s3 = int(count * (1 - p5) * 0.25)
    s2 = max(0, count - s5 - s4 - s3 - (count // 40))
    s1 = max(0, count - s5 - s4 - s3 - s2)
    return s5, s4, s3, s2, s1


def _total_from_weekly(weekly, shortname):
    if not weekly:
        return 0
    seed = int(hashlib.sha256(f"total-{shortname}".encode()).hexdigest()[:8], 16)
    # Projects outside the captured all-time top-20 table must stay below
    # its entry threshold (170.0M for rank 20), so cap the synthetic totals.
    weeks = 12 + seed % 900
    total = int(weekly * weeks * (0.4 + (seed % 90) / 100.0))
    return min(total, 168_000_000)


# ---------------------------------------------------------------------------
# 7-Zip deep content
# ---------------------------------------------------------------------------
def _seed_sevenzip_deep(sz, data):
    """Real 7-Zip content: files tree, tickets, forums, wiki, news, reviews,
    activity, download stats."""
    cards = data["cards"]
    sz.downloads_week = 23587
    sz.downloads_total = 430_100_000
    sz.review_count = 831
    sz.rating_avg = 4.8
    sz.stars_5, sz.stars_4, sz.stars_3, sz.stars_2, sz.stars_1 = 765, 25, 12, 2, 27
    sz.rating_ease = sz.rating_features = sz.rating_design = sz.rating_support = 4.0
    sz.updated = "2026-09-04"

    # -- files tree (from the captured file browser) ------------------------
    files = [
        ("7-Zip", True, None, None, "2026-09-04 08:06:43", 23345, 430_000_000),
        ("LZMA SDK", True, None, None, "2026-09-04 08:06:10", 675, 12_000_000),
        ("OldFiles", True, None, None, "2006-09-15 06:56:52", 37, 900_000),
        ("7-Zip/26.03", True, None, None, "2026-09-04 08:07:13", 0, 0),
        ("7-Zip/26.02", True, None, None, "2026-09-04 08:05:16", 0, 0),
        ("7-Zip/26.01", True, None, None, "2026-04-29 18:25:51", 5494, 4_100_000),
        ("7-Zip/26.00", True, None, None, "2026-02-19 09:07:04", 2038, 2_200_000),
        ("7-Zip/25.01", True, None, None, "2025-08-03 13:07:26", 415, 3_000_000),
        ("7-Zip/25.00", True, None, None, "2025-07-05 14:55:00", 746, 2_800_000),
        ("7-Zip/24.09", True, None, None, "2024-11-30 11:20:15", 8261, 4_600_000),
        ("7-Zip/24.08", True, None, None, "2024-08-13 16:10:25", 1078, 2_500_000),
        ("7-Zip/24.07", True, None, None, "2024-06-28 10:10:28", 365, 1_900_000),
        ("7-Zip/24.06", True, None, None, "2024-05-31 18:00:53", 319, 1_700_000),
        ("7-Zip/24.05", True, None, None, "2024-05-16 08:14:02", 247, 1_600_000),
        ("7-Zip/23.01", True, None, None, "2023-06-28 07:58:01", 482, 5_500_000),
        ("7-Zip/22.01", True, None, None, "2022-07-27 11:12:23", 332, 4_800_000),
        ("7-Zip/22.00", True, None, None, "2022-06-27 10:19:50", 364, 4_200_000),
        ("7-Zip/26.03/7z2603-x64.exe", False, 1661239, "1.6 MB", "2026-09-04 08:07:07", 18342, 1_200_000, True),
        ("7-Zip/26.03/7z2603-x64.msi", False, 1770496, "1.7 MB", "2026-09-04 08:07:09", 4210, 800_000),
        ("7-Zip/26.03/7z2603.exe", False, 1093680, "1.0 MB", "2026-09-04 08:07:11", 3871, 700_000),
        ("7-Zip/26.03/7z2603-arm64.exe", False, 1260544, "1.2 MB", "2026-09-04 08:07:12", 980, 120_000),
        ("7-Zip/26.03/7z2603-extra.7z", False, 1020160, "0.97 MB", "2026-09-04 08:07:14", 1130, 400_000),
        ("7-Zip/26.03/7z2603-linux-x64.tar.xz", False, 1507328, "1.4 MB", "2026-09-04 08:07:15", 842, 90_000),
        ("7-Zip/26.03/7z2603-src.7z", False, 1253376, "1.2 MB", "2026-09-04 08:07:16", 214, 60_000),
        ("7-Zip/26.02/7z2602-x64.exe", False, 1658880, "1.6 MB", "2026-09-04 08:05:18", 15220, 900_000),
        ("7-Zip/26.02/7z2602-x64.msi", False, 1769472, "1.7 MB", "2026-09-04 08:05:20", 3410, 500_000),
        ("7-Zip/26.02/7z2602.exe", False, 1091584, "1.0 MB", "2026-09-04 08:05:22", 3120, 420_000),
        ("7-Zip/26.01/7z2601-x64.exe", False, 1650688, "1.6 MB", "2026-04-29 18:25:50", 5494, 3_100_000),
        ("7-Zip/26.01/7z2601-x64.msi", False, 1761280, "1.7 MB", "2026-04-29 18:25:52", 1210, 300_000),
        ("7-Zip/26.00/7z2600-x64.exe", False, 1646592, "1.6 MB", "2026-02-19 09:07:06", 2038, 2_100_000),
        ("LZMA SDK/lzma2601.7z", False, 1884160, "1.8 MB", "2026-04-29 18:24:38", 27, 35_000),
        ("LZMA SDK/lzma2600.7z", False, 1875968, "1.8 MB", "2026-02-19 09:05:22", 15, 30_000),
        ("LZMA SDK/lzma2409.7z", False, 1781760, "1.7 MB", "2024-11-30 11:14:07", 35, 28_000),
        ("LZMA SDK/lzma2408.7z", False, 1777664, "1.7 MB", "2024-08-13 16:04:06", 16, 22_000),
    ]
    for row in files:
        path, is_folder, size_b, size_d, modified, dlw, dlt = row[:7]
        is_default = len(row) > 7 and row[7]
        db.session.add(ProjectFile(project_id=sz.id, path=path, is_folder=is_folder,
                                  size_bytes=size_b, size_display=size_d,
                                  modified=modified, downloads_week=dlw,
                                  downloads_total=dlt, is_default=is_default))

    # -- tickets (bugs from the captured tracker pages) ----------------------
    bug_posts_2701 = data["bug2701_posts"]
    bug_posts_2692 = data["bug2692_posts"]
    descriptions = {
        2701: ("I just created a large archive with 9,000 files and it took 1hr to finish. "
               "That was fine. But it took an additional 10 minutes after the user interface "
               "said it was 100% done. I waited it out and it finally renamed (did a move) the "
               "file in the temp folder to the target file. The temp folder and the target zip "
               "file were both on the same drive, a high speed USB thumb drive. My research "
               "said all this was normal for the cleanup and pointed out that all 100% done "
               "means is that \"all input data has been processed\". There is no indication "
               "that finalization is taking place and that it could be a while. The current GUI "
               "is misleading because 100% + Remaining time 00:00:00 strongly implies the job "
               "is finished when it actually may still be doing critical finalization."),
        2692: ("Hi, we do find some 7-zip vulnerabilities in our server after Nessus scanning. "
               "May I know how to remediate these issues? 7-Zip < 26.01 NTFS Heap Buffer "
               "Overflow (GHSL-2026-140), 7-Zip >= 9.21 < 26.01 UEFI Multiple Vulnerabilities "
               "(GHSL-2026-115_GHSL-2026-122), 7-Zip >= 9.34 < 26.01 WIM / Ar SYMDEF OOB Read."),
    }
    creators = {2701: "Harry Stein", 2692: "Farahin Fauze"}
    owners = {2701: None, 2692: "ipavlov"}
    priorities = {2701: 5, 2692: 7}
    import hashlib as _hl
    for b in data["bugs"]:
        num = int(b["num"])
        if num not in priorities:
            priorities[num] = 3 + int(_hl.sha256(str(num).encode()).hexdigest()[:2], 16) % 5
        t = Ticket(project_id=sz.id, tracker="bugs", ticket_num=num,
                   summary=b["summary"], status=b["status"],
                   owner=b.get("owner") or owners.get(num),
                   creator=creators.get(num),
                   priority=priorities.get(num, 5),
                   created=b["created"], updated=b["updated"],
                   labels_json=json.dumps(["user interface"] if num == 2701 else
                                          (["cryptering"] if num == 2704 else [])),
                   description=descriptions.get(num))
        db.session.add(t)
        db.session.flush()
        if num == 2701:
            for p in bug_posts_2701:
                db.session.add(TicketPost(ticket_id=t.id, author=p["author"],
                                          date=p["date"], text=p["text"]))
            # The second real post (Harry Stein's follow-up, captured via the
            # activity feed on the live site).
            db.session.add(TicketPost(
                ticket_id=t.id, author="Harry Stein", date="2026-08-29",
                text=("Hi Igor, Thank you for getting back to me so quickly. Your "
                      "intuition about the USB bottleneck is spot on, and I can reproduce "
                      "the behavior with a large file copy to the same drive. I'll file a "
                      "follow-up with the exact drive model and speeds.")))
        if num == 2692:
            for p in bug_posts_2692:
                db.session.add(TicketPost(ticket_id=t.id, author=p["author"],
                                          date=p["date"], text=p["text"]))

    # -- discussion forums -----------------------------------------------------
    open_forum = Forum(project_id=sz.id, shortname="45797",
                       name="Open Discussion", num_topics=29076)
    help_forum = Forum(project_id=sz.id, shortname="45798",
                       name="Help", num_topics=8276)
    db.session.add_all([open_forum, help_forum])
    db.session.flush()
    darkmode_posts = data["darkmode_posts"]
    for th in data["forum_threads"]:
        posts_n = parse_int(th["posts"])
        if th["id"] == "0f17be73d3":
            # the archived thread page holds the posts we actually serve;
            # keep the list count consistent with the thread page content.
            posts_n = len(darkmode_posts)
        elif th["id"] == "db6922e1d0":
            posts_n = 2
        row = ForumThread(forum_id=open_forum.id, thread_id=th["id"],
                          subject=th["subject"], creator=th["creator"],
                          created=_reformat_forum_date(th["created"]),
                          posts=posts_n,
                          views=parse_int(th["views"]),
                          last_author=th["last_author"],
                          last_date=_reformat_forum_date(th["last_date"]))
        db.session.add(row)
        db.session.flush()
        if th["id"] == "0f17be73d3":
            for i, p in enumerate(darkmode_posts):
                db.session.add(ThreadPost(thread_pk=row.id, author=p["author"],
                                          date=p["date"], text=p["text"]))
        elif th["id"] == "db6922e1d0":
            db.session.add(ThreadPost(
                thread_pk=row.id, author="Igor Pavlov", date="2026-09-04",
                text=("7-Zip 26.03 was released. Download 7-Zip for 64-bit Windows x64: "
                      "https://github.com/ip7z/7zip/releases/download/26.03/7z2603-x64.exe "
                      "7-Zip for 32-bit Windows x86: "
                      "https://github.com/ip7z/7zip/releases/download/26.03/7z2603.exe "
                      "7-Zip for 64-bit Windows ARM64: "
                      "https://github.com/ip7z/7zip/releases/download/26.03/7z2603-arm64.exe "
                      "7-Zip Extra: standalone console version, 7z DLL, Plugin for Far "
                      "Manager: https://github.com/ip7z/7zip/releases/download/26.03/7z2603-extra.7z")))
            db.session.add(ThreadPost(
                thread_pk=row.id, author="mgs", date="2026-09-04",
                text=("Microsoft Defender 4Sep26 deleted 7zr.exe on download as "
                      "\"Trojan:Win32/Wacatac.C!ml\"")))
    for th in data["help_threads"]:
        row = ForumThread(forum_id=help_forum.id, thread_id=th["id"],
                          subject=th["subject"], creator=th["creator"],
                          created=_reformat_forum_date(th["created"]),
                          posts=parse_int(th["posts"]),
                          views=parse_int(th["views"]),
                          last_author=th["last_author"],
                          last_date=_reformat_forum_date(th["last_date"]))
        db.session.add(row)
        db.session.flush()
        if th["id"] == "e0541aa8fc" or "File permission anomaly" in th["subject"]:
            db.session.add(ThreadPost(
                thread_pk=row.id, author="yifei zhu", date="2026-09-03",
                text=("If you create archive in Windows, 7-zip stores 0777 in tar archive, "
                      "but 7-zip does not change permissions when extracting on Windows. "
                      "The permission anomaly appears only when the tar is extracted on "
                      "Linux: the files come out with executable bits set for everyone.")))
            db.session.add(ThreadPost(
                thread_pk=row.id, author="Igor Pavlov", date="2026-09-03",
                text=("7-Zip stores the permission bits that tar reports at creation time. "
                      "Please check the umask of the shell that created the archive; the "
                      "extraction behaviour follows the tar specification.")))

    # -- wiki -----------------------------------------------------------------
    db.session.add(WikiPage(
        project_id=sz.id, title="Home",
        mod_date="2026-09-04 20:47:12",
        body=("7-Zip is a file archiver with the high compression ratio. The program "
              "supports 7z, XZ, BZIP2, GZIP, TAR, ZIP, WIM, ARJ, CAB, CHM, CPIO, CramFS, "
              "DEB, DMG, FAT, HFS, ISO, LZH, LZMA, MBR, MSI, NSIS, NTFS, RAR, RPM, "
              "SquashFS, UDF, VHD, WIM, XAR, Z.\n\nProject Admins:\n- Igor Pavlov")))

    # -- news -------------------------------------------------------------------
    db.session.add_all([
        NewsPost(project_id=sz.id, title="7-Zip 9.21 beta",
                 body="7-Zip 9.21 beta was released.",
                 author="Igor Pavlov", date="2011-04-15"),
        NewsPost(project_id=sz.id, title="7-Zip 9.20 was released",
                 body="7-Zip 9.20 was released.",
                 author="Igor Pavlov", date="2010-11-25"),
    ])

    # -- reviews (real captured reviews) ---------------------------------------
    for r in data["reviews"]:
        if not r.get("text"):
            continue
        db.session.add(Review(project_id=sz.id,
                              author_name=r["author"],
                              rating=int(r["rating"] or 5),
                              text=r["text"],
                              created=(r.get("date") or "2026-01-01")[:10]))

    # -- activity feed ------------------------------------------------------------
    releases = ["7z2603-x64.msi", "7zr.exe", "7z2603-x64.exe", "7z2603-src.tar.xz",
                "7z2603-src.7z", "7z2603-mac.tar.xz", "7z2603-linux-x86.tar.xz",
                "7z2603-linux-x64.tar.xz", "7z2603-linux-arm64.tar.xz",
                "7z2603-linux-arm.tar.xz"]
    events = []
    events.append(("Igor Pavlov", False, "modified", "a comment",
                   f"/p/sevenzip/discussion/45797/thread/db6922e1d0/",
                   "discussion Open Discussion", "/p/sevenzip/discussion/45797/",
                   "7-Zip 26.03 was released. Download 7-Zip for 64-bit Windows x64.",
                   "2026-09-04 15:31:14"))
    events.append(("mgs", False, "posted", "a comment",
                    f"/p/sevenzip/discussion/45797/thread/096400c30b/",
                    "discussion Open Discussion", "/p/sevenzip/discussion/45797/",
                    "Microsoft Defender 4Sep26 deleted 7zr.exe on download as "
                    "\"Trojan:Win32/Wacatac.C!ml\"", "2026-09-04 12:05:09"))
    for i, fn in enumerate(releases):
        events.append((sz.name, True, "released", f"/7-Zip/26.03/{fn}",
                       f"/projects/sevenzip/files/7-Zip/26.03/{fn}/download",
                       None, None, None, "2026-09-04 08:07:%02d" % (7 + i)))
    events.append(("Harry Stein", False, "posted", "a comment",
                   "/p/sevenzip/bugs/2701/", "ticket #2701", "/p/sevenzip/bugs/2701/",
                   "Hi Igor, Thank you for getting back to me so quickly.", "2026-08-29 00:00:23"))
    events.append(("Harry Stein", False, "created", "ticket #2701",
                   "/p/sevenzip/bugs/2701/", None, None,
                   "user interface misleading", "2026-08-27 20:45:01"))
    events.append(("Nigbir", False, "created", "ticket #705",
                   "/p/sevenzip/feature-requests/705/", None, None,
                   "Please add PNX archive", "2026-08-26 15:44:30"))
    for i, (actor, is_proj, verb, obj, obj_url, target, target_url, summary, date) in enumerate(events):
        db.session.add(ActivityEvent(project_id=sz.id, actor=actor,
                                      actor_is_project=is_proj, verb=verb,
                                      obj=obj, obj_url=obj_url, target=target,
                                      target_url=target_url, summary=summary,
                                      date=date, ordinal=i))

    # -- download statistics (real daily series) ------------------------------------
    for row in data["stats_daily"].get("downloads", []):
        db.session.add(DownloadStat(project_id=sz.id,
                                    date=row[0][:10], count=int(row[1])))
    for label, count in [("Windows", 90456), ("Unknown", 71000),
                         ("Macintosh", 6494), ("Linux", 2575),
                         ("Android", 1969), ("BSD", 25)]:
        db.session.add(OsStat(project_id=sz.id, label=label, count=count))
    for rank, (label, count) in enumerate([
            ("United States", 40718), ("Czech Republic", 23121),
            ("China", 15048), ("India", 7960), ("Russia", 7894),
            ("Germany", 7828), ("Ukraine", 5058), ("France", 4513),
            ("Poland", 4410), ("Italy", 4200), ("Brazil", 3900),
            ("Japan", 3600)], start=1):
        db.session.add(CountryStat(project_id=sz.id, rank=rank,
                                   label=label, count=count))


def _reformat_forum_date(text):
    """Wayback forum rows carry 'Fri Sep 04, 2026 07:52 AM' style dates."""
    if not text:
        return None
    m = re.search(r"(\w{3}) (\w{3}) (\d{1,2}), (\d{4})", text)
    if not m:
        return text
    try:
        d = datetime.strptime(f"{m.group(2)} {m.group(3)} {m.group(4)}", "%b %d %Y")
        return d.strftime("%a %b %d, %Y")
    except ValueError:
        return text


def _seed_community_users(catalog):
    """Materialise the upstream community identities that appear on project
    pages (developers, review authors, forum/thread participants) so profile
    and user-mention links resolve like the live site."""
    seen = {}
    for p in catalog.values():
        for u, dn in zip(p.get("developers") or [], p.get("dev_names") or []):
            if u:
                seen[u] = dn or u
    for r in _load("sevenzip_reviews.json"):
        if r.get("author"):
            seen.setdefault(r["author"], r["author"])
    for extra in ["ipavlov", "hstein2000", "karlynhoz", "gau33", "pol098",
                  "tansy", "tanzmusikus", "farahinfauze", "shinchiro",
                  "kb0000001", "neustradamus"]:
        seen.setdefault(extra, extra.replace("_", " ").title())
    for username, display in sorted(seen.items()):
        db.session.add(User(username=username, display_name=display,
                            email=f"{username}@users.sourceforge.net",
                            password_hash="!",
                            joined="2000-08-17"))


# ---------------------------------------------------------------------------
# Site content + business directory
# ---------------------------------------------------------------------------
def _seed_site_content(proj_rows):
    content = {
        "home_stats": {
            "downloads_week": 20351888,
            "code_commits": 12299,
        },
        "oss_categories": [
            {"slug": "artificial-intelligence", "name": "Artificial Intelligence"},
            {"slug": "blockchain", "name": "Blockchain"},
            {"slug": "business", "name": "Business"},
            {"slug": "communications", "name": "Communications"},
            {"slug": "database", "name": "Database"},
            {"slug": "desktop-environment", "name": "Desktop Environment"},
            {"slug": "education", "name": "Education"},
            {"slug": "formats-and-protocols", "name": "Formats and Protocols"},
            {"slug": "games", "name": "Games"},
            {"slug": "internet", "name": "Internet"},
            {"slug": "mobile", "name": "Mobile"},
            {"slug": "multimedia", "name": "Multimedia"},
            {"slug": "printing", "name": "Printing"},
            {"slug": "productivity", "name": "Productivity"},
            {"slug": "religion-and-philosophy", "name": "Religion and Philosophy"},
            {"slug": "scientific-engineering", "name": "Scientific/Engineering"},
            {"slug": "security", "name": "Security"},
            {"slug": "social-sciences", "name": "Social sciences"},
            {"slug": "software-development", "name": "Software Development"},
            {"slug": "system", "name": "System"},
            {"slug": "terminals", "name": "Terminals"},
            {"slug": "text-editors", "name": "Text Editors"},
        ],
        "business_categories": [
            {"slug": "advertising", "name": "Advertising"},
            {"slug": "application-development", "name": "Application Development"},
            {"slug": "artificial-intelligence", "name": "Artificial Intelligence"},
            {"slug": "blockchain", "name": "Blockchain"},
            {"slug": "business-intelligence", "name": "Business Intelligence"},
            {"slug": "collaboration", "name": "Collaboration"},
            {"slug": "communications", "name": "Communications"},
            {"slug": "compliance", "name": "Compliance"},
            {"slug": "construction-management", "name": "Construction Management"},
            {"slug": "content-management", "name": "Content Management"},
            {"slug": "crm", "name": "CRM"},
            {"slug": "crypto", "name": "Crypto"},
            {"slug": "customer-service", "name": "Customer Service"},
            {"slug": "data-management", "name": "Data Management"},
            {"slug": "document-management", "name": "Document Management"},
            {"slug": "ecommerce", "name": "eCommerce"},
            {"slug": "education", "name": "Education"},
            {"slug": "engineering", "name": "Engineering"},
            {"slug": "erp", "name": "ERP"},
            {"slug": "event-management", "name": "Event Management"},
            {"slug": "field-service-management", "name": "Field Service Management"},
            {"slug": "finance", "name": "Finance"},
            {"slug": "government", "name": "Government"},
            {"slug": "hardware", "name": "Hardware"},
            {"slug": "healthcare", "name": "Healthcare"},
            {"slug": "human-resources", "name": "Human Resources"},
            {"slug": "insurance", "name": "Insurance"},
            {"slug": "it-management", "name": "IT Management"},
            {"slug": "it-security", "name": "IT Security"},
            {"slug": "legal", "name": "Legal"},
            {"slug": "logistics", "name": "Logistics"},
            {"slug": "manufacturing", "name": "Manufacturing"},
            {"slug": "marketing", "name": "Marketing"},
            {"slug": "multimedia", "name": "Multimedia"},
            {"slug": "network-management", "name": "Network Management"},
            {"slug": "nonprofit", "name": "Nonprofit"},
            {"slug": "operations-management", "name": "Operations Management"},
            {"slug": "productivity", "name": "Productivity"},
            {"slug": "project-management", "name": "Project Management"},
            {"slug": "real-estate", "name": "Real Estate"},
            {"slug": "retail-management", "name": "Retail Management"},
            {"slug": "sales", "name": "Sales"},
            {"slug": "system-utilities", "name": "System Utilities"},
            {"slug": "trading", "name": "Trading"},
            {"slug": "travel", "name": "Travel"},
            {"slug": "vertical-market", "name": "Vertical Market"},
            {"slug": "web-hosting", "name": "Web Hosting"},
        ],
        "leadership": [
            {"name": "Logan Abbott", "title": "President, SourceForge & COO, Slashdot Media",
             "image": "leadership_logan.png"},
            {"name": "Roger Sheppard", "title": "President of Slashdot Media",
             "image": "leadership_roger.png"},
            {"name": "Chance Abbott", "title": "Vice President Marketing & Sales",
             "image": "leadership_chance.png"},
            {"name": "Linda Condon", "title": "Human Resources Director",
             "image": "leadership_linda.png"},
        ],
        "support_best": {
            "sevenzip": "http://sourceforge.net/projects/sevenzip/forums/forum/45797",
        },
        "related_business": {
            "file-compression": ["File Compression", "Backup", "Archiving"],
            "security": ["IT Security", "Compliance", "Network Management"],
            "games": ["Multimedia", "Application Development"],
            "business": ["CRM", "Project Management", "Collaboration"],
            "multimedia": ["Multimedia", "Marketing", "Application Development"],
            "software-development": ["Application Development", "IT Management"],
            "database": ["Data Management", "Business Intelligence"],
            "system": ["IT Management", "System Utilities"],
        },
        "top_searches": {
            "sevenzip": ["7zip", "7-zip", "zip", "download installer", "7 zip", "7z"],
            "keepass": ["keepass", "password manager", "keepass2", "password safe"],
            "filezilla": ["filezilla", "ftp client", "filezilla download", "sftp"],
        },
    }
    for key, value in content.items():
        db.session.add(SiteContent(key=key, value_json=json.dumps(value)))


def _seed_business_products():
    """The /software/ business directory: real SourceForge-listed products
    captured from the live homepage cards and directory pages."""
    products = [
        ("Gemini-Enterprise-Agent-Platform", "Gemini Enterprise Agent Platform",
         "Gemini Enterprise Agent Platform is a comprehensive solution from Google Cloud "
         "designed to help organizations build, scale, govern, and optimize AI agents. The "
         "platform provides access to over 200 leading AI models and enables teams to create "
         "intelligent agents using both low-code and code-first development environments.",
         4.5, 999, "artificial-intelligence", True),
        ("Google-Cloud-Platform", "Google Cloud Platform",
         "Google Cloud Platform lets you build and scale applications on the same "
         "infrastructure Google uses. Compute Engine virtual machines with proven "
         "price/performance advantages, fully managed data warehousing, batch and stream "
         "processing, and state-of-the-art software-defined networking products.",
         4.5, 61049, "application-development", True),
        ("NinjaOne", "NinjaOne",
         "NinjaOne is the unified IT operations platform that gives IT teams complete "
         "visibility and control over all their endpoints. Remote monitoring and management, "
         "patching, backup, and endpoint protection in a single pane of glass.",
         4.5, 6035, "it-management", True),
        ("Google-AI-Studio", "Google AI Studio",
         "Google AI Studio is a unified development platform that helps teams explore, build, "
         "and deploy applications using Google's most advanced AI models. It brings text, "
         "image, audio, and video models together in one interface.",
         4.5, 420, "artificial-intelligence", False),
        ("Pipedrive", "Pipedrive",
         "Pipedrive is the easy-to-use CRM built for sales teams. Visual pipelines keep "
         "every deal on track, and activity reminders make sure nothing slips.",
         4.4, 3120, "crm", False),
        ("Freshservice", "Freshservice",
         "Freshservice is the modern IT service management solution with AI-powered "
         "ticketing, asset management, and change management in a clean, simple interface.",
         4.5, 1875, "it-management", False),
        ("Atera", "Atera",
         "Atera is an all-in-one remote monitoring and management platform for MSPs and IT "
         "departments, combining RMM, PSA, ticketing, and billing.",
         4.5, 1590, "it-management", False),
        ("Rippling", "Rippling",
         "Rippling is the employee management platform that unifies HR, IT, and finance "
         "operations: payroll, benefits, device management, and apps in one system.",
         4.5, 2240, "human-resources", False),
        ("MongoDB-Atlas", "MongoDB Atlas",
         "MongoDB Atlas is the fully managed cloud database with built-in vector search "
         "and global availability across 125+ regions. Start building AI apps faster.",
         4.5, 5400, "data-management", False),
        ("Zabbix", "Zabbix",
         "Zabbix is the ultimate enterprise-level open source monitoring solution for "
         "networks, servers, applications and services, designed for real-time monitoring "
         "of millions of metrics.",
         4.5, 890, "network-management", False),
        ("Odoo", "Odoo",
         "Odoo is a suite of open source business apps covering all company needs: CRM, "
         "eCommerce, accounting, inventory, point of sale and project management, all "
         "seamlessly integrated.",
         4.3, 4100, "erp", False),
        ("ownCloud", "ownCloud",
         "ownCloud is the market-leading open source file sync and share platform, giving "
         "teams self-hosted control over their data with collaboration on any device.",
         4.3, 780, "document-management", False),
        ("Jitsi", "Jitsi",
         "Jitsi is a set of open-source projects allowing you to easily build and deploy "
         "secure video conferencing solutions with world-class encryption.",
         4.4, 960, "communications", False),
        ("GLPI", "GLPI",
         "GLPI is a free IT asset management and helpdesk solution with inventory, "
         "ticketing and financial tracking for companies of any size.",
         4.3, 720, "it-management", False),
        ("SuiteCRM", "SuiteCRM",
         "SuiteCRM is the award-winning open source CRM that gives every business a free "
         "alternative to proprietary software with sales, marketing and support automation.",
         4.2, 1150, "crm", False),
        ("EspoCRM", "EspoCRM",
         "EspoCRM is an open source web application allowing you to see and enter your "
         "company's relationships with customers and partners in real time.",
         4.4, 480, "crm", False),
        ("Dolibarr", "Dolibarr ERP - CRM",
         "Dolibarr is a modern software package to manage your company or foundation "
         "activity (contacts, suppliers, invoices, orders, stocks, agenda and more).",
         4.2, 940, "erp", False),
        ("OrangeHRM", "OrangeHRM",
         "OrangeHRM is a comprehensive human capital management solution combining "
         "personnel records, leave, time, recruitment, and performance modules.",
         4.1, 610, "human-resources", False),
        ("Akaunting", "Akaunting",
         "Akaunting is a free, online accounting software for small businesses and "
         "freelancers with invoicing, expenses and banking built in.",
         4.2, 530, "finance", False),
        ("Firefly-III", "Firefly III",
         "Firefly III is a self-hosted financial manager for households and small "
         "businesses: budgets, recurring transactions, rules, and rich reports.",
         4.6, 410, "finance", False),
        ("Frappe", "Frappe Framework",
         "Frappe Framework is a full-stack web application framework with batteries "
         "included: ORM, forms, workflows, reports, role-based permissions and more.",
         4.4, 350, "application-development", False),
        ("Taiga", "Taiga",
         "Taiga is an open source project management platform for agile teams with "
         "scrum and kanban boards, epics, sprints and wiki.",
         4.3, 660, "project-management", False),
        ("Kimai", "Kimai",
         "Kimai is a free open source time-tracker with invoice generation, customer "
         "and project management, and extensive reporting.",
         4.4, 470, "productivity", False),
        ("Mautic", "Mautic",
         "Mautic is the world's largest open source marketing automation platform: "
         "campaigns, email marketing, contact management and lead nurturing.",
         4.1, 880, "marketing", False),
    ]
    for slug, name, desc, rating, count, category, featured in products:
        db.session.add(BusinessProduct(slug=slug, name=name, description=desc,
                                       rating_avg=rating, ratings_count=count,
                                       category=category, is_featured=featured))


# ---------------------------------------------------------------------------
# Benchmark users
# ---------------------------------------------------------------------------
def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    digest = stable_password_hash(BENCHMARK_PASSWORD)
    for u in BENCHMARK_USERS:
        db.session.add(User(username=u["username"], display_name=u["display"],
                            email=u["email"], password_hash=digest,
                            country=u["country"],
                            joined="2024-03-15", is_benchmark=True))
    db.session.flush()
    alice = User.query.filter_by(username="alice_j").first()
    bob = User.query.filter_by(username="bob_c").first()
    for p_short, user in [("sevenzip", alice), ("keepass", alice),
                          ("crystaldiskinfo", alice), ("winscp", bob),
                          ("crystaldiskinfo", bob)]:
        p = Project.query.filter_by(shortname=p_short).first()
        if p and user:
            db.session.add(Bookmark(user_id=user.id, project_id=p.id,
                                    created="2026-08-20"))
    db.session.commit()


# ---------------------------------------------------------------------------
# Entry point: build instance_seed/sourceforge.db
# ---------------------------------------------------------------------------
def build_seed_file() -> None:
    """Materialise instance_seed/sourceforge.db from a fresh runtime build."""
    import hashlib

    INSTANCE_DIR = BASE_DIR / "instance"
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    db_path = INSTANCE_DIR / "sourceforge.db"
    if db_path.exists():
        db_path.unlink()
    with app.app_context():
        app_module.create_schema()
        seed_database()
        seed_benchmark_users()
        INSTANCE_SEED.mkdir(parents=True, exist_ok=True)
        seed_path = INSTANCE_SEED / "sourceforge.db"
        for stale in INSTANCE_SEED.glob("*.db"):
            stale.unlink()
        shutil.copy2(db_path, seed_path)
        size = seed_path.stat().st_size
        digest = hashlib.sha256(seed_path.read_bytes()).hexdigest()
    print(f"[seed] instance_seed/sourceforge.db written ({size} bytes, sha256 {digest[:16]}…)")


if __name__ == "__main__":
    build_seed_file()

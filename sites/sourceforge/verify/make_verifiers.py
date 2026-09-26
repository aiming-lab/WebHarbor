#!/usr/bin/env python3
"""Generate the 21 per-task verifier modules (verify_0.py .. verify_20.py).

Ground truth is frozen from the seed database + upstream captures and is
HARDCODED here (never in tasks.jsonl). Run from sites/sourceforge/verify/:
    python3 make_verifiers.py
"""
from pathlib import Path

HEADER = '''#!/usr/bin/env python3
"""Verify SourceForge--{n}.

{question}
"""
from verify_lib import (check_answer_number, check_answer_phrase, check_read_only,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, final_answer, run_verifier,
                        table_diff, check_answer_any)

TASK_ID = "SourceForge--{n}"

'''

FOOTER = '''

def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
{checks}
{state}

if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))
'''

RO = '''    check_read_only(judge, initial_db, after_db)
'''

Q = {
0: "My Windows laptop needs a free file archiver. Compare 7-Zip and the top result for the directory search \"file compression\" sorted by Most Popular: report each project's weekly download count, its average star rating, and its registered date. Then tell me which of the two was updated more recently, and what license the 7-Zip project page lists.",
1: "I want the current 7-Zip release for a 64-bit Windows machine. Find the latest version folder in 7-Zip's file browser, list every build it ships for different platforms with file sizes, and identify which file the big Download button on the project page points to. Also report the weekly download count of the folder that contains them.",
2: "Before I recommend 7-Zip to my team I need its review record. Report its overall rating out of 5, the number of 5-star and 1-star reviews from the histogram, and the text of the featured Highest Rated review with its author. Then from the 4-star filter view, tell me how many 4-star reviews exist in total.",
3: "A coworker filed a 7-Zip bug about the progress bar reaching 100% while archiving was still running. Find that ticket in the Bugs tracker, report its number, summary, status, creator, and priority, and summarize what the project owner replied in the discussion. Also tell me the tracker's total open ticket count shown in the sidebar filter.",
4: "In 7-Zip's Open Discussion forum, find the thread asking for a dark mode. Report its subject, who created it and when, how many posts and views it has, and what the latest post in the thread suggests. Also identify which thread in that forum has the highest view count and its exact view number.",
5: "I'm researching download trends. From the Top Downloaded Projects page, report the #1 project all-time with its download figure, the #1 project for last week with its figure, and where 7-Zip ranks in the all-time table with its total downloads. Then say which of the two #1 projects was registered on SourceForge more recently, based on their project pages.",
6: "Our procurement team wants a CRM shortlist. Browse the Business Software directory's CRM category, list the products shown, and report which one has the most ratings and its rating value. Then open that product's page and give its full description, plus the category label the page displays.",
7: "Using the demo account (email: alice.j@test.com, password: TestPass123!), log in and research password managers: search the directory for \"password manager\", report the top result by relevance and its weekly downloads, bookmark it, then write it a 5-star review saying you use it daily. Confirm both the bookmark and the review appear on your account page.",
8: "Where in the world does 7-Zip get downloaded? From its download statistics pages, report the top country by downloads with its count, the top operating system with its count and the total across all OSes, and the exact day in the statistics table with the highest download count together with that count.",
9: "I only want open source games that run on Linux. Browse the Games category, report how many projects it lists and the first project's name, then open that project's page and report its license, its intended audience, and its last update date. Also tell me what the second project in the list is.",
10: "Compare this month's homepage picks. Report which project is the Staff Choice and which is the Community Choice in Open Source Projects of the Month, each with its review count and rating. Then from the Popular Projects list, find the one that is a portable software platform and report its weekly downloads and registered date from its own page.",
11: "Search the open source directory for \"video player\". Report the total number of results, which result is an Android native video player, and which is an open source HTML5 video player. Then narrow the search to Windows projects only and report the new result count plus the first result's name and weekly downloads. Finally open the HTML5 player's project page and report its summary line and last update date.",
12: "Who maintains 7-Zip? From the project page identify the developer, open their user profile, and report their username, join date, and every project the profile associates with them. Then pick the most recently updated of those other projects and report its summary line and last update date.",
13: "Register a new SourceForge account with username mirror-tester and email mirror-tester@example.com (password: LongPass123!). Then edit your profile to set your country to Germany, verify the change is saved, and report the exact wording of the two account pages you used plus what the account page shows for a brand-new user with no bookmarks.",
14: "The 7-Zip wiki documents supported archive formats. From the project's Wiki tab, report which formats the Home page lists, who the wiki page credits as author, and the wiki's last modification date. Then check the News tab and report the titles and dates of the two most recent news posts.",
15: "Search the 7-Zip Bugs tracker for tickets mentioning \"CVE\". Report how many tickets the search returns, the ticket numbers and summaries of the two newest, and the status of each. Then open the newest one and report who owns it and its priority.",
16: "I need an old 7-Zip build for compatibility testing. In the file browser, explore the folder that holds the LZMA SDK and report the exact filenames it ships, each file's size and modification date, and the weekly download count of the newest SDK file. Also report the all-time weekly downloads shown for the SDK folder itself.",
17: "Compare KeePass and 7-Zip head to head. Report each project's weekly downloads, average rating, review count, and registered date from their project pages, then check each project's Additional Project Details and report which operating systems each supports. Finally state which project has the larger total download count on the all-time Top list.",
18: "Using the demo account (email: bob.c@test.com, password: TestPass123!), log in and review your existing bookmarks. Report every project currently bookmarked with its name, then remove the disk-health tool from your bookmarks, add the bootable USB drive tool instead, write that new project a 4-star review mentioning USB sticks, and confirm the final bookmark list on the account page.",
19: "What does SourceForge itself say about itself? From the About page report the year it was founded and the number of software titles its business directory lists, then from the Leadership page report the names and titles of the first two team members listed. Finally report the headquarters street address shown in the footer of any page.",
20: "I'm evaluating ERP software and want an open source option. Browse the Business Software directory's ERP category and report every product listed with its rating and ratings count. Then identify which product also exists in the open source directory, open its project page, and report its summary, license, weekly downloads, and last update date.",
}

# per-task: list of (kind, args) emitted as checks
def num(name, value, label=None):
    return f'    check_answer_number(judge, answer, "{name}", {value!r}{", " + repr(label) if label else ""})'

def phrase(name, text):
    return f'    check_answer_phrase(judge, answer, "{name}", {text!r})'

def path(name, pattern):
    return f'    check_visited_path(judge, traj, "{name}", r"{pattern}")'

def anyof(name, variants, label=""):
    return f'    check_answer_any(judge, answer, "{name}", {variants!r}{", " + repr(label) if label else ""})'

TASKS = {}

TASKS[0] = [
    ("path", "search_results_page", r"/directory/\?q=file\+compression"),
    ("path", "visited_filezilla", r"/projects/filezilla/"),
    ("path", "visited_7zip", r"/projects/sevenzip/"),
    ("path", "visited_reviews_for_ratings", r"/projects/(sevenzip|filezilla)/reviews/"),
    ("n", "top_week", 2419, "FileZilla weekly downloads"),
    ("n", "top_rating", "4.1", "FileZilla rating"),
    ("p", "top_registered", "2001-02-27"),
    ("n", "sz_week", 23587, "7-Zip weekly downloads"),
    ("n", "sz_rating", "4.8", "7-Zip rating"),
    ("p", "sz_registered", "2000-11-10"),
    ("p", "sz_updated_more_recent", "2026-09-04"),
    ("p", "license_lgpl", "GNU Library or Lesser General Public License version 2.0"),
]

TASKS[1] = [
    ("path", "visited_files", r"/projects/sevenzip/files/"),
    ("path", "visited_latest_folder", r"/projects/sevenzip/files/7-Zip/26\.03/"),
    ("path", "visited_project_page", r"/projects/sevenzip/$"),
    ("p", "build_x64", "7z2603-x64.exe"),
    ("p", "build_msi", "7z2603-x64.msi"),
    ("p", "build_x86", "7z2603.exe"),
    ("p", "build_arm64", "7z2603-arm64.exe"),
    ("p", "build_extra", "7z2603-extra.7z"),
    ("p", "build_linux", "7z2603-linux-x64.tar.xz"),
    ("p", "build_src", "7z2603-src.7z"),
    ("p", "size_x64", "1.6 MB"),
    ("p", "size_msi", "1.7 MB"),
    ("p", "download_button_target", "latest/download"),
    ("any", "folder_week", ["23,345", "23345", "0"], "weekly count of the containing folder (26.03 row shows 0; 7-Zip root shows 23,345)"),
]

TASKS[2] = [
    ("path", "visited_reviews", r"/projects/sevenzip/reviews/"),
    ("path", "visited_4star_filter", r"filter-stars=4"),
    ("n", "avg_rating", "4.8", "overall rating"),
    ("n", "five_star", 765, "5-star count"),
    ("n", "one_star", 27, "1-star count"),
    ("p", "featured_author", "itreet-raking5"),
    ("p", "featured_text", "This is my tribute to your great 7-zip"),
    ("n", "four_star_total", 6, "4-star reviews in the filter view"),
]

TASKS[3] = [
    ("path", "visited_bugs", r"/p/sevenzip/bugs/"),
    ("path", "visited_ticket_2701", r"/p/sevenzip/bugs/2701/"),
    ("p", "ticket_summary", "user interface misleading"),
    ("p", "ticket_status_open", "open"),
    ("p", "ticket_creator", "Harry Stein"),
    ("n", "ticket_priority", 5, "ticket 2701 priority"),
    ("p", "owner_reply", "Maybe your usb was slow"),
    ("n", "open_tickets", 31, "open ticket count"),
    ("n", "all_tickets", 35, "total ticket count"),
]

TASKS[4] = [
    ("path", "visited_forum", r"/p/sevenzip/discussion/45797/"),
    ("path", "visited_darkmode_thread", r"/thread/0f17be73d3/"),
    ("p", "thread_subject", "Dark Mode"),
    ("p", "thread_creator", "Carlos Nunes"),
    ("p", "thread_created", "Tue Jul 08, 2025"),
    ("n", "thread_views", "3,206", "Dark Mode views"),
    ("p", "latest_post_suggestion", "plugin support for GUI"),
    ("n", "max_views", "297,148", "highest-view thread view count"),
    ("p", "max_views_thread", "7-Zip 26.02"),
]

TASKS[5] = [
    ("path", "visited_top", r"/top"),
    ("p", "alltime_no1", "TrueType core fonts"),
    ("p", "alltime_no1_downloads", "3.3B"),
    ("p", "weekly_no1", "MinGW"),
    ("p", "weekly_no1_downloads", "3,600,000"),
    ("p", "sz_alltime", "430.1M"),
    ("p", "sz_rank_or_total", "7-Zip"),
    ("p", "corefonts_more_recent", "2001-08-22"),
]

TASKS[6] = [
    ("path", "visited_crm", r"/software/crm/"),
    ("path", "visited_pipedrive", r"/software/product/Pipedrive/"),
    ("p", "product_pipedrive", "Pipedrive"),
    ("p", "product_suitecrm", "SuiteCRM"),
    ("p", "product_espocrm", "EspoCRM"),
    ("p", "most_ratings_count", "3,120"),
    ("p", "most_ratings_value", "4.4"),
    ("p", "pipedrive_description", "easy-to-use CRM built for sales teams"),
    ("p", "category_label", "CRM"),
]

TASKS[7] = [
    ("path", "login_page", r"/auth/"),
    ("path", "search_results", r"/directory/\?q=password\+manager"),
    ("path", "visited_passwordsafe", r"/projects/passwordsafe/"),
    ("path", "visited_review_form", r"/projects/passwordsafe/reviews/new"),
    ("path", "visited_account", r"/account/"),
    ("p", "top_result", "Password Safe"),
    ("n", "top_week", 1788, "Password Safe weekly downloads"),
    ("p", "review_text_daily", "daily"),
    ("state", None),
]

TASKS[8] = [
    ("path", "visited_stats", r"/stats/timeline"),
    ("path", "visited_os", r"/stats/os"),
    ("path", "visited_map", r"/stats/map"),
    ("p", "top_country", "United States"),
    ("n", "top_country_count", "40,718", "US downloads"),
    ("p", "top_os", "Windows"),
    ("n", "top_os_count", "90,456", "Windows downloads"),
    ("n", "os_total", "172,519", "total across OSes"),
    ("p", "max_day", "2026-09-19"),
    ("n", "max_day_count", "6,001", "highest-day downloads"),
]

TASKS[9] = [
    ("path", "visited_games", r"/directory/games/"),
    ("path", "visited_dosbox", r"/projects/dosbox/"),
    ("n", "games_count", 26, "games project count"),
    ("p", "first_project", "DOSBox"),
    ("p", "first_license", "GNU General Public License version 2.0"),
    ("p", "first_audience", "Advanced End Users"),
    ("p", "first_updated", "2025-08-25"),
    ("p", "second_project", "Neko Void"),
]

TASKS[10] = [
    ("path", "visited_homepage", r"47093/"),
    ("path", "visited_portableapps", r"/projects/portableapps/"),
    ("p", "staff_choice", "7-Zip"),
    ("p", "community_choice", "KeePass"),
    ("n", "staff_reviews", 831, "7-Zip review count"),
    ("n", "staff_rating", "4.8", "7-Zip rating"),
    ("n", "community_reviews", 606, "KeePass review count"),
    ("n", "community_rating", "4.9", "KeePass rating"),
    ("p", "portable_platform", "PortableApps.com"),
    ("n", "portable_week", "422,400", "PortableApps.com weekly downloads"),
    ("p", "portable_registered", "2005-10-21"),
]

TASKS[11] = [
    ("path", "search_results", r"/directory/\?q=video\+player"),
    ("path", "windows_facet", r"/directory/windows/"),
    ("path", "visited_videojs", r"/projects/video-js/"),
    ("n", "total_results", 53, "video player results"),
    ("p", "android_native", "Next Player"),
    ("p", "html5_player", "Video.js"),
    ("n", "windows_count", 13, "windows-only result count"),
    ("p", "windows_first", "mpv player (Windows)"),
    ("n", "windows_first_week", "9,572", "mpv player (Windows) weekly downloads"),
    ("p", "videojs_summary", "Open source HTML5 video player"),
    ("p", "videojs_updated", "2026-08-10"),
]

TASKS[12] = [
    ("path", "visited_7zip", r"/projects/sevenzip/"),
    ("path", "visited_profile", r"/u/ipavlov/profile/"),
    ("p", "username", "ipavlov"),
    ("p", "display_name", "Igor Pavlov"),
    ("p", "join_date", "2000-08-17"),
    ("p", "project_7zip", "7-Zip"),
    ("p", "project_p7zip", "p7zip"),
    ("p", "project_7far", "7-Far"),
    ("p", "project_7max", "7-max"),
    ("p", "recent_other_summary", "Command-line port of the 7-Zip file archiver"),
    ("p", "recent_other_updated", "2016-10-04"),
]

TASKS[13] = [
    ("path", "visited_registration", r"/user/registration/"),
    ("path", "visited_account_edit", r"/account/edit"),
    ("path", "visited_account", r"/account/"),
    ("p", "username_registered", "mirror-tester"),
    ("p", "country_germany", "Germany"),
    ("p", "bookmarks_wording", "bookmark"),
    ("state", None),
]

TASKS[14] = [
    ("path", "visited_wiki", r"/p/sevenzip/wiki/"),
    ("path", "visited_news", r"/p/sevenzip/news/"),
    ("p", "wiki_format_7z", "7z"),
    ("p", "wiki_format_zip", "ZIP"),
    ("p", "wiki_format_gzip", "GZIP"),
    ("p", "wiki_author", "Igor Pavlov"),
    ("p", "news_title_1", "7-Zip 9.21 beta"),
    ("p", "news_date_1", "2011-04-15"),
    ("p", "news_title_2", "7-Zip 9.20 was released"),
    ("p", "news_date_2", "2010-11-25"),
]

TASKS[15] = [
    ("path", "visited_bugs_search", r"/p/sevenzip/bugs/.*[?&]q=CVE"),
    ("path", "visited_ticket_2681", r"/p/sevenzip/bugs/2681/"),
    ("n", "cve_ticket_count", 3, "CVE search results"),
    ("p", "newest_summary", "CVE-2026-58052"),
    ("p", "second_summary", "CVE-2026-48102"),
    ("p", "ticket_status_open", "open"),
    ("p", "newest_owner_nobody", "nobody"),
    ("n", "newest_priority", 7, "ticket 2681 priority"),
]

TASKS[16] = [
    ("path", "visited_files", r"/projects/sevenzip/files/"),
    ("path", "visited_sdk_folder", r"/projects/sevenzip/files/LZMA(%20|\+)SDK/"),
    ("p", "file_2601", "lzma2601.7z"),
    ("p", "file_2600", "lzma2600.7z"),
    ("p", "file_2409", "lzma2409.7z"),
    ("p", "file_2408", "lzma2408.7z"),
    ("p", "size_2601", "1.8 MB"),
    ("p", "modified_2601", "2026-04-29"),
    ("n", "newest_week", 27, "lzma2601.7z weekly downloads"),
    ("n", "sdk_folder_week", 675, "LZMA SDK folder weekly downloads"),
]

TASKS[17] = [
    ("path", "visited_7zip", r"/projects/sevenzip/"),
    ("path", "visited_keepass", r"/projects/keepass/"),
    ("path", "visited_top", r"/top"),
    ("n", "kp_week", "205,800", "KeePass weekly downloads"),
    ("n", "kp_rating", "4.9", "KeePass rating"),
    ("n", "kp_reviews", 606, "KeePass review count"),
    ("p", "kp_registered", "2003-11-15"),
    ("n", "sz_week", 23587, "7-Zip weekly downloads"),
    ("n", "sz_rating", "4.8", "7-Zip rating"),
    ("n", "sz_reviews", 831, "7-Zip review count"),
    ("p", "sz_registered", "2000-11-10"),
    ("p", "kp_os_windows", "windows"),
    ("p", "kp_os_linux", "linux"),
    ("p", "sz_total", "430.1M"),
    ("p", "kp_total", "190.7M"),
]

TASKS[18] = [
    ("path", "login_page", r"/auth/"),
    ("path", "visited_account", r"/account/"),
    ("path", "visited_crystaldiskinfo", r"/projects/crystaldiskinfo/"),
    ("path", "visited_ventoy", r"/projects/ventoy/"),
    ("path", "visited_review_form", r"/projects/ventoy/reviews/new"),
    ("p", "bookmark_winscp", "WinSCP"),
    ("p", "bookmark_before_crystaldiskinfo", "CrystalDiskInfo"),
    ("p", "bookmark_after_ventoy", "Ventoy"),
    ("p", "review_mentions_usb", "USB"),
    ("state", None),
]

TASKS[19] = [
    ("path", "visited_about", r"/about"),
    ("path", "visited_leadership", r"/about/leadership"),
    ("p", "founded_1999", "1999"),
    ("p", "software_titles", "123,200"),
    ("p", "leader_1", "Logan Abbott"),
    ("p", "leader_1_title", "President, SourceForge"),
    ("p", "leader_2", "Roger Sheppard"),
    ("p", "leader_2_title", "President of Slashdot Media"),
    ("p", "hq_address", "1320 Columbia Street Suite 310"),
    ("p", "hq_city", "San Diego"),
]

TASKS[20] = [
    ("path", "visited_erp", r"/software/erp/"),
    ("path", "visited_dolibarr", r"/software/product/Dolibarr"),
    ("path", "visited_dolibarr_project", r"/projects/dolibarr/"),
    ("p", "product_odoo", "Odoo"),
    ("p", "product_dolibarr", "Dolibarr"),
    ("p", "odoo_rating", "4.3"),
    ("p", "odoo_ratings_count", "4,100"),
    ("p", "dolibarr_rating", "4.2"),
    ("p", "dolibarr_ratings_count", "940"),
    ("p", "dolibarr_summary", "Open source ERP and CRM web software for business"),
    ("n", "dolibarr_week", 2932, "Dolibarr weekly downloads"),
    ("p", "dolibarr_updated", "2026-05-26"),
]

# stateful DB-delta check bodies
STATE_7 = '''    # stateful: alice bookmarked Password Safe and posted it a 5-star review.
    check_only_tables_changed(judge, initial_db, after_db, {"bookmarks", "reviews", "projects"})
    added, removed, changed = table_diff(initial_db, after_db, "bookmarks")
    judge.check("bookmark_added_passwordsafe",
                len(added) == 1 and added and all(r["project_id"] == _pid(after_db, "passwordsafe") and r["user_id"] == 1991 for r in added.values()) and not removed and not changed,
                f"added={list(added.values())} removed={list(removed.values())} changed={list(changed.values())[:2]}")
    added, removed, changed = table_diff(initial_db, after_db, "reviews")
    ok_rev = (len(added) == 1 and not removed)
    if ok_rev:
        row = list(added.values())[0]
        ok_rev = (row["author_name"] == "alice_j" and row["rating"] == 5
                  and "daily" in (row["text"] or ""))
    judge.check("review_added_5star_daily", ok_rev,
                f"added={list(added.values())} removed={list(removed.values())}")
    added, removed, changed = table_diff(initial_db, after_db, "projects")
    ok_p = len(changed) == 1 and not added and not removed
    if ok_p:
        old, new = list(changed.values())[0]
        ok_p = (new["review_count"] == old["review_count"] + 1
                and new["stars_5"] == old["stars_5"] + 1
                and new["shortname"] == "passwordsafe")
    judge.check("passwordsafe_counters_bumped", ok_p,
                f"changed={[(c, v[1]['shortname']) for c, v in changed.items()]}")
'''

STATE_13 = '''    # stateful: a new user mirror-tester registered and set country to Germany.
    check_only_tables_changed(judge, initial_db, after_db, {"users"})
    added, removed, changed = table_diff(initial_db, after_db, "users")
    ok_u = len(added) == 1 and not removed and not changed
    if ok_u:
        row = list(added.values())[0]
        ok_u = (row["username"] == "mirror-tester"
                and row["email"] == "mirror-tester@example.com"
                and row["country"] == "DE")
    judge.check("user_registered_country_de", ok_u,
                f"added={list(added.values())} removed={list(removed.values())} changed={list(changed.values())[:2]}")
'''

STATE_18 = '''    # stateful: bob removed CrystalDiskInfo, added Ventoy, posted a 4-star review.
    check_only_tables_changed(judge, initial_db, after_db, {"bookmarks", "reviews", "projects"})
    added, removed, changed = table_diff(initial_db, after_db, "bookmarks")
    ok_b = False
    delta = {"added": list(added.values()), "removed": list(removed.values()),
             "changed": [(k, v[0]["project_id"], v[1]["project_id"]) for k, v in changed.items()]}
    if len(changed) == 1 and not added and not removed:
        (old_row, new_row) = list(changed.values())[0]
        ok_b = (new_row["user_id"] == 1992
                and new_row["project_id"] == _pid(after_db, "ventoy")
                and old_row["project_id"] == _pid(initial_db, "crystaldiskinfo"))
    elif len(added) == 1 and len(removed) == 1 and not changed:
        ok_b = (all(r["project_id"] == _pid(after_db, "ventoy") and r["user_id"] == 1992 for r in added.values())
                and all(r["project_id"] == _pid(initial_db, "crystaldiskinfo") and r["user_id"] == 1992 for r in removed.values()))
    judge.check("bookmark_swap_ventoy_for_crystaldiskinfo", ok_b,
                f"delta={delta}")
    added, removed, changed = table_diff(initial_db, after_db, "reviews")
    ok_rev = (len(added) == 1 and not removed)
    if ok_rev:
        row = list(added.values())[0]
        ok_rev = (row["author_name"] == "bob_c" and row["rating"] == 4
                  and "usb" in (row["text"] or "").lower())
    judge.check("review_added_4star_usb", ok_rev,
                f"added={list(added.values())} removed={list(removed.values())}")
    added, removed, changed = table_diff(initial_db, after_db, "projects")
    ok_p = len(changed) == 1 and not added and not removed
    if ok_p:
        old, new = list(changed.values())[0]
        ok_p = (new["review_count"] == old["review_count"] + 1
                and new["stars_4"] == old["stars_4"] + 1
                and new["shortname"] == "ventoy")
    judge.check("ventoy_counters_bumped", ok_p,
                f"changed={[(c, v[1]['shortname']) for c, v in changed.items()]}")
'''

HELPER = '''

def _pid(db, shortname):
    return db.execute("SELECT id FROM projects WHERE shortname = ?", (shortname,)).fetchone()[0]
'''

def build(n):
    checks = []
    for item in TASKS[n]:
        kind = item[0]
        if kind == "p":
            name, text = item[1], item[2]
            checks.append(phrase(name, text))
        elif kind == "n":
            name, value = item[1], item[2]
            label = item[3] if len(item) > 3 else None
            checks.append(num(name, value, label))
        elif kind == "any":
            name, variants = item[1], item[2]
            label = item[3] if len(item) > 3 else ""
            checks.append(anyof(name, variants, label))
        elif kind == "path":
            name, pattern = item[1], item[2]
            checks.append(path(name, pattern))
    state = ""
    if n == 7:
        state = STATE_7
    elif n == 13:
        state = STATE_13
    elif n == 18:
        state = STATE_18
    else:
        state = RO
    body = HEADER.format(n=n, question=Q[n]) + HELPER + FOOTER.format(checks="\n".join(checks), state=state)
    return body

out = Path(__file__).parent
for n in range(21):
    p = out / f"verify_{n}.py"
    p.write_text(build(n))
    print("wrote", p)

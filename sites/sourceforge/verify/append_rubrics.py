#!/usr/bin/env python3
"""Append verifier_path + judge_rubric to sites/sourceforge/tasks.jsonl.

Contract:
  - the ORIGINAL five keys (id, ques, upstream_url, web, web_name) stay
    BYTE-IDENTICAL on every line: the two new keys are appended textually
    before the closing brace, so the original bytes are untouched;
  - no `answer` key is ever written;
  - judge_rubric is pure-rule English (no ground truth leaked);
  - verifier_path points at this directory's per-task deterministic verifier.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE.parent / "tasks.jsonl"

RUBRICS = {
    0: "Verify the agent actually ran the directory search for 'file compression' and opened both project pages (the top result and 7-Zip) plus at least one reviews page for the numeric ratings. The answer must state the top result (FileZilla) and 7-Zip with each project's weekly download count, average star rating and registered date, name the more recently updated project (7-Zip), and quote 7-Zip's license from its project page. Fail any answer that invents numbers or names a different top result.",
    1: "Verify the agent opened 7-Zip's file browser and the latest version folder (7-Zip/26.03) and read the Download button target on the project page. The answer must list every build shipped in 26.03 with file sizes (7z2603-x64.exe, -x64.msi, -x64.exe, -arm64.exe, -extra.7z, -linux-x64.tar.xz, -src.7z) and report the weekly download count shown for the containing folder (the 26.03 row displays 0; the 7-Zip root folder displays 23,345 - accept either as displayed). The Download button must resolve to the latest-version download (7z2603-x64.exe).",
    2: "Verify the agent opened 7-Zip's reviews page and applied the 4-star filter view. The answer must report the overall rating (4.8 out of 5), the 5-star (765) and 1-star (27) histogram counts, quote the featured Highest Rated review text with its author (itreet-raking5), and state how many 4-star reviews the filter view lists (6). Fail answers that confuse the histogram count (25) with the filter view count.",
    3: "Verify the agent searched the 7-Zip Bugs tracker and opened ticket #2701. The answer must report the ticket number (2701), summary ('user interface misleading'), status (open), creator (Harry Stein), priority (5), summarize Igor Pavlov's reply (the USB drive may have been slow for data writing), and report the tracker's open ticket count (31 of 35). A near-miss ticket (#2680, text overlapping the progress bar) exists; answers must distinguish them.",
    4: "Verify the agent opened the Open Discussion forum and the Dark Mode thread. The answer must report the subject (Dark Mode), creator (Carlos Nunes), creation date (Tue Jul 08, 2025), post and view counts (4 posts, 3,206 views), what the latest post suggests (at least a plugin for the GUI), and the forum's highest-view thread with its exact count (7-Zip 26.02 with 297,148 views).",
    5: "Verify the agent opened the Top Downloaded Projects page and both #1 project pages. The answer must report the all-time #1 (Microsoft's TrueType core fonts, 3.3B), the last-week #1 (MinGW, 3,600,000), 7-Zip's all-time entry (430.1M), and correctly state which #1 was registered more recently (corefonts, 2001-08-22 vs mingw 2000-02-09).",
    6: "Verify the agent browsed the Business Software CRM category and opened the top product's page. The answer must list the CRM products shown (Pipedrive, SuiteCRM, EspoCRM), name the most-rated one (Pipedrive with 3,120 ratings, 4.4), give Pipedrive's full description, and the category label the product page displays (CRM).",
    7: "Verify the agent logged in as the demo user, searched 'password manager', bookmarked the top result and posted it a 5-star review. The answer must name the top result (Password Safe) with its weekly downloads (1,788), and the DB must show exactly one new alice_j bookmark for Password Safe and one new 5-star alice_j review mentioning daily use, with the Password Safe counters bumped and every other table untouched.",
    8: "Verify the agent opened all three download-statistics pages (timeline, OS breakdown, country map). The answer must report the top country (United States, 40,718), the top OS (Windows, 90,456), the total across all OSes (172,519), and the highest-download day with its count (2026-09-19 with 6,001).",
    9: "Verify the agent browsed the Games category and opened the first project. The answer must report the project count (26), the first project (DOSBox) with its license (GPLv2), intended audience (Advanced End Users) and last update (2025-08-25), and the second project (Neko Void).",
    10: "Verify the agent read the homepage picks and opened the portable platform's own page. The answer must name the Staff Choice (7-Zip, 831 reviews, 4.8) and Community Choice (KeePass, 606 reviews, 4.9), identify PortableApps.com as the portable software platform, and report its weekly downloads (422,400) and registered date (2005-10-21) from its project page.",
    11: "Verify the agent ran the 'video player' search, applied the Windows facet, and opened the HTML5 player's project page. The answer must report the total result count (53), the Android native video player (Next Player), the open source HTML5 video player (Video.js), the Windows-only count (13), the first Windows result with weekly downloads (mpv player (Windows), 9,572), and Video.js's summary and last update (2026-08-10).",
    12: "Verify the agent opened 7-Zip's project page and the developer's profile. The answer must report the username (ipavlov), display name (Igor Pavlov), join date (2000-08-17), every project the profile associates with him (7-Zip, p7zip, 7-Far, 7-max), and the most recently updated of the other projects (p7zip, 2016-10-04) with its summary line.",
    13: "Verify the agent registered a new account and edited its profile. The answer must mention the mirror-tester registration, the Germany country setting, and the account page wording; the DB must show exactly one new user row (mirror-tester, mirror-tester@example.com, country DE) and no other table touched.",
    14: "Verify the agent opened 7-Zip's Wiki and News tabs. The answer must report the archive formats the wiki Home page lists (7z, XZ, BZIP2, GZIP, TAR, ZIP, WIM, ARJ, CAB, ...), the credited author (Igor Pavlov), and the two most recent news posts with dates (7-Zip 9.21 beta, 2011-04-15; 7-Zip 9.20 was released, 2010-11-25). The wiki page displays no modification date; answers must not invent one.",
    15: "Verify the agent searched the Bugs tracker for CVE. The answer must report how many tickets the search returns (3), the two newest ticket numbers and summaries (#2681 CVE-2026-58052, #2670 CVE-2026-48102), their status (open), and the newest ticket's owner (nobody) and priority (7).",
    16: "Verify the agent explored the LZMA SDK folder in the file browser. The answer must report the exact filenames shipped (lzma2601.7z, lzma2600.7z, lzma2409.7z, lzma2408.7z) with sizes and modification dates, the newest SDK file's weekly download count (27), and the SDK folder's own weekly count (675).",
    17: "Verify the agent opened both project pages, both reviews pages for the numeric ratings, and the all-time Top list. The answer must report KeePass (205,800 weekly, 4.9, 606 reviews, registered 2003-11-15) and 7-Zip (23,587 weekly, 4.8, 831 reviews, registered 2000-11-10), the operating systems each supports (KeePass: wine/linux/windows-server/mac/windows; 7-Zip: windows), and state that 7-Zip has the larger all-time total (430.1M vs 190.7M).",
    18: "Verify the agent logged in as bob, reviewed the existing bookmarks (WinSCP, CrystalDiskInfo), removed the disk-health tool, added the bootable USB tool, posted the 4-star review, and confirmed the final list. The answer must name all of these; the DB must show bob's bookmark swapped from CrystalDiskInfo to Ventoy, one new 4-star bob_c review mentioning USB, the Ventoy counters bumped, and every other table untouched.",
    19: "Verify the agent opened the About and Leadership pages and read the footer. The answer must report the founding year (1999), the software-titles figure (123,200), the first two leadership members with titles (Logan Abbott, President, SourceForge & COO, Slashdot Media; Roger Sheppard, President of Slashdot Media), and the headquarters street address (1320 Columbia Street Suite 310, San Diego).",
    20: "Verify the agent browsed the ERP category and opened the cross-listed product's project page. The answer must list every ERP product with rating and ratings count (Odoo 4.3 / 4,100; Dolibarr 4.2 / 940), identify Dolibarr as the one also in the open source directory, and report its summary ('Open source ERP and CRM web software for business'), weekly downloads (2,932) and last update (2026-05-26).",
}


def main() -> None:
    lines = TASKS.read_text(encoding="utf-8").splitlines()
    out_lines = []
    for line in lines:
        row = json.loads(line)
        n = int(row["id"].split("--")[1])
        assert set(row) == {"id", "ques", "upstream_url", "web", "web_name"}, \
            f"unexpected pre-existing keys in {row['id']}"
        assert line.endswith("}"), line[-40:]
        addition = (f', "verifier_path": "sites/sourceforge/verify/verify_{n}.py", '
                    f'"judge_rubric": {json.dumps(RUBRICS[n], ensure_ascii=False)}')
        out_lines.append(line[:-1] + addition + "}")
    TASKS.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"appended verifier_path + judge_rubric to {len(out_lines)} tasks "
          "(original 5 keys byte-untouched)")


if __name__ == "__main__":
    main()

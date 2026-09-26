"""Frozen per-task fixture specs for the sourceforge verifier tests.

URLs and honest answers come from the reviewer's live honest runs
(agent at http://localhost:47093, container wh-sf-review); the SQL reproduces the
exact stateful writes the application performs. No LLM.
"""

BASE = 'http://localhost:47093'

SPECS = {
    0: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=7-Zip", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/directory/?q=download%20installer", "http://localhost:47093/projects/sevenzip/reviews/", "http://localhost:47093/directory/?q=file+compression&sort=popular", "http://localhost:47093/directory/?q=file+compression&sort=popular", "http://localhost:47093/projects/filezilla/", "http://localhost:47093/projects/filezilla/", "http://localhost:47093/projects/filezilla/reviews/", "http://localhost:47093/projects/filezilla/reviews/"],
        "answer": "Top result for 'file compression' (Most Popular sort selected): FileZilla\u00ae \u2014 weekly downloads 2,419, rating 4.1/5, registered 2001-02-27. 7-Zip \u2014 weekly downloads 23,587, rating 4.8/5, registered 2000-11-10. 7-Zip was updated more recently (2026-09-04 vs 2025-10-11). 7-Zip's license: GNU Library or Lesser General Public License version 2.0 (LGPLv2).",
    },
    1: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=7-Zip", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/projects/sevenzip/files/", "http://localhost:47093/projects/sevenzip/files/7-Zip/", "http://localhost:47093/projects/sevenzip/files/7-Zip/", "http://localhost:47093/projects/sevenzip/files/7-Zip/26.03/", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/projects/sevenzip/"],
        "answer": "Latest version folder: 7-Zip/26.03. Builds: 7z2603-arm64.exe 2026-09-04 1.2 MB 980; 7z2603-extra.7z 2026-09-04 0.97 MB 1,130; 7z2603-linux-x64.tar.xz 2026-09-04 1.4 MB 842; 7z2603-src.7z 2026-09-04 1.2 MB 214; 7z2603-x64.exe 2026-09-04 1.6 MB 18,342; 7z2603-x64.msi 2026-09-04 1.7 MB 4,210; 7z2603.exe 2026-09-04 1.0 MB 3,871. The big Download button on the project page points to /projects/sevenzip/files/latest/download (the 26.03 folder row shows 0 downloads this week; the 7-Zip root folder shows 23,345).",
    },
    2: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=7-Zip", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/directory/?q=download%20installer", "http://localhost:47093/projects/sevenzip/reviews/", "http://localhost:47093/projects/sevenzip/reviews/", "http://localhost:47093/projects/sevenzip/reviews/?filter-stars=4", "http://localhost:47093/projects/sevenzip/reviews/?filter-stars=4"],
        "answer": "7-Zip overall rating: 4.8 out of 5. Histogram (5..1 stars): ['765', '25', '12', '2', '27']. Featured Highest Rated review: This is my tribute to your great 7-zip, Igor Pavlov. itreet-raking5 vs Lowest Rated &#34;This is an outstanding application that fully satisfies all my requirements for working with archived files. Its performance is far. The 4-star filter view shows 6 four-star reviews.",
    },
    3: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=7-Zip", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/p/sevenzip/bugs/", "http://localhost:47093/p/sevenzip/bugs/", "http://localhost:47093/p/sevenzip/bugs/", "http://localhost:47093/p/sevenzip/bugs/search/?q=progress+bar+100%25", "http://localhost:47093/p/sevenzip/bugs/2680/", "http://localhost:47093/p/sevenzip/bugs/", "http://localhost:47093/p/sevenzip/bugs/", "http://localhost:47093/p/sevenzip/bugs/2701/", "http://localhost:47093/p/sevenzip/bugs/2701/"],
        "answer": "Ticket #2701 'user interface misleading', status open, created by Harry Stein, priority 5. Igor Pavlov replied: 'Maybe your usb was slow for data writing by some reason. What is your usb drive speed?' The tracker sidebar shows 31 open tickets (35 total). (A near-miss ticket 2680 about text overlapping the progress bar also exists.)",
    },
    4: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=7-Zip", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/p/sevenzip/discussion/", "http://localhost:47093/p/sevenzip/discussion/45797/", "http://localhost:47093/p/sevenzip/discussion/45797/", "http://localhost:47093/p/sevenzip/discussion/45797/thread/0f17be73d3/", "http://localhost:47093/p/sevenzip/discussion/45797/thread/0f17be73d3/"],
        "answer": "The Open Discussion thread 'Dark Mode' was created by Carlos Nunes on Tue Jul 08, 2025, has 4 posts and 3,206 views. The latest post (by john, 2025-11-04) suggests 'or a least make a plugin support for GUI'. The thread with the highest view count is '7-Zip 26.02' with 297,148 views.",
    },
    5: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/top", "http://localhost:47093/top", "http://localhost:47093/projects/corefonts/", "http://localhost:47093/directory/?q=MinGW", "http://localhost:47093/projects/mingw/", "http://localhost:47093/projects/mingw/"],
        "answer": "All-time #1: Microsoft's TrueType core fonts with 3.3B downloads; last-week #1: MinGW - Minimalist GNU for Windows with 3,600,000 downloads; 7-Zip ranks in the all-time table with 430.1M. Registered dates: corefonts 2001-08-22, mingw 2000-02-09 \u2014 corefonts was registered more recently.",
    },
    6: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/software/", "http://localhost:47093/software/", "http://localhost:47093/software/crm/", "http://localhost:47093/software/crm/", "http://localhost:47093/software/product/Pipedrive/", "http://localhost:47093/software/product/Pipedrive/"],
        "answer": "CRM category lists Pipedrive (4.4, 3,120 ratings), SuiteCRM (4.2, 1,150 ratings) and EspoCRM (4.4, 480 ratings). Pipedrive has the most ratings. Its description: 'Pipedrive is the easy-to-use CRM built for sales teams. Visual pipelines keep every deal on track, and activity reminders make sure nothing slips.' The page's category label is CRM.",
    },
    7: {
        "urls": ["http://localhost:47093/auth/", "http://localhost:47093/auth/", "http://localhost:47093/auth/", "http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=password+manager", "http://localhost:47093/directory/?q=password+manager", "http://localhost:47093/projects/passwordsafe/", "http://localhost:47093/projects/passwordsafe/", "http://localhost:47093/projects/passwordsafe/", "http://localhost:47093/projects/passwordsafe/reviews/", "http://localhost:47093/projects/passwordsafe/reviews/new", "http://localhost:47093/projects/passwordsafe/reviews/new", "http://localhost:47093/projects/passwordsafe/reviews/new", "http://localhost:47093/projects/passwordsafe/reviews/", "http://localhost:47093/account/", "http://localhost:47093/account/"],
        "answer": "Top result for 'password manager': Password Safe download | SourceForge.net with 1,788 weekly downloads. Bookmarked it and posted a 5-star review reading 'I use this password manager daily - it is reliable and secure.' Account page shows: For Vendors Help Create My Account Log Out Business Software Open Source Software Top Downloaded Projects Resources My Account Profile Username: alice_j Country: United States Bookmarked Projects Password Safe Remove bookmark 7-Zip Remove bookmark Ke",
        "sql": ["INSERT INTO bookmarks (user_id, project_id, created) VALUES (1991, (SELECT id FROM projects WHERE shortname='passwordsafe'), '2026-09-26')", "INSERT INTO reviews (project_id, author_name, rating, text, created, helpful_count) VALUES ((SELECT id FROM projects WHERE shortname='passwordsafe'), 'alice_j', 5, 'I use this password manager daily - it is reliable and secure.', '2026-09-26', 0)", "UPDATE projects SET review_count = review_count + 1, stars_5 = stars_5 + 1, rating_avg = 4.8 WHERE shortname = 'passwordsafe'"],
    },
    8: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=7-Zip", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/projects/sevenzip/files/", "http://localhost:47093/projects/sevenzip/files/7-Zip/", "http://localhost:47093/projects/sevenzip/files/7-Zip/", "http://localhost:47093/projects/sevenzip/files/7-Zip/22.00/stats/timeline", "http://localhost:47093/projects/sevenzip/files/stats/os", "http://localhost:47093/projects/sevenzip/files/stats/map", "http://localhost:47093/projects/sevenzip/files/stats/map"],
        "answer": "Top country by downloads: United States with 40,718. Top OS: Windows with 90,456; total across all OSes 172,519. Highest download day in the statistics table: 2026-09-19 with 6,001 downloads.",
    },
    9: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/games/", "http://localhost:47093/directory/games/", "http://localhost:47093/projects/dosbox/", "http://localhost:47093/directory/games/", "http://localhost:47093/directory/games/"],
        "answer": "Games category lists 26 projects. First: DOSBox (license GNU General Public License version 2.0 (GPLv2), audience Advanced End Users User Interface X Window System (X11), Win32 (MS Windows), Cocoa (MacOS X), Carbon (Mac OS X) Programming Language C, last update 2025-08-25). Second project: Neko Void.",
    },
    10: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/projects/portableapps/", "http://localhost:47093/projects/portableapps/"],
        "answer": "Staff Choice: 7-Zip (831 Reviews, 4.8 rating). Community Choice: KeePass (606 Reviews, 4.9 rating). The portable software platform in Popular Projects is PortableApps.com with 422,400 weekly downloads, registered 2005-10-21.",
    },
    11: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=video+player", "http://localhost:47093/directory/?q=video+player", "http://localhost:47093/directory/windows/?q=video%20player", "http://localhost:47093/directory/?q=video+player", "http://localhost:47093/projects/video-js/", "http://localhost:47093/projects/video-js/"],
        "answer": "'video player' search: 53 results. Android native video player: Next Player; open source HTML5 video player: Video.js. Windows-only: 13 results, first mpv player (Windows) with 9,572 weekly downloads. Video.js summary: Video.js Open source HTML5 video player Downloads: 16 This Week Last Update: 2026-08-10 Share This \u2606 Bookmark This Proje; last update 2026-08-10.",
    },
    12: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=7-Zip", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/u/ipavlov/profile/", "http://localhost:47093/u/ipavlov/profile/"],
        "answer": "7-Zip is maintained by ipavlov (Igor Pavlov), joined 2000-08-17. Projects the profile associates with him: 7-Zip, p7zip, 7-Far, 7-max. The most recently updated of the other projects is p7zip (Command-line port of the 7-Zip file archiver for Linux and other POSIX systems, last update 2016-10-04).",
    },
    13: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/user/registration/", "http://localhost:47093/user/registration/", "http://localhost:47093/user/registration/", "http://localhost:47093/user/registration/", "http://localhost:47093/user/registration/", "http://localhost:47093/user/registration/", "http://localhost:47093/account/", "http://localhost:47093/account/edit", "http://localhost:47093/account/edit", "http://localhost:47093/account/", "http://localhost:47093/account/"],
        "answer": "Registered mirror-tester. Account page for a brand-new user: For Vendors Help Create My Account Log Out Business Software Open Source Software Top Downloaded Projects Resources My Account Profile Username: mirror-tester Country: Not set Bookmarked Projects No bookmarks yet. Browse the directory and bookmark pr After setting country to Germany: For Vendors Help Create My Account Log Out Business Software Open Source Software Top Downloaded Projects Resources My Account Profile Username: mirror-tester Country: Germany Bookmarked Projects No bookmarks yet. Browse the directory and bookmark pr",
        "sql": ["INSERT INTO users (username, display_name, email, password_hash, country, joined, is_benchmark) VALUES ('mirror-tester', 'Mirror Tester', 'mirror-tester@example.com', 'x', 'DE', '2026-09-26', 0)"],
    },
    14: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=7-Zip", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/p/sevenzip/wiki/", "http://localhost:47093/p/sevenzip/news/", "http://localhost:47093/p/sevenzip/news/"],
        "answer": "Wiki Home lists the formats 7z, XZ, BZIP2, GZIP, TAR, ZIP, WIM, ARJ, CAB, CHM, CPIO, CramFS, DEB, DMG, FAT, HFS, ISO, LZH, LZMA, MBR, MSI, NSIS, NTFS, RAR, RPM, SquashFS, UDF, VHD, WIM, XAR, Z. The wiki credits Igor Pavlov as author. (No last-modification date is displayed on the wiki page.) The two most recent news posts are '7-Zip 9.21 beta' (2011-04-15) and '7-Zip 9.20 was released' (2010-11-25).",
    },
    15: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=7-Zip", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/p/sevenzip/bugs/", "http://localhost:47093/p/sevenzip/bugs/", "http://localhost:47093/p/sevenzip/bugs/search/?q=CVE", "http://localhost:47093/p/sevenzip/bugs/search/?q=CVE", "http://localhost:47093/p/sevenzip/bugs/2681/", "http://localhost:47093/p/sevenzip/bugs/2681/"],
        "answer": "CVE search returns 3 tickets: #2681 CVE-2026-58052 (open) and #2670 CVE-2026-48102 (open) are the two newest. The newest ticket #2681 is owned by nobody and has priority 7.",
    },
    16: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=7-Zip", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/projects/sevenzip/files/", "http://localhost:47093/projects/sevenzip/files/LZMA%20SDK/", "http://localhost:47093/projects/sevenzip/files/LZMA%20SDK/", "http://localhost:47093/projects/sevenzip/files/LZMA%20SDK/"],
        "answer": "LZMA SDK folder ships lzma2601.7z (1.8 MB, modified 2026-04-29, 27 weekly downloads), lzma2600.7z (1.8 MB, 2026-02-19, 15), lzma2409.7z (1.7 MB, 2024-11-30, 35), lzma2408.7z (1.7 MB, 2024-08-13, 16). The SDK folder itself shows 675 weekly downloads.",
    },
    17: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=7-Zip", "http://localhost:47093/projects/sevenzip/", "http://localhost:47093/directory/?q=download%20installer", "http://localhost:47093/projects/sevenzip/reviews/", "http://localhost:47093/directory/?q=KeePass", "http://localhost:47093/projects/keepass/", "http://localhost:47093/directory/?q=keepass2", "http://localhost:47093/projects/keepass/reviews/", "http://localhost:47093/", "http://localhost:47093/top", "http://localhost:47093/top"],
        "answer": "7-Zip: 23,587 weekly downloads, 4.8 rating, 831 reviews, registered 2000-11-10, supports Windows. KeePass: 205,800 weekly downloads, 4.9 rating, 606 reviews, registered 2003-11-15, OS: wine, linux, windows-server, mac, windows. On the all-time Top list 7-Zip shows 430.1M total downloads and KeePass 190.7M, so 7-Zip has the larger total.",
    },
    18: {
        "urls": ["http://localhost:47093/auth/", "http://localhost:47093/auth/", "http://localhost:47093/auth/", "http://localhost:47093/", "http://localhost:47093/account/", "http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=CrystalDiskInfo", "http://localhost:47093/projects/crystaldiskinfo/", "http://localhost:47093/projects/crystaldiskinfo/", "http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/directory/?q=Ventoy", "http://localhost:47093/projects/ventoy/", "http://localhost:47093/projects/ventoy/", "http://localhost:47093/projects/ventoy/", "http://localhost:47093/projects/ventoy/reviews/", "http://localhost:47093/projects/ventoy/reviews/new", "http://localhost:47093/projects/ventoy/reviews/new", "http://localhost:47093/projects/ventoy/reviews/new", "http://localhost:47093/projects/ventoy/reviews/", "http://localhost:47093/account/", "http://localhost:47093/account/"],
        "answer": "Bob's bookmarks before: For Vendors Help Create My Account Log Out Business Software Open Source Software Top Downloaded Projects Resources My Account Profile Username: bob_c Country: China Bookmarked Projects WinSCP Remove  After: For Vendors Help Create My Account Log Out Business Software Open Source Software Top Downloaded Projects Resources My Account Profile Username: bob_c Country: China Bookmarked Projects Ventoy Remove bookmark WinSCP Remove bookmark My Reviews Ventoy \u2014 4 stars (2026-09-26) Great for making USB sticks (removed CrystalDiskInfo, added Ventoy, posted a 4-star review mentioning USB sticks).",
        "sql": ["UPDATE bookmarks SET project_id = (SELECT id FROM projects WHERE shortname='ventoy'), created = '2026-09-26' WHERE user_id = 1992 AND project_id = (SELECT id FROM projects WHERE shortname='crystaldiskinfo')", "INSERT INTO reviews (project_id, author_name, rating, text, created, helpful_count) VALUES ((SELECT id FROM projects WHERE shortname='ventoy'), 'bob_c', 4, 'Great for making USB sticks bootable - works every time.', '2026-09-26', 0)", "UPDATE projects SET review_count = review_count + 1, stars_4 = stars_4 + 1, rating_avg = 4.6 WHERE shortname = 'ventoy'"],
    },
    19: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/", "http://localhost:47093/about", "http://localhost:47093/about/leadership", "http://localhost:47093/about/leadership", "http://localhost:47093/about/leadership"],
        "answer": "SourceForge was founded in 1999; its business directory lists 123,200 software titles. The first two leadership team members are Logan Abbott (President, SourceForge & COO, Slashdot Media) and Roger Sheppard (President of Slashdot Media). Footer HQ: 1320 Columbia Street Suite 310 San Diego, CA 92101 +1 (858) 422-6466 Resources S",
    },
    20: {
        "urls": ["http://localhost:47093/", "http://localhost:47093/software/", "http://localhost:47093/software/", "http://localhost:47093/software/erp/", "http://localhost:47093/software/erp/", "http://localhost:47093/software/product/Dolibarr/", "http://localhost:47093/directory/?q=Dolibarr", "http://localhost:47093/projects/dolibarr/", "http://localhost:47093/projects/dolibarr/"],
        "answer": "ERP category lists Odoo (4.3, 4,100 ratings) and Dolibarr ERP - CRM (4.2, 940 ratings). Dolibarr also exists in the open source directory: summary 'Open source ERP and CRM web software for business', license GPL, 2,932 weekly downloads, last update 2026-05-26.",
    },
}

WRONG_ANSWERS = {
    0: "Top result is WinSCP with 5,000 weekly downloads and a 3.9 rating, registered 2010-01-01; WinSCP was updated more recently. 7-Zip's license is MIT.",
    1: "The latest version folder is 25.01 shipping 7z2501-x64.exe (2.5 MB); the Download button points to 7z2602-x64.msi and the folder shows 999 weekly downloads.",
    2: "7-Zip's overall rating is 3.2 out of 5 with 100 five-star and 400 one-star reviews; the featured review is by Igor Pavlov; the 4-star filter shows 55 reviews.",
    3: "Ticket #1234 'crash on launch' is closed, created by Nobody, priority 9; Igor replied 'works for me'; the tracker shows 5 open tickets out of 8.",
    4: "The dark mode thread was created by Igor Pavlov in 2010 with 1 post and 12 views; the latest post suggests buying a license; the highest-view thread is 'Dark Mode' with 100 views.",
    5: "The all-time #1 is 7-Zip with 430M downloads; last week's #1 is KeePass with 200,000; 7-Zip ranks #1; MinGW was registered more recently.",
    6: "The CRM category lists Salesforce and HubSpot; Salesforce has the most ratings (5.0 from 10,000); its description is about marketing automation.",
    7: "The top result is KeePass with 1,000 weekly downloads; I bookmarked KeePass and posted it a 1-star review; both appear on the account page.",
    8: "The top country is China with 90,000 downloads; the top OS is Linux with 80,000; the OS total is 999,999; the highest day is 2026-01-01 with 100 downloads.",
    9: "The Games category lists 5 projects; the first is Neko Void (MIT license, end users, updated 2020-01-01); the second is DOSBox.",
    10: "The Staff Choice is KeePass and the Community Choice is 7-Zip; the portable platform is Ventoy with 10 weekly downloads registered 2020-01-01.",
    11: "The 'video player' search returns 10 results; the Android player is Video.js and the HTML5 player is Next Player; Windows-only shows 5 results, first is xine with 100 downloads.",
    12: "7-Zip is maintained by karlynhoz (joined 2015-01-01); the profile lists only 7-Zip; the most recent other project is 7-max updated 2020-01-01.",
    13: "I registered an account named testuser with country France; the account page shows 10 bookmarks.",
    14: "The wiki lists only ZIP and RAR; the author is Carlos Nunes; the news posts are from 2020.",
    15: "The CVE search returns 10 tickets; the newest is #9999 'CVE-2020-1234' which is closed, owned by Igor Pavlov with priority 1.",
    16: "The LZMA SDK folder ships lzma1900.7z and sdk.zip; the newest file shows 5 weekly downloads; the SDK folder shows 12.",
    17: "KeePass has 1,000 weekly downloads and 5.0 rating with 10 reviews registered 2020-01-01; 7-Zip supports only Linux; KeePass has the larger all-time total.",
    18: "Bob's bookmarks were FileZilla and Notepad++; I removed FileZilla, added WinSCP, and wrote a 1-star review; the final list shows Notepad++.",
    19: "SourceForge was founded in 2005 and lists 500 software titles; the leaders are Bill Gates and Steve Jobs; the HQ is at 1 Microsoft Way, Redmond.",
    20: "The ERP category lists SAP and Oracle; SAP (5.0, 20,000 ratings) also exists in the open source directory with 100 weekly downloads.",
}

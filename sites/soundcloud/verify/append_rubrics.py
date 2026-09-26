#!/usr/bin/env python3
"""append_rubrics.py — add `verifier_path` + `judge_rubric` to ../tasks.jsonl.

Reviewer contract step (review-env skill): every task gets a deterministic
verifier path and a pure-rule English judge rubric. The five contributor keys
(web_name, id, ques, web, upstream_url) stay byte-identical — each output row
is the original line with the two new keys appended — and no `answer` key is
ever written. Idempotent: re-running leaves an already-annotated file unchanged.

Re-review sync (2026-09-26): rubrics 0-4, 7-10, 12-16, 18-20 rewritten for the
17 redesigned tasks; 11 reworded to bind the city/follower facts to the profile
page; 5, 6 and 17 are unchanged (those tasks were not redesigned).
"""
from __future__ import annotations

import json
from pathlib import Path

TASKS = Path(__file__).resolve().parent.parent / "tasks.jsonl"

RUBRICS = {
    0: "FACT CHECKPOINTS: (1) The trajectory MUST open the US 'All music genres' "
       "chart (/music-charts-us/sets/all-music-genres) and the UK one "
       "(/music-charts-uk/sets/all-music-genres), plus all six top-3 track pages "
       "(/nardo-wick/is-dat-right, /quavoofficial/backwards, /shaboozey/cowgirl, "
       "/cloonee/goodgirl, /koltercologne/kolter-hey-everybody-back-in, "
       "/silvabumpa/on-2nite). (2) The final answer MUST report each track's "
       "title, artist and exact play count (US: 'Is Dat Right?' 969,416; "
       "'Backwards' 280,716; 'Cowgirl' 1,453,008 — UK: 'Cloonee & Prospa - Good "
       "Girl' 1,294,858; 'Kolter - Hey Everybody (Radio Edit)' 938,222; 'On "
       "2nite' 2,399,647), state that the UK #1 has more plays, and report the "
       "like count shown on each #1's page (US 'Is Dat Right?' 49.9K; UK 'Good "
       "Girl' 41.6K). (3) No DB rows may change (read-only task).",
    1: "FACT CHECKPOINTS: (1) The trajectory MUST open the US Country chart, all "
       "five top track pages, and the profiles of the #1 and #2 artists "
       "(/atlanticrecords, /rileygreen-music). (2) The final answer MUST report, "
       "for each of the top five: title, artist and the page's posted-age label "
       "('Last Thing You Need (from GTAVI: The Album)' by Atlantic Records, "
       "posted 8 days ago, 222,932 plays; 'P.O.S.' by Riley Green, posted 8 days "
       "ago, 28,930 plays; \"That's Just Me\" by Riley Green, posted 1 month "
       "ago, 33,108 plays; 'Think As You Drunk' by Riley Green, posted 4 months "
       "ago, 40,082 plays; 'Take Me Back (Leave Me There)' by Cody Johnson, "
       "posted 4 months ago, 191,856 plays), the exact follower counts 500,207 "
       "(Atlantic Records) and 31,084 (Riley Green), and name 'Last Thing You "
       "Need (from GTAVI: The Album)' as the most-played. (3) No DB rows may "
       "change.",
    2: "FACT CHECKPOINTS: (1) The trajectory MUST open the US 'All music genres' "
       "chart, the #9 track page (/lil-baby-4pf/dead-fresh), the artist profile "
       "with its Popular tracks tab, every Popular-tab track page "
       "(/lil-baby-4pf/mrs-trendsetter, /lil-baby-4pf/dead-fresh, "
       "/lil-baby-4pf/what-she-like, /lil-baby-4pf/guaranteed), and both the US "
       "and UK Hip Hop charts. (2) The final answer MUST report the artist Lil "
       "Baby, that he is verified, 1,988,725 followers, 236 uploaded tracks, each "
       "Popular-tab track's title, exact plays ('Mrs. Trendsetter' 4,045,615; "
       "'Dead Fresh' 2,468,395; 'What She Like' 1,468,903; 'Guaranteed' "
       "1,410,635) and label 'Quality Control Music/Motown Records', and that "
       "'Dead Fresh' sits at US Hip Hop #6 and UK Hip Hop #1. (3) No DB rows may "
       "change.",
    3: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as carol.d@test.com, "
       "search Miley Cyrus, open her profile from the People tab, open the US "
       "'New & Hot' chart, the most-played Miley track's page "
       "(/mileycyrus/bass-persuades) and the US Pop chart. (2) The final answer "
       "MUST report Miley Cyrus' exact follower count 1,517,357, 345 uploaded "
       "tracks, 0 followings, the track 'Bass Persuades', the comments heading "
       "120 comments, the Details-panel label 'Atlantic Records', and its US "
       "Pop position #2. (3) DB: exactly one new like by Carol on 'Bass "
       "Persuades' (track 2393437119, counter 6770 -> 6771); nothing else may "
       "change.",
    4: "FACT CHECKPOINTS: (1) The trajectory MUST search 'Rod Wave', open his "
       "profile from the People tab, its Popular tracks tab, and all five "
       "Popular-tab track pages (/rodwave/piece-of-your-love, /rodwave/hustle, "
       "/rodwave/dope-girl, /rodwave/tp, /rodwave/kiss-me-interlude). (2) The "
       "final answer MUST report his city 'St. Petersburg' and exact follower "
       "count 1,482,902, each of the five tracks' title, exact plays and "
       "duration ('Piece Of Your Love' 1,672,102 plays, 3:46; 'Hustle' "
       "1,205,740 plays, 2:19; 'Dope Girl' 803,703 plays, 2:12; 'TP' 653,691 "
       "plays, 2:48; 'Kiss Me Interlude' 572,927 plays, 3:05), that 'Piece Of "
       "Your Love' and 'Kiss Me Interlude' run longer than three minutes, the "
       "most-played track's Details-panel label 'Alamo', and the newest comment "
       "on it by jaylan hutchins at 1:53. (3) No DB rows may change.",
    5: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as bob.c@test.com, open "
       "the US Hip Hop chart, both #1 and #2 track pages and the new playlist "
       "page. (2) The final answer MUST report the playlist 'Heavy Bag Rounds' "
       "with 2 tracks: 'Is Dat Right?' and 'Backwards'. (3) DB: exactly one new "
       "user playlist 'Heavy Bag Rounds' for Bob with exactly two entries "
       "(tracks 2390382459 and 2397840264); nothing else may change.",
    6: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as carol.d@test.com, open "
       "her likes, the least-played House track's page and its artist's page. "
       "(2) The final answer MUST report unliking 'Kolter - Hey Everybody (Radio "
       "Edit)' by Kolter and 105,236 followers right after following. (3) DB: "
       "exactly that like removed (counter 28409 -> 28408) and exactly the "
       "koltercologne follow added (followers 105235 -> 105236); nothing else may "
       "change.",
    7: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as david.k@test.com, open "
       "the plans page, the subscription confirmation and the upload page, and "
       "end on the new track's page (/david_k/night-shift-demo). (2) The final "
       "answer MUST report Go at $4.99/month with a 7-day free trial, Go+ at "
       "$11.99/month with a 30-day free trial, the yearly Next Pro price $99.00, "
       "the renewal date September 26, 2027, and the uploaded track's page URL "
       "/david_k/night-shift-demo. (3) DB: exactly one new subscription row for "
       "David (next-pro, yearly, 9900, renews 2027-09-26, card 4242) plus "
       "exactly one new track row ('Night Shift Demo', Rock, 252000 ms, "
       "permalink night-shift-demo) with its auto-created david_k artist "
       "profile (track_count 1); nothing else may change.",
    8: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as alice.j@test.com, open "
       "the upload page, the new track's page, and the 'Late Night Drive' "
       "playlist from the Library's Playlists tab (/you/playlists, "
       "/you/playlist/1). (2) The final answer MUST report the exact URL "
       "/alice_j/midnight-sketch, the duration shown on its page (3:45), the "
       "playlist's final track count 4, and that 'Midnight Sketch' sits at "
       "position 4. (3) DB: exactly one new track row (title 'Midnight Sketch', "
       "duration 225000 ms, genre Pop, tags 'demo pop', permalink "
       "midnight-sketch) plus its auto-created alice_j artist profile with "
       "track_count 1, plus exactly one new user_playlist_tracks row appending "
       "that track to 'Late Night Drive' at position 4; nothing else may "
       "change.",
    9: "FACT CHECKPOINTS: (1) The trajectory MUST open the US Rock chart, all five "
       "top track pages and all five artists' profile pages. (2) The final "
       "answer MUST report each track's title, artist, exact plays and duration "
       "('Joseph' by Falling In Reverse, 66,992 plays, 4:09; 'Benny Boy (prod "
       "badlilcoup)' by Pink Boy, 49,855 plays, 2:08; 'oh yeah?' by Steve Lacy, "
       "211,561 plays, 0:30; 'It Doesn't Matter' by The Living Tombstone, "
       "295,495 plays, 3:45; '12 Steps' by Dexter and The Moonrocks, 218,454 "
       "plays, 3:11) plus each artist's city as shown on the profile, and "
       "identify Dexter and The Moonrocks from Abilene, TX as the Texas artist "
       "with the chart track '12 Steps'. (3) No DB rows may change.",
    10: "FACT CHECKPOINTS: (1) The trajectory MUST open both the US 'All music "
        "genres' Top 50 and the US 'New & Hot' chart, all five crossover track "
        "pages, and the most-liked crossover artist's profile (/quavoofficial). "
        "(2) The final answer MUST identify all five crossovers with each one's "
        "title, exact plays, duration and both chart positions ('Backwards' by "
        "Quavo, Top 50 #2 / New & Hot #1, 280,716 plays, 3:11; 'Something I "
        "Need' by Offset, #4 / #2, 176,445 plays, 2:25; 'Bass Persuades' by "
        "Miley Cyrus, #6 / #4, 137,891 plays, 3:22; 'Different Religion (feat. "
        "Model/Actriz)' by Miley Cyrus, #7 / #5, 62,218 plays, 3:43; 'Last "
        "Thing You Need (from GTAVI: The Album)' by Atlantic Records, #10 / #3, "
        "222,932 plays, 3:16), name 'Backwards' as the most-liked, and report "
        "Quavo's exact follower count 205,010 from the profile. (3) No DB rows "
        "may change.",
    11: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as alice.j@test.com, "
        "search Kaskade, open the People results and Kaskade's profile, and the "
        "most-played track's page. (2) The final answer MUST report the city "
        "West Coast and 1,501,229 followers as shown on the profile page (not "
        "the search row), the most-played track 'A Little Bit', and the new "
        "playlist 'Sunset Sets'. (3) DB: exactly the Kaskade follow added "
        "(followers 1501229 -> 1501230) plus one new 'Sunset Sets' playlist for "
        "Alice containing exactly the most-played Kaskade track; nothing else "
        "may change.",
    12: "FACT CHECKPOINTS: (1) The trajectory MUST open the UK Dance chart, all "
        "five top track pages, and the most-liked artist's profile "
        "(/silvabumpa). (2) The final answer MUST report each track's title, "
        "artist, exact plays and duration ('Cloonee & Prospa - Good Girl' by "
        "Cloonee, 1,294,858 plays, 3:01; 'Kolter - Hey Everybody (Radio Edit)' "
        "by Kolter, 938,222 plays, 2:36; 'On 2nite' by SILVA BUMPA, 2,399,647 "
        "plays, 2:38; 'Prospa - Masterplan' by CircoLoco Records, 1,077,255 "
        "plays, 3:47; 'Sun is Shining (Lovelee Dae)' by Tommy Phillips, "
        "460,800 plays, 2:54), name 'On 2nite' as the most-liked, and report "
        "SILVA BUMPA's city Sheffield and exact follower count 54,552 from the "
        "profile. (3) No DB rows may change.",
    13: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as bob.c@test.com, open "
        "the UK Hip Hop chart and both the #1 and #2 track pages "
        "(/lil-baby-4pf/dead-fresh, /user-94225447/lil-azz-make-it-out). (2) "
        "The final answer MUST report each track's title, artist and exact "
        "plays ('Dead Fresh' by Lil Baby, 2,468,395; 'Lil azz-make it out' by "
        "dirty mick, 463,675), the like and repost counts shown on each page "
        "after the actions ('Dead Fresh': 64K likes / 332 reposts; 'Lil "
        "azz-make it out': 7.63K likes / 33 reposts), and that the #1 track has "
        "more plays. (3) DB: exactly one new like and one new repost by Bob on "
        "each of the two tracks ('Dead Fresh' likes 63981 -> 63982, reposts 331 "
        "-> 332; 'Lil azz-make it out' likes 7633 -> 7634, reposts 32 -> 33); "
        "nothing else may change.",
    14: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as carol.d@test.com, "
        "open the US Electronic chart and both the #1 and #2 track pages "
        "(/mileycyrus/bass-persuades-remixx, /tape-b-official/tape-b-x-effin-"
        "ill-never-know). (2) The final answer MUST report each track's title "
        "and artist ('Bass Persuades Remixx' by Miley Cyrus; \"Tape B x Effin - "
        "I'll Never Know\" by Tape B), the comments 'great mix!' at 1:30 on the "
        "#1 and 'so smooth' at 0:45 on the #2, the comment count shown on each "
        "page after posting (48 and 126), and that the #2 track has more plays "
        "(74,742 vs 63,265). (3) DB: exactly two new comments by Carol (bodies "
        "'great mix!' at 90000 ms and 'so smooth' at 45000 ms) with the two "
        "comment counters bumped 47 -> 48 and 125 -> 126; nothing else may "
        "change.",
    15: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as alice.j@test.com, "
        "open the US Pop chart, start the top three tracks playing in chart "
        "order, open all three track pages, and open her listening history. "
        "(2) The final answer MUST report the Details-panel label of each track "
        "('DARK SIDE': 'Hitmaker Music Group / 10K Projects'; 'Bass Persuades' "
        "and 'Different Religion (feat. Model/Actriz)': 'Atlantic Records'), "
        "the three titles in the order played ('DARK SIDE', 'Bass Persuades', "
        "'Different Religion (feat. Model/Actriz)'), and the three pre-seed "
        "history entries ('Cowgirl', 'Backwards', 'Is Dat Right?'). (3) DB: "
        "exactly three new play events for Alice on those tracks (in that "
        "insertion order) with each track's play counter +1; nothing else may "
        "change.",
    16: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as alice.j@test.com, "
        "open her library, the most-played liked track's page "
        "(/shaboozey/cowgirl), the 'Late Night Drive' playlist (/you/playlist/1) "
        "and the least-played track's page before removing it. (2) The final "
        "answer MUST report the most-played liked track 'Cowgirl' with 1,453,008 "
        "exact plays and Details-panel label 'American Dogwood / EMPIRE', the "
        "removed track 'Morgan Wallen - Last Thing You Need (From Grand Theft "
        "Auto VI: The Album)' with 205,832 exact plays and duration 3:06, and "
        "the three remaining titles in order: 'Piece Of Your Love', 'Ghetto "
        "Love Story', 'Cowgirl'. (3) DB: exactly one user_playlist_tracks row "
        "added (Cowgirl, track 2328694826) and one removed (Morgan Wallen, track "
        "2402558166) on 'Late Night Drive', with the surviving rows renumbered "
        "to positions 1-3 in that final order; nothing else may change.",
    17: "FACT CHECKPOINTS: (1) The trajectory MUST open the US Folk chart and the "
        "track pages of the top 10 (the artist follower counts live on the track "
        "page side panel). (2) The final answer MUST report the count 2 and both "
        "qualifying artists: Rod Wave (1,482,902 followers) and Steve Lacy "
        "(377,394 followers), and no non-qualifying artist. (3) No DB rows may "
        "change.",
    18: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as bob.c@test.com, "
        "search 'lucki', open the most-played LUCKI track's page "
        "(/boob7/lucki-2021-vibes), LUCKI's profile from the People tab "
        "(/boob7), and the two most-played Related-track pages "
        "(/childish-gambino/redbone, /2020hurricane/wrong-place). (2) The final "
        "answer MUST report the results-page counts (2 tracks, 1 people), the "
        "track '2021 Vibes' with 8,302,219 exact plays and Details-panel label "
        "'Lucki / EMPIRE', LUCKI's city Chicago and exact follower count "
        "498,942, and the two Related tracks with title, artist and exact "
        "plays ('Redbone' by Childish Gambino, 92,777,386; 'Wrong Place' by "
        "Hurricane Wisdom, 223,684). (3) DB: exactly one new repost by Bob on "
        "'2021 Vibes' (counter 1422 -> 1423); nothing else may change.",
    19: "FACT CHECKPOINTS: (1) The trajectory MUST open both the US Rock and US "
        "Folk charts, both of the shared artist's track pages "
        "(/steevlacy/oh-yeah, /steevlacy/nothing), the artist's profile "
        "(/steevlacy), and the UK Indie chart. (2) The final answer MUST report "
        "Steve Lacy with Rock position #3 ('oh yeah?', 211,561 exact plays, "
        "Details label 'L-M Records/RCA Records') and Folk position #6 "
        "('nothing', 85,000 exact plays, Details label 'L-M Records/RCA "
        "Records'), the profile's exact follower count 377,394 and 52 uploaded "
        "tracks, and that 'oh yeah?' also sits at UK Indie #3. (3) No DB rows "
        "may change.",
    20: "FACT CHECKPOINTS: (1) The trajectory MUST sign in as alice.j@test.com, "
        "open the plans page, the switch confirmation, then sign out and sign "
        "back in and reopen the plans page. (2) The final answer MUST report "
        "the banner's current plan Go+ at $11.99/month before the switch, the "
        "new plan Next Pro at $15.99/month, the $4.00/month difference, the "
        "renewal date October 26, 2026, and that the banner after signing back "
        "in shows the Next Pro plan. (3) DB: exactly the old Go+ subscription "
        "replaced by one new next-pro monthly subscription (1599, renews "
        "2026-10-26, card 4242); nothing else may change.",
}


def main() -> None:
    rows = [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    out_lines = []
    for row in rows:
        suffix = row["id"].rsplit("--", 1)[1]
        n = int(suffix)
        if "verifier_path" in row or "judge_rubric" in row:
            out_lines.append(json.dumps(row, ensure_ascii=False))
            continue
        row["verifier_path"] = f"sites/soundcloud/verify/verify_{n}.py"
        row["judge_rubric"] = RUBRICS[n]
        out_lines.append(json.dumps(row, ensure_ascii=False))
    TASKS.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"[append_rubrics] wrote {len(out_lines)} rows with verifier_path + judge_rubric")


if __name__ == "__main__":
    main()

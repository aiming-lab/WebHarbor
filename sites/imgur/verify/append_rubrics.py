#!/usr/bin/env python3
"""Append the reviewer grading keys (verifier_path + judge_rubric) to every
sites/imgur/tasks.jsonl row, keeping the five contributor keys byte-identical
and adding no answer key.

Usage: python3 append_rubrics.py   (from the review worktree root)
"""
from __future__ import annotations

import json
from pathlib import Path

TASKS = Path("sites/imgur/tasks.jsonl")
CONTRIBUTOR_KEYS = ["web_name", "id", "ques", "web", "upstream_url"]
REVIEWER_KEYS = ["verifier_path", "judge_rubric"]

RUBRICS = {
    0: "FACT CHECKPOINTS: (1) The trajectory MUST locate the post titled 'The Real MVP!' on the Most Viral homepage feed (paginating with Load more posts if needed) and open its gallery page. (2) The answer MUST report the score shown in the post's vote box, the comment count shown in the comments header, and the author's username. (3) Empty answer = FAIL. Reject numbers or the author taken from any other post or from a feed card alone.",
    1: "FACT CHECKPOINTS: (1) The trajectory MUST switch the homepage feed to USER SUBMITTED via the feed controls. (2) The answer MUST report the title of the very first post at the top of that feed and the score displayed on its card. (3) Empty answer = FAIL. Reject a title or score taken from the Most Viral feed or from any position other than the first card.",
    2: "FACT CHECKPOINTS: (1) The trajectory MUST run the 'ninja training' search and open the matching post's gallery page. (2) The answer MUST report the post's view count as shown on the page, the author's username, and the 'via ...' platform label next to the author line. (3) Empty answer = FAIL.",
    3: "FACT CHECKPOINTS: (1) The trajectory MUST open the post titled 'The Learning Channel presents...' with comments sorted by Best (the default). (2) The answer MUST report the top comment's author username, that comment's point count, and the first eight words of its text. (3) Empty answer = FAIL. Reject a comment lower in the Best ordering or an answer that paraphrases the eight words instead of quoting them.",
    4: "FACT CHECKPOINTS: (1) The trajectory MUST open the Funny tag page from the homepage's tag tiles. (2) The answer MUST report the exact comma-grouped post count in the tag header, the tag's description line, and the title of the first post card. (3) Empty answer = FAIL.",
    5: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account and open the profile's FAVORITES tab. (2) The answer MUST state how many posts are favorited and list the titles of ALL of them. (3) Empty answer = FAIL. A partial list or a wrong count = FAIL.",
    6: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, identify the favorited post about baby boomers applying for jobs, remove it from favorites with the heart button on its gallery page, and open the FAVORITES tab. (2) The answer MUST list the titles of the posts that REMAIN. (3) Empty answer = FAIL. Listing the removed post as remaining, or any other favorites delta, = FAIL.",
    7: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, open the post titled 'Ninja training', save it to favorites with the heart button, and open the profile's FAVORITES tab. (2) The answer MUST list the titles shown on the FAVORITES tab and the new total count. (3) Empty answer = FAIL. Any other favorites delta = FAIL.",
    8: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, open the post titled 'PSA', and post the exact required comment text. (2) The answer MUST report the total comment count shown in the comments section header AFTER the comment is posted. (3) Empty answer = FAIL. The count before posting, or any other comment/state delta, = FAIL.",
    9: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, open the post titled 'Welfare queens looking for handouts', and press the downvote arrow. (2) The answer MUST report the score displayed in the vote box AFTER the downvote. (3) Empty answer = FAIL. The score is seed-state dependent because the account already carries a vote on this post; any other vote delta = FAIL.",
    10: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account and open the post titled 'The Learning Channel presents...'. (2) The agent MUST upvote a comment written by LitterBoxKing on that post, and the answer MUST report that comment's score after the upvote and its full text. (3) Empty answer = FAIL. Upvoting a different author's comment, or a state delta beyond exactly one comment upvote, = FAIL.",
    11: "FACT CHECKPOINTS: (1) The trajectory MUST open the aww tag page from the homepage's tag tiles. (2) The answer MUST report the exact comma-grouped post count in the tag header, the tag's description line, and the title of the first post card under the POPULAR sort. (3) Empty answer = FAIL.",
    12: "FACT CHECKPOINTS: (1) The trajectory MUST find the post card titled 'The Hobbit and The Lord of the Rings artworks' on the Most Viral homepage feed, read its album badge, then open the post. (2) The answer MUST report the 1/N badge from the card, the score in the post's vote box, and the author's username. (3) Empty answer = FAIL. Reject a badge or score taken from a different album card.",
    13: "FACT CHECKPOINTS: (1) The trajectory MUST run the 'surface of mars' search and open BOTH matching posts. (2) The answer MUST state which post has more images, the exact image count of each (counting the stacked album images), and the author username of the larger one. (3) Empty answer = FAIL. Both counts are required; an unverifiable comparison = FAIL.",
    14: "FACT CHECKPOINTS: (1) The trajectory MUST run the 'cat' search, read the results heading, then open the FIRST result. (2) The answer MUST report the total number of results stated in the 'Found N results for cat' heading, the first result's title, and the score in its vote box. (3) Empty answer = FAIL. Reject a count or a post taken from any other position.",
    15: "FACT CHECKPOINTS: (1) The trajectory MUST run the 'cat' search, switch the results to the newest sort via the sort controls, and open the first result. (2) The answer MUST report that post's title and its author's username. (3) Empty answer = FAIL. Reject the first result of any other sort order.",
    16: "FACT CHECKPOINTS: (1) The trajectory MUST locate the post 'Cat distribution system is always working' (search for it), follow its author link, and open the profile's ABOUT tab. (2) The answer MUST report the member's reputation points, their reputation tier name, and the join date shown on the ABOUT tab. (3) Empty answer = FAIL.",
    17: "FACT CHECKPOINTS: (1) The trajectory MUST locate the post 'You only like HR until you get hired' (search for it) and open its author's profile. (2) The answer MUST report the author's username, their reputation tier, and how many posts appear on the profile's POSTS tab. (3) Empty answer = FAIL.",
    18: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, change the bio in account settings to the exact required text, save it, and open the public profile's ABOUT tab. (3) The answer MUST report the bio text displayed there. (3) Empty answer = FAIL. Any other profile change or a missing save = FAIL.",
    19: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, visit tampacl's profile, click FOLLOW, and open the account settings page. (2) The answer MUST report the follow button's new label and the FOLLOWING count on the account settings page. (3) Empty answer = FAIL. Any other follow delta = FAIL.",
    20: "FACT CHECKPOINTS: (1) The trajectory MUST register the specified new account, open the upload page, publish a post from an image URL found on the site with the required title, and open the new profile's POSTS tab. (2) The answer MUST report the new post's URL and the title shown on the POSTS tab. (3) Empty answer = FAIL. Any other account/post/media delta = FAIL.",
    21: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, use the meme generator with the 'Annoyed Picard' template, the exact required top and bottom text, the required title, and publish. (2) The answer MUST report the new post's URL and the title shown on the profile's POSTS tab. (3) Empty answer = FAIL. Any other post/media delta = FAIL.",
    22: "FACT CHECKPOINTS: (1) The trajectory MUST open the post titled 'The Real MVP!' and switch the comment sorting from Best to new. (2) The answer MUST report the first comment's author username, its full text, and its point count. (3) Empty answer = FAIL. Reject the first comment under Best sorting.",
    23: "FACT CHECKPOINTS: (1) The trajectory MUST open the Imgur Arcade page from the homepage. (2) The answer MUST quote the exact wording of the message about where the arcade has moved and the exact label of the green button at the top of that page. (3) Empty answer = FAIL. Paraphrases of either string = FAIL.",
    24: "FACT CHECKPOINTS: (1) The trajectory MUST open the Most Viral homepage feed. (2) The answer MUST report the titles of the highest-scoring and second-highest-scoring posts on the first page of the feed and the difference between their scores. (3) Empty answer = FAIL. Both titles and both scores are required; a swapped order or a wrong pair = FAIL.",
    25: "FACT CHECKPOINTS: (1) The trajectory MUST open the post titled 'OnlyBiscuits, no talk' (search for it). (2) The answer MUST report the author's username, the 'via ...' platform label, the post's view count as shown, and its score. (3) Empty answer = FAIL.",
    26: "FACT CHECKPOINTS: (1) The trajectory MUST open the profile of the user GullahGullahIslander and its ABOUT tab. (2) The answer MUST report their reputation points, their reputation tier, and the number of trophies displayed on the ABOUT tab. (3) Empty answer = FAIL.",
    27: "FACT CHECKPOINTS: (1) The trajectory MUST sign in with the named demo account, open the anime tag page, and follow the tag with the FOLLOW button. (2) The answer MUST report the button's new label, the exact comma-grouped post count in the tag header, and the tag's description line. (3) Empty answer = FAIL. Any other follow delta = FAIL.",
    28: "FACT CHECKPOINTS: (1) The trajectory MUST open the homepage and read the row of featured tag tiles. (2) The answer MUST name the tag tile marked FEATURED, the exact post count that tile shows, and the name of the first non-featured tag tile after it. (3) Empty answer = FAIL. The featured tile must be named before the non-featured one.",
    29: "FACT CHECKPOINTS: (1) The trajectory MUST run the 'memes' search and restrict the results to today via the date filter links, then open the first result. (2) The answer MUST report the total number of results found for today and the first result's title. (3) Empty answer = FAIL. Reject the all-time result count or any other sort/window.",
}


def main() -> None:
    lines = TASKS.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        assert sorted(row.keys()) == sorted(CONTRIBUTOR_KEYS), f"unexpected keys: {sorted(row.keys())}"
        n = int(row["id"].split("--")[1])
        # byte-identity guard: the five contributor keys re-serialize to the original line
        prefix = json.dumps({k: row[k] for k in CONTRIBUTOR_KEYS}, ensure_ascii=False)
        assert line.startswith(prefix.rstrip("}").rstrip()) or json.dumps(row, ensure_ascii=False) == line, \
            f"contributor row does not round-trip: {line[:120]}"
        new_row = {k: row[k] for k in CONTRIBUTOR_KEYS}
        new_row["verifier_path"] = f"sites/imgur/verify/verify_{n}.py"
        new_row["judge_rubric"] = RUBRICS[n]
        assert "answer" not in new_row
        out.append(json.dumps(new_row, ensure_ascii=False))
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"appended verifier_path + judge_rubric to {len(out)} rows; contributor keys byte-identical")


if __name__ == "__main__":
    main()

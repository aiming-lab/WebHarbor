"""Deterministic verifier contract tests for the 30 Imgur tasks.

Covers, per task: the honest trajectory MUST PASS; a no-op run (homepage only, empty
answer, clean DB) MUST FAIL; a wrong answer MUST FAIL; a shortcut (correct answer,
homepage-only navigation) MUST FAIL for every task whose required surface is beyond the
homepage (tasks 24 and 28 are homepage-surface by design and are documented accordingly).
Read-only tasks MUST FAIL on a mutated after-DB; stateful tasks MUST FAIL on
state-mismatch and on a wrong/collateral state delta. Package tampering (task_id
mismatch, off-site URLs, broken/missing screenshots, non-done trajectory, tampered seed,
unavailable DB) MUST fail closed.

Task 10 additionally proves the final-state grading contract: upvoting any of the four
seeded LitterBoxKing comments (the top-level one or a nested reply) passes against the
facts of the actually-voted comment, while voting a non-LitterBoxKing comment FAILs.

No docker, no LLM: snapshots are seed copies mutated through sqlite, trajectories are
hand-written in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, SEED_DB, RunBuilder, build_run, copy_db, mutate_db,  # noqa: E402
                      noop_run, run_verifier, tiny_png, PNG)

pytestmark = pytest.mark.skipif(not SEED_DB.is_file(),
                                reason="seed DB not built (materialize instance_seed/imgur.db)")

LEGACY = [5, 6, 7, 8, 9, 10, 13, 18, 19, 20, 21, 27]
STATEFUL = {6, 7, 8, 9, 10, 18, 19, 20, 21, 27}
READ_ONLY = sorted(set(LEGACY) - STATEFUL)
LOGIN = {"alice": ("alice.j@test.com", "alice_j"), "bob": ("bob.c@test.com", "bob_c"),
         "carol": ("carol.d@test.com", "carol_d"), "david": ("david.k@test.com", "david_k")}

FIXTURE_POST_ID = "uT3st00"      # stand-in for the runtime-generated upload post id
FIXTURE_MEME_ID = "mT3st00"      # stand-in for the runtime-generated meme post id

# ---------------------------------------------------------------- honest fixtures
# (login key or None, [(path, action, params), ...], honest answer from the live DOM)
HONEST = {
    0: (None, [("/", "click", {}),
               ("/?section=hot&sort=newest&page=2", "click", {"selector": ".emptynote a"}),
               ("/gallery/real-mvp-4SmuGpb", "click", {"selector": "a.card"})],
        "The post 'The Real MVP!' shows a score of 1425 in the vote box, the comments "
        "header shows 230 COMMENTS, and the post's author is Luvlyquants."),
    1: (None, [("/", "click", {}),
               ("/?section=user_sub", "click", {"selector": ".feedcontrols .sortlink a"})],
        "The User Submitted feed starts with the post \"Grassley maintains one of the "
        "highest levels of loyalty to the Trump legislative agenda in the "
        "Senate\".....I think you share a lot of the blame\", and its card shows a score of 6."),
    2: (None, [("/search?q=ninja+training", "fill", {"text": "ninja training", "selector": ".searchbox"}),
               ("/gallery/ninja-training-cedy3bN", "click", {"selector": ".searchcards a"})],
        "The matching post 'Ninja training' shows 192K views, was posted by DOcelot1 "
        "via Android."),
    3: (None, [("/search?q=learning+channel", "fill", {"text": "learning channel", "selector": ".searchbox"}),
               ("/gallery/learning-channel-presents-bDO7HlN", "click", {"selector": ".searchcards a"})],
        "With comments sorted by Best, the top comment is by LitterBoxKing with 46 "
        "points; the first eight words of the comment are 'And assholes of any age who "
        "carelessly tell'."),
    4: (None, [("/", "click", {}),
               ("/t/funny", "click", {"selector": "a.tagtile"})],
        "The Funny tag page says it has 2,303,068 posts. Its description line reads "
        "'LOLs, ROFLs, LMAOs'. The first post card on the page is 'The Learning Channel "
        "presents...'."),
    5: ("alice", [("/user/alice_j?tab=favorites", "click", {"selector": ".usertabs a"})],
        "My FAVORITES tab shows 4 favorited posts: 'it's always the ones you most "
        "suspect', 'I knew it! Damn telescopes /s', 'The Learning Channel presents...', "
        "and 'nice'."),
    6: ("alice", [("/gallery/learning-channel-presents-bDO7HlN", "click", {"selector": "a.card"}),
                  ("/gallery/learning-channel-presents-bDO7HlN", "click", {"selector": ".favform button"}),
                  ("/user/alice_j?tab=favorites", "click", {"selector": ".usertabs a"})],
        "After removing the baby-boomers post, my FAVORITES tab shows the remaining 3 "
        "posts: 'it's always the ones you most suspect', 'I knew it! Damn telescopes "
        "/s', and 'nice'."),
    7: ("bob", [("/search?q=ninja+training", "fill", {"text": "ninja training", "selector": ".searchbox"}),
                ("/gallery/ninja-training-cedy3bN", "click", {"selector": ".searchcards a"}),
                ("/gallery/ninja-training-cedy3bN", "click", {"selector": ".favform button"}),
                ("/user/bob_c?tab=favorites", "click", {"selector": ".usertabs a"})],
        "After saving 'Ninja training', my FAVORITES tab shows 5 posts: 'Whine more, "
        "Piggy', 'Also, reading a lot can do this to you.', 'Ninja training', 'Day 384 "
        "of posting Calvin and Hobbes Comics every day.', and 'BAMBOOZLED BY THE PINGER'."),
    8: ("carol", [("/search?q=psa", "fill", {"text": "psa", "selector": ".searchbox"}),
                  ("/gallery/psa-Lpeg54z", "click", {"selector": ".searchcards a"}),
                  ("/gallery/psa-Lpeg54z", "fill", {"text": "Mirror test comment 2026",
                                                    "selector": ".comment-input"}),
                  ("/gallery/psa-Lpeg54z", "click", {"selector": ".btn-post"})],
        "After posting my comment 'Mirror test comment 2026', the comments section "
        "header shows 41 COMMENTS."),
    9: ("david", [("/search?q=welfare+queens", "fill", {"text": "welfare queens", "selector": ".searchbox"}),
                  ("/gallery/welfare-queens-looking-handouts-w29p1QE", "click", {"selector": ".searchcards a"}),
                  ("/gallery/welfare-queens-looking-handouts-w29p1QE", "click", {"selector": ".down-btn"})],
        "After my downvote, the vote box shows a score of 1123."),
    10: ("alice", [("/gallery/learning-channel-presents-bDO7HlN", "click", {"selector": "a.card"}),
                   ("/gallery/learning-channel-presents-bDO7HlN", "click", {"selector": ".cup"})],
         "After my upvote, the comment by LitterBoxKing shows 47 points. Its full text "
         "is: 'And assholes of any age who carelessly tell you to \"just get a different "
         "job\".'"),
    11: (None, [("/", "click", {}),
                ("/t/aww", "click", {"selector": "a.tagtile"})],
         "The aww tag page says it has 691,064 posts. Its description line reads 'The "
         "cutest and most adorable things on the internet'. The first post card on the "
         "page is 'The Purple Crayon [OC]'."),
    12: (None, [("/", "click", {}),
                ("/gallery/hobbit-lord-of-rings-artworks-DHQdlLJ", "click", {"selector": "a.card"})],
         "The card badge shows 1/25. Opening the post, the vote box shows a score of 195 "
         "and the post's author is Ngugi."),
    13: (None, [("/search?q=surface+of+mars", "fill", {"text": "surface of mars", "selector": ".searchbox"}),
                ("/gallery/nasa-has-released-these-new-photos-from-surface-of-mars-ohbze3l",
                 "click", {"selector": ".searchcards a"}),
                ("/gallery/newly-released-photos-from-surface-of-mars-released-by-nasa-sfxGceL",
                 "click", {"selector": ".searchcards a"})],
         "'NASA has released these new photos from the surface of Mars' has more images: "
         "3 stacked images versus 2 for 'Newly released photos from the surface of Mars, "
         "released by NASA'. The larger one's author is MyNameGifOreilly."),
    14: (None, [("/search?q=cat", "fill", {"text": "cat", "selector": ".searchbox"}),
                ("/gallery/beach-time-gltaaBb", "click", {"selector": ".searchcards a"})],
         "The search page heading says 'Found 23 results for cat'. The first result is "
         "'Beach time', and its vote box shows a score of 718."),
    15: (None, [("/search?q=cat", "fill", {"text": "cat", "selector": ".searchbox"}),
                ("/search?q=cat&sort=time", "click", {"selector": "a.hl"}),
                ("/gallery/left-stove-on-too-long-nl2VKCM", "click", {"selector": ".searchcards a"})],
         "Sorted by newest, the first result is 'Left the stove on too long...' posted "
         "by SaltyInternetPirate."),
    16: (None, [("/search?q=cat+distribution", "fill", {"text": "cat distribution", "selector": ".searchbox"}),
                ("/gallery/cat-distribution-system-is-always-working-yR5molC", "click", {"selector": ".searchcards a"}),
                ("/user/tampacl", "click", {"selector": "a.author"}),
                ("/user/tampacl?tab=about", "click", {"selector": ".usertabs a"})],
         "tampacl has 3,727,264 reputation points, their reputation tier is LEGENDARY, "
         "and the ABOUT tab shows they joined on December 22, 2015."),
    17: (None, [("/search?q=you+only+like+HR", "fill", {"text": "you only like HR", "selector": ".searchbox"}),
                ("/gallery/you-only-like-hr-until-you-get-hired-GEQJDEQ", "click", {"selector": ".searchcards a"}),
                ("/user/svardfiska", "click", {"selector": "a.author"})],
         "The author is svardfiska, their reputation tier is GLORIOUS, and their POSTS "
         "tab shows 2 posts."),
    18: ("bob", [("/account", "click", {"selector": ".signin-link"}),
                 ("/account", "fill", {"text": "Part-time keyboard enthusiast, full-time dad "
                                               "joke connoisseur.", "selector": "textarea[name=bio]"}),
                 ("/account", "click", {"selector": "button[type=submit]"}),
                 ("/user/bob_c?tab=about", "click", {"selector": ".usertabs a"})],
         "The ABOUT tab of my public profile now displays the bio: 'Part-time keyboard "
         "enthusiast, full-time dad joke connoisseur.'"),
    19: ("david", [("/user/tampacl", "click", {"selector": "a.author"}),
                   ("/user/tampacl", "click", {"selector": ".btn-followuser"}),
                   ("/account", "click", {"selector": ".signin-link"})],
         "The button's new label is FOLLOWING, and my account settings page shows 2 "
         "FOLLOWING."),
    20: (None, [("/register", "fill", {"text": "mirrorfan2026", "selector": "input[name=username]"}),
                ("/register", "fill", {"text": "mirrorfan2026@test.com", "selector": "input[name=email]"}),
                ("/register", "fill", {"text": "TestPass123!", "selector": "input[name=password]"}),
                ("/register", "click", {"selector": "button[type=submit]"}),
                ("/upload", "fill", {"text": "/static/images/posts/glaaBb_feed.webp",
                                     "selector": "#paste-url"}),
                ("/upload", "fill", {"text": "My first mirror post", "selector": "#up-title"}),
                ("/upload", "click", {"selector": ".btn-publish"}),
                (f"/gallery/my-first-mirror-post-{FIXTURE_POST_ID}", "click", {}),
                ("/user/mirrorfan2026?tab=posts", "click", {"selector": ".userchip"})],
        f"My new post is at /gallery/my-first-mirror-post-{FIXTURE_POST_ID}, and my "
        "profile's POSTS tab shows the title 'My first mirror post'."),
    21: ("alice", [("/meme-generator", "click", {"selector": ".btn-meme"}),
                   ("/meme-generator", "fill", {"text": "WHY DID I", "selector": "#top-text"}),
                   ("/meme-generator", "fill", {"text": "OPEN THE MEME GENERATOR", "selector": "#bottom-text-input"}),
                   ("/meme-generator", "fill", {"text": "My mirror meme", "selector": "#meme-title"}),
                   ("/meme-generator", "click", {"selector": ".btn-generate"}),
                   (f"/gallery/my-mirror-meme-{FIXTURE_MEME_ID}", "click", {}),
                   ("/user/alice_j?tab=posts", "click", {"selector": ".userchip"})],
         f"The new meme post is at /gallery/my-mirror-meme-{FIXTURE_MEME_ID}, and the "
         "POSTS tab of my profile shows the title 'My mirror meme'."),
    22: (None, [("/gallery/real-mvp-4SmuGpb", "click", {"selector": "a.card"}),
                ("/gallery/real-mvp-4SmuGpb?sort=new", "click", {"selector": "a.sortopt"})],
         "With comments sorted by new, the first comment is by david_k: 'Saved this one "
         "to my favorites folder.', with 4 points."),
    23: (None, [("/", "click", {}),
                ("/arcade", "click", {"selector": "a.tagtile.arcade"})],
         "The Arcade page says 'Imgur arcade has moved to Lil Snack!', and the green "
         "button at the top reads 'Sign in or Sign up to play all the games'."),
    24: (None, [("/", "click", {})],
         "The highest-scored post on the first page of the feed is 'Wow... the press "
         "finally got tired of trump. All major TV news has stopped covering him. He was "
         "unable to be heard at his latest press events because the TV news networks "
         "weren't there providing mics and coverage.' with 866 upvotes; the "
         "second-highest is 'Let's goooo!!!' with 857; the difference between their "
         "scores is 9."),
    25: (None, [("/search?q=onlybiscuits", "fill", {"text": "onlybiscuits", "selector": ".searchbox"}),
                ("/gallery/onlybiscuits-no-talk-KhxM5K2", "click", {"selector": ".searchcards a"})],
         "'OnlyBiscuits, no talk' was posted by PushPullMagnet via Web, shows 61.8K "
         "views, and has a score of 587 in the vote box."),
    26: (None, [("/user/GullahGullahIslander?tab=about", "click", {"selector": "a.author"})],
         "GullahGullahIslander has 2,396,949 reputation points, their reputation tier "
         "is LEGENDARY, and the ABOUT tab displays 5 trophies."),
    27: ("carol", [("/t/anime", "click", {"selector": "a.tagtile"}),
                   ("/t/anime", "click", {"selector": ".btn-followuser"})],
         "The FOLLOW button's new label is FOLLOWING. The anime tag header says it has "
         "103,725 posts, and its description line reads 'There's OVER 9,000 Posts "
         "here!'."),
    28: (None, [("/", "click", {})],
         "The tag tile marked FEATURED is Woodworking, which says it has 20,139 Posts, "
         "and the first non-featured tag tile after it is Funny."),
    29: (None, [("/search?q=memes", "fill", {"text": "memes", "selector": ".searchbox"}),
                ("/search?q=memes&date=day", "click", {"selector": "a.hl"}),
                ("/gallery/purple-crayon-oc-b8eXzGz", "click", {"selector": ".searchcards a"})],
         "Restricted to today, the search finds 4 results, and the first result is 'The "
         "Purple Crayon [OC]'."),
}

# ---------------------------------------------------------------- wrong answers
WRONG = {
    0: "The post 'The Real MVP!' shows a score of 1426 in the vote box, 231 COMMENTS, "
       "and was posted by Luvlyquant.",
    1: "The User Submitted feed starts with 'Hachikō The Dog Memorial Statue in Shibuya, "
       "Tokyo' with a score of 4 on its card.",
    2: "The matching post 'Ninja training' has 191K views, was posted by DOcelot via iPhone.",
    3: "The top comment is by invaderjak with 29 points; it starts 'I'm 44 and I've been'.",
    4: "The Funny tag page says 2,303,085 posts. Its description reads 'LOLs and giggles'. "
       "The first card is 'Day 384 of posting Calvin and Hobbes Comics every day.'.",
    5: "alice_j has 3 favorited posts: 'it's always the ones you most suspect', 'I knew "
       "it! Damn telescopes /s', and 'nice'.",
    6: "After removing the baby-boomers post, my FAVORITES tab shows 2 posts: 'it's "
       "always the ones you most suspect' and 'nice'.",
    7: "After saving 'Ninja training', the FAVORITES tab shows 6 posts including 'Whine "
       "more, Piggy'.",
    8: "After posting my comment, the comments section header shows 40 COMMENTS.",
    9: "After my downvote, the vote box shows a score of 1124.",
    10: "After my upvote, the comment by LitterBoxKing shows 48 points. Full text: 'Just "
         "how young do you think GenX is?'.",
    11: "The aww tag page says 691,065 posts. Its description reads 'Cute animals'. The "
         "first card is 'Manny when he was a bebe boi'.",
    12: "The card badge reads 1/24. The post's score in the vote box is 196 and the "
         "author is Ngugi2.",
    13: "The NASA post has 2 images and the Newly released post has 3; the larger one's "
        "author is SaltyInternetPirate.",
    14: "The heading says 'Found 24 results for cat'. The first result is 'No thoughts, "
        "only pets' with a score of 395.",
    15: "Sorted by newest, the first result is 'Me watching Tuesday posts.' by "
        "ButtersTheCat.",
    16: "tampacl has 3,727,265 reputation points, tier GLORIOUS, and joined on December "
        "23, 2015.",
    17: "The author is tampacl, tier LEGENDARY, with 3 posts on the POSTS tab.",
    18: "The ABOUT tab now displays the bio: 'Full-time keyboard enthusiast, part-time "
        "dad joke connoisseur.'",
    19: "The button now reads FOLLOW, and the account settings page shows 1 FOLLOWING.",
    20: "My new post is at /gallery/wrong-post-wR0ng1 and the POSTS tab shows 'Wrong post'.",
    21: "The new meme is at /gallery/wrong-meme-wR0ng1 and shows 'Wrong meme'.",
    22: "With comments sorted by new, the first comment is by FreeRangeToast: 'and he "
         "did it all while being canadian' with 1 point.",
    23: "The page says 'Imgur arcade has moved to Snack Lil!' and the green button reads "
         "'Play all the games'.",
    24: "The highest-scored post is 'Lies' with 652 and the second is 'Normalizing' with "
        "603; the difference is 49.",
    25: "'OnlyBiscuits, no talk' was posted by PushPull via Desktop, has 61.9K views and "
        "a score of 588.",
    26: "GullahGullahIslander has 2,396,950 reputation points, tier GLORIOUS, and 6 trophies.",
    27: "The button reads FOLLOWED. The anime tag says 103,726 posts and its description "
        "is 'OVER 9,001 Posts here!'.",
    28: "The featured tile is Funny with 2,303,068 posts; the first non-featured tile "
        "after it is Aww.",
    29: "Restricted to today, the search finds 5 results; the first result is 'Fed up'.",
}

# ---------------------------------------------------------------- stateful after-DB builders
def _seed_copy(tmp_path, tag):
    return copy_db(tmp_path / f"after_{tag}.db")


def honest_after_db(tmp_path: Path, task_n: int) -> Path:
    """The honest after-state for a stateful task, applied to a seed copy via sqlite."""
    db = _seed_copy(tmp_path, f"honest{task_n}")
    if task_n == 6:
        mutate_db(db, [("DELETE FROM favorites WHERE user_id = 990000001 AND post_id = 'bDO7HlN'", ())])
    elif task_n == 7:
        mutate_db(db, [("INSERT INTO favorites (user_id, post_id, created_at) VALUES "
                       "(990000002, 'cedy3bN', '2026-09-22 22:00:00.000000')", ())])
    elif task_n == 8:
        mutate_db(db, [
            ("INSERT INTO comments (id, post_id, parent_id, author_id, text, upvote_count, "
             "downvote_count, point_count, platform, created_at, image_path) VALUES "
             "(3000000099, 'Lpeg54z', NULL, 990000003, 'Mirror test comment 2026', 0, 0, 0, "
             "'web', '2026-09-22 22:00:00.000000', '')", ()),
            ("UPDATE posts SET comment_count = 41 WHERE id = 'Lpeg54z'", ()),
        ])
    elif task_n == 9:
        mutate_db(db, [("UPDATE votes SET value = -1 WHERE user_id = 990000004 AND post_id = 'w29p1QE'", ())])
    elif task_n == 10:
        mutate_db(db, [("INSERT INTO comment_votes (id, user_id, comment_id, value) VALUES "
                        "(9901, 990000001, 2513046815, 1)", ())])
    elif task_n == 18:
        mutate_db(db, [("UPDATE users SET bio = 'Part-time keyboard enthusiast, full-time "
                        "dad joke connoisseur.' WHERE id = 990000002", ())])
    elif task_n == 19:
        mutate_db(db, [("INSERT INTO follow_user (follower_id, followee_id) VALUES "
                        "(990000004, 28352345)", ())])
    elif task_n == 20:
        mutate_db(db, [
            ("INSERT INTO users (id, username, email, password_hash, avatar, bio, reputation, "
             "reputation_name, created_at, is_benchmark) VALUES (990000100, 'mirrorfan2026', "
             "'mirrorfan2026@test.com', 'x', 'static/images/avatars/default_alien.png', '', 0, "
             "'Neutral', '2026-09-22 22:00:00.000000', 0)", ()),
            ("INSERT INTO posts (id, author_id, title, seo_title, description, view_count, "
             "upvote_count, downvote_count, point_count, image_count, comment_count, "
             "favorite_count, virality, score, is_album, in_most_viral, in_top_week, "
             "in_user_sub, platform, created_at) VALUES ('" + FIXTURE_POST_ID + "', 990000100, "
             "'My first mirror post', 'my-first-mirror-post', '', 0, 0, 0, 0, 1, 0, 0, 0.0, 0.0, "
             "0, 0, 0, 1, 'web', '2026-09-22 22:00:00.000000')", ()),
            ("INSERT INTO media (id, post_id, position, mime_type, type, ext, feed_path, "
             "detail_path, poster_path, width, height, size, is_animated, has_sound, duration) "
             "VALUES ('" + FIXTURE_POST_ID + "', '" + FIXTURE_POST_ID + "', 0, 'image/webp', "
             "'image', 'webp', 'static/images/posts/glaaBb_feed.webp', "
             "'static/images/posts/glaaBb_detail.jpeg', '', 520, 693, 0, 0, 0, 0.0)", ()),
        ])
    elif task_n == 21:
        mutate_db(db, [
            ("INSERT INTO posts (id, author_id, title, seo_title, description, view_count, "
             "upvote_count, downvote_count, point_count, image_count, comment_count, "
             "favorite_count, virality, score, is_album, in_most_viral, in_top_week, "
             "in_user_sub, platform, created_at) VALUES ('" + FIXTURE_MEME_ID + "', 990000001, "
             "'My mirror meme', 'my-mirror-meme', 'Annoyed Picard\nWHY DID I\nOPEN THE MEME GENERATOR', 0, 0, 0, 0, 1, 0, 0, 0.0, 0.0, 0, 0, 0, "
             "1, 'web', '2026-09-22 22:00:00.000000')", ()),
            ("INSERT INTO media (id, post_id, position, mime_type, type, ext, feed_path, "
             "detail_path, poster_path, width, height, size, is_animated, has_sound, duration) "
             "VALUES ('" + FIXTURE_MEME_ID + "', '" + FIXTURE_MEME_ID + "', 0, 'image/jpeg', "
             "'image', 'jpg', 'instance/uploads/meme_fixture12.jpg', "
             "'instance/uploads/meme_fixture12.jpg', '', 500, 500, 0, 0, 0, 0.0)", ()),
        ])
    elif task_n == 27:
        mutate_db(db, [("INSERT INTO follow_tag (user_id, tag_name) VALUES (990000003, 'anime')", ())])
    return db


def mismatch_after_db(tmp_path: Path, task_n: int) -> Path:
    """State-mismatch after-state: the DB never changed although the answer claims success."""
    return _seed_copy(tmp_path, f"mismatch{task_n}")


def adversarial_after_db(tmp_path: Path, task_n: int) -> Path:
    """A wrong / collateral state delta that must FAIL."""
    db = _seed_copy(tmp_path, f"adv{task_n}")
    if task_n == 6:      # removed the WRONG favorite
        mutate_db(db, [("DELETE FROM favorites WHERE user_id = 990000001 AND post_id = 'C8JgWDF'", ())])
    elif task_n == 7:    # favorited a different post than the task names
        mutate_db(db, [("INSERT INTO favorites (user_id, post_id, created_at) VALUES "
                        "(990000002, '4SmuGpb', '2026-09-22 22:00:00.000000')", ())])
    elif task_n == 8:    # comment added by the wrong author
        mutate_db(db, [
            ("INSERT INTO comments (id, post_id, parent_id, author_id, text, upvote_count, "
             "downvote_count, point_count, platform, created_at, image_path) VALUES "
             "(3000000098, 'Lpeg54z', NULL, 990000001, 'Mirror test comment 2026', 0, 0, 0, "
             "'web', '2026-09-22 22:00:00.000000', '')", ()),
            ("UPDATE posts SET comment_count = 41 WHERE id = 'Lpeg54z'", ()),
        ])
    elif task_n == 9:    # vote removed entirely
        mutate_db(db, [("DELETE FROM votes WHERE user_id = 990000004 AND post_id = 'w29p1QE'", ())])
    elif task_n == 10:   # upvoted a comment that is NOT LitterBoxKing's
        mutate_db(db, [("INSERT INTO comment_votes (id, user_id, comment_id, value) VALUES "
                        "(9902, 990000001, 2513047559, 1)", ())])
    elif task_n == 18:   # bio changed to the wrong text + a non-identity collateral edit
        mutate_db(db, [("UPDATE users SET bio = 'Wrong bio text.', reputation = reputation + 1 "
                        "WHERE id = 990000002", ())])
    elif task_n == 19:   # followed the wrong member
        mutate_db(db, [("INSERT INTO follow_user (follower_id, followee_id) VALUES "
                        "(990000004, 135752727)", ())])
    elif task_n == 20:   # post created with the wrong title (user row still fine)
        mutate_db(db, [
            ("INSERT INTO users (id, username, email, password_hash, avatar, bio, reputation, "
             "reputation_name, created_at, is_benchmark) VALUES (990000100, 'mirrorfan2026', "
             "'mirrorfan2026@test.com', 'x', 'static/images/avatars/default_alien.png', '', 0, "
             "'Neutral', '2026-09-22 22:00:00.000000', 0)", ()),
            ("INSERT INTO posts (id, author_id, title, seo_title, description, view_count, "
             "upvote_count, downvote_count, point_count, image_count, comment_count, "
             "favorite_count, virality, score, is_album, in_most_viral, in_top_week, "
             "in_user_sub, platform, created_at) VALUES ('" + FIXTURE_POST_ID + "', 990000100, "
             "'Wrong post title', 'wrong-post-title', '', 0, 0, 0, 0, 1, 0, 0, 0.0, 0.0, 0, 0, 0, "
             "1, 'web', '2026-09-22 22:00:00.000000')", ()),
            ("INSERT INTO media (id, post_id, position, mime_type, type, ext, feed_path, "
             "detail_path, poster_path, width, height, size, is_animated, has_sound, duration) "
             "VALUES ('" + FIXTURE_POST_ID + "', '" + FIXTURE_POST_ID + "', 0, 'image/webp', "
             "'image', 'webp', 'static/images/posts/glaaBb_feed.webp', "
             "'static/images/posts/glaaBb_detail.jpeg', '', 520, 693, 0, 0, 0, 0.0)", ()),
        ])
    elif task_n == 21:   # meme post authored by the wrong member
        mutate_db(db, [
            ("INSERT INTO posts (id, author_id, title, seo_title, description, view_count, "
             "upvote_count, downvote_count, point_count, image_count, comment_count, "
             "favorite_count, virality, score, is_album, in_most_viral, in_top_week, "
             "in_user_sub, platform, created_at) VALUES ('" + FIXTURE_MEME_ID + "', 990000002, "
             "'My mirror meme', 'my-mirror-meme', 'Annoyed Picard\nWHY DID I\nOPEN THE MEME GENERATOR', 0, 0, 0, 0, 1, 0, 0, 0.0, 0.0, 0, 0, 0, "
             "1, 'web', '2026-09-22 22:00:00.000000')", ()),
            ("INSERT INTO media (id, post_id, position, mime_type, type, ext, feed_path, "
             "detail_path, poster_path, width, height, size, is_animated, has_sound, duration) "
             "VALUES ('" + FIXTURE_MEME_ID + "', '" + FIXTURE_MEME_ID + "', 0, 'image/jpeg', "
             "'image', 'jpg', 'instance/uploads/meme_fixture12.jpg', "
             "'instance/uploads/meme_fixture12.jpg', '', 500, 500, 0, 0, 0, 0.0)", ()),
        ])
    elif task_n == 27:   # followed the wrong tag
        mutate_db(db, [("INSERT INTO follow_tag (user_id, tag_name) VALUES (990000003, 'funny')", ())])
    return db


def tamper_after_db(tmp_path: Path) -> Path:
    """A read-only task's after-DB with one illicit favorites row."""
    db = _seed_copy(tmp_path, "tamper")
    mutate_db(db, [("INSERT INTO favorites (user_id, post_id, created_at) VALUES "
                    "(990000001, '4SmuGpb', '2026-09-22 22:00:00.000000')", ())])
    return db


# ---------------------------------------------------------------- helpers
def _honest_fixture(tmp_path: Path, task_n: int, answer: str | None = None,
                    login: tuple[str, str] | None = None,
                    steps=None) -> tuple[Path, Path, Path]:
    initial = copy_db(tmp_path / "initial.db")
    login_key, nav, honest_answer = HONEST[task_n]
    who = login if login is not None else (LOGIN[login_key] if login_key else None)
    run = build_run(tmp_path / "run", f"Imgur--{task_n}", steps or nav,
                    answer if answer is not None else honest_answer, login=who)
    after = (honest_after_db(tmp_path, task_n) if task_n in STATEFUL
             else copy_db(tmp_path / "after.db"))
    return run, initial, after


# ---------------------------------------------------------------- honest PASS x30
@pytest.mark.parametrize("task_n", LEGACY)
def test_honest_pass(tmp_path, task_n):
    run, initial, after = _honest_fixture(tmp_path, task_n)
    verdict = run_verifier(task_n, run, initial, after)
    assert verdict["pass"] is True, json.dumps(verdict, indent=1)


def test_honest_task10_nested_litterboxking_comment_passes(tmp_path):
    """Final-state grading: upvoting a NESTED LitterBoxKing reply passes against that
    comment's own frozen facts (3 -> 4 points, its own text)."""
    run = build_run(tmp_path / "run", "Imgur--10",
                    HONEST[10][1], login=LOGIN["alice"],
                    answer="After my upvote, the comment by LitterBoxKing shows 4 points. Its "
                           "full text is: 'I've also received them 10 months after applying.'")
    initial = copy_db(tmp_path / "initial.db")
    after = _seed_copy(tmp_path, "t10nested")
    mutate_db(after, [("INSERT INTO comment_votes (id, user_id, comment_id, value) VALUES "
                       "(9903, 990000001, 2513056851, 1)", ())])
    verdict = run_verifier(10, run, initial, after)
    assert verdict["pass"] is True, json.dumps(verdict, indent=1)


# ---------------------------------------------------------------- no-op FAIL x30
@pytest.mark.parametrize("task_n", LEGACY)
def test_noop_fails(tmp_path, task_n):
    run = noop_run(tmp_path / "run", f"Imgur--{task_n}")
    initial = copy_db(tmp_path / "initial.db")
    after = copy_db(tmp_path / "after.db")
    verdict = run_verifier(task_n, run, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "final_answer_nonempty"


# ---------------------------------------------------------------- wrong answer FAIL x30
@pytest.mark.parametrize("task_n", LEGACY)
def test_wrong_answer_fails(tmp_path, task_n):
    run, initial, after = _honest_fixture(tmp_path, task_n, answer=WRONG[task_n])
    verdict = run_verifier(task_n, run, initial, after)
    assert verdict["pass"] is False, json.dumps(verdict, indent=1)
    assert verdict.get("infra_error") is not True  # it must fail on the ANSWER, not the harness


# ---------------------------------------------------------------- shortcut FAIL x28
# Tasks 24 and 28 are homepage-surface tasks BY DESIGN (their required surface is the
# homepage feed itself), so a homepage-only trajectory with the correct answer passes;
# every other task requires a deeper surface and must reject the shortcut.
SHORTCUT_EXPECTED_PASS = {24, 28}


@pytest.mark.parametrize("task_n", sorted(set(LEGACY) - SHORTCUT_EXPECTED_PASS))
def test_shortcut_fails(tmp_path, task_n):
    run = build_run(tmp_path / "run", f"Imgur--{task_n}",
                    [("/", "click", {}), ("/", "scroll", {"down": True})],
                    HONEST[task_n][2])
    initial = copy_db(tmp_path / "initial.db")
    after = copy_db(tmp_path / "after.db")
    verdict = run_verifier(task_n, run, initial, after)
    assert verdict["pass"] is False
    assert verdict.get("infra_error") is not True


# ---------------------------------------------------------------- read-only DB tamper FAIL x20
@pytest.mark.parametrize("task_n", READ_ONLY)
def test_readonly_tamper_fails(tmp_path, task_n):
    run, initial, _ = _honest_fixture(tmp_path, task_n)
    after = tamper_after_db(tmp_path)
    verdict = run_verifier(task_n, run, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "read_only_db_unchanged"


# ---------------------------------------------------------------- stateful negatives x20
@pytest.mark.parametrize("task_n", sorted(STATEFUL & set(LEGACY)))
def test_state_mismatch_fails(tmp_path, task_n):
    """The answer claims success but the DB never changed."""
    run, initial, _ = _honest_fixture(tmp_path, task_n)
    after = mismatch_after_db(tmp_path, task_n)
    verdict = run_verifier(task_n, run, initial, after)
    assert verdict["pass"] is False
    assert verdict.get("infra_error") is not True


@pytest.mark.parametrize("task_n", sorted(STATEFUL & set(LEGACY)))
def test_adversarial_state_delta_fails(tmp_path, task_n):
    """A wrong or collateral state delta must not pass with the honest answer."""
    run, initial, _ = _honest_fixture(tmp_path, task_n)
    after = adversarial_after_db(tmp_path, task_n)
    verdict = run_verifier(task_n, run, initial, after)
    assert verdict["pass"] is False
    assert verdict.get("infra_error") is not True


# ---------------------------------------------------------------- package tampering x7
def test_wrong_task_id_fails(tmp_path):
    run, initial, after = _honest_fixture(tmp_path, 7)
    traj = json.loads((run / "trajectory.json").read_text())
    traj["task_id"] = "Imgur--29"
    (run / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(7, run, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "trajectory_task_matches"


def test_offsite_url_fails(tmp_path):
    run, initial, after = _honest_fixture(tmp_path, 7)
    traj = json.loads((run / "trajectory.json").read_text())
    traj["steps"][0]["url"] = "https://evil.example.com/gallery/real-mvp-4SmuGpb"
    (run / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(7, run, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "all_urls_match_local_origin"


def test_broken_png_fails(tmp_path):
    run, initial, after = _honest_fixture(tmp_path, 7)
    (run / "screenshots" / "step_001.png").write_bytes(b"\x89PNG\r\n\x1a\nGARBAGE")
    verdict = run_verifier(7, run, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "screenshots_decode"


def test_missing_screenshot_fails(tmp_path):
    run, initial, after = _honest_fixture(tmp_path, 7)
    (run / "screenshots" / "step_001.png").unlink()
    verdict = run_verifier(7, run, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "screenshots_decode"


def test_not_done_trajectory_fails(tmp_path):
    run, initial, after = _honest_fixture(tmp_path, 7)
    traj = json.loads((run / "trajectory.json").read_text())
    traj["terminated"] = False
    traj["termination_reason"] = "max_steps"
    (run / "trajectory.json").write_text(json.dumps(traj))
    verdict = run_verifier(7, run, initial, after)
    assert verdict["pass"] is False
    assert verdict["reason"] == "trajectory_completed"


def test_tampered_seed_fails_closed(tmp_path):
    """A mutated initial snapshot must fail closed before any task check runs."""
    run, initial, after = _honest_fixture(tmp_path, 7)
    mutate_db(initial, [("UPDATE tags SET total_items = total_items + 1 WHERE name = 'funny'", ())])
    verdict = run_verifier(7, run, initial, after)
    assert verdict["pass"] is False
    assert verdict.get("infra_error") is True
    assert verdict["reason"] == "snapshot_contract_invalid"


def test_missing_db_fails_closed(tmp_path):
    run, _, _ = _honest_fixture(tmp_path, 7)
    verdict = run_verifier(7, run, tmp_path / "nonexistent.db", tmp_path / "nonexistent2.db")
    assert verdict["pass"] is False
    assert verdict.get("infra_error") is True
    assert verdict["reason"] == "database_unavailable"

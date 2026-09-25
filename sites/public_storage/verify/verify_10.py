#!/usr/bin/env python3
"""Verify Public Storage--10 (read-only) — r2 task text.

Read the blog article about organizing a storage unit like a pro: what
should you do before tossing items in, what goes on the bottom when
stacking, how many sides of every bin should you label, what should you keep
near the front, and what should you leave down the middle? Then find the
same-category article about keeping clothes in a storage unit: is there a
specific time limit, what should you do to clothes before storing them, and
what is one of the biggest long-term concerns? Also report the blog category
each article is filed under.

Frozen ground truth (seed DB): the article "Tips for Organizing a Storage
Unit Like a Pro" (blog/storage-tips) says to map it out (divide into zones)
before tossing items in, that heavy items go on the bottom, to label three
sides of every bin, to keep frequently used items near the front, and to
leave a small walkway down the middle. The same-category article "How Long
Can You Keep Clothes In a Storage Unit?" says there isn't a specific time
limit, to clean (wash or dry-clean) clothes before storing them, and that
moisture is one of the biggest long-term concerns. Both are filed under the
storage-tips category.
"""
from verify_lib import (check_read_only, check_seed_contract, check_trajectory_identity,
                        contains_any_phrase, contains_phrase, final_answer,
                        navigated_blog_article, navigated_blog_index, run_verifier)

TASK_ID = "Public Storage--10"
SLUG = "tips-for-organizing-a-storage-unit-like-a-pro"
CLOTHES_SLUG = "how-long-can-you-keep-clothes-in-a-storage-unit"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_blog_index", navigated_blog_index(traj),
                "required: blog index or category listing")
    judge.check("visited_pro_article", navigated_blog_article(traj, SLUG),
                "required: the organize-like-a-pro article page")
    judge.check("visited_clothes_article", navigated_blog_article(traj, CLOTHES_SLUG),
                "required: the clothes-in-storage article page")
    # organize-like-a-pro facts
    judge.check("answer_before_tossing",
                contains_any_phrase(answer, ["map it out", "map the space",
                                             "divide the space into zones",
                                             "mentally divide the space"]),
                "before tossing items in: map it out into zones")
    judge.check("answer_bottom_items",
                contains_any_phrase(answer, ["heavy items go on the bottom",
                                             "heaviest items on the bottom",
                                             "heavy items on the bottom"]),
                "heavy items go on the bottom when stacking")
    judge.check("answer_bin_sides",
                contains_phrase(answer, "three sides"),
                "label three sides of every bin")
    judge.check("answer_near_front",
                contains_any_phrase(answer, ["frequently used items",
                                             "frequently-used items",
                                             "items you use often"]),
                "keep frequently used items near the front")
    judge.check("answer_down_middle",
                contains_any_phrase(answer, ["walkway", "aisle"]),
                "leave a walkway down the middle")
    # clothes-in-storage facts
    judge.check("answer_time_limit",
                contains_any_phrase(answer, ["isn't a specific time limit",
                                             "is not a specific time limit",
                                             "no specific time limit",
                                             "no time limit"]),
                "there isn't a specific time limit")
    judge.check("answer_clean_before_storing",
                contains_any_phrase(answer, ["clean them", "wash or dry-clean",
                                             "wash or dry clean", "clean the clothes",
                                             "clean your clothes", "dry-clean"]),
                "clean (wash or dry-clean) clothes before storing them")
    judge.check("answer_biggest_concern", contains_phrase(answer, "moisture"),
                "moisture is one of the biggest long-term concerns")
    # category of each article
    judge.check("answer_category",
                contains_phrase(answer, "storage tips") or contains_phrase(answer, "storage-tips"),
                "blog category: storage-tips")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

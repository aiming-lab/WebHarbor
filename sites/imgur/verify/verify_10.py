#!/usr/bin/env python3
"""Verify the LitterBoxKing comment-upvote flow in Imgur--10.

The task says 'the comment written by LitterBoxKing' — the post carries four comments by
that member (one top-level, three nested replies). The deterministic contract: alice must
have upvoted exactly one LitterBoxKing comment on the Learning Channel post, and the
reported score and text must match THAT comment from the frozen table below
(final-state semantics; grading never depends on which of the four was chosen).
"""


from verify_lib import (Judge, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, check_visited_path, contains_count,
                        contains_phrase, final_answer, run_verifier, table_delta)

TASK_ID = "Imgur--10"
ALICE_EMAIL = "alice.j@test.com"
ALICE_USER_ID = 990000001
GALLERY_PATH = "/gallery/learning-channel-presents-bDO7HlN"
POST_ID = "bDO7HlN"
# Frozen ground truth (seed DB): every comment authored by LitterBoxKing on bDO7HlN.
LITTERBOXKING_COMMENTS = {
    2513046815: ("And assholes of any age who carelessly tell you to \"just get a different job\".", 46),
    2513049103: ("Just how young do you think GenX is?  Except for the tail end, most of GenX grew "
                 "up precisely as you described.", 17),
    2513056723: ("Nah, preferably a year.  6 months gets them past their probationary period, "
                 "but let's see whether they survive the annual rank-and-yank at many companies.", 2),
    2513056851: ("I've also received them 10 months after applying.", 3),
}


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, ALICE_EMAIL, "alice_j")
    check_visited_path(judge, traj, "visited_learning_channel_gallery", GALLERY_PATH)
    # DB after-state: only one comment_votes row appears — alice's upvote.
    check_only_tables_changed(judge, initial_db, after_db, {"comment_votes"})
    delta = table_delta(initial_db, after_db, "comment_votes")
    judge.check("exactly_one_comment_vote_added",
                delta["removed"] == [] and len(delta["added"]) == 1 and len(delta["changed"]) == 0,
                f"comment_votes delta={delta!r}")
    voted_comment_id = None
    if delta["added"]:
        from verify_lib import row_dict
        added = row_dict(initial_db, "comment_votes", delta["added"][0])
        judge.check("vote_is_alice_upvote",
                    str(added.get("user_id")) == str(ALICE_USER_ID) and int(added.get("value")) == 1,
                    f"added comment_vote row={added!r}")
        voted_comment_id = int(added.get("comment_id"))
        judge.check("voted_comment_is_litterboxking_on_learning_channel",
                    voted_comment_id in LITTERBOXKING_COMMENTS,
                    f"voted comment_id={voted_comment_id!r}, allowed={sorted(LITTERBOXKING_COMMENTS)}")
    if voted_comment_id in LITTERBOXKING_COMMENTS:
        text, base_points = LITTERBOXKING_COMMENTS[voted_comment_id]
        words = text.replace("-", " ").split()
        head = " ".join(words[:6])
        tail = " ".join(words[-3:])
        from verify_lib import _affirmative_search, _number_word, normalize_text
        import re
        value = str(base_points + 1)
        word = _number_word(base_points + 1)
        number = "(?:" + value + ("|" + re.escape(word) if word else "") + ")"
        pattern = r"\b" + number + r"\s*(?:points?|pts)\b|\bscore\s*(?:of|is|:)??\s*" + number + r"\b"
        judge.check("answer_comment_score_after_upvote", _affirmative_search(pattern, normalize_text(answer)),
                    f"expected {base_points + 1} points after the upvote")
        judge.check("answer_comment_text_head", contains_phrase(answer, head),
                    f"expected the comment text head {head!r}")
        judge.check("answer_comment_text_tail", contains_phrase(answer, tail),
                    f"expected the comment text tail {tail!r}")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

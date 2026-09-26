#!/usr/bin/env python3
"""Verify SoundCloud--0.

Compare the top of SoundCloud's two main charts. Take the #1, #2, and #3 tracks from the US 'All music genres' Top 50 and from the UK 'All music genres' Top 50 this week. Open all six track pages and report each track's title, artist, and exact play count. Then state which country's #1 has more plays, and report the like count shown on each #1's page.
"""
from verify_lib import (Judge, check_answer_number, check_answer_phrase, check_read_only,
                        check_trajectory_identity, check_visited_path, final_answer,
                        run_verifier)

TASK_ID = "SoundCloud--0"

# (title, artist, exact plays, track page path) — frozen from the seed chart order.
US_TOP3 = [
    ("Is Dat Right?", "Nardo Wick", 969416, "/nardo-wick/is-dat-right"),
    ("Backwards", "Quavo", 280716, "/quavoofficial/backwards"),
    ("Cowgirl", "Shaboozey", 1453008, "/shaboozey/cowgirl"),
]
UK_TOP3 = [
    ("Good Girl", "Cloonee", 1294858, "/cloonee/goodgirl"),
    ("Kolter - Hey Everybody (Radio Edit)", "Kolter", 938222, "/koltercologne/kolter-hey-everybody-back-in"),
    ("On 2nite", "SILVA BUMPA", 2399647, "/silvabumpa/on-2nite"),
]
# like counts as shown on the two #1 track pages (compact form)
US1_LIKES = "49.9K"
UK1_LIKES = "41.6K"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_visited_path(judge, traj, "visited_us_chart", r"/music-charts-us/sets/all-music-genres")
    check_visited_path(judge, traj, "visited_uk_chart", r"/music-charts-uk/sets/all-music-genres")
    for i, (title, artist, plays, path) in enumerate(US_TOP3):
        check_visited_path(judge, traj, f"visited_us{i+1}_track", path)
        check_answer_phrase(judge, answer, f"us{i+1}_title", title)
        check_answer_phrase(judge, answer, f"us{i+1}_artist", artist)
        check_answer_number(judge, answer, f"us{i+1}_plays", plays, f"US #{i+1} exact plays")
    for i, (title, artist, plays, path) in enumerate(UK_TOP3):
        check_visited_path(judge, traj, f"visited_uk{i+1}_track", path)
        check_answer_phrase(judge, answer, f"uk{i+1}_title", title)
        check_answer_phrase(judge, answer, f"uk{i+1}_artist", artist)
        check_answer_number(judge, answer, f"uk{i+1}_plays", plays, f"UK #{i+1} exact plays")
    # UK #1 (1,294,858) has more plays than US #1 (969,416)
    judge.check("which_number_one_has_more_plays",
                ("uk" in answer.casefold()
                 and UK_TOP3[0][2] > US_TOP3[0][2]
                 and "more plays" in answer.casefold()
                 and answer.casefold().rfind("uk") > -1),
                "answer must state that the UK #1 has more plays")
    judge.check("us1_like_count",
                US1_LIKES.lower() in answer.casefold() or "49,930" in answer,
                f"answer must report the like count shown on the US #1 page ({US1_LIKES})")
    judge.check("uk1_like_count",
                UK1_LIKES.lower() in answer.casefold() or "41,587" in answer,
                f"answer must report the like count shown on the UK #1 page ({UK1_LIKES})")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    raise SystemExit(run_verifier(TASK_ID, run_checks))

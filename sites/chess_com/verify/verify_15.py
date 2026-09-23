#!/usr/bin/env python3
"""Verify the French vs Caro-Kann Games Played comparison in Chess.com--15."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--15"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: BOTH opening pages the task compares.
    check_visited_path(judge, traj, "visited_french_opening", "/openings/French-Defense")
    check_visited_path(judge, traj, "visited_carokann_opening", "/openings/Caro-Kann-Defense")
    # Frozen ground truth: French Defense 262713 > Caro-Kann Defense 187337.
    judge.check("answer_french_games", contains_amount(answer, 262713), "expected 262,713 (French)")
    judge.check("answer_carokann_games", contains_amount(answer, 187337), "expected 187,337 (Caro-Kann)")
    # The comparison direction must be attached correctly (deterministic direction check):
    # an upward comparative (higher/more/...) must be attributed to the French Defense
    # in its own sentence, a downward one (lower/fewer/...) to the Caro-Kann Defense.
    # Attribution is sentence-local: within the sentence holding the comparative word,
    # the subject is the opening named closest BEFORE the comparative (or the first one
    # after it when the comparative leads the sentence). An honest answer that first
    # states both numbers and then concludes "so the French Defense has the higher
    # count" attributes "higher" to the French Defense in that sentence and PASSES;
    # any clause attributing the upward word to the Caro-Kann Defense (or the downward
    # word to the French Defense) is a reversed comparison and FAILS.
    import re
    from verify_lib import normalize_text
    normalized = normalize_text(answer)
    UP = r"higher|more|greater|larger|bigger"
    DOWN = r"lower|fewer|smaller|less"

    def attributed_opening(sentence, pos):
        """Which opening the comparative at `pos` refers to (sentence-local)."""
        before = sentence[:pos]
        nearest = None
        for m in re.finditer(r"\b(french|caro)\b", before):
            nearest = m.group(1)
        if nearest:
            return nearest
        after = re.search(r"\b(french|caro)\b", sentence[pos:])
        return after.group(1) if after else None

    def negated(sentence, pos):
        clause = sentence[max(0, pos - 40):pos]
        return bool(re.search(r"\b(not|no|never|isn't|wasn't|isnt|wasnt|doesn't|dont|doesn)\b", clause))

    direction_ok = False
    reversed_direction = False
    for sentence in re.split(r"[.!?;:\n]+", normalized):
        for m in re.finditer(rf"\b({UP})\b", sentence):
            if negated(sentence, m.start()):
                continue
            subject = attributed_opening(sentence, m.start())
            if subject == "french":
                direction_ok = True
            elif subject == "caro":
                reversed_direction = True
        for m in re.finditer(rf"\b({DOWN})\b", sentence):
            if negated(sentence, m.start()):
                continue
            subject = attributed_opening(sentence, m.start())
            if subject == "caro":
                direction_ok = True
            elif subject == "french":
                reversed_direction = True
    judge.check("answer_names_french_as_higher", direction_ok and not reversed_direction,
                "the comparative clause must identify the French Defense as the higher count "
                "(or the Caro-Kann Defense as the lower one)")
    check_read_only(judge, initial_db, after_db)



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)

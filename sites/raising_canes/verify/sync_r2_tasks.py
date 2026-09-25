#!/usr/bin/env python3
"""r2 re-sync of the raising_canes grading contract to the fixed tasks.

The contributor's fix commit 6a563727 re-anchored 5 task texts
(T9 Dallas-TX count, T11 5:00 PM slot, T12 named plush, T16 points
sub-questions, T17 La Marque reference/department). This script rebuilds
sites/raising_canes/tasks.jsonl so that every row's 5-key prefix is
byte-identical to the contribute branch's fixed tasks.jsonl, keeps the
verifier_path key unchanged, and installs the r2 judge_rubric for the 5
re-anchored rows (the other 15 rows keep their committed bytes).

No answer key is ever written. Run from the review worktree:

    python3 sites/raising_canes/verify/sync_r2_tasks.py \
        --contribute /path/to/wh-rc-r2-wt/sites/raising_canes/tasks.jsonl
"""
import json
import sys
from pathlib import Path

TASKS = Path(__file__).resolve().parents[1] / "tasks.jsonl"

R2_RUBRICS = {
    9: ("FACT CHECKPOINTS: The agent MUST search the Locations page for Dallas "
        "with the Catering Delivery service filter and report how many of the "
        "restaurants are in Dallas, TX, open the Ross Avenue restaurant page "
        "to read its phone number, then order a 75-Finger Tailgate with the "
        "family-style sauce option for pickup today 5:00 PM at that restaurant "
        "under the name given in the task, paying at the restaurant. The final "
        "answer MUST report the Dallas, TX count, the Ross Avenue phone number, "
        "the order number and the order total. An answer missing any of these, "
        "or an empty answer, is a FAIL."),
    11: ("FACT CHECKPOINTS: The agent MUST use the site search to find the "
         "Cane's Sauce menu item, report its calories per serving and its "
         "allergen letters from the nutritional information page, and order 25 "
         "servings of it for pickup today at 5:00 PM at the Government Street "
         "Baton Rouge restaurant under the name given in the task, paying at "
         "the restaurant. The final answer MUST report the calories per "
         "serving, the allergen letters, the order number and the order total. "
         "An answer missing any of these, or an empty answer, is a FAIL."),
    12: ("FACT CHECKPOINTS: The agent MUST sign in as Alice with the given demo "
         "credentials, add the Raising Cane's Retro Crewneck in size M and the "
         "Cool Cane Barking Plush Puppy to the gear cart, check whether the "
         "order qualifies for free shipping, and if not, add the cheapest "
         "accessory that crosses the free-shipping threshold, then check out "
         "to her home address with her saved Visa. The final answer MUST list "
         "every item in the order and the final total. An answer missing any "
         "item or the total, or an empty answer, is a FAIL."),
    16: ("FACT CHECKPOINTS: The agent MUST sign in as Alice with the given demo "
         "credentials, open her order history, work out which of her food "
         "orders is the most recent one, and cancel it. The final answer MUST "
         "report the cancelled order's number, the restaurant (city) it was "
         "for, its total, how many Caniac Club points the cancellation "
         "returned to her, and her Caniac Club points balance afterwards. An "
         "answer missing any of these, or an empty answer, is a FAIL."),
    17: ("FACT CHECKPOINTS: The agent MUST search the Careers page for "
         "Restaurant Manager jobs in Texas, list every city where one is "
         "currently open, open the La Marque opening and report its street "
         "address, its reference number and the department shown for it, and "
         "separately find the Cashier opening on Polaris Parkway in Columbus, "
         "Ohio, reporting its reference number and the shift noted in its job "
         "title. The final answer MUST include every Texas city, the La Marque "
         "street address, reference number and department, the Cashier "
         "reference number and the shift. An answer missing any of these, or "
         "an empty answer, is a FAIL."),
}

AFFECTED = sorted(R2_RUBRICS)


def main():
    contribute = Path(sys.argv[sys.argv.index("--contribute") + 1])
    contrib_lines = contribute.read_text(encoding="utf-8").splitlines()
    review_lines = TASKS.read_text(encoding="utf-8").splitlines()
    assert len(contrib_lines) == 20 and len(review_lines) == 20

    out = []
    changed = []
    for i, (cline, rline) in enumerate(zip(contrib_lines, review_lines)):
        cprefix = json.dumps(json.loads(cline), ensure_ascii=False)
        rrow = json.loads(rline)
        assert sorted(rrow.keys()) == ["id", "judge_rubric", "ques", "upstream_url",
                                       "verifier_path", "web", "web_name"], rrow.keys()
        # 5-key prefix of the current review row, re-serialized
        rprefix = json.dumps({k: rrow[k] for k in
                              ("web_name", "id", "ques", "web", "upstream_url")},
                             ensure_ascii=False)
        if i in R2_RUBRICS:
            if rprefix != cprefix:
                changed.append(i)
            new_row = json.loads(cline)
            new_row["verifier_path"] = rrow["verifier_path"]
            new_row["judge_rubric"] = R2_RUBRICS[i]
            out.append(json.dumps(new_row, ensure_ascii=False))
        else:
            # unaffected row: keep the committed review bytes untouched
            assert rprefix == cprefix, f"row {i} 5-key prefix drifted from contribute"
            out.append(rline)

    # global invariants: 7 keys, 5-key prefix byte-identical to contribute, no answer
    for i, (cline, oline) in enumerate(zip(contrib_lines, out)):
        cprefix = json.dumps(json.loads(cline), ensure_ascii=False)
        assert oline.startswith(cprefix[:-1] + ", "), f"row {i} prefix mismatch"
        orow = json.loads(oline)
        assert len(orow) == 7 and "answer" not in orow, f"row {i} keys"
        assert orow["verifier_path"] == f"sites/raising_canes/verify/verify_{i}.py"
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"r2 sync done; re-anchored rows: {changed}; "
          f"all 20 rows 7-key, 5-key prefix byte-identical to contribute, "
          f"no answer key")


if __name__ == "__main__":
    main()

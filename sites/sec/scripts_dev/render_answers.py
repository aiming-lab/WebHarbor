#!/usr/bin/env python3
"""Render the recorded round-1 answers as honest prose (what a competent
agent would write) and validate the contract claims against them.

Also emits verify/tests/answer_controls.json: for every task the recorded
prose as the positive control plus programmatic negatives (empty, wrong
values, negations) that must all FAIL.

Run: python3 scripts_dev/render_answers.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "verify"))
from contract_engine import check_claims  # noqa: E402

SITE = Path(__file__).resolve().parents[1]
RUNS = SITE / "runs" / "round1"
SPEC = json.loads((SITE / "verify" / "contract.json").read_text())


def recorded(task):
    return json.loads((RUNS / task / "trajectory.json").read_text())


def render(task, a=None):
    """Render a task's recorded fact dict as honest prose.

    The walker imports this same function so the prose stored in
    trajectory.json and the prose baked into answer_controls.json can never
    drift apart.
    """
    if a is None:
        a = recorded(task)["facts"]
    if task == "SEC.gov--0":
        return (f"Apple's most recent Form 10-K was filed {a['tenk_filed']} with period "
                f"of report {a['tenk_period']} and accession number {a['tenk_accession']}. "
                f"The most recent Form 10-Q was filed {a['tenq_filed']} with period of "
                f"report {a['tenq_period']} and accession number {a['tenq_accession']}. "
                f"The 10-K covers the longer period. Alice's watchlist now shows "
                f"{a['watchlist']} companies.")
    if task == "SEC.gov--1":
        return (f"The artificial intelligence query limited to Form 10-K matches "
                f"{a['total_10k']} documents; the top result is "
                f"{a['top_10k']['company']}, filed {a['top_10k']['date']}. The same "
                f"query limited to Form 8-K matches {a['total_8k']} documents. "
                f"Narrowed to filings from 2020-01-01 onward, the results table "
                f"lists {a['narrowed_count']} documents. Apple's EDGAR company page "
                f"lists {a['apple']['count']} 10-K filings; the newest was filed "
                f"{a['apple']['newest']}. Apple's CIK is {a['apple']['cik']}, and its "
                f"newest 10-K has period of report {a['apple']['period']}.")
    if task == "SEC.gov--2":
        return (f"Microsoft's CIK is {a['cik']}, SIC {a['sic']}, state of incorporation "
                f"{a['state']}, filer category {a['category']}. Its most recent DEF 14A was "
                f"filed {a['def14a_date']}, accession {a['def14a_accession']}. Microsoft has "
                f"{a['eightk_count']} 8-K filings in the snapshot. Bob's watchlist now "
                f"shows {a['watchlist']} companies.")
    if task == "SEC.gov--3":
        f8, s8 = a["first_8k"], a["second_8k"]
        return (f"Tesla's most recent Form 8-K was filed {f8['date']} with items "
                f"{f8['items']} and accession number {f8['accession']}; the next 8-K "
                f"on the list was filed {s8['date']} with items {s8['items']} and "
                f"accession number {s8['accession']}. They share item {a['shared']}. "
                f"The most recent 8-K's period of report is {f8['period']} and its "
                f"primary document page shows {f8['primary_doc']}. The next 8-K's "
                f"period of report is {s8['period']}. Tesla lists {a['form4']['count']} "
                f"Form 4 filings and {a['tenq_count']} 10-Q filings; the newest Form 4 "
                f"has period of report {a['form4']['period']}.")
    if task == "SEC.gov--4":
        return (f"Asudani's litigation release is No. {a['asudani']['no']} dated "
                f"{a['asudani']['date']}, filed in the {a['asudani']['court']} court; the "
                f"complaint says he traded ahead of the acquisition of {a['asudani']['acquired']}. "
                f"The case document label is {a['asudani']['document_label']} and it opened "
                f"({a['asudani']['document_href']}). The BitConnect promoters' release is No. "
                f"{a['bitconnect']['no']}; Michael Noble must pay {a['bitconnect']['noble_total']} "
                f"in total. The administrative proceeding against Trevon Brown is release "
                f"{a['brown_admin']['release']}, file number {a['brown_admin']['file_number']}.")
    if task == "SEC.gov--5":
        return (f"The settled orders page is dated {a['date']} and lists seven file numbers: "
                f"{a['file_numbers']}. Quillan Black's civil penalty is {a['black_penalty']} and "
                f"Tyler MacKechnie's is {a['mackechnie_penalty']}. Seven order PDFs are linked; "
                f"the first is {a['first_resource']}. My TCR reference number is {a['reference']}.")
    if task == "SEC.gov--6":
        flags = "; ".join(a["red_flags"][:2])
        return (f"Happy City Holdings Limited was suspended on {a['suspension_date']}, "
                f"release {a['release_no']}. The cold-caller alert lists red flags including: "
                f"{flags}. The pump-and-dump answer says {a['pump_answer']} My complaint "
                f"reference number is {a['reference']}.")
    if task == "SEC.gov--7":
        return (f"The Meyer Global press release is {a['meyer_pr']['no']} dated "
                f"{a['meyer_pr']['date']}; the funds held interests in SpaceX and other "
                f"pre-IPO securities, and the fund forfeited its nearly {a['meyer_pr']['forfeited']} "
                f"investment. The veterans press release is {a['veterans']['no']} dated "
                f"{a['veterans']['date']}; the two individuals orchestrated {a['veterans']['scheme']}. "
                f"Searching press releases for Meyer returns {a['meyer_search_count']} release. "
                f"The litigation release is No. {a['lr']['no']} for {a['lr']['respondents']}.")
    if task == "SEC.gov--8":
        return (f"Form 10-K is the {a['tenk']['description']}, SEC number "
                f"{a['tenk']['sec_number']}, last updated {a['tenk']['last_updated']}. Form 8-K "
                f"is SEC {a['eightk']['sec_number']} ({a['eightk']['last_updated']}); Form 1-A "
                f"is SEC {a['onea']['sec_number']} ({a['onea']['last_updated']}) under the "
                f"{a['onea']['statute']}. Public Companies filed-by filter: {a['public_count']} "
                f"forms; Securities Act of 1933 statute filter: {a['statute_count']} forms. "
                f"The Form 10-K PDF was served: {a['pdf_served']}.")
    if task == "SEC.gov--9":
        return (f"A Form 10-K is the annual report most reporting companies file; companies "
                f"must file it within {a['tenk']['window']} of the fiscal year end "
                f"(origin: {a['tenk']['origin']}). Brokers must legally seek "
                f"{a['bestex']['requirement']} (origin: {a['bestex']['origin']}). The SEC fee "
                f"under Section 31 is based on {a['sec31']['basis']} (origin: "
                f"{a['sec31']['origin']}). Ponzi organizers often promise {a['ponzi']['promise']} "
                f"(origin: {a['ponzi']['origin']}). The Proxy Statement answer was modified "
                f"{a['proxy']['modified']} (origin: {a['proxy']['origin']}).")
    if task == "SEC.gov--10":
        signs = ", ".join(a["ponzi"]["signs"]).rstrip(".")
        flags = ", ".join(a["cold"]["flags"][:2]).rstrip(".")
        return (f"The Ponzi schemes alert ({a['ponzi']['date']}) lists three warning "
                f"signs: {signs}. The fees bulletin says a {a['fees']['cost']} over a "
                f"30-year horizon, and names {a['fees']['one_type']} among fee types. "
                f"The cold-callers alert lists red flags including {flags}. The "
                f"municipal bond alert ({a['municipal']['date']}) describes risks "
                f"including {a['municipal']['risk']}. Searching the catalog for 'risks' "
                f"returns {a['risks_count']} items. Filtering to bulletins shows "
                f"{a['bulletin_count']} items; switching to alerts shows "
                f"{a['alert_count']} items.")
    if task == "SEC.gov--11":
        return (f"The Interval Fund Modernization proposed rule is dated {a['interval']['date']}, "
                f"file number {a['interval']['file_no']}, releases {a['interval']['releases']}; "
                f"looking it up by file number returns {a['file_lookup_count']} item. Proposed "
                f"Rules: {a['proposed_count']} items; Final Rules: {a['final_count']} items. The "
                f"Commission quorum requirement final rule is dated {a['quorum']['date']}, "
                f"release {a['quorum']['release']}. The electronic delivery proposed rule is "
                f"file number {a['edelivery']['file_no']} dated {a['edelivery']['date']}. "
                f"Clearing the filters shows {a['total']} items in total.")
    if task == "SEC.gov--12":
        return (f"The latest press release is \"{a['latest_pr']['title']}\" (Release "
                f"No. {a['latest_pr']['no']}). Opened, it is dated {a['latest']['date']} "
                f"and the charged funds invested in {a['latest']['preipo']}. Searching "
                f"speeches for 'Trump' returns {a['trump']['count']} result: the staff "
                f"statement on Trump Accounts by {a['trump']['speaker']}, dated "
                f"{a['trump']['date']}. What's New lists litigation releases for "
                f"{a['whatsnew']['first']} and {a['whatsnew']['second']}, both dated "
                f"{a['whatsnew']['date']}. Zoe Financial was charged for "
                f"{a['zoe']['charge']} (Release No. {a['zoe']['no']}, {a['zoe']['date']}). "
                f"The footer signup with news.fan@example.com was confirmed: now "
                f"subscribed to SEC email updates.")
    if task == "SEC.gov--13":
        return (f"My complaint reference number is {a['reference']}, and My Account shows "
                f"the complaint against Granite Harbor Capital LLC.")
    if task == "SEC.gov--14":
        return (f"My question reference number is {a['reference']}. One red flag from the "
                f"cold-caller alert: {a['red_flag']}. The footer signup with "
                f"updates.carol@example.com was confirmed: now subscribed.")
    if task == "SEC.gov--15":
        pairs = ", ".join(f"{c} ({t})" for c, t in zip(a["companies"], a["tickers"]))
        return (f"Dana's watchlist now shows {a['final_count']} companies: "
                f"{pairs}.")
    if task == "SEC.gov--16":
        return (f"Alphabet's CIK is {a['cik']} and its SIC is {a['sic']}. After signing out "
                f"and back in, the watchlist still lists Alphabet Inc. with ticker GOOGL "
                f"(persisted: {a['watchlist_company']} and {a['watchlist_ticker']}).")
    if task == "SEC.gov--17":
        g, m = a["gs"], a["ms"]
        return (f"Goldman Sachs: CIK {g['cik']}, state of incorporation {g['state']}, "
                f"SIC {g['sic']}, filer category {g['category']}. It lists "
                f"{g['tenk_count']} 10-K filings; the newest 10-K has period of report "
                f"{g['tenk_period']}. It lists {g['tenq_count']} 10-Q filings, the newest "
                f"filed {g['tenq_newest']}. Microsoft: CIK {m['cik']}, state of "
                f"incorporation {m['state']}, SIC {m['sic']}, filer category "
                f"{m['category']}. It lists {m['tenk_count']} 10-K filings; the newest "
                f"10-K has period of report {m['tenk_period']}. It lists "
                f"{m['tenq_count']} 10-Q filings, the newest filed {m['tenq_newest']}. "
                f"{a['more']} has more 10-K filings in the snapshot.")
    if task == "SEC.gov--18":
        flags = "; ".join(a["red_flags"][:2])
        return (f"Two red flags from the crypto-assets alert: {flags}. The Ponzi FAST Answer "
                f"says organizers often promise {a['promise']}. The digital assets query in "
                f"Form 8-K matched {a['total']} documents; the top result was {a['top_company']}. "
                f"My TCR reference number is {a['reference']}.")
    if task == "SEC.gov--19":
        return (f"The 2026 litigation release filter shows {a['year_count']} releases. The "
                f"Bernardi and Chandra release is No. {a['bernardi']['no']} dated "
                f"{a['bernardi']['date']}; the former executives were charged at "
                f"{a['bernardi']['company']}. The OTC Link administrative proceeding is titled "
                f"\"{a['otc_title']}\". What's New lists the litigation release numbered "
                f"{a['whatsnew_first']['no']} under {a['whatsnew_first']['division']}.")
    raise SystemExit(f"no renderer for {task}")


def negatives(task, prose):
    """Programmatic wrong answers that must FAIL the claims."""
    out = []
    out.append({"task": task, "name": "empty", "answer": "", "expected": False})
    out.append({"task": task, "name": "irrelevant",
                "answer": "I could not find any of that information on the site.",
                "expected": False})
    # digit-mangled: every number off by one class of error. For tasks whose
    # answer is a runtime-generated reference plus prose (the reference is
    # random per run), digit-mangling is not detectably wrong, so those get a
    # targeted negative instead.
    if task in ("SEC.gov--13", "SEC.gov--14"):
        if task == "SEC.gov--13":
            out.append({"task": task, "name": "no-account-confirmation",
                        "answer": "My complaint reference number is IC-1A2B3C4D.",
                        "expected": False})
        else:
            out.append({"task": task, "name": "no-red-flag",
                        "answer": "My question reference number is Q-1A2B3C4D. "
                                  "I signed up for the email updates and it said "
                                  "now subscribed.",
                        "expected": False})
    else:
        wrong = re.sub(r"\d", lambda m: "9" if m.group() != "9" else "8", prose)
        out.append({"task": task, "name": "wrong-numbers", "answer": wrong,
                    "expected": False})
    # negated: prepend/append explicit rejection
    out.append({"task": task, "name": "reject-all",
                "answer": "The following is false: " + prose, "expected": False})
    return out


def main():
    controls = []
    failures = 0
    for i in range(20):
        task = f"SEC.gov--{i}"
        traj = recorded(task)
        prose = traj["final_answer"]
        rendered = render(task, traj["facts"])
        if prose != rendered:
            print(f"FAIL {task} -> stored prose differs from rendered facts")
            failures += 1
        try:
            check_claims(prose, SPEC[task]["claims"])
            print("PASS", task)
        except ValueError as exc:
            failures += 1
            print("FAIL", task, "->", exc)
        controls.append({"task": task, "name": "recorded", "answer": prose,
                         "expected": True})
        controls.extend(negatives(task, prose))
    out = SITE / "verify" / "tests" / "answer_controls.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(controls, indent=1))
    print(f"\nanswer_controls.json: {len(controls)} cases, claim failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

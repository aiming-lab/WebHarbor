#!/usr/bin/env python3
"""append_rubrics.py — append verifier_path + judge_rubric to ../tasks.jsonl.

The five contributor keys stay byte-identical (each output row is the
original line with the two keys appended); no ``answer`` key is ever
written. The rubrics are pure English grading rules with no ground-truth
anchors (the answers live only in the frozen verifiers). Idempotent.

Run: python3 append_rubrics.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE.parent / "tasks.jsonl"

# ---------------------------------------------------------------------------
# Judge rubrics: pure rules, no answer values. Every rubric states the
# checkpoints the agent must open and the facts it must report exactly as
# the opened pages show them.
# ---------------------------------------------------------------------------
RUBRICS = {
"SEC.gov--0":
 "FACT CHECKPOINTS: Find Apple through EDGAR company search and open its "
 "company page. Report the most recent Form 10-K's filing date, period of "
 "report and accession number, and the most recent Form 10-Q's filing date, "
 "period of report and accession number, exactly as the filing pages show "
 "them, and which period of report is longer. Log in as alice.j@test.com / "
 "TestPass123!, add Apple to her watchlist from the company page, open My "
 "Account and report the watchlist count shown. PASS requires every date, "
 "period, accession number and count exactly as the pages show them. FAIL on "
 "any wrong value or an empty answer.",
"SEC.gov--1":
 "FACT CHECKPOINTS: On EDGAR full-text search, run the artificial "
 "intelligence query limited to Form 10-K and report the total documents and "
 "the top result's company and filing date exactly as shown. Run the same "
 "query limited to Form 8-K and report that total. Open Apple's EDGAR "
 "company page and report the 10-K count from the page's own count label, "
 "the filing date of the newest 10-K, and Apple's CIK. PASS requires both "
 "totals, the top hit's company and date, and Apple's three values exactly "
 "as the pages show them. FAIL on any wrong count or invented values.",
"SEC.gov--2":
 "FACT CHECKPOINTS: Find Microsoft through EDGAR company search and report "
 "its CIK, SIC code and description, state of incorporation and filer "
 "category exactly as its company page shows them. Open its most recent "
 "DEF 14A and report the filing date and accession number. Report the 8-K "
 "count from the company page's count label with the 8-K filter applied. "
 "Log in as bob.c@test.com / TestPass123!, add Microsoft to the watchlist "
 "from its company page and report the new watchlist total from My Account. "
 "PASS requires every field and count exactly as shown. FAIL on any wrong "
 "value.",
"SEC.gov--3":
 "FACT CHECKPOINTS: Find Tesla through EDGAR company search. Report the "
 "most recent Form 8-K's filing date, Item numbers and accession number, and "
 "the same three fields for the next 8-K on the list, plus which items the "
 "two share. Open the most recent 8-K's document page and report the primary "
 "document filename. Report Tesla's Form 4 count and 10-Q count from the "
 "page's count labels, and the filing date of its newest Form 4. PASS "
 "requires every value exactly as the opened pages show them. FAIL on any "
 "wrong item list or date.",
"SEC.gov--4":
 "FACT CHECKPOINTS: In litigation releases, open the release for Mukesh "
 "Asudani and report its release number, date, the court named in the case "
 "caption, and the acquisition the complaint says he traded ahead of, plus "
 "the label of the case document linked on the page. Open the release for "
 "Trevon Brown, Craig Grant and Michael Noble and report its number and "
 "Michael Noble's total payment exactly as the release text states it. Find "
 "the administrative proceeding row against Trevon Brown and report its "
 "release number and file number. PASS requires every value exactly as "
 "shown. FAIL on any wrong release number, amount or court.",
"SEC.gov--5":
 "FACT CHECKPOINTS: In administrative proceedings, open the settled-orders "
 "detail page for Quillan Black and the other unregistered brokers and "
 "report the date, the number of file numbers the page lists, and the civil "
 "penalty amounts for Quillan Black and for Tyler MacKechnie exactly as the "
 "text states them. Report how many order PDFs are linked under Resources "
 "and the label of the first. Log in as bob.c@test.com / TestPass123!, "
 "submit a TCR tip about an unregistered broker with a description of at "
 "least 30 characters, and report the TCR reference number from the "
 "confirmation page. PASS requires both penalties, the PDF count and label, "
 "and a well-formed reference number exactly as shown. FAIL on any wrong "
 "penalty or an invented reference.",
"SEC.gov--6":
 "FACT CHECKPOINTS: In trading suspensions, search for Happy City Holdings "
 "and report the suspension date and release number exactly as the row "
 "shows them. Open the investor alert about cold callers and report two of "
 "the red flags its text lists. Open the FAST Answer on pump-and-dump "
 "schemes and report what it says fraudsters do after pumping the price. "
 "File an investor complaint as Maria Lopez with the email "
 "maria.lopez@example.com, choosing a problem type, naming the firm, and "
 "describing the call, and report the complaint reference number from the "
 "confirmation page. PASS requires the suspension facts, two verbatim red "
 "flags, the pump-and-dump fact and a well-formed reference. FAIL on any "
 "wrong date or invented reference.",
"SEC.gov--7":
 "FACT CHECKPOINTS: Open the press release charging Meyer Global Management "
 "and its CEO and report the release number, date, what the funds' "
 "investments included, and the amount of the forfeited SpaceX investment "
 "exactly as the release states it. Search press releases for veterans, "
 "open the result and report its release number, date, and what the two "
 "individuals orchestrated. Search press releases for Meyer and report the "
 "result count the page shows. Open the litigation release for Owen E.H. "
 "Meyer and report its number and respondents. PASS requires every value "
 "exactly as the opened pages show them. FAIL on any wrong amount or "
 "number.",
"SEC.gov--8":
 "FACT CHECKPOINTS: In the forms index, search for Form 10-K and report its "
 "description, SEC number and last-updated date exactly as the row shows "
 "them. Do the same SEC number and last-updated lookup for Form 8-K and "
 "Form 1-A, and report the statute shown for Form 1-A. Apply the filed-by "
 "Public Companies filter and report the form count the page shows; apply "
 "the Securities Act of 1933 statute filter instead and report that count. "
 "Open the Form 10-K PDF link and report whether the mirror serves it. PASS "
 "requires every field and both counts exactly as shown. FAIL on any wrong "
 "SEC number or count.",
"SEC.gov--9":
 "FACT CHECKPOINTS: In FAST Answers, open the Form 10-K answer and report "
 "the filing window it describes and whether the page marks it captured or "
 "fixture. Open the Best Execution answer and report the legal requirement "
 "and its origin tag. Open the Section 31 fee answer and report what the "
 "fee is based on and its origin tag. Open the Ponzi-schemes answer and "
 "report what organizers often promise. Open the Proxy Statement answer and "
 "report its modified date. PASS requires every fact and origin tag exactly "
 "as the pages show them. FAIL on any wrong requirement or date.",
"SEC.gov--10":
 "FACT CHECKPOINTS: Open the Ponzi schemes investor alert and report its "
 "date and the three warning signs its text lists. Open the fees and "
 "expenses bulletin and report what a 1% annual fee difference can cost "
 "over 30 years and one fee type it names. Filter the catalog to bulletins "
 "and report the count; filter to alerts and report the count. Report the "
 "dates of the cold-callers alert and the crypto-assets alert. PASS "
 "requires every date, count and fact exactly as the pages show them. FAIL "
 "on any wrong count or warning sign.",
"SEC.gov--11":
 "FACT CHECKPOINTS: In rulemaking activity, search for the Interval Fund "
 "Modernization proposed rule and report its date, file number and release "
 "numbers exactly as the row shows them. Filter to Proposed Rules and "
 "report the count; switch to Final Rules and report the count and the date "
 "and release number of the Commission quorum requirement rule. Search for "
 "the electronic delivery proposed rule and report its file number and "
 "date. Clear the filters and search and report the total item count. PASS "
 "requires every field and count exactly as shown. FAIL on any wrong file "
 "number or count.",
"SEC.gov--12":
 "FACT CHECKPOINTS: From the newsroom, report the title and release number "
 "of the latest press release exactly as shown. Find the staff statement on "
 "Trump Accounts and report its speaker and date, and the total number of "
 "speeches and statements the page shows. In What's New, report the first "
 "two litigation releases listed with their dates. Search press releases "
 "for Zoe Financial, open the result and report what the SEC charged the "
 "firm with, the release number and its date. PASS requires every title, "
 "speaker, date and number exactly as the pages show them. FAIL on any "
 "wrong value.",
"SEC.gov--13":
 "FACT CHECKPOINTS: Log in as alice.j@test.com / TestPass123! and complete "
 "the investor complaint form about Granite Harbor Capital LLC with "
 "unauthorized trading as the problem type, the individual T. Brooks, "
 "ticker GRHN, an address, a phone number and a description. Report the "
 "complaint reference number from the confirmation page exactly as shown, "
 "then open My Account and report the firm name shown for the new "
 "complaint. PASS requires a well-formed reference number and the firm "
 "appearing in My Account. FAIL on an invented reference or a missing "
 "account entry.",
"SEC.gov--14":
 "FACT CHECKPOINTS: Log in as carol.d@test.com / TestPass123! and submit an "
 "investor question with the investment professional topic and a question "
 "of at least 20 characters; report the reference number from the "
 "confirmation page. Open the cold callers investor alert and report one "
 "red flag its text lists. Sign up from the footer for email updates with "
 "updates.carol@example.com and the investor alerts topic checked, and "
 "report the confirmation the page gives. PASS requires a well-formed "
 "reference number, one verbatim red flag and the signup confirmation. FAIL "
 "on invented values.",
"SEC.gov--15":
 "FACT CHECKPOINTS: Log in as dana.k@test.com / TestPass123!, open My "
 "Account and remove Meta Platforms from the watchlist. Find Tesla through "
 "EDGAR company search and add it to the watchlist from its company page; "
 "do the same for NVIDIA. Report the final watchlist count from My Account, "
 "the companies listed on it, and the ticker shown for each. PASS requires "
 "the exact final count, both company names and both tickers as the account "
 "page shows them. FAIL on any wrong count or company.",
"SEC.gov--16":
 "FACT CHECKPOINTS: Create a new account for Jordan Lee with the email "
 "jordan.lee@test.com and a password of at least 8 characters. Find Alphabet "
 "through EDGAR company search, add it to the watchlist from its company "
 "page, and report Alphabet's CIK and SIC description exactly as the page "
 "shows them. Sign out, sign back in with the same credentials, open My "
 "Account and report the watchlisted company and its ticker. PASS requires "
 "the CIK, the SIC description, and the watchlist surviving the sign-out "
 "and sign-in exactly as shown. FAIL on any wrong value.",
"SEC.gov--17":
 "FACT CHECKPOINTS: Find Goldman Sachs and Microsoft through EDGAR company "
 "search. Report each company's CIK, state and SIC description exactly as "
 "its company page shows them. With the 10-K filter applied, report each "
 "company's 10-K count and the filing date of its most recent 10-K. Report "
 "which company has more 10-K filings and the filer category each company "
 "shows. PASS requires every CIK, state, description, count, date and "
 "category exactly as the pages show them. FAIL on any wrong count or CIK.",
"SEC.gov--18":
 "FACT CHECKPOINTS: Open the crypto assets investor alert and report two "
 "red flags its text lists. Open the FAST Answer on Ponzi schemes and "
 "report what organizers often promise. On EDGAR full-text search, run the "
 "digital assets query limited to Form 8-K and report the total documents "
 "and the top result's company exactly as shown. Submit a TCR tip with the "
 "fraud violation type, a subject firm and a description of at least 30 "
 "characters, and report the TCR reference number from the confirmation "
 "page. PASS requires two verbatim red flags, the promise, the total, the "
 "company and a well-formed reference number. FAIL on any wrong total or "
 "invented reference.",
"SEC.gov--19":
 "FACT CHECKPOINTS: In litigation releases with the year 2026 filter "
 "applied, report how many releases the first page shows. Open the release "
 "for Robert Bernardi and Sunil Chandra and report its number, date, and "
 "the company whose former CEO and Vice President were charged exactly as "
 "the release text names it. Open the administrative proceeding detail page "
 "for OTC Link LLC and report its title. In What's New, report the first "
 "item listed and its division. PASS requires every value exactly as the "
 "opened pages show them. FAIL on any wrong count or title.",
}

VERIFIER = {f"SEC.gov--{n}": f"sites/sec/verify/verify_{n}.py" for n in range(20)}


def main():
    rows = [line for line in TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = []
    for line in rows:
        row = json.loads(line)
        tid = row["id"]
        if tid not in VERIFIER:
            raise SystemExit(f"unknown task id {tid}")
        if "verifier_path" in row:
            out.append(line)  # idempotent: already appended
            continue
        assert set(row) == {"web_name", "id", "ques", "web", "upstream_url"}, row.keys()
        extended = json.loads(line)
        extended["verifier_path"] = VERIFIER[tid]
        extended["judge_rubric"] = RUBRICS[tid]
        # byte-identical contributor keys + two appended keys
        pieces = line[:-1] + f', "verifier_path": {json.dumps(VERIFIER[tid])}' \
                       f', "judge_rubric": {json.dumps(RUBRICS[tid])}}}'
        assert json.loads(pieces) == extended
        out.append(pieces)
    TASKS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"append_rubrics: {len(out)} rows written (7-key contract)")


if __name__ == "__main__":
    main()

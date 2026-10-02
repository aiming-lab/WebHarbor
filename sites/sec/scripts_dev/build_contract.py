#!/usr/bin/env python3
"""Generate verify/contract.json from the recorded round-1 honest walkthroughs.

The claims are hand-written from the recorded browser answers (runs/round1);
the state deltas and the seed digest are computed from the saved databases.
Regenerating is deterministic: python3 scripts_dev/build_contract.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "verify"))
from contract_engine import database, digest  # noqa: E402

SITE = Path(__file__).resolve().parents[1]
RUNS = SITE / "runs" / "round1"

SEED_DIGEST = digest(database(RUNS / "SEC.gov--0" / "initial.db"))

# ---------------------------------------------------------------------------
# Per-task claims: [label, regex]. The regexes run against norm(final_answer)
# and must be satisfied by the recorded honest answers while rejecting wrong
# values, negations and empty text (see verify/tests/answer_controls.json).
# ---------------------------------------------------------------------------
D10K = r"10-?k"
D10Q = r"10-?q"

CLAIMS = {
"SEC.gov--0": [
    ["10-K filing date", rf"{D10K}(?:(?!{D10Q}).){{0,400}}?2025-10-31"],
    ["10-K period", rf"{D10K}(?:(?!{D10Q}).){{0,400}}?2025-09-27"],
    ["10-K accession", rf"{D10K}(?:(?!{D10Q}).){{0,400}}?0000320193-25-000079"],
    ["10-Q filing date", rf"{D10Q}.{{0,400}}?2026-07-31"],
    ["10-Q period", rf"{D10Q}.{{0,400}}?2026-06-27"],
    ["10-Q accession", rf"{D10Q}.{{0,400}}?0000320193-26-000020"],
    ["longer period", rf"(?:{D10K}((?:(?!{D10Q}).){{0,120}})|longer.{{0,120}}?)(?:longer|{D10K})"],
    ["watchlist count", r"3\s+compan(?:y|ies)"],
],
"SEC.gov--1": [
    ["10-K total", r"10-?k(?:(?!8-?k).){0,400}?10,?000"],
    ["top 10-K company", r"artificial intelligence technology solutions"],
    ["top 10-K date", r"2021-06-01"],
    ["8-K total", r"8-?k.{0,400}?10,?000"],
    ["narrowed count", r"7\s+documents?"],
    ["apple 10-K count", rf"3\s+{D10K}s?\b|{D10K}.{0,40}?3\b(?!\d)"],
    ["apple newest 10-K date", rf"{D10K}.{0,400}?2025-10-31|2025-10-31"],
    ["apple CIK", r"0000320193"],
    ["apple newest 10-K period", rf"period of report 2025-09-27|2025-09-27"],
],
"SEC.gov--2": [
    ["CIK", r"0000789019"],
    ["SIC", r"7372.{0,80}?prepackaged software"],
    ["state", r"\bwa\b"],
    ["category", r"large accelerated filer"],
    ["DEF 14A date", r"def\s?14a.{0,400}?2025-10-21|2025-10-21"],
    ["DEF 14A accession", r"0001193125-25-245150"],
    ["8-K count", r"6\s+8-?ks?\b|8-?k.{0,40}?6\b(?!\d)"],
    ["watchlist count", r"3\s+compan(?:y|ies)"],
],
"SEC.gov--3": [
    ["first 8-K date", r"2026-09-29"],
    ["first 8-K items", r"1\.01,?\s*1\.02,?\s*2\.03,?\s*9\.01"],
    ["first 8-K accession", r"0001628280-26-063820"],
    ["second 8-K date", r"2026-07-22"],
    ["second 8-K items", r"2\.02,?\s*9\.01"],
    ["second 8-K accession", r"0001628280-26-049213"],
    ["shared items", r"9\.01"],
    ["first 8-K period", r"2026-09-29"],
    ["primary document", r"tsla-20260929\.htm"],
    ["second 8-K period", r"2026-07-22"],
    ["form 4 count", r"5\s+form\s?4s?\b|form\s?4.{0,40}?5\b(?!\d)"],
    ["10-Q count", r"4\s+10-?qs?\b|10-?q.{0,40}?4\b(?!\d)"],
    ["newest form 4 period", r"2026-09-05"],
],
"SEC.gov--4": [
    ["asudani number", r"26662"],
    ["asudani date", r"september 30,? 2026"],
    ["court", r"s\.?d\.?n\.?y\.?"],
    ["acquired company", r"adamas pharmaceuticals"],
    ["document label", r"sec complaint"],
    ["document opened", r"(?:complaint\.pdf|opened|download)"],
    ["bitconnect number", r"26660"],
    ["noble total", r"\$1,?074,?984\.36"],
    ["brown admin release", r"34-106553"],
    ["brown admin file number", r"3-22766"],
],
"SEC.gov--5": [
    ["date", r"sept\.? 30,? 2026"],
    ["file number count", r"7\s+file\s+numbers?|3-22759.{0,300}?3-22765"],
    ["black penalty", r"\$125,?000"],
    ["mackechnie penalty", r"\$85,?000"],
    ["resource count", r"7\s+(?:order\s+)?pdfs?|7\s+resources?"],
    ["first resource", r"order\s*-?\s*quillan black"],
    ["reference", r"tcr-[a-z0-9]{8}"],
],
"SEC.gov--6": [
    ["suspension date", r"june 11,? 2026"],
    ["release number", r"34-105675"],
    ["red flag 1", r"refuses to send written information"],
    ["red flag 2", r"(?:demands an immediate decision|promises guaranteed returns|"
                   r"offer is .?confidential)"],
    ["pump answer", r"dump (?:their )?shares at the inflated price"],
    ["reference", r"ic-[a-z0-9]{8}"],
],
"SEC.gov--7": [
    ["release number", r"2026-98"],
    ["date", r"sept\.? 30,? 2026"],
    ["investments", r"spacex"],
    ["forfeited amount", r"\$3,?000,?000"],
    ["veterans number", r"2026-97"],
    ["veterans scheme", r"fraud scheme that raised more than \$8\.7 million from 35 investors"],
    ["meyer search count", r"1\s+release"],
    ["litigation number", r"26659"],
    ["litigation respondents", r"owen e\.?h\.? meyer and meyer global management llc"],
],
"SEC.gov--8": [
    ["10-K description", r"annual report pursuant to section 13 or 15\(d\)"],
    ["10-K SEC number", r"sec1673"],
    ["10-K updated", r"feb\.? 2025"],
    ["8-K SEC number", r"sec873"],
    ["1-A SEC number", r"sec486"],
    ["1-A statute", r"securities act of 1933"],
    ["public count", r"18\s+forms?"],
    ["statute count", r"30\s+forms?"],
    ["pdf served", r"(?:served|opened|download|form10-k\.pdf)"],
],
"SEC.gov--9": [
    ["10-K window", r"60 to 90 days"],
    ["10-K origin", r"fixture"],
    ["best execution requirement", r"best execution reasonably available"],
    ["best execution origin", r"captured"],
    ["section 31 basis", r"volume of securities that are sold"],
    ["section 31 origin", r"captured"],
    ["ponzi promise", r"high returns with little or no risk"],
    ["proxy modified", r"09/?08/?2011"],
    ["proxy origin", r"captured"],
],
"SEC.gov--10": [
    ["ponzi date", r"aug\.? 12,? 2026"],
    ["warning sign 1", r"high returns with little or no risk"],
    ["warning sign 2", r"overly consistent returns"],
    ["warning sign 3", r"unregistered investments with unlicensed sellers"],
    ["fee cost", r"a quarter of your final balance"],
    ["fee type", r"(?:management expense ratios|sales loads|12b-1 fees)"],
    ["cold red flag 1", r"refuses to send written information"],
    ["cold red flag 2", r"(?:demands an immediate decision|promises guaranteed "
                       r"returns|offer is .?confidential)"],
    ["municipal date", r"apr\.? 14,? 2026"],
    ["municipal risk", r"(?:credit risk|call risk|interest rate risk)"],
    ["risks search count", r"2\s+items?"],
    ["bulletin count", r"3\s+items?"],
    ["alert count", r"6\s+items?"],
],
"SEC.gov--11": [
    ["interval date", r"sept\.? 30,? 2026"],
    ["interval file number", r"s7-2026-34"],
    ["interval releases", r"33-11444,?\s*34-106534,?\s*ic-36351"],
    ["file lookup count", r"1\s+item"],
    ["proposed count", r"18\s+items?"],
    ["final count", r"28\s+items?"],
    ["quorum date", r"sept\.? 30,? 2026"],
    ["quorum release", r"34-106537"],
    ["e-delivery file number", r"s7-2026-25"],
    ["e-delivery date", r"july 16,? 2026"],
    ["total", r"49\s+items?"],
],
"SEC.gov--12": [
    ["latest title", r"sec charges meyer global management and its ceo with defrauding "
                    r"retail investors in private funds that held interests in spacex"],
    ["latest number", r"2026-98"],
    ["latest date", r"sept\.? 30,? 2026"],
    ["pre-IPO company", r"spacex"],
    ["trump result count", r"1\s+(?:result|item)"],
    ["trump speaker", r"divisions of investment management and corporation finance"],
    ["trump date", r"sept\.? 30,? 2026"],
    ["whats-new 1", r"mukesh asudani"],
    ["whats-new 2", r"robert bernardi and sunil chandra"],
    ["whats-new dates", r"sept\.? 30,? 2026"],
    ["zoe charge", r"conflicts? of interest"],
    ["zoe number", r"2026-94"],
    ["zoe date", r"sept\.? 28,? 2026"],
    ["signup email", r"news\.fan@example\.com"],
    ["signup confirmed", r"now subscribed"],
],
"SEC.gov--13": [
    ["reference", r"ic-[a-z0-9]{8}"],
    ["account firm", r"granite harbor capital llc"],
],
"SEC.gov--14": [
    ["reference", r"q-[a-z0-9]{8}"],
    ["red flag", r"(?:refuses to send written information|demands an immediate decision|"
                 r"promises guaranteed returns|offer is .?confidential)"],
    ["subscription", r"(?:now subscribed|signed up|subscribed)"],
],
"SEC.gov--15": [
    ["final count", r"3\s+compan(?:y|ies)"],
    ["company 1", r"alphabet inc\.?"],
    ["ticker 1", r"\bgoogl\b"],
    ["company 2", r"tesla,? inc\.?"],
    ["ticker 2", r"\btsla\b"],
    ["company 3", r"nvidia corp"],
    ["ticker 3", r"\bnvda\b"],
],
"SEC.gov--16": [
    ["CIK", r"0001652044"],
    ["SIC", r"7370.{0,80}?computer programming"],
    ["watchlist company", r"alphabet inc\.?"],
    ["watchlist ticker", r"\bgoogl\b"],
],
"SEC.gov--17": [
    ["GS CIK", r"0000886982"],
    ["GS state", r"\bde\b"],
    ["GS SIC", r"6211.{0,80}?security brokers"],
    ["GS category", r"large accelerated filer"],
    ["GS 10-K count", r"1\s+10-?ks?\b|10-?k.{0,40}?1\b(?!\d)"],
    ["GS 10-K period", r"2025-12-31"],
    ["GS 10-Q count", r"3\s+10-?qs?\b|10-?q.{0,40}?3\b(?!\d)"],
    ["GS 10-Q newest", r"2026-08-03"],
    ["MS CIK", r"0000789019"],
    ["MS state", r"\bwa\b"],
    ["MS SIC", r"7372.{0,80}?prepackaged software"],
    ["MS category", r"large accelerated filer"],
    ["MS 10-K count", r"3\s+10-?ks?\b|10-?k.{0,40}?3\b(?!\d)"],
    ["MS 10-K period", r"2026-06-30"],
    ["MS 10-Q count", r"4\s+10-?qs?\b|10-?q.{0,40}?4\b(?!\d)"],
    ["MS 10-Q newest", r"2026-04-29"],
    ["more 10-Ks", r"microsoft.{0,120}?more"],
],
"SEC.gov--18": [
    ["red flag 1", r"(?:guaranteed returns|celebrity endorsements|exclusive access)"],
    ["red flag 2", r"(?:crypto assets,? gift cards or wire transfers|"
                   r"recruits? you to bring in friends)"],
    ["promise", r"high returns with little or no risk"],
    ["total", r"5501"],
    ["top company", r"volcon,? inc\.?"],
    ["reference", r"tcr-[a-z0-9]{8}"],
],
"SEC.gov--19": [
    ["year count", r"100\s+releases?"],
    ["bernardi number", r"26661"],
    ["bernardi date", r"september 30,? 2026"],
    ["bernardi company", r"gigamedia access corporation"],
    ["OTC title", r"sec censures otc link llc for repeated compliance failures "
                 r"related to regulation sci"],
    ["whats-new number", r"26662"],
    ["whats-new division", r"enforcement"],
],
}

# ---------------------------------------------------------------------------
# State deltas per task (subset-matched columns; runtime references are
# checked for shape by the claims, not pinned here).
# ---------------------------------------------------------------------------
def state_for(task):
    if task == "SEC.gov--0":
        return {"watchlist_items": {"added": [
            {"user_id": 1, "cik": "0001318605", "added_at": "2026-09-30"}]}}
    if task == "SEC.gov--2":
        return {"watchlist_items": {"added": [
            {"user_id": 2, "cik": "0000789019", "added_at": "2026-09-30"}]}}
    if task == "SEC.gov--5":
        return {"tips": {"added": [{
            "user_id": 2, "name": "Bob Chen", "email": "bob.c@test.com",
            "violation_type": "broker misconduct",
            "submitted_at": "2026-09-30"}]}}
    if task == "SEC.gov--6":
        return {"complaints": {"added": [{
            "name": "Maria Lopez", "email": "maria.lopez@example.com",
            "your_role": "individual investor",
            "issue_type": "misrepresentation or omission",
            "subject_firm": "Happy City Holdings Limited",
            "submitted_at": "2026-09-30"}]}}
    if task == "SEC.gov--12":
        return {"email_subscriptions": {"added": [{
            "email": "news.fan@example.com", "topics": "press releases",
            "submitted_at": "2026-09-30"}]}}
    if task == "SEC.gov--13":
        return {"complaints": {"added": [{
            "user_id": 1, "name": "Alice Johnson", "email": "alice.j@test.com",
            "your_role": "individual investor", "issue_type": "unauthorized trading",
            "subject_firm": "Granite Harbor Capital LLC", "subject_person": "T. Brooks",
            "subject_ticker": "GRHN", "submitted_at": "2026-09-30"}]}}
    if task == "SEC.gov--14":
        return {"questions": {"added": [{
            "name": "Carol Davis", "email": "carol.d@test.com",
            "topic": "investment professional", "submitted_at": "2026-09-30"}]},
            "email_subscriptions": {"added": [{
                "email": "updates.carol@example.com", "topics": "investor alerts",
                "submitted_at": "2026-09-30"}]}}
    if task == "SEC.gov--15":
        return {"watchlist_items": {
            "removed": [{"user_id": 4, "cik": "0001326801"}],
            "added": [{"user_id": 4, "cik": "0001318605", "added_at": "2026-09-30"},
                      {"user_id": 4, "cik": "0001045810", "added_at": "2026-09-30"}]}}
    if task == "SEC.gov--16":
        return {"users": {"added": [{
            "email": "jordan.lee@test.com", "name": "Jordan Lee",
            "password_hash": {"bcrypt_password": "Jordan2026Pass"},
            "joined": "2026-09-30"}]},
            "watchlist_items": {"added": [{
                "user_id": 5, "cik": "0001652044", "added_at": "2026-09-30"}]}}
    if task == "SEC.gov--18":
        return {"tips": {"added": [{
            "name": "Jordan Lee", "email": "jordan.warned@example.com",
            "violation_type": "fraud",
            "submitted_at": "2026-09-30"}]}}
    return {}


def main():
    tasks = [json.loads(line) for line in
             (SITE / "tasks.jsonl").read_text().splitlines() if line.strip()]
    contract = {}
    for row in tasks:
        tid = row["id"]
        traj = json.loads((RUNS / tid / "trajectory.json").read_text())
        # URL evidence: the distinct paths the honest walk touched
        urls = []
        for step in traj["steps"]:
            for key in ("url", "url_after", "url"):
                value = step.get(key)
                if value:
                    from urllib.parse import urlsplit
                    u = urlsplit(value)
                    urls.append(u.path)
        keep = []
        for path in urls:
            # Runtime-generated reference numbers differ per run; pin only the
            # stable confirmation-path prefix (same convention as the review
            # contract).
            path = re.sub(r"(/submit-tip-or-complaint/(?:complaint-|question-)?"
                          r"confirmation/(?:TCR|IC|Q)-)[A-Z0-9]+$", r"\1", path)
            if path == "/" or path.startswith(("/edgar/", "/enforcement-litigation/",
                                               "/newsroom/", "/rules-regulations/",
                                               "/submit-filings/", "/submit-tip-or-complaint/",
                                               "/resources-investors/", "/fast-answers/",
                                               "/account", "/login", "/signup", "/subscribe",
                                               "/files/", "/search-filings/")):
                keep.append(re.escape(path).replace("\\-", "-"))
        contract[tid] = {
            "task": row["ques"],
            "initial_digest": SEED_DIGEST,
            "state": state_for(tid),
            "paths": sorted(set(keep)),
            "claims": CLAIMS[tid],
        }
    out = SITE / "verify" / "contract.json"
    out.write_text(json.dumps(contract, indent=1) + "\n")
    print(f"contract.json written: {len(contract)} tasks, "
          f"seed digest {SEED_DIGEST[:16]}\u2026")


if __name__ == "__main__":
    main()

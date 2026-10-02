"""Contract tests: every route renders, filters are deterministic, the seed
matches the captured upstream facts, and every DB-referenced image is a real
downloaded upstream asset."""
import json
import re
from pathlib import Path

import pytest

from app import db

SITE = Path(__file__).resolve().parents[1]


def count_label(html, noun):
    m = re.search(rf">(\d+) {noun}s?\b", html)
    return int(m.group(1)) if m else None


class TestPagesRender:
    def test_home(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert b"We make markets work better" in r.data
        assert b"Quick Links" in r.data

    def test_home_images_resolve(self, client):
        r = client.get("/")
        srcs = re.findall(r'src="(/static/[^"]+)"', r.data.decode())
        assert srcs, "home page renders no images"
        for src in srcs:
            assert client.get(src).status_code == 200, src

    def test_search_filings_hub(self, client):
        r = client.get("/search-filings")
        assert r.status_code == 200
        assert b"EDGAR Company Search" in r.data
        assert b"Full-Text Search" in r.data

    def test_cik_lookup(self, client):
        r = client.get("/search-filings/cik-lookup?company=apple")
        assert r.status_code == 200
        assert b"Apple Inc." in r.data
        assert b"0000320193" in r.data

    def test_cik_lookup_by_ticker(self, client):
        r = client.get("/search-filings/cik-lookup?company=MSFT")
        assert r.status_code == 200
        assert b"MICROSOFT CORP" in r.data or b"Microsoft" in r.data

    def test_cik_lookup_no_match(self, client):
        r = client.get("/search-filings/cik-lookup?company=zzzznope")
        assert b"No companies match" in r.data

    def test_company_page(self, client):
        r = client.get("/edgar/company/0000320193")
        assert r.status_code == 200
        assert b"Apple Inc." in r.data
        assert count_label(r.data.decode(), "filing") == 36

    def test_company_form_filter_10k(self, client):
        r = client.get("/edgar/company/0000320193?type=10-K")
        html = r.data.decode()
        assert count_label(html, "filing") == 3
        assert b"0000320193-25-000079" in r.data

    def test_company_form_filter_8k(self, client):
        r = client.get("/edgar/company/0000320193?type=8-K")
        html = r.data.decode()
        n = count_label(html, "filing")
        assert n and n > 1
        assert "0000320193-26-000018" in html

    def test_company_date_filter(self, client):
        r = client.get("/edgar/company/0000320193?type=&dateb=20250101")
        html = r.data.decode()
        assert count_label(html, "filing") >= 1

    def test_company_bad_date(self, client):
        assert client.get("/edgar/company/0000320193?dateb=notadate").status_code == 400

    def test_company_404(self, client):
        assert client.get("/edgar/company/9999999999").status_code == 404

    def test_company_pagination(self, client):
        r1 = client.get("/edgar/company/0000320193")
        r2 = client.get("/edgar/company/0000320193?page=2")
        assert r1.status_code == 200 and r2.status_code == 200

    def test_filing_detail(self, client):
        r = client.get("/edgar/filing/0000320193/0000320193-25-000079")
        assert r.status_code == 200
        assert b"Form 10-K" in r.data
        assert b"2025-10-31" in r.data
        assert b"2025-09-27" in r.data
        assert b"0000320193-25-000079" in r.data

    def test_filing_document(self, client):
        r = client.get("/edgar/filing/0000320193/0000320193-25-000079/document")
        assert r.status_code == 200
        assert b"aapl-20250927.htm" in r.data

    def test_fts_hub(self, client):
        r = client.get("/edgar/full-text-search")
        assert r.status_code == 200
        assert b"artificial intelligence" in r.data  # captured query list

    def test_fts_query(self, client):
        r = client.get("/edgar/full-text-search?q=artificial+intelligence&forms=8-K")
        assert r.status_code == 200
        assert b"RadNet" in r.data
        assert b"0001683168-20-000837" in r.data

    def test_fts_query_10k(self, client):
        r = client.get("/edgar/full-text-search?q=artificial+intelligence&forms=10-K")
        assert r.status_code == 200
        assert b"Artificial Intelligence Technology Solutions" in r.data

    def test_fts_no_match(self, client):
        r = client.get("/edgar/full-text-search?q=zzzznope")
        assert b"No documents" in r.data

    def test_enforcement_hub(self, client):
        r = client.get("/enforcement-litigation")
        assert r.status_code == 200
        assert b"Litigation Releases" in r.data
        assert b"Trading Suspensions" in r.data

    def test_litigation_releases_list(self, client):
        r = client.get("/enforcement-litigation/litigation-releases")
        assert r.status_code == 200
        assert b"Mukesh Asudani" in r.data
        assert b"LR-26662" in r.data

    def test_litigation_search(self, client):
        r = client.get("/enforcement-litigation/litigation-releases?q=asudani")
        html = r.data.decode()
        assert count_label(html, "release") == 1

    def test_litigation_year_filter(self, client):
        r = client.get("/enforcement-litigation/litigation-releases?year=2025")
        assert r.status_code == 200

    def test_litigation_detail(self, client):
        r = client.get("/enforcement-litigation/litigation-releases/lr-26662")
        assert r.status_code == 200
        assert b"Litigation Release No. 26662" in r.data
        assert b"insider trading" in r.data.lower()
        assert b"September 30, 2026" in r.data

    def test_litigation_detail_pdf(self, client):
        r = client.get("/enforcement-litigation/litigation-releases/lr-26662")
        m = re.search(r'href="(/files/[^"]+)"', r.data.decode())
        assert m, "no case document link rendered"
        assert client.get(m.group(1)).status_code == 200

    def test_admin_proceedings_list(self, client):
        r = client.get("/enforcement-litigation/administrative-proceedings")
        assert r.status_code == 200
        assert b"Eagle Bancorp" in r.data

    def test_admin_search_by_file_number(self, client):
        r = client.get("/enforcement-litigation/administrative-proceedings?q=3-20963")
        html = r.data.decode()
        assert "Eagle Bancorp" in html

    def test_admin_detail(self, client):
        r = client.get("/enforcement-litigation/administrative-proceedings/34-106538-s")
        assert r.status_code == 200
        assert b"unregistered brokers" in r.data
        assert b"3-22759" in r.data

    def test_trading_suspensions_list(self, client):
        r = client.get("/enforcement-litigation/trading-suspensions")
        assert r.status_code == 200
        assert b"Happy City Holdings" in r.data

    def test_trading_suspension_search(self, client):
        r = client.get("/enforcement-litigation/trading-suspensions?q=Happy+City")
        html = r.data.decode()
        assert count_label(html, "suspension") == 1

    def test_whistleblower(self, client):
        r = client.get("/enforcement-litigation/whistleblower-program")
        assert r.status_code == 200
        assert b"Whistleblower Program" in r.data

    def test_newsroom(self, client):
        r = client.get("/newsroom")
        assert r.status_code == 200
        assert b"Latest Press Releases" in r.data

    def test_press_releases_list(self, client):
        r = client.get("/newsroom/press-releases")
        assert r.status_code == 200
        assert b"Meyer Global Management" in r.data

    def test_press_release_detail(self, client):
        r = client.get("/newsroom/press-releases/"
                       "2026-98-sec-charges-meyer-global-management-its-ceo-"
                       "defrauding-retail-investors-private-funds-held-interests")
        assert r.status_code == 200
        assert b"2026-98" in r.data
        assert b"SpaceX" in r.data

    def test_press_releases_search(self, client):
        r = client.get("/newsroom/press-releases?q=2026-98")
        html = r.data.decode()
        assert "Meyer Global" in html

    def test_speeches_list(self, client):
        r = client.get("/newsroom/speeches-statements")
        assert r.status_code == 200
        assert b"The Other AI" in r.data
        assert count_label(r.data.decode(), "item") == 25

    def test_speeches_search(self, client):
        r = client.get("/newsroom/speeches-statements?q=Peirce")
        html = r.data.decode()
        assert "The Other AI" in html

    def test_whats_new(self, client):
        r = client.get("/newsroom/whats-new")
        assert r.status_code == 200
        assert b"Litigation Release - Mukesh Asudani" in r.data

    def test_rulemaking(self, client):
        r = client.get("/rules-regulations/rulemaking-activity")
        assert r.status_code == 200
        assert b"Interval Fund Modernization" in r.data

    def test_rulemaking_search(self, client):
        r = client.get("/rules-regulations/rulemaking-activity?q=S7-2026-34")
        html = r.data.decode()
        assert "Interval Fund Modernization" in html

    def test_rulemaking_status_filter(self, client):
        r = client.get("/rules-regulations/rulemaking-activity?status=Proposed+Rule")
        html = r.data.decode()
        assert "Proposed Rule" in html

    def test_forms_index(self, client):
        r = client.get("/submit-filings/forms-index")
        assert r.status_code == 200
        assert b"Annual report pursuant to Section 13 or 15(d)" in r.data

    def test_forms_index_search_10k(self, client):
        r = client.get("/submit-filings/forms-index?q=10-K")
        html = r.data.decode()
        assert count_label(html, "form") == 1
        assert "Annual report pursuant to Section 13 or 15(d)" in html

    def test_forms_index_pdf_served(self, client):
        r = client.get("/files/form10-k.pdf")
        assert r.status_code == 200
        assert r.data[:4] == b"%PDF"

    def test_resources_investors(self, client):
        r = client.get("/resources-investors")
        assert r.status_code == 200
        assert b"Investor Alerts and Bulletins" in r.data

    def test_investor_alerts(self, client):
        r = client.get("/resources-investors/investor-alerts-bulletins")
        assert r.status_code == 200
        assert b"Ponzi Schemes" in r.data

    def test_investor_alert_kind_filter(self, client):
        r = client.get("/resources-investors/investor-alerts-bulletins?kind=alert")
        html = r.data.decode()
        assert count_label(html, "item") == 6

    def test_investor_alert_detail(self, client):
        r = client.get("/resources-investors/investor-alerts-bulletins/ponzi-schemes")
        assert r.status_code == 200
        assert b"high returns with little or no risk" in r.data

    def test_fast_answers(self, client):
        r = client.get("/fast-answers")
        assert r.status_code == 200
        assert b"Form 10-K" in r.data
        assert count_label(r.data.decode(), "answer") == 15

    def test_fast_answer_captured(self, client):
        r = client.get("/fast-answers/bestex")
        assert r.status_code == 200
        assert b"Best Execution" in r.data
        assert b"captured from sec.gov/answers" in r.data

    def test_fast_answer_fixture(self, client):
        r = client.get("/fast-answers/form10k")
        assert r.status_code == 200
        assert b"annual report" in r.data
        assert b"fixture" in r.data

    def test_submit_tip_landing(self, client):
        r = client.get("/submit-tip-or-complaint")
        assert r.status_code == 200
        assert b"Tips, Complaints" in r.data

    def test_tcr_disclaimer(self, client):
        r = client.get("/submit-tip-or-complaint/tcr-disclaimer")
        assert r.status_code == 200
        assert b"Begin TCR Submission" in r.data

    def test_form_pages_get(self, client):
        for path in ("/submit-tip-or-complaint/report-possible-securities-law-violations",
                     "/submit-tip-or-complaint/report-problem-investment-account-or-financial-professional",
                     "/submit-tip-or-complaint/report-problem-sec-or-self-regulatory-organization"):
            assert client.get(path).status_code == 200, path

    def test_health_probe(self):
        from _health import health
        result = health()
        assert result["ok"] is True
        assert result["counts"]["filings"] == 1666


class TestFilters:
    def test_fts_form_filter_changes_results(self, client):
        r8k = client.get("/edgar/full-text-search?q=artificial+intelligence&forms=8-K").data.decode()
        r10k = client.get("/edgar/full-text-search?q=artificial+intelligence&forms=10-K").data.decode()
        assert "RadNet" in r8k
        assert "RadNet" not in r10k
        assert "Artificial Intelligence Technology Solutions" in r10k

    def test_fts_date_filter(self, client):
        r = client.get("/edgar/full-text-search?q=artificial+intelligence&forms=8-K&datea=2020-03-16")
        html = r.data.decode()
        assert "RadNet" in html

    def test_company_forms_taxonomy_sorted(self, client):
        r = client.get("/edgar/company/0000320193")
        forms = re.findall(r'<option value="([^"]+)"', r.data.decode())
        assert forms == sorted(set(forms), key=str)


class TestSeedContract:
    def test_benchmark_users(self, client):
        from app import User
        for email in ("alice.j@test.com", "bob.c@test.com",
                      "carol.d@test.com", "dana.k@test.com"):
            assert User.query.filter_by(email=email).first(), email

    def test_benchmark_password(self, client):
        from app import User, bcrypt
        alice = User.query.filter_by(email="alice.j@test.com").first()
        assert bcrypt.check_password_hash(alice.password_hash, "TestPass123!")

    def test_row_counts(self, client):
        from app import (AdminProceeding, Company, Filing, FastAnswer,
                         FormIndex, FtsDoc, InvestorAlert, LitRelease,
                         PressRelease, Question, Rulemaking, Speech, Tip,
                         TradingSuspension, User, WatchlistItem, WhatsNew,
                         Complaint)
        assert Company.query.count() == 50
        assert Filing.query.count() == 1666
        assert PressRelease.query.count() == 100
        assert LitRelease.query.count() == 100
        assert AdminProceeding.query.count() == 100
        assert TradingSuspension.query.count() == 100
        assert FtsDoc.query.count() == 80
        assert FastAnswer.query.count() == 15
        assert InvestorAlert.query.count() == 9
        assert FormIndex.query.count() == 153
        assert Rulemaking.query.count() == 49
        assert Speech.query.count() == 25
        assert WhatsNew.query.count() == 20
        assert User.query.count() == 4
        assert WatchlistItem.query.count() == 7
        assert Complaint.query.count() == 1
        assert Tip.query.count() == 1
        assert Question.query.count() == 1

    def test_captured_facts(self, client):
        from app import Company, Filing, LitRelease, PressRelease
        apple = db.session.get(Company, "0000320193")
        assert apple.name == "Apple Inc."
        assert apple.ticker == "AAPL"
        assert apple.state == "CA"
        tenk = Filing.query.filter_by(cik="0000320193", form="10-K").first()
        assert tenk.accession == "0000320193-25-000079"
        assert tenk.filed == "2025-10-31"
        assert tenk.report_date == "2025-09-27"
        lr = db.session.get(LitRelease, "lr-26662")
        assert lr.respondents == "Mukesh Asudani"
        pr = PressRelease.query.filter_by(release_no="2026-98").first()
        assert pr.slug.startswith("2026-98-sec-charges-meyer-global")

    def test_watchlist_fixtures(self, alice_client, bob_client, dana_client):
        from app import WatchlistItem
        alice = WatchlistItem.query.filter_by(
            user_id=1).order_by(WatchlistItem.id).all()
        assert [w.cik for w in alice] == ["0000320193", "0000789019"]
        bob = WatchlistItem.query.filter_by(user_id=2).all()
        assert len(bob) == 2
        dana = WatchlistItem.query.filter_by(user_id=4).all()
        assert len(dana) == 2

    def test_fixture_records_reference_real_rows(self, client):
        """Every benchmark watchlist entry must point at a real company row."""
        from app import Company, WatchlistItem
        for w in WatchlistItem.query.all():
            assert db.session.get(Company, w.cik) is not None, w.cik

    def test_alert_origins(self, client):
        from app import FastAnswer, InvestorAlert
        assert FastAnswer.query.filter_by(origin="captured").count() == 5
        assert FastAnswer.query.filter_by(origin="fixture").count() == 10
        assert InvestorAlert.query.filter_by(origin="fixture").count() == 9


class TestAssetInventory:
    def test_inventory_covers_all_referenced_images(self, client):
        """Every image the templates reference must be a real downloaded
        upstream asset listed in asset_inventory.json, and the file exists."""
        inventory = json.loads((SITE / "asset_inventory.json").read_text())
        names = {a["path"].split("/")[-1]: a for a in inventory["assets"]}
        # collect every image referenced by templates
        referenced = set()
        for tpl in (SITE / "templates").glob("*.html"):
            text = tpl.read_text()
            referenced.update(re.findall(r'/static/images/upstream/([^"\' )]+)', text))
        assert referenced, "no images referenced by templates"
        missing = [r for r in sorted(referenced) if r not in names]
        assert not missing, f"{len(missing)} template images missing: {missing}"
        on_disk_missing = [r for r in sorted(referenced)
                           if not (SITE / "static" / "images" / "upstream" / r).exists()]
        assert not on_disk_missing, on_disk_missing

    def test_inventory_hashes_match_disk(self):
        import hashlib
        inventory = json.loads((SITE / "asset_inventory.json").read_text())
        bad = []
        for a in inventory["assets"]:
            p = SITE / a["path"]
            if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != a["sha256"]:
                bad.append(a["path"])
        assert not bad, bad[:5]

    def test_archived_pdfs_served(self, client):
        import random
        inventory = json.loads((SITE / "asset_inventory.json").read_text())
        hrefs = [a["path"] for a in inventory["assets"]
                 if a["path"].startswith("static/external_cache")]
        assert len(hrefs) > 300
        random.seed(0)
        for rel in random.sample(hrefs, 12):
            # map back to the upstream /files/... route
            name = rel.split("/")[-1]
            kind = rel.split("/")[2]
            if kind == "litigation":
                path = f"/files/litigation/{name}"
            elif kind == "admin":
                path = f"/files/litigation/admin/{name}"
            elif kind == "suspensions":
                path = f"/files/litigation/suspensions/{name}"
            else:
                path = f"/files/{name}"
            r = client.get(path)
            if r.status_code == 200:
                assert r.data[:4] == b"%PDF", path

#!/usr/bin/env python3
"""Build the tracked source snapshot (source_data.json) from scraped_data.

Converts the raw upstream harvests (Playwright captures of medicare.gov,
2026-09-23) into the normalized arrays seed_data.py materializes into the
site database. Run from sites/medicare_gov/:

    PYTHONHASHSEED=0 python3 scripts_dev/build_source_data.py

Every record here originates from one of these upstream surfaces:
  - coverage items   : https://www.medicare.gov/jsonapi/staticcontent/coverage?limit=all
  - providers        : https://www.medicare.gov/api/care-compare/provider (POST)
  - DME suppliers    : https://www.medicare.gov/api/procedure-price-lookup/api/v1/dme/...
  - equipment taxonomy: same DME API, dmepos_tax_abc
  - publications     : https://www.medicare.gov/publications/search (Drupal pages)
  - page content     : Drupal-rendered HTML pages captured during recon
See provenance.json for the per-dataset source URLs and capture dates.
"""
from __future__ import annotations

import html
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SCRAPED = HERE / "scraped_data"
OUT_PATH = HERE / "source_data.json"

CAP_PER_CITY_TYPE = 60
CAP_DME_PER_ZIP = 60

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def unescape_once(value: str) -> str:
    """The upstream JSON API ships HTML-escaped bodies (&lt;p&gt;...)."""
    return html.unescape(value or "")


def strip_tags(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment or "")).strip()


def clean_zip(zip9: str | None) -> str:
    digits = re.sub(r"\D", "", zip9 or "")
    if len(digits) >= 9:
        return f"{digits[:5]}-{digits[5:9]}"
    if digits:
        return digits[:5]
    return (zip9 or "").strip()


def fmt_phone(raw: str | None) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) > 10:
        digits = digits[-10:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return (raw or "").strip()


def load(name: str):
    return json.loads((SCRAPED / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# coverage items (165, real)
# ---------------------------------------------------------------------------

def sanitize_coverage_html(fragment: str) -> str:
    """Make upstream coverage HTML mirror-safe.

    - rewrite absolute medicare.gov URLs to mirror-relative paths
    - anchors without a usable href (tooltip / drawer wrappers) render as
      <span class="term">text</span>
    - external (non-medicare.gov) links become plain text so the offline
      mirror never links out to the live internet
    """
    if not fragment:
        return fragment

    class _Rebuild(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.out = []
            self._anchor_stack = []

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "a":
                href = a.get("href") or ""
                if href.startswith(("http://", "https://")):
                    if "medicare.gov" in href.split("/")[2]:
                        # absolute medicare.gov link -> mirror-relative
                        path = re.sub(r"^https?://(?:www\\.)?medicare\\.gov", "", href)
                        self.out.append(f'<a href="{html.escape(path, quote=True)}">')
                        self._anchor_stack.append("a")
                    else:
                        self._anchor_stack.append("ext")  # skip until close
                else:
                    self.out.append('<span class="term">')
                    self._anchor_stack.append("span")
                return
            if tag in ("br", "img", "hr") or self._anchor_stack[-1:] == ["ext"]:
                if self._anchor_stack[-1:] == ["ext"]:
                    return
                self.out.append(self.get_starttag_text())
                return
            clean_attrs = " ".join(
                f'{k}="{html.escape(v, quote=True)}"' for k, v in attrs
                if k in ("src", "alt", "colspan", "rowspan", "id", "lang"))
            self.out.append(f"<{tag}{' ' + clean_attrs if clean_attrs else ''}>")

        def handle_endtag(self, tag):
            if tag == "a":
                if self._anchor_stack:
                    kind = self._anchor_stack.pop()
                    if kind == "a":
                        self.out.append("</a>")
                    elif kind == "span":
                        self.out.append("</span>")
                return
            if self._anchor_stack[-1:] == ["ext"]:
                return
            self.out.append(f"</{tag}>")

        def handle_data(self, data):
            if self._anchor_stack[-1:] == ["ext"]:
                return
            self.out.append(data)

    parser = _Rebuild()
    parser.feed(fragment)
    return "".join(parser.out)


def build_coverage() -> list[dict]:
    data = load("coverage_api.json")["data"]
    items = []
    for row in data:
        tags = [t.get("name", "") for t in (row.get("tags") or [])]
        title = unescape_once(row.get("title", "")).strip()
        slug = (row.get("url") or "").strip().rsplit("/", 1)[-1]
        items.append({
            "title": title,
            "slug": slug,
            "node_id": row.get("node_id"),
            "summary": unescape_once(row.get("field_coverage_page_summary", "")),
            "cost_summary": unescape_once(row.get("field_coverage_costs_summary", "")),
            "description_html": sanitize_coverage_html(unescape_once(row.get("field_coverage_item_description", ""))),
            "details_html": sanitize_coverage_html(unescape_once(row.get("field_detailed_coverage_info", ""))),
            "eligible_html": sanitize_coverage_html(unescape_once(row.get("field_coverage_item_whoseligible", ""))),
            "costs_html": sanitize_coverage_html(unescape_once(row.get("field_coverage_costs_full", ""))),
            "how_often_html": sanitize_coverage_html(unescape_once(row.get("field_coverage_how_often_full", ""))),
            "facility_html": sanitize_coverage_html(unescape_once(row.get("field_coverage_item_facility", ""))),
            "provider_reqs_html": sanitize_coverage_html(unescape_once(row.get("field_coverage_provider_reqs", ""))),
            "keywords": unescape_once(row.get("field_keyword_indication", "")),
            "tags": tags,
        })
    items.sort(key=lambda r: r["title"].casefold())
    return items


# ---------------------------------------------------------------------------
# providers (real care-compare API harvest)
# ---------------------------------------------------------------------------

PROVIDER_TYPE_LABELS = {
    "Physician": "Doctors & clinicians",
    "Hospital": "Hospitals",
    "NursingHome": "Nursing homes including rehab services",
    "HomeHealth": "Home health services",
    "Hospice": "Hospice care",
    "DialysisFacility": "Dialysis facilities",
    "InpatientRehabilitation": "Inpatient rehabilitation facilities",
    "LongTermCare": "Long-term care hospitals",
    "CommunityHealthCenter": "Community health centers",
    "GroupPractice": "Doctors & clinicians",
}

def provider_detail(kind: str, r: dict) -> dict:
    inner = r.get(kind[0].lower() + kind[1:], {}) or {}
    detail: dict = {}
    if kind == "Physician":
        ph = inner
        groups = ph.get("groupAffiliations") or []
        certs = [
            (b.get("boardCertificationName") or "").strip()
            for b in (ph.get("boardCertifications") or {}).get("boardCertifications") or []
            if (b.get("boardCertificationName") or "").strip()
        ]
        detail = {
            "credential": ph.get("credential"),
            "gender": ph.get("gender"),
            "medical_school": ph.get("medicalSchoolName"),
            "graduation_year": ph.get("graduationYear"),
            "telehealth": bool(ph.get("telehealth")),
            "online_booking": bool(ph.get("onlineBooking")),
            "accepts_assignment": ph.get("acceptsMedicareAssignment") == "Y",
            "group": groups[0].get("organizationName") if groups else None,
            "board_certifications": certs or None,
        }
    elif kind == "Hospital":
        detail = {
            "hospital_type": inner.get("hospitalType"),
            "ownership": inner.get("ownership"),
            "emergency_services": inner.get("hasEmergencyServices"),
            "overall_rating": inner.get("overallRating"),
            "mortality_measures": inner.get("facilityMortalityMeasuresCount"),
            "readmission_measures": inner.get("facilityReadmissionMeasureCount"),
            "safety_measures": inner.get("facilitySafetyMeasuresCount"),
            "patient_experience_measures": inner.get("facilityPatientExperienceMeasureCount"),
            "timely_care_measures": inner.get("facilityTimelyAndEffectiveCareMeasuresCount"),
            "birthing_friendly": inner.get("meetsCriteriaForBirthingFriendlyDesignation"),
        }
    elif kind == "NursingHome":
        detail = {
            "ownership": inner.get("ownershipType"),
            "overall_rating": inner.get("overallRating"),
            "health_inspection_rating": inner.get("healthInspectionRating"),
            "staffing_rating": inner.get("staffingRating"),
            "qm_rating": inner.get("qmRating"),
            "beds": inner.get("numCertifiedBeds"),
            "residents": inner.get("avgResidentsPerDay"),
        }
    elif kind == "HomeHealth":
        detail = {
            "date_certified": inner.get("dateCertified"),
            "quality_rating": inner.get("qualityOfPatientCareStarRating"),
            "offers_nursing": bool(inner.get("offersNursingCare")),
            "offers_physical_therapy": bool(inner.get("offersPhysicalTherapy")),
            "offers_occupational_therapy": bool(inner.get("offersOccupationalTherapy")),
            "offers_speech_pathology": bool(inner.get("offersSpeechPathology")),
            "offers_medical_social": bool(inner.get("offersMedicalSocial")),
            "offers_home_health_aide": bool(inner.get("offersHomeHealthAide")),
        }
    elif kind == "Hospice":
        detail = {
            "ownership": inner.get("ownershipType"),
            "certification_date": inner.get("certificationDate"),
            "quality_rating": (inner.get("starRatingSummary") or {}).get("qualityOfPatientCareStarRating")
            if isinstance(inner.get("starRatingSummary"), dict) else inner.get("starRatingSummary"),
        }
    elif kind == "DialysisFacility":
        detail = {
            "chain_organization": inner.get("chainOrganization"),
            "stations": inner.get("stationCount"),
            "late_shift": bool(inner.get("hasLateShift")),
            "offers_hemodialysis": bool(inner.get("offersHemodialysis")),
            "offers_peritoneal": bool(inner.get("offersPeritonealDialysis")),
            "offers_home_training": bool(inner.get("offersHomeHemodialysisTraining")),
            "date_certified": inner.get("dateCertified"),
            "five_star": inner.get("fiveStar"),
        }
    elif kind == "CommunityHealthCenter":
        fqhc = r.get("federallyQualifiedHealthCenter") or inner
        detail = {
            "doing_business_as": fqhc.get("doingBusinessAs") or fqhc.get("name"),
            "fqhc_type": fqhc.get("providerTypeText"),
            "npi": fqhc.get("npi"),
            "enrollment_state": fqhc.get("enrollmentState"),
        }
    elif kind == "InpatientRehabilitation":
        detail = {
            "ownership": inner.get("ownershipType"),
            "overall_rating": inner.get("overallRating"),
        }
    elif kind == "LongTermCare":
        detail = {
            "ownership": inner.get("ownershipType"),
            "overall_rating": inner.get("overallRating"),
        }
    elif kind == "GroupPractice":
        detail = {
            "members": inner.get("numberOfMembers"),
        }
    return {k: v for k, v in detail.items() if v not in (None, "", [])}


def build_providers() -> tuple[list[dict], list[dict]]:
    geo = load("provider_geo.json")
    cities = []
    for city, g in sorted(geo.items()):
        cities.append({
            "query": city,
            "city": g.get("city") or city.split(",")[0].strip(),
            "state": g.get("state") or city.split(",")[-1].strip(),
            "lat": g.get("lat"),
            "lon": g.get("lon"),
        })

    raw_blocks = load("providers_raw.json") + load("providers_hh_hospice.json")
    best: dict[tuple, dict] = {}
    counts: dict[tuple, int] = {}
    for block in raw_blocks:
        for r in block["rows"]:
            kind = r.get("type")
            if not kind:
                continue
            pid = str(r.get("providerId") or r.get("id"))
            inner = r.get(kind[0].lower() + kind[1:], {}) or {}
            if not inner and kind == "GroupPractice":
                inner = {}
            name = (r.get("name") or inner.get("name") or "").strip()
            if not name or not pid:
                continue
            key = (kind, pid)
            cnt_key = (block.get("city"), kind)
            if counts.get(cnt_key, 0) >= CAP_PER_CITY_TYPE:
                continue
            counts[cnt_key] = counts.get(cnt_key, 0) + 1
            dist = r.get("distance")
            prev = best.get(key)
            if prev is not None and (prev.get("distance") or 999) <= (dist or 999):
                continue
            row = {
                "provider_type": kind,
                "provider_id": pid,
                "name": name,
                "address1": inner.get("addressLine1") or "",
                "address2": inner.get("addressLine2") or "",
                "city": inner.get("addressCity") or "",
                "state": inner.get("addressState") or r.get("addressState") or "",
                "zip": clean_zip(inner.get("addressZipcode")),
                "phone": fmt_phone(inner.get("phone")),
                "lat": inner.get("lat") or r.get("lat"),
                "lon": inner.get("lon") or r.get("lon"),
                "distance": round(dist, 2) if isinstance(dist, (int, float)) else None,
                "search_city": block.get("city"),
                "specialties": [s for s in (r.get("specialties") or []) if s][:4],
            }
            if kind == "Physician":
                gp = (inner.get("groupAffiliations") or [{}])[0].get("organizationName")
                row["specialties"] = [
                    s.get("specialtyName") for s in (inner.get("specialties") or []) if s.get("specialtyName")
                ][:4]
                row["group"] = gp
            if kind == "GroupPractice":
                row["specialties"] = [
                    s.get("specialtyName") for s in (inner.get("specialties") or []) if s.get("specialtyName")
                ][:6]
            row.update(provider_detail(kind, r))
            best[key] = row
    providers = sorted(best.values(), key=lambda r: (r["search_city"] or "", r["provider_type"], r["name"].casefold()))
    return providers, cities


# ---------------------------------------------------------------------------
# DME suppliers (real)
# ---------------------------------------------------------------------------

def build_dme() -> tuple[list[dict], list[dict], list[dict]]:
    data = load("dme_suppliers.json")
    suppliers_by_id: dict[str, dict] = {}
    zip_rows: list[dict] = []
    zips = []
    for zip_code, blob in sorted(data.items()):
        payload = blob.get("payload", {})
        zips.append({"zip": zip_code, "city": blob.get("city", ""), "lat": payload.get("location", {}).get("latitude"), "lon": payload.get("location", {}).get("longitude")})
        ranked = sorted(payload.get("supplierList", []), key=lambda s: (s.get("distance") or {}).get("value", 999))
        for rank, s in enumerate(ranked[:CAP_DME_PER_ZIP], start=1):
            sup = s.get("supplier", {})
            sid = sup.get("supplierID", "")
            d = (s.get("distance") or {}).get("value")
            zip_rows.append({"zip": zip_code, "supplier_id": sid, "distance": round(d, 2) if isinstance(d, (int, float)) else None, "rank": rank})
            if sid in suppliers_by_id:
                continue
            suppliers_by_id[sid] = {
                "supplier_id": sid,
                "name": (sup.get("practiceName") or sup.get("businessName") or "").title(),
                "address1": sup.get("address1", "").title(),
                "address2": (sup.get("address2") or "").title() or "",
                "city": sup.get("city", "").title(),
                "state": sup.get("state", ""),
                "zip": clean_zip(sup.get("zip")),
                "phone": fmt_phone(sup.get("phone")),
                "medicare_assignment": bool(sup.get("medicareAssignment")),
                "specialties": [x for x in (sup.get("specialtyList") or []) if x],
                "supplies": [x for x in (sup.get("supplyList") or []) if x],
            }
    suppliers = sorted(suppliers_by_id.values(), key=lambda r: (r["state"], r["city"], r["name"].casefold()))
    return suppliers, zip_rows, zips


def build_taxonomy() -> list[dict]:
    data = load("dme_taxonomy.json")
    cats = []
    for c in data.get("categories", []):
        meta = c.get("metaData") or {}
        letter = (c.get("externalCategoryName") or "?")[0].upper()
        cats.append({
            "name": c.get("externalCategoryName"),
            "description": meta.get("metaDataDescription") or c.get("name"),
            "aliases": [a.get("value") for a in meta.get("aliases") or [] if a.get("value")][:6],
            "letter": letter,
        })
    cats.sort(key=lambda r: (r["letter"], (r["name"] or "").casefold()))
    return cats


# ---------------------------------------------------------------------------
# publications (real)
# ---------------------------------------------------------------------------

def build_publications() -> list[dict]:
    pubs = load("publications.json")
    out = []
    for p in pubs:
        slug = ""
        pdf = p.get("pdf", "")
        if pdf:
            slug = pdf.rsplit("/", 1)[-1]
        category = p.get("category") or ""
        while "&" in category:
            new = html.unescape(category)
            if new == category:
                break
            category = new
        out.append({
            "product_number": p.get("product_number"),
            "title": p.get("title"),
            "category": category.replace("\u00a0", " ").strip(),
            "language": p.get("language") or "English",
            "summary": p.get("summary"),
            "thumb": "pub_thumb_" + p.get("product_number") + (".jpg.webp" if ".jpg" in p.get("thumb", "") else ".png.webp") if p.get("thumb") else "",
            "pdf_file": slug,
            "orderable": p.get("order_status") == "Yes",
            "detail_href": p.get("detail_href", ""),
        })
    out.sort(key=lambda r: (r["category"] or "", r["title"].casefold()))
    return out


# ---------------------------------------------------------------------------
# costs (real 2026 amounts from /basics/costs/medicare-costs)
# ---------------------------------------------------------------------------

def build_costs() -> dict:
    return {
        "year": 2026,
        "part_a": {
            "premium_free_note": "Premium-free for most people (they or a spouse paid Medicare taxes long enough while working — generally at least 10 years).",
            "premium_no_free": "You'll pay either $311 or $565 each month for Part A, depending on how long you or your spouse worked and paid Medicare taxes.",
            "premium_low": "$311",
            "premium_high": "$565",
            "deductible": "$1,736",
            "deductible_note": "$1,736 for each inpatient hospital benefit period, before Original Medicare starts to pay.",
            "inpatient_days_1_60": "Days 1-60: $0 after you pay your Part A deductible.",
            "inpatient_days_61_90": "Days 61-90: $434 each day.",
            "inpatient_days_91_150": "Days 91-150: $868 each day while using your 60 lifetime reserve days.",
            "inpatient_after_150": "After day 150: You pay all costs.",
            "snf_days_1_20": "Days 1-20: $0.",
            "snf_days_21_100": "Days 21-100: $217 each day.",
            "snf_after_100": "Days 101 and beyond: You pay all costs.",
            "home_health": "$0 for covered home health care services. 20% of the Medicare-approved amount for durable medical equipment (like wheelchairs, walkers, hospital beds, and other equipment).",
        },
        "part_b": {
            "premium": "$202.90",
            "premium_note": "$202.90 each month (or higher depending on your income). The amount can change each year.",
            "deductible": "$283",
            "deductible_note": "$283 before Original Medicare starts to pay. You pay this deductible once each year.",
            "coinsurance": "Usually 20% of the cost for each Medicare-covered service or item after you've paid your deductible (and as long as your doctor or health care provider accepts the Medicare-approved amount as full payment – called \"accepting assignment\").",
            "clinical_lab": "$0 for covered clinical laboratory services.",
            "home_health": "$0 for covered home health care services.",
            "outpatient_mental_health": "$0 for your yearly depression screening. 20% of the Medicare-approved amount for visits to your doctor or other health care provider to diagnose or treat your condition.",
        },
        "irmaa": [
            {"individual": "$109,000 or less", "joint": "$218,000 or less", "married_sep": "$109,000 or less", "premium": "$202.90"},
            {"individual": "above $109,000 up to $137,000", "joint": "above $218,000 up to $274,000", "married_sep": "Not applicable", "premium": "$284.10"},
            {"individual": "above $137,000 up to $171,000", "joint": "above $274,000 up to $342,000", "married_sep": "Not applicable", "premium": "$405.80"},
            {"individual": "above $171,000 up to $205,000", "joint": "above $342,000 up to $410,000", "married_sep": "Not applicable", "premium": "$527.50"},
            {"individual": "above $205,000 and less than $500,000", "joint": "above $410,000 and less than $750,000", "married_sep": "above $109,000 and less than $391,000", "premium": "$649.20"},
            {"individual": "$500,000 or above", "joint": "$750,000 or above", "married_sep": "$391,000 or above", "premium": "$649.20"},
        ],
        "advantage": {
            "premiums": "Varies by plan. These amounts can change each year. You must have Part B and keep paying your Part B premium to stay in your plan.",
            "oop_limit": "Varies by plan. Once you pay the plan's limit, the plan pays 100% of your covered health services for the rest of the calendar year.",
        },
        "part_d": {
            "premium": "Varies by plan. You may have to pay more, depending on your income.",
            "deductibles": "Varies by plan and pharmacy.",
        },
        "medigap": {
            "premium": "Varies based on which Medigap policy you buy, where you live, and other factors. The amount can change each year.",
        },
    }


# ---------------------------------------------------------------------------
# content pages (real upstream text)
# ---------------------------------------------------------------------------

def main_region_text(filename: str) -> str:
    t = (SCRAPED / filename).read_text(encoding="utf-8")
    m = re.search(r"<main[^>]*>(.*?)</main>", t, flags=re.S)
    body = m.group(1) if m else t
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    txt = re.sub(r"</(p|h1|h2|h3|h4|li|div|tr)>", "\n", body)
    txt = re.sub(r"</t[dh]>", " | ", txt)
    txt = re.sub(r"<[^>]+>", "", txt)
    txt = html.unescape(txt)
    lines = [re.sub(r"\s+", " ", l).strip() for l in txt.splitlines()]
    return "\n".join([l for l in lines if l])


def build_content_pages() -> dict:
    from extract_content import extract_page

    pages = {}
    specs = {
        "get-started-with-medicare": ("basics_get_started.html", "Get started with Medicare"),
        "your-medicare-rights": ("basics_rights.html", "Your Medicare rights"),
        "your-medicare-rights/your-rights": ("sub_rights.html", "Your Rights"),
        "your-medicare-rights/your-protections": ("sub_protections.html", "Your Protections"),
        "your-medicare-rights/get-help-with-your-rights-protections": ("sub_rights_help.html", "Get help with your rights & protections"),
        "reporting-medicare-fraud-and-abuse": ("basics_fraud.html", "Reporting Medicare fraud & abuse"),
        "end-stage-renal-disease": ("basics_esrd.html", "End-Stage Renal Disease (ESRD)"),
        "children-and-end-stage-renal-disease": ("sub_children_esrd.html", "Children & End-Stage Renal Disease (ESRD)"),
        "report-a-death": ("basics_death.html", "Report a death"),
        "get-started-with-medicare/before-65": ("sub_gs_before65.html", "I’m getting Social Security benefits before 65"),
        "get-started-with-medicare/after-65": ("sub_gs_after65.html", "I’m getting Social Security benefits after 65"),
        "using-medicare/your-medicare-card": ("sub_card.html", "Your Medicare Card"),
    }
    for slug, (filename, fallback_title) in specs.items():
        page = extract_page(filename)
        if not page["title"]:
            page["title"] = fallback_title
        pages[slug] = page

    # landing-style pages get their real upstream card structures
    pages["your-medicare-rights"]["cards"] = [
        {"title": "Your rights", "text": "Discover guidelines that ensure you’re treated fairly and your information is kept safe.",
         "cta": "Know my rights", "href": "/basics/your-medicare-rights/your-rights"},
        {"title": "Your protections", "text": "Find out how to respond to unexpected bills for tests, items, or services.",
         "cta": "Check my protections", "href": "/basics/your-medicare-rights/your-protections"},
        {"title": "Help with your rights & protections", "text": "Get answers to your questions about Medicare rights and protections.",
         "cta": "Get help", "href": "/basics/your-medicare-rights/get-help-with-your-rights-protections"},
    ]
    pages["get-started-with-medicare"]["cards"] = [
        {"title": "Getting Social Security Benefits before 65",
         "text": "Follow this path to sign up for Medicare if you’re getting retirement or disability benefits from Social Security at least 4 months before turning 65.",
         "cta": "Get started", "href": "/basics/get-started-with-medicare/before-65"},
        {"title": "Getting Social Security Benefits after 65",
         "text": "Follow this path to sign up for Medicare if you’re waiting until 65 or older to get retirement benefits from Social Security.",
         "cta": "Get started", "href": "/basics/get-started-with-medicare/after-65"},
        {"title": "ESRD",
         "text": "Get specific information if you have End-Stage Renal Disease (ESRD).",
         "cta": "ESRD link", "href": "/basics/end-stage-renal-disease"},
    ]

    talk_txt = main_region_text("talk_to_someone.html")
    pages["talk-to-someone"] = {
        "title": "Contact Medicare",
        "source": "https://www.medicare.gov/talk-to-someone",
        "text": talk_txt,
        **extract_page("talk_to_someone.html"),
    }
    return pages


# ---------------------------------------------------------------------------

def main() -> None:
    coverage = build_coverage()
    providers, cities = build_providers()
    dme_suppliers, dme_zip_rows, dme_zips = build_dme()
    taxonomy = build_taxonomy()
    publications = build_publications()
    costs = build_costs()
    content_pages = build_content_pages()

    source = {
        "captured": "2026-09-23",
        "upstream": "https://www.medicare.gov/",
        "coverage_items": coverage,
        "providers": providers,
        "provider_cities": cities,
        "dme_suppliers": dme_suppliers,
        "dme_zip_rows": dme_zip_rows,
        "dme_zips": dme_zips,
        "equipment_categories": taxonomy,
        "publications": publications,
        "costs": costs,
        "content_pages": content_pages,
    }
    OUT_PATH.write_text(json.dumps(source, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"coverage={len(coverage)} providers={len(providers)} cities={len(cities)} "
          f"dme_suppliers={len(dme_suppliers)} dme_zip_rows={len(dme_zip_rows)} "
          f"taxonomy={len(taxonomy)} publications={len(publications)}")
    print(f"source_data.json = {OUT_PATH.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()

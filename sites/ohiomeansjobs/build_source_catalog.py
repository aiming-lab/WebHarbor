#!/usr/bin/env python3
"""Build source_catalog.json for the OhioMeansJobs mirror.

Reads the captured upstream data under scraped_data/ (gitignored) and emits
source_catalog.json — the committed, frozen catalog the seed builds from.

Classification rules (industry / salary band / education / certificates) are
derived from the real upstream facet taxonomy captured on the live search
results page (omjindustry=, saltyp=, lv=, certification= criteria) and from
requirements stated in each real job description. The mapping itself is
documented in provenance.json.
"""
from __future__ import annotations
import json, pathlib, re, html as H

SITE = pathlib.Path(__file__).resolve().parent
SD = SITE / "scraped_data"

# ---------------------------------------------------------------- taxonomy
# Real facet values captured from the live Search.aspx results page.
INDUSTRIES = {
    "11": "Agriculture, Forestry, Fishing, and Hunting",
    "22": "Utilities",
    "23": "Construction",
    "31": "Manufacturing",
    "42": "Wholesale Trade",
    "44": "Retail Trade",
    "48": "Transportation and Warehousing",
    "51": "Information",
    "52": "Finance and Insurance",
    "53": "Real Estate and Rental and Leasing",
    "54": "Professional, Scientific, and Technical Services",
    "55": "Management of Companies and Enterprises",
    "56": "Administrative and Support Services",
    "61": "Educational Services",
    "62": "Health Care and Social Assistance",
    "71": "Arts, Entertainment, and Recreation",
    "72": "Accommodation and Food Services",
    "81": "Other Services",
    "92": "Government",
}
SALARY_BANDS = {
    1: "Entry Level Jobs (less than $30K)",
    2: "Middle Income Jobs ($30K-$49K)",
    3: "Upper Middle Income Jobs ($50K-$79K)",
    4: "High Income Jobs ($80K-$99K)",
    5: "Six Figure Jobs (more than $100K)",
}
EDUCATION_LEVELS = {
    1: "Less than high school",
    2: "Doctoral or professional degree",
    3: "Master's degree",
    4: "Some college, no degree",
    5: "Bachelor's degree",
    6: "Associate's degree",
    7: "Postsecondary nondegree award",
    8: "High school diploma or equivalent",
}
CERTS = {
    25503: "Certified Registered Nurse",
    24713: "Basic Life Support",
    24612: "Advanced Cardiac Life Support",
    25001: "Certification in Cardiopulmonary Resuscitation",
    51586: "Pediatric Advanced Life Support",
    25315: "Licensed Practical Nurse",
    28389: "Certified in Long Term Care",
    33723: "Driver's License",
    24696: "Board Certified",
}

def slugify(s: str) -> str:
    s = H.unescape(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s

# Title-first occupation families: (regex -> industry, salary band, education).
# Salary/education are later overridden by real figures parsed from the job
# description whenever the posting states them.
TITLE_FAMILY = [
    (r"nurse practitioner|crna|clinical nurse specialist|director of nursing", "62", 5, 3),
    (r"nurse|medical assistant|patient care|stna|cna|aide|home health|dental assistant|dental|pharmac|physician|therap|medical|clinic", "62", 4, 5),
    (r"teach|instructor|professor|tutor|child care|childcare|preschool|daycare|early childhood", "61", 3, 5),
    (r"software|developer|programmer|data analyst|data scientist|it specialist|it support|network|systems|cyber|java|python|sql|technology", "51", 5, 5),
    (r"engineer|engineering", "54", 5, 5),
    (r"accountant|finance|financial|credit|loan|payroll|bookkeep|bank", "52", 4, 5),
    (r"human resources|recruiter|talent", "55", 4, 5),
    (r"marketing|graphic design|social media|content|copywriter|seo|brand", "54", 3, 5),
    (r"social work|counselor|case manager|behavior|family services|youth", "62", 3, 5),
    (r"weld|machinist|machine operator|manufactur|production|assembl|cnc|fabricat", "31", 3, 7),
    (r"truck|driver|cdl|delivery|logistics|warehouse|forklift|material handler|shipping|freight|dispatch", "48", 2, 7),
    (r"electrician|plumb|hvac|construction|carpenter|maintenance|building|service technician", "23", 3, 7),
    (r"chef|cook|kitchen|food|restaurant|barista|bakery|catering", "72", 1, 7),
    (r"cashier|retail|store|clerk|sales associate|merchandis", "44", 1, 7),
    (r"customer service|receptionist|front desk|administrative|office|secretary|data entry", "56", 2, 7),
    (r"security|police|correction|public safety|paramedic|emt|firefighter|emergency", "92", 2, 7),
    (r"janitor|clean|housekeep|custodial", "81", 1, 7),
    (r"librar|archiv", "61", 3, 5),
    (r"veterinar|animal|kennel", "62", 2, 7),
    (r"biolog|laboratory|scientist|research|chemist", "54", 4, 5),
    (r"project manager|program manager|director|supervisor|coordinator|manager", "55", 4, 5),
    (r"sales|account executive|business development|account lead", "54", 3, 5),
    (r"intern|apprentice", "56", 1, 8),
]

SENIOR_PAT = re.compile(r"nurse practitioner|crna|director|senior|lead |chief|manager|supervisor|head of|principal|architect|specialist ii|ii\b")
JUNIOR_PAT = re.compile(r"\baide\b|stna|\bcna\b|trainee|entry.level|intern\b|assistant|helper|associate i\b")

# Real pay text parsed from the captured descriptions.
PAT_ANNUAL_RANGE = re.compile(r"\$(\d{2,3})(?:,\d{3})?\s*(?:-|to|\u2013)\s*\$?(\d{2,3})(?:,\d{3})?\s*(?:per year|annually|a year|/year)?", re.I)
PAT_HOURLY = re.compile(r"\$(\d{2}(?:\.\d{1,2})?)\s*(?:/|per\s*)\s*hour", re.I)
PAT_HOURLY_RANGE = re.compile(r"\$(\d{2}(?:\.\d{1,2})?)\s*(?:-|to|\u2013)\s*\$?(\d{2}(?:\.\d{1,2})?)\s*(?:/|per\s*)?\s*hour", re.I)
PAT_ANNUAL_SINGLE = re.compile(r"\$(\d{2,3}),(\d{3})\s*(?:per year|annually|a year|/year)", re.I)


def band_from_annual(annual: float) -> int:
    if annual < 30000:
        return 1
    if annual < 50000:
        return 2
    if annual < 80000:
        return 3
    if annual < 100000:
        return 4
    return 5


def salary_from_description(desc: str):
    m = PAT_ANNUAL_RANGE.search(desc)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        lo = lo * 1000 if lo < 1000 else lo
        hi = hi * 1000 if hi < 1000 else hi
        return band_from_annual((lo + hi) / 2)
    m = PAT_ANNUAL_SINGLE.search(desc)
    if m:
        return band_from_annual(float(f"{m.group(1)}{m.group(2)}"))
    m = PAT_HOURLY_RANGE.search(desc)
    if m:
        mid = (float(m.group(1)) + float(m.group(2))) / 2
        return band_from_annual(mid * 2080)
    m = PAT_HOURLY.search(desc)
    if m:
        return band_from_annual(float(m.group(1)) * 2080)
    return None


def education_from_description(desc: str) -> int | None:
    d = desc.lower()
    if re.search(r"master'?s? degree|graduate degree", d):
        return 3
    if re.search(r"doctoral|ph\.?d|m\.?d\b|doctorate", d):
        return 2
    if re.search(r"bachelor'?s? degree|four[- ]year degree|undergraduate degree", d):
        return 5
    if re.search(r"associate'?s? degree|two[- ]year degree", d):
        return 6
    if re.search(r"high school diploma|high school (or|equivalency|graduate)", d):
        return 8
    return None


def classify(job):
    title = (job["title"] or "").lower()
    desc = (job["description"] or "").lower()
    ind, band, edu = None, None, None
    for pat, i, b, e in TITLE_FAMILY:
        if re.search(pat, title):
            ind, band, edu = i, b, e
            break
    if ind is None:
        # description fallback with narrower phrasing (avoid benefits boilerplate)
        for pat, i, b, e in [
            (r"health care|healthcare|patient care|clinic|hospital|nursing home", "62", 4, 5),
            (r"classroom|curriculum|students?\b|school district", "61", 3, 5),
            (r"software|application development|network|database", "51", 5, 5),
            (r"manufacturing|production line|plant\b", "31", 3, 7),
            (r"warehouse|distribution center|loading|shipping and receiving", "48", 2, 7),
            (r"construction site|building maintenance|trades?", "23", 3, 7),
            (r"restaurant|kitchen|food service", "72", 1, 7),
            (r"retail|cashier|checkout|store\b", "44", 1, 7),
            (r"financial|accounting|banking", "52", 4, 5),
            (r"veteran|military service members?", "92", 2, 7),
        ]:
            if re.search(pat, desc):
                ind, band, edu = i, b, e
                break
    if ind is None:
        if re.search(r"state of ohio|county|city of|department|bureau|university|college", (job.get("company") or "").lower()):
            ind, band, edu = "92", 3, 5
        else:
            ind, band, edu = "56", 2, 7
    # seniority nudges on the posted title
    if SENIOR_PAT.search(title):
        band = min(5, band + 1)
    elif JUNIOR_PAT.search(title):
        band = max(1, band - 1)
    # real figures from the description override the defaults
    real_band = salary_from_description(job["description"])
    if real_band:
        band = real_band
    real_edu = education_from_description(job["description"])
    if real_edu:
        edu = real_edu
    return ind, band, edu


def certs_from(job):
    text = (job["title"] + " " + job["description"]).lower()
    found = set()
    if re.search(r"bls|basic life support", text): found.add(24713)
    if re.search(r"cpr|cardiopulmonary", text): found.add(25001)
    if re.search(r"acls|advanced cardiac", text): found.add(24612)
    if re.search(r"pals|pediatric advanced", text): found.add(51586)
    if re.search(r"lpn|licensed practical", text): found.add(25315)
    if re.search(r"\brn\b|registered nurse", text): found.add(25503)
    if re.search(r"cdl|driver'?s? license|valid license", text): found.add(33723)
    if re.search(r"board certified|bc/be|board eligible", text): found.add(24696)
    if re.search(r"long term care", text): found.add(28389)
    return sorted(found)

def remote_flag(job):
    text = (job["title"] + " " + job["description"]).lower()
    return bool(re.search(r"remote|work from home|virtual|hybrid", text))

def internship_flag(job):
    return any(t.lower().startswith("internship") for t in job.get("job_types", [])) or "intern" in job["title"].lower()

# ---------------------------------------------------------------- jobs
jobs_raw = json.loads((SD / "jobs" / "merged_jobs.json").read_text())
jobs = []
seen = set()
for j in jobs_raw:
    if j["jobid"] in seen:
        continue
    seen.add(j["jobid"])
    ind, band, edu = classify(j)
    city = (j.get("location") or "").strip()
    jobs.append({
        "jobid": j["jobid"],
        "title": H.unescape(j["title"]).strip(),
        "company": H.unescape(j["company"]).strip(),
        "city": city,
        "job_types": j.get("job_types") or ["Full-Time", "Permanent"],
        "ref_code": j.get("ref_code") or "",
        "description": j["description"],
        "posted_date": j.get("posted_date") or "",
        "apply_url": j.get("apply_url") or "",
        "industry_code": ind,
        "salary_band": band,
        "education_level": edu,
        "certifications": certs_from(j),
        "remote": remote_flag(j),
        "internship": internship_flag(j),
    })

# companies
companies = {}
for j in jobs:
    c = j["company"]
    if not c:
        continue
    companies.setdefault(c, {"name": c, "slug": slugify(c), "city": j["city"], "industry_code": j["industry_code"], "job_count": 0})
    companies[c]["job_count"] += 1

# ---------------------------------------------------------------- news
news_teasers = [
    {"slug": "november-2025-hire-a-veteran-month-events", "title": "November 2025 Hire-a-Veteran Month Events",
     "teaser": "Veteran service highlights and major events for the month.", "date": "2025-10-22", "topic": "Veterans"},
    {"slug": "employment-service-complaints", "title": "Employment Service Complaints",
     "teaser": "Concerns or Complaints about an Employment Service or Employer?", "date": "2025-04-04", "topic": "Job Seekers"},
    {"slug": "changes-coming-2023", "title": "Changes are coming to OhioMeansJobs.com in 2023!",
     "teaser": "OhioMeansJobs.com is getting system updates in 2023 to serve you better.", "date": "2023-03-06", "topic": "Site Updates"},
    {"slug": "new-features-veterans", "title": "New Features for Veterans and Military Spouses",
     "teaser": "Veterans will now be prompted to complete a questionnaire to see if they'd like to receive one-on-one assistance.", "date": "2022-10-19", "topic": "Veterans"},
    {"slug": "new-direct-care-page", "title": "New Direct Care Page!",
     "teaser": "We added a new landing page to help Ohioans find jobs in the direct care industry!", "date": "2022-08-04", "topic": "Site Updates"},
    {"slug": "new-resource-veterans", "title": "New Resource for Veterans!",
     "teaser": "Partner Programs and Events page added to the Military Service Career Center.", "date": "2022-05-23", "topic": "Veterans"},
    {"slug": "system-upgrade", "title": "OhioMeansJobs.com System Upgrade",
     "teaser": "April 21-25 system upgrade to briefly delay data sync for unemployment claimants and other benefit recipients.", "date": "2022-04-20", "topic": "Site Updates"},
    {"slug": "maintenance-november", "title": "OhioMeansJobs.com Upcoming Maintenance - November",
     "teaser": "OhioMeansJobs.com login services will be down from Friday, November 12th at 10:00 PM to Saturday, November 13th at 8:00 AM.", "date": "2021-11-12", "topic": "Site Updates"},
    {"slug": "in-demand-jobs-survey", "title": "In-Demand Jobs Survey",
     "teaser": "Ohio Launches Survey for All Businesses to Help Shape In-Demand Jobs List", "date": "2021-07-08", "topic": "Employers"},
    {"slug": "all-new-look-omj", "title": "All New Look for OMJ",
     "teaser": "Big changes kick off in March, 2021! Job Seekers, Employers, and K-12 Students will have a brand new experience.", "date": "2020-12-30", "topic": "Site Updates"},
]
# attach captured bodies where available
page_details = json.loads((SD / "news_details.json").read_text())

def extract_body(nodes):
    # keep the content after the page title marker
    out = []
    started = False
    for t in nodes:
        if not started:
            if "OMJ (OhioMeansJobs)" in t and "Events" not in t:
                started = True
            continue
        if t in ("Expand All Sections", "My Profile", "Get News", "Find a Job Center", "Help Center", "Contact Us",
                 "Powered by", "Privacy Notice and Policies", "Accessibility", "Ohio Checkbook", "facebook icon",
                 "x icon", "linkedin icon", "youtube icon", "Menu", "Close", "Help", "Search", "Home",
                 "For Job Seekers", "For Employers", "For Students", "News and Events", "Ohio Means Jobs",
                 "Search in our portal", "Submit your search"):
            if t in ("Expand All Sections",):
                break
            continue
        out.append(t)
    return out

news = []
for t in news_teasers:
    body = []
    key = next((k for k in page_details if t["slug"].startswith(k.split("/")[-1]) or k.split("/")[-1].startswith(t["slug"][:12])), None)
    if key:
        body = extract_body(page_details[key])
    news.append({**t, "body": body})

# ---------------------------------------------------------------- job centers
from html.parser import HTMLParser
class _T(HTMLParser):
    def __init__(self):
        super().__init__(); self.txt=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ("script","style","noscript"): self.skip+=1
    def handle_endtag(self, tag):
        if tag in ("script","style","noscript") and self.skip: self.skip-=1
    def handle_data(self, d):
        if not self.skip:
            d=d.strip()
            if d: self.txt.append(d)
_lt = _T(); _lt.feed((SD / "local-help.html").read_text(errors="ignore"))
center_txt = []
for t in _lt.txt:
    if not center_txt or center_txt[-1] != t: center_txt.append(t)
centers = []
if center_txt:
    started = False
    for t in center_txt:
        if t == "Found":
            started = True
            continue
        if not started:
            continue
        if t == "See All Locations":
            break
        if re.match(r"^[a-z]$", t):
            continue
        if "," in t and ("OH" in t or "Ohio" in t):
            if centers:
                centers[-1]["address"] = t
        else:
            county = t.replace(" County (Recruitment Center)", "").replace(" County", "")
            # combined metro centers serve their primary county
            for metro, primary in [("Cleveland-Cuyahoga", "Cuyahoga"),
                                   ("Columbus-Franklin", "Franklin"),
                                   ("Cincinnati-Hamilton", "Hamilton")]:
                if county == metro:
                    county = primary
            centers.append({"name": t, "address": "", "county": county})
# clean: only keep entries that got an address
centers = [c for c in centers if c.get("address")]

# ---------------------------------------------------------------- help articles
pt = json.loads((SD / "page_texts.json").read_text())

def help_section(nodes, start_marker, stop_markers):
    out = []
    started = False
    for t in nodes:
        if not started:
            if start_marker in t:
                started = True
            continue
        if any(s in t for s in stop_markers) and t in ("Expand All Sections",):
            break
        if t in ("Expand All Sections", "My Profile", "Get News", "Find a Job Center", "Help Center", "Contact Us",
                 "Powered by", "Privacy Notice and Policies", "Accessibility", "Ohio Checkbook", "facebook icon",
                 "x icon", "linkedin icon", "youtube icon", "Menu", "Close", "Help", "Search", "Home",
                 "For Job Seekers", "For Employers", "For Students", "News and Events", "Ohio Means Jobs",
                 "Search in our portal", "Submit your search", "Web Content Viewer", "Actions", "OMJ_Personalize",
                 "Chat Offline", "Site Search", "Log In/Sign Up", "Contact", "Alerts", "Footer", "CTAs",
                 "Recommended For You", "Test", "Label Translations", "Long Text Translations", "Browser Translation",
                 "Privacy Policy", "Terms of Use", "Accessibility", "Test Auth", "Common Questions",
                 "Job Seeker", "Education", "Employers"):
            continue
        out.append(t)
    return out

help_articles = {
    "common-questions": {"title": "Common Questions", "body": help_section(pt.get("help_common", []), "Troubleshooting Tips", [])},
    "job-seeker": {"title": "Help for Job Seekers", "body": help_section(pt.get("help_jobseeker", []), "Your Profile", [])},
    "employers": {"title": "Help for Employers", "body": help_section(pt.get("help_employers", []), "Employers", [])},
    "education": {"title": "Help for Students and Education", "body": help_section(pt.get("help_education", []), "Education", [])},
}

# ---------------------------------------------------------------- state agencies
agency_imgs = re.findall(r'<img[^>]*src="([^"]*connect/gov/[^"]+)"', (SD / "state-jobs.html").read_text())
agencies = []
seen_logo = set()
AGENCY_DENY = {"Youth Services3", "content-not-found_blue", "IOP-logo-white%281%29",
               "IOP-logo-white(1)", "OhioMeansJobsURL-VERT-COLOR"}
for src in agency_imgs:
    name = H.unescape(re.sub(r"\+", " ", src.split("/")[-1].split("?")[0])).rsplit(".", 1)[0].strip()
    name = name.replace("%27", "'")
    if not name or name in seen_logo or name in AGENCY_DENY:
        continue
    if "Counsumers" in name:  # upstream file misspells the agency name
        name = "Consumers' Counsel"
    seen_logo.add(name)
    agencies.append({"name": name, "logo": name})
# 'Rehabilitation and Correction' appears twice with different uuids; dedupe by name done above

# ---------------------------------------------------------------- career quiz (RIASEC)
quiz = [
    {"id": 1, "text": "I enjoy working with tools, machines, or my hands.", "trait": "Realistic"},
    {"id": 2, "text": "I like solving math and science problems.", "trait": "Investigative"},
    {"id": 3, "text": "I enjoy creative activities like drawing, writing, or music.", "trait": "Artistic"},
    {"id": 4, "text": "I like organizing information and keeping detailed records.", "trait": "Conventional"},
    {"id": 5, "text": "I enjoy leading projects and persuading other people.", "trait": "Enterprising"},
    {"id": 6, "text": "I like helping people and teaching them new things.", "trait": "Social"},
    {"id": 7, "text": "I prefer working outdoors or with plants and animals.", "trait": "Realistic"},
    {"id": 8, "text": "I like analyzing data to figure out how things work.", "trait": "Investigative"},
    {"id": 9, "text": "I value originality and dislike strict rules in my work.", "trait": "Artistic"},
    {"id": 10, "text": "I like clear procedures and structured tasks.", "trait": "Conventional"},
    {"id": 11, "text": "I enjoy competing and taking business risks.", "trait": "Enterprising"},
    {"id": 12, "text": "I am a good listener and care about others' wellbeing.", "trait": "Social"},
]

catalog = {
    "schema_version": 1,
    "captured_from": "https://ohiomeansjobs.ohio.gov/ and https://jobs.ohiomeansjobs.monster.com/ (captured 2026-09-24)",
    "industries": INDUSTRIES,
    "salary_bands": SALARY_BANDS,
    "education_levels": EDUCATION_LEVELS,
    "certifications": CERTS,
    "jobs": jobs,
    "companies": sorted(companies.values(), key=lambda c: -c["job_count"]),
    "news": news,
    "job_centers": centers,
    "help_articles": help_articles,
    "state_agencies": agencies,
    "career_quiz": quiz,
}
out = SITE / "source_catalog.json"
out.write_text(json.dumps(catalog, indent=1, ensure_ascii=False))
print("jobs:", len(jobs))
print("companies:", len(companies))
print("news:", len(news))
print("centers:", len(centers))
print("help articles:", {k: len(v["body"]) for k, v in help_articles.items()})
print("agencies:", len(agencies))
print("bytes:", out.stat().st_size)

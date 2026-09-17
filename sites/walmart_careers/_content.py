"""Static CMS-style copy and design constants for the Walmart Careers mirror.

Nothing in here is runtime data: these are the marketing strings, benefit tiles
and map outlines that the real site serves from AEM. Runtime data (jobs, stores,
users, saved roles, applications) lives in SQLite only.
"""
from __future__ import annotations

from datetime import date

# The mirror is frozen against this date. Never call date.today() anywhere in
# the seed or bootstrap path.
MIRROR_REFERENCE_DATE = date(2026, 8, 31)

SITE_NAME = "Walmart Careers"
COPYRIGHT = "©2026 Walmart Inc."

HERO_HEADLINE_1 = "Cashiers wanted."
HERO_HEADLINE_2 = "Next move, yours."
SEARCH_PLACEHOLDER = "Search by team, department, keyword"

VALUES = [
    ("Respect for the individual", "We listen, we support, and we help each other grow."),
    ("Service to the customer", "Everything starts with the people who shop with us."),
    ("Strive for excellence", "We look for a better way, every single day."),
    ("Act with integrity", "We do the right thing, especially when it is hard."),
]

BENEFIT_ROWS = [
    ("Financial perks", "Enjoy 401(k) matching and stock purchase plans.", "benefit-financial.svg"),
    ("Paid time off", "Take a break as needed for vacations, sick leave, holidays, parental leave and more.", "benefit-pto.svg"),
    ("Comprehensive health benefits", "Medical, dental, vision and wellness programs for you and your family.", "benefit-health.svg"),
    ("Wellbeing programs", "Access mental health resources and assistance programs for life's challenges.", "benefit-wellbeing.svg"),
    ("Career growth opportunities", "Training, leadership programs, and clear paths to advance.", "benefit-growth.svg"),
]

# --------------------------------------------------------------------------- #
# Benefit tiles on the job detail page. Keyed by brand; hourly and salaried
# postings surface a slightly different Live Better U line, exactly as upstream.
# --------------------------------------------------------------------------- #
_WALMART_PLUS_TILE = (
    "Walmart+",
    "Free shipping",
    "As a Walmart Associate, you're eligible to become a Walmart+ member. Enjoy benefits "
    "like free store delivery and shipping, fuel savings, and video streaming. Sam's Club "
    "associates are eligible for a Club Membership.",
    "tile-walmart-plus.svg",
)
_DISCOUNT_TILE = (
    "Discount Card",
    "Get 10% off",
    "Walmart associates are eligible for a 10% discount card on all general merchandise "
    "items and fresh produce in-store and on select items at Walmart.com. Eligible after "
    "90 days of employment.",
    "tile-card.svg",
)
_LBU_FIELD_TILE = (
    "Live Better U",
    "100% covered",
    "Earn a degree or in-demand skills certificates with no debt - Walmart covers 100% of "
    "tuition and books. Live Better U offers 60+ programs for Associates to pursue their dreams.",
    "tile-graduation.svg",
)
_LBU_CORP_TILE = (
    "Live Better U",
    "100% covered",
    "Through Live Better U, Walmart and Sam's Club associates can learn critical skills and "
    "create pathways for promotion into in-demand jobs within the company. Whether earning a "
    "college degree, certificate or high school diploma, Walmart pays for tuition and books.",
    "tile-graduation.svg",
)
_ACADEMY_TILE = (
    "Walmart Academy",
    "Grow your skills",
    "Ready to grow your career? Walmart Academy offers job-specific retail training and "
    "leadership courses to help Associates reach their career goals.",
    "tile-growth.svg",
)


def benefit_tiles_for(brand: str, population: str) -> list[tuple[str, str, str, str]]:
    first = _DISCOUNT_TILE if population == "salaried" else _WALMART_PLUS_TILE
    second = _LBU_CORP_TILE if population == "salaried" else _LBU_FIELD_TILE
    return [first, second, _ACADEMY_TILE]


JOB_BENEFIT_ROWS = [
    ("Financial perks", "Enjoy 401(k) matching and stock purchase plans", "benefit-financial.svg"),
    ("Wellbeing programs", "Access mental health resources and assistance programs for life's challenges", "benefit-wellbeing.svg"),
    ("Paid time off", "Take a break as needed for vacation, sick leave, holidays, parental leave, and more", "benefit-pto.svg"),
    ("Career growth opportunities", "Training, leadership programs, and clear paths to advance", "benefit-growth.svg"),
    ("Comprehensive health benefits", "Medical, dental, vision, and wellness programs for you and your family", "benefit-health.svg"),
]

LIFE_AT_WALMART_HEADING = "Life at Walmart"
LIFE_AT_WALMART_QUOTE = (
    "Join us, and help us continue our mission to bring everyday value and support to communities everywhere."
)

DRUG_FREE_NOTICE = (
    "Walmart is committed to maintaining a drug-free workplace and has a no tolerance policy regarding "
    "the use of illegal drugs and alcohol on the job. This policy applies to all employees and aims to "
    "create a safe and productive work environment."
)

HOURLY_PAY_NOTICE = [
    "The actual hourly rate will equal or exceed the required minimum wage applicable to the job location.",
    "Additional compensation includes annual or quarterly performance incentives.",
    "Additional compensation in the form of premiums may be paid in amounts ranging from $0.35 per hour "
    "to $3.00 per hour in specific circumstances. Premiums may be based on schedule, facility, season, "
    "or specific work performed. Multiple premiums may apply if applicable criteria are met.",
]

MIN_QUAL_PREAMBLE = (
    "Outlined below are the required minimum qualifications for this position. If none are listed, "
    "there are no minimum qualifications."
)
PREF_QUAL_PREAMBLE = (
    "Outlined below are the optional preferred qualifications for this position. If none are listed, "
    "there are no preferred qualifications."
)

# Salaried detail pages: the boilerplate blocks that follow "What you'll bring"
# on the live corporate postings. Static chrome, keyed by career-area slug for
# the "About ..." paragraph; everything per-posting lives on Job.
SALARIED_ABOUT_AREA = {
    "technology": (
        "About Walmart Global Tech",
        "Imagine working in an environment where one line of code can make life easier for hundreds of "
        "millions of people. That's what we do at Walmart Global Tech. We're a team of software engineers, "
        "data scientists, cybersecurity experts and service professionals within the world's leading "
        "retailer who make an epic impact and are at the forefront of the next retail disruption. People "
        "are why we innovate, and people power our innovations. We are people-led and tech-empowered. We "
        "train our team in the skillsets of the future and bring in experts like you to help us grow.",
    ),
    "corporate": (
        "About Walmart",
        "Our home office and corporate teams set the direction for the world's largest retailer: the "
        "strategy, the finances, the merchandise, the marketing and the people practices behind more "
        "than 10,000 stores and clubs and the associates who run them. The work you do here shows up on "
        "shelves and in carts within weeks, not years.",
    ),
    "students": (
        "About our internships",
        "Our internships are paid, project-based and designed to end with a real deliverable. Interns "
        "join a team, own a piece of work for the term, present it to leadership and leave with a "
        "network across the business. Many of our leaders started as interns.",
    ),
}
SALARIED_ABOUT_DEFAULT = (
    "About Walmart",
    "Walmart Inc. is the world's largest retailer, serving more than 250 million customers every week "
    "through stores, clubs and eCommerce sites in nineteen countries.",
)
SALARIED_HYBRID_NOTE = (
    "We use a hybrid way of working that is primarily in office coupled with virtual when not onsite. "
    "Our campuses serve as a hub for collaboration, bring us together for purpose, and deliver on business "
    "needs. This approach helps us make quicker decisions, remove location barriers across our global "
    "team, and be more flexible in our personal lives."
)
SALARIED_BENEFITS_NOTE = (
    "Beyond our great compensation package, you can receive incentive awards for your performance. Other "
    "great perks include 401(k) match, stock purchase plan, paid maternity and parental leave, PTO, "
    "multiple health plans, and much more."
)
SALARIED_PAY_NOTE = (
    "At Walmart, we offer competitive pay as well as performance-based bonus awards and other great "
    "benefits for a happier mind, body, and wallet. Health benefits include medical, vision and dental "
    "coverage. Financial benefits include 401(k), stock purchase and company-paid life insurance. Paid "
    "time off benefits include PTO (including sick leave), parental leave, family care leave, "
    "bereavement, jury duty, and voting. Other benefits include short-term and long-term disability, "
    "company discounts, Military Leave Pay, adoption and surrogacy expense reimbursement, and more."
)
SALARIED_EEO_NOTE = (
    "Walmart, Inc. is an Equal Opportunity Employer - By Choice. We believe we are best equipped to help "
    "our associates, customers and the communities we serve live better when we really know them."
)
SALARIED_SCOPE_NOTE = (
    "The above information has been designed to indicate the general nature and level of work performed "
    "in the role. It is not designed to contain or be interpreted as a comprehensive inventory of all "
    "responsibilities and qualifications required of employees assigned to this job. The full Job "
    "Description can be made available as part of the hiring process."
)

# --------------------------------------------------------------------------- #
# Resources pages
# --------------------------------------------------------------------------- #
LOCATIONS_HEADING = "Our locations"
LOCATIONS_BLURB = (
    "Our hubs spark collaboration and innovation, so you're free to energize and push boundaries "
    "from the space that serves you best."
)
LOCATIONS_CLOSING = (
    "Between making an impact at scale and our culture of promoting from within, from coders all the "
    "way to cashiers, Walmart is the best place to build a career, period."
)

HIRING_HEADING = "How we hire"
HIRING_BLURB = (
    "Every career starts with a first step. Whether you're applying for your first job or your next "
    "big move, this is the beginning of something new. At Walmart and Sam's Club, the hiring process "
    "is about more than landing a role, it's about discovering where you belong, where you can grow, "
    "and where your work can make a real difference."
)
HIRING_STEPS = [
    ("1. Find your role", "Search open roles by keyword, career area or location, then save the ones you like."),
    ("2. Apply online", "Share your contact details and work history. Most applications take 20-25 minutes."),
    ("3. Interview", "A recruiter or hiring manager reaches out, usually within a week of your application."),
    ("4. Offer and onboarding", "Accept your offer, complete pre-employment steps and pick your start date."),
]
HIRING_FAQ = [
    (
        "Before you apply",
        [
            (
                "Do I need a resume or CV to apply for all Walmart jobs?",
                "Not necessarily. A resume or CV is not required to apply, but you will need to provide "
                "details about your job history and other information on the application. If you would "
                "like to include your resume, LinkedIn profile, portfolio or website, there will be a "
                "section where you can add it to your application.",
            ),
            (
                "How long does it take to fill out an application on average?",
                "On average, it takes 20-25 minutes to complete your application for the first time. "
                "Subsequent applications will take less time to apply as our system saves your "
                "application information.",
            ),
            (
                "Can I start the application process and finish it later?",
                "For hourly roles within the Walmart Online Hiring Center, you have the ability to save "
                "your work and log back in at a later time.",
            ),
            (
                "Can I change my application after submitting?",
                "No, you cannot change your application after submitting. Please make sure that "
                "everything is finalized before you hit the submit button.",
            ),
        ],
    ),
    (
        "After you apply",
        [
            (
                "Will I receive confirmation that my application was successfully submitted?",
                "Yes. Once you complete your application you will see a confirmation screen with a "
                "confirmation number that starts with WMC-.",
            ),
            (
                "When should I expect to hear back after submitting my application?",
                "Timing varies, but we try to respond to applicants within a week of submission.",
            ),
            (
                "Will I be notified if I am not selected for an interview?",
                "Yes, you will be informed if you are not selected for an interview at this time.",
            ),
            (
                "Do you provide reasonable accommodations during the application process?",
                "Yes, reach out to your manager, recruiter or recruiting coordinator about any needs "
                "you have. We are happy to do what we can to support you.",
            ),
        ],
    ),
]

TERMS_HEADING = "Terms & Conditions"
TERMS_SECTIONS = [
    (
        "About this mirror",
        "This is an offline WebHarbor mirror of careers.walmart.com built for agent benchmarking. "
        "No application submitted here reaches Walmart Inc., and no data leaves the container.",
    ),
    (
        "Candidate accounts",
        "Accounts created on this mirror exist only inside the local database and are removed whenever "
        "the environment is reset to its seed state.",
    ),
    (
        "Applications",
        "Submitting an application records a row in the local database and returns a confirmation number "
        "in the form WMC-000000. It creates no relationship, express or implied, with Walmart Inc.",
    ),
    (
        "Accuracy of postings",
        "Job postings, pay ranges, store addresses and requisition IDs shown here are synthetic mirror "
        "data modelled on the structure of the real site.",
    ),
]

# --------------------------------------------------------------------------- #
# Footer
# --------------------------------------------------------------------------- #
FOOTER_CAREER_LINKS = [
    ("Stores and Clubs", "stores-and-clubs"),
    ("Supply Chain and Transportation", "supply-chain-and-transportation"),
    ("Healthcare", "healthcare"),
    ("Technology", "technology"),
    ("Corporate", "corporate"),
]
FOOTER_BRANDS = ["Walmart", "Sam's Club", "VIZIO"]
FOOTER_SOCIAL = [
    ("Facebook", "social-facebook.svg"),
    ("Instagram", "social-instagram.svg"),
    ("LinkedIn", "social-linkedin.svg"),
    ("X", "social-x.svg"),
    ("YouTube", "social-youtube.svg"),
    ("Glassdoor", "social-glassdoor.svg"),
]
FOOTER_EEO = (
    "Walmart, Inc. is an Equal Opportunity Employer. We believe we are best equipped to help our "
    "associates, customers, and the communities we serve live better when we really know them. That "
    "means understanding, respecting, and valuing unique styles, experiences, identities, abilities, "
    "ideas and opinions- while welcoming all people. Walmart Inc. participates in E-verify. Learn more "
    "about applicant rights under Federal Employment Laws."
)
FOOTER_BENEFITS_NOTE = (
    "Eligibility for benefits depends on your job classification, and benefits are subject to specific "
    "plan or program terms. For more information about your benefits options, please see the Associate "
    "Benefits Book at One.Walmart.com/BenefitsBook."
)

EMPTY_FUTURE_ROLES = (
    "Future roles are not part of this mirror. Every posting in this environment is an open role you "
    "can browse, save and apply to from the Open roles tab."
)
EMPTY_CONTENT_TAB = (
    "Content search is not part of this mirror. Use the Open roles tab, the career area pages or the "
    "Resources pages to explore this site."
)

# --------------------------------------------------------------------------- #
# Coarse lat/lng outlines used by the deterministic server-rendered cluster map.
# Points are (lng, lat).
# --------------------------------------------------------------------------- #
US_OUTLINE = [
    (-124.7, 48.4), (-123.0, 48.2), (-122.6, 47.0), (-124.0, 46.3), (-124.1, 43.7),
    (-124.4, 42.0), (-124.2, 40.4), (-122.4, 37.8), (-121.9, 36.6), (-120.6, 34.6),
    (-118.4, 33.7), (-117.1, 32.5), (-114.7, 32.7), (-111.1, 31.3), (-108.2, 31.3),
    (-106.5, 31.8), (-104.9, 30.6), (-103.1, 29.0), (-101.4, 29.8), (-99.1, 26.4),
    (-97.1, 25.9), (-97.4, 28.0), (-95.0, 29.1), (-93.8, 29.7), (-91.0, 29.2),
    (-89.4, 29.0), (-89.0, 30.2), (-87.5, 30.3), (-85.0, 29.7), (-84.0, 30.1),
    (-82.8, 27.9), (-81.8, 25.9), (-80.1, 25.2), (-80.1, 27.0), (-81.4, 30.7),
    (-80.8, 32.0), (-78.9, 33.7), (-75.7, 35.2), (-76.0, 36.9), (-75.1, 38.3),
    (-74.0, 39.7), (-73.9, 40.6), (-71.9, 41.3), (-70.0, 41.7), (-70.2, 42.6),
    (-70.8, 43.2), (-69.0, 43.9), (-67.0, 44.8), (-67.8, 45.7), (-69.2, 47.5),
    (-71.5, 45.0), (-74.7, 45.0), (-76.9, 43.3), (-79.2, 43.4), (-82.4, 41.7),
    (-83.1, 42.2), (-82.5, 45.3), (-84.4, 46.5), (-87.6, 46.0), (-88.0, 48.2),
    (-89.5, 48.0), (-95.2, 49.0), (-104.0, 49.0), (-116.0, 49.0), (-123.0, 49.0),
]
PR_OUTLINE = [
    (-67.3, 18.5), (-66.4, 18.5), (-65.6, 18.4), (-65.6, 17.9), (-66.6, 17.9), (-67.3, 18.1),
]


# --------------------------------------------------------------------------- #
# Header navigation. The dropdown groups mirror the live top bar:
# Career areas | Brands | Resources | About Us | Military.
# --------------------------------------------------------------------------- #
# (label, brand filter value) for the Brands dropdown.
NAV_BRANDS = [
    ("Walmart", "Walmart"),
    ("Sam's Club", "Sam's Club"),
    ("VIZIO", "Vizio"),
]
# (label, endpoint) for the Resources dropdown.
NAV_RESOURCES = [
    ("How we hire", "resources_hiring"),
    ("Office Locations", "resources_location"),
    ("Terms & Conditions", "resources_terms"),
]

ABOUT_HEADING = "About Us"
ABOUT_BLURB = (
    "Walmart is a people-led, tech-powered omnichannel retailer. Around the world our associates "
    "serve customers in stores, clubs, distribution centers and online, and every one of those jobs "
    "is a step toward something greater."
)
ABOUT_SECTIONS = [
    (
        "Our purpose",
        "We save people money so they can live better. That purpose has guided every decision since "
        "Sam Walton opened the first store in Rogers, Arkansas, and it still shapes how we hire, how "
        "we promote, and how we invest in the communities we serve.",
    ),
    (
        "How we work",
        "We are people-led and tech-powered. Associates in stores, clubs, supply chain and the home "
        "office work with the same tools and the same data, so a good idea can start anywhere and "
        "reach millions of customers quickly.",
    ),
    (
        "Where you can grow",
        "About three quarters of our salaried store managers began as hourly associates. Live Better U "
        "pays for tuition, books and fees, and Walmart Academy runs skills training in every market we "
        "operate in.",
    ),
]

# --------------------------------------------------------------------------- #
# US state / territory names, used to resolve a plain state in the location box
# ("PR", "Puerto Rico", "Ohio") into a state-wide result set.
# --------------------------------------------------------------------------- #
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DC": "District of Columbia",
    "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "IA": "Iowa", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "MA": "Massachusetts",
    "MD": "Maryland", "ME": "Maine", "MI": "Michigan", "MN": "Minnesota",
    "MO": "Missouri", "MS": "Mississippi", "MT": "Montana", "NC": "North Carolina",
    "ND": "North Dakota", "NE": "Nebraska", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NV": "Nevada", "NY": "New York", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "PR": "Puerto Rico",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VA": "Virginia", "VI": "U.S. Virgin Islands",
    "VT": "Vermont", "WA": "Washington", "WI": "Wisconsin", "WV": "West Virginia",
    "WY": "Wyoming",
}
STATE_CODES_BY_NAME = {name.lower(): code for code, name in sorted(STATE_NAMES.items())}


# --------------------------------------------------------------------------- #
# Home page chrome below the fold: the values bento, the milestone badges and
# the "See our associates in action" strip. Static marketing copy only.
# --------------------------------------------------------------------------- #
HOME_INTRO_HEADLINE = ("Grow your future.", "Make an impact.")
HOME_INTRO_CTA = "See our values in action"
BENEFITS_ASIDE = "That's just the beginning. We offer more perks specific to your work location and role."
BENEFITS_CTA = "Learn more about benefits"
MILESTONE_HEADING = "Here, every job is a step toward something greater"
# (figure sentence, badge label, style) — style picks the badge colour scheme.
MILESTONE_BADGES = [
    ("$1 billion invested in associate career training and development", "", "sky"),
    ("75% of salaried managers began as hourly associates", "5 YEARS", "spark"),
    ("300,000 associates have earned a 10+ year badge", "10 YEARS", "navy"),
    ("120,000 U.S. associates have participated in Live Better U", "20 YEARS", "blue"),
]
ASSOCIATES_HEADING = "See our associates in action"
ASSOCIATES_BLURB = (
    "Every day, Walmart associates step up - solving problems, serving communities, and making a "
    "difference. They don't just do the job; they bring it to life."
)
FIND_ROLE_HEADING = "Find the role that's a perfect fit"
FIND_ROLE_PLACEHOLDER = "Search by team, department, or keyword"

# --------------------------------------------------------------------------- #
# Career-area page chrome (per area slug): the lower sections of the L1 pages.
# --------------------------------------------------------------------------- #
AREA_PAGE = {
    "stores-and-clubs": {
        "tiles": ("Purpose", "Growth", "Pride"),
        "headline": "You power the experience for millions",
        "cta": "See all stores and clubs roles",
        "photos": ("area-stores-3.jpg", "area-stores-2.jpg"),
        "quote": "At Walmart and Sam's Club, our stores and clubs are powered by people, dedicated "
                 "associates working together to create exceptional experiences for the communities "
                 "we serve.",
        "testimonials": [
            ("Curtis", "Store Manager", "Every shift is a chance to make someone's day a little easier."),
            ("D'Rogelio", "Store Manager", "You can be you in this environment and still succeed."),
            ("Jamaily", "Club Manager", "I started on the floor. Now I run the building."),
        ],
    },
    "supply-chain-and-transportation": {
        "tiles": ("Safety", "Scale", "Momentum"),
        "headline": "Move what matters, at scale",
        "cta": "See all supply chain roles",
        "photos": ("area-supply-chain-2.jpg", "supply-drone.jpg"),
        "quote": "Our supply chain associates move millions of items a day through a network that "
                 "reaches nearly every community in the country - and they do it safely.",
        "testimonials": [
            ("Caleb", "Maintenance Tech", "The equipment is the most advanced I've worked on anywhere."),
            ("Renee", "Yard Driver", "I know exactly how my work gets product to a shelf."),
            ("Marcus", "Area Manager", "We promote from the floor. That's not a slogan here."),
        ],
    },
    "healthcare": {
        "tiles": ("Care", "Community", "Growth"),
        "headline": "Care for the communities you call home",
        "cta": "See all healthcare roles",
        "photos": ("area-healthcare.jpg", "jobhero-wm-2.jpg"),
        "quote": "Our pharmacies, vision centers and clinics put affordable care within a short drive "
                 "of most of the country - and our associates make it personal.",
        "testimonials": [
            ("Yasinya", "Pharmacy Tech", "Patients know my name. That's the part I love."),
            ("Andre", "Optician", "Every fitting is a small problem to solve well."),
            ("Priya", "Pharmacy Manager", "Walmart paid for my certification through Live Better U."),
        ],
    },
    "technology": {
        "tiles": ("Belonging", "Impact"),
        "headline": "Tech with real-world impact",
        "cta": "See all technology roles",
        "photos": ("area-technology-2.jpg", "supply-drone.jpg"),
        "quote": "Our vision is strong here. Walmart Global Tech works at the forefront of "
                 "cutting-edge technologies inspired by the vision of transforming retail tech.",
        "hubs_heading": "Four hubs. One mission. Endless possibilities",
        "hubs_blurb": "Our hubs spark collaboration and innovation, so you're free to energize and push "
                      "boundaries from the space that serves you best.",
        "testimonials": [
            ("Tatiana", "Software Engineer (iOS)", "The scale of what ships every week still amazes me."),
            ("Christopher", "Senior Manager, Food Media Insights",
             "We're data geeks, and the depth we get to explore here keeps us excited every single day."),
            ("Antony", "Yield Manager", "I get to work on problems no other retailer has."),
        ],
    },
    "corporate": {
        "tiles": ("Curiosity", "Ownership", "Impact"),
        "headline": "Shape how the world shops",
        "cta": "See all corporate roles",
        "photos": ("area-corporate-2.jpg", "jobhero-corp-3.jpg"),
        "quote": "From merchandising to finance to people, our home office teams make decisions that "
                 "reach 240 million customers a week.",
        "hubs_heading": "Hubs built for the way you work",
        "hubs_blurb": "Bentonville, Sunnyvale, Hoboken and Dallas: pick the space that serves you best.",
        "testimonials": [
            ("Jorden", "Associate Merchant", "I own a category. At 26. That doesn't happen elsewhere."),
            ("Nina", "Finance Manager", "The numbers are big, but the teams are small and close."),
            ("Sam", "People Partner", "We hire for potential and then we invest in it."),
        ],
    },
    "Military": {
        "tiles": ("Transition", "Translate", "Thrive"),
        "headline": "Walmart supports Veterans",
        "cta": "See all opportunities",
        "photos": ("area-military.jpg", "military-banner.png"),
        "quote": "Every day, thousands of veterans build careers at Walmart. Learn more about our "
                 "commitment to veterans and military families.",
        "testimonials": [
            ("Mark", "Veteran, Store Coach", "My leadership experience translated on day one."),
            ("Kim", "Store Manager", "Walmart's not only committed to the veteran - veteran spouses have just the same opportunity."),
            ("Jeremy", "Club Manager", "SkillBridge got me in the door. The team kept me here."),
        ],
    },
}
AREA_PAGE_DEFAULT = {
    "tiles": ("Purpose", "Growth", "Pride"),
    "headline": "Grow your future. Make an impact.",
    "cta": "See all open roles",
    "photos": ("area-stores-3.jpg", "area-stores-2.jpg"),
    "quote": LIFE_AT_WALMART_QUOTE,
    "testimonials": [],
}
INSPIRATION_HEADING = "Inspiration in every role"

# Locations page hero and the promo block on the saved-roles page.
LOCATIONS_HERO_IMAGE = "loc-silicon-valley.jpg"
SAVED_PROMO_HEADLINE = ("Get more out of", "Walmart Careers")
SAVED_PROMO_BLURB = (
    "With an account you get role recommendations, create job alerts, and view your application "
    "status from a personalized dashboard."
)
SAVED_PROMO_IMAGE = "area-healthcare.jpg"
SAVED_EMPTY_NOTE = "You have no saved roles."

# Footer links on the stripped sign-in / register layout.
AUTH_FOOTER_LINKS = [
    "Give feedback", "Terms of Use", "Privacy Notice", "California Supply Chain Act",
    "Your Privacy Choices", "Customer Privacy Center", "Notice at Collection",
]
AUTH_COPYRIGHT = "© 2026 Walmart. All Rights Reserved."


# --------------------------------------------------------------------------- #
# "Life at Walmart" on the detail pages: a lead sentence, the paragraphs beside
# the photo, the paragraphs under it, the blue quote band and the closing lines.
# Hourly postings use the field copy, salaried postings the home-office copy.
# --------------------------------------------------------------------------- #
LIFE_AT_WALMART_FIELD = {
    "lead": "At Walmart, you're welcome for who you are, no matter your background, experiences, "
            "or perspectives.",
    "left": [
        "Our stores and services are for everyone, and so is our workplace. We believe different "
        "experiences drive our ability to better serve our communities and deliver affordable "
        "products across the nation.",
        "Here, your unique insights and ideas are encouraged, valued, and essential to creating a "
        "forward-thinking company that thrives on fresh ideas and dedicated teamwork.",
    ],
    "right": [],
    "band": "Since our founding, we've focused on bringing affordable essentials to families "
            "everywhere, and today, Walmart is one of the most recognizable names in retail worldwide.",
    "closing": LIFE_AT_WALMART_QUOTE,
    "note": "We're driven by a commitment to make life better for millions of customers and support "
            "our associates with opportunities to grow, learn, and advance.",
    "photo": "jobhero-wm-4.jpg",
}
LIFE_AT_WALMART_CORP = {
    "lead": "Imagine a workplace surrounded by innovation. At Walmart's new Home Office in "
            "Bentonville, Arkansas, we're redefining what it means to work at a global leader.",
    "left": [
        "Set on 350 acres of thoughtfully revitalized land, our new campus seamlessly integrates "
        "the charm of Northwest Arkansas with cutting edge design and technology. From biking "
        "trails and outdoor courtyards to flexible, tech-enabled workspaces, every detail reflects "
        "our commitment to sustainability, connection, and culture.",
    ],
    "right": [
        "With amenities like on-site childcare at our Little Squiggles Children's Enrichment "
        "Center, the Walton Family Whole Health & Fitness Center, and a vibrant food hall "
        "featuring local and international favorites, we're creating a space where work-life "
        "balance isn't just a goal - it's a reality.",
        "Beyond the campus, Bentonville offers a dynamic lifestyle with world-class dining, art at "
        "the Crystal Bridges Museum, and countless outdoor activities.",
    ],
    "band": "Whether you're exploring High South cuisine, enjoying live performances at our new "
            "amphitheater, or cycling the Razorback Greenway, you'll experience the perfect blend "
            "of small-town charm and big-city amenities.",
    "closing": "Join us at Walmart and grow your career alongside a community that feels like home.",
    "note": "This isn't just a workplace - it's a destination for leaders eager to make a difference.",
    "photo": "life-home-office.jpg",
}

# Stores & Clubs L1: the "Meet Brandon" day-in-the-life block under the bento.
MEET_STORE_COACH = {
    "name": "Brandon",
    "kicker": "Day in the life",
    "role": "Walmart store coach",
    "blurb": "As a store coach, Brandon leads with energy, empathy, and focus. In this video, he "
             "shares what it takes to guide a team in one of Walmart's busiest stores - balancing "
             "daily priorities, supporting associates, and helping people grow.",
}

# Military L1: the two feature rows and the three program tiles under the hero.
MILITARY_FEATURES = [
    (
        "SkillBridge: Your Transition, Supported",
        "Preparing to separate from active duty? Through the DoD SkillBridge program, you can build "
        "career-ready skills with structured training and real-world experience while you're still "
        "serving. Explore opportunities designed to help you translate your military strengths into "
        "a long-term career at Walmart.",
        "Explore opportunities now",
        "area-military.jpg",
    ),
    (
        "Military skills translator",
        "Translate your military experience into civilian job skills. Use our tool to discover the "
        "best career opportunities that align with your unique qualifications.",
        "Explore now",
        "jobhero-corp-3.jpg",
    ),
]
MILITARY_PROGRAMS = [
    (
        "Discover Walmart: job simulations",
        "Experience various roles at Walmart through our flexible job simulations. Choose modules, "
        "upskill at your pace, and gain insights to succeed in the application process. Explore "
        "multiple career paths at Walmart.",
        "jobhero-corp-2.jpg",
    ),
    (
        "Internships: kickstart your career",
        "Our internship programs offer valuable opportunities for individuals at any stage of their "
        "education or career. Gain experience in various fields, apply your unique skills, receive "
        "mentorship, and get hands-on training that sets you apart in your chosen career path.",
        "area-students.png",
    ),
    (
        "Join our talent network",
        "Sign up for our talent network, participate in one of our engaging hiring events or "
        "military connected workshops designed to showcase diverse career paths and provide "
        "opportunities to network with Walmart professionals.",
        "area-corporate.jpg",
    ),
]

# How-we-hire page: hero photo, the intro beside each FAQ group, the job simulator block.
HIRING_HERO_IMAGE = "area-corporate-2.jpg"
HIRING_HERO_CTA = "Explore something new"
HIRING_FAQ_INTROS = [
    ("We're here to help you put your best foot forward. Get tips and guidance to feel confident "
     "as you take the first step toward a role that's right for you.", "benefit-wellbeing.svg"),
    ("You've taken a big step and we're glad you did! Here's what to expect next, plus answers to "
     "common questions to help you stay informed and encouraged along the way.", "benefit-pto.svg"),
]
HIRING_SIMULATOR = {
    "heading": "Experience a day in the role",
    "blurb": "Want to know what a role at Walmart and Sam's Club is really like? Our interactive job "
             "simulations give you a chance to preview the role, showcase your skills, and see if "
             "it's a good fit for you.",
    "cta": "Job simulator",
    "photo": "jobhero-corp-2.jpg",
}

# Apply flow: the first-party contact step's heading and hint.
APPLY_HEADING = "Let us know how to contact you"
APPLY_EMAIL_HINT = "Avoid using an email address you share with others"

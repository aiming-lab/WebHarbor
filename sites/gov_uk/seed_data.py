"""Idempotent seed data for the GOV.UK mirror.

Every seed_*() function early-returns if its primary table is already
populated — required by WebHarbor's byte-identity invariant for /reset.

All content is synthesized in the spirit of GOV.UK guidance.
"""
from datetime import datetime, date, timedelta


# ─── Source tables ───────────────────────────────────────────────────────

TOPICS = [
    ("benefits", "Benefits", "Includes eligibility, appeals, tax credits and Universal Credit", 10),
    ("births-deaths-marriages", "Births, deaths, marriages and care", "Parenting, civil partnerships, divorce and Lasting Power of Attorney", 20),
    ("business", "Business and self-employed", "Tools and guidance for businesses", 30),
    ("childcare", "Childcare and parenting", "Includes giving birth, fostering, adopting, benefits for children, childcare and schools", 40),
    ("citizenship", "Citizenship and living in the UK", "Voting, community participation, life in the UK, international projects", 50),
    ("crime-justice", "Crime, justice and the law", "Legal processes, courts and the police", 60),
    ("disabilities", "Disabled people", "Includes carers, your rights, benefits and the Equality Act", 70),
    ("driving", "Driving and transport", "Includes vehicle tax, MOT and driving licences", 80),
    ("education", "Education and learning", "Includes student finance and admissions", 90),
    ("employment", "Employing people", "Includes pay, contracts and hiring", 100),
    ("environment", "Environment and countryside", "Includes flooding, recycling and wildlife", 110),
    ("housing", "Housing and local services", "Owning or renting and council services", 120),
    ("money", "Money and tax", "Includes debt and Self Assessment", 130),
    ("passports", "Passports, travel and living abroad", "Includes renewing passports and travel advice by country", 140),
    ("visas-immigration", "Visas and immigration", "Apply to visit, work, study, settle or seek asylum in the UK", 150),
    ("working", "Working, jobs and pensions", "Includes holidays and finding a job", 160),
]


# (topic_slug, subtopic_slug, name, description)
SUBTOPICS = [
    # benefits
    ("benefits", "universal-credit", "Universal Credit", "Apply, manage your claim, payments and changes"),
    ("benefits", "tax-credits", "Tax credits", "Working Tax Credit and Child Tax Credit"),
    ("benefits", "appeals", "Benefit appeals and overpayments", "Challenge a decision, mandatory reconsideration"),
    # births-deaths-marriages
    ("births-deaths-marriages", "register-a-birth", "Register a birth", "How to register a birth in England, Wales, Scotland and Northern Ireland"),
    ("births-deaths-marriages", "marriage-civil-partnership", "Marriage and civil partnership", "Give notice, ceremonies, change name"),
    ("births-deaths-marriages", "lasting-power-of-attorney", "Lasting power of attorney", "Make, register, use and cancel"),
    # business
    ("business", "setting-up", "Setting up a business", "Sole trader, limited company, business names"),
    ("business", "running-a-limited-company", "Running a limited company", "Directors, accounts, Corporation Tax"),
    ("business", "vat", "VAT", "Register, returns, schemes and rates"),
    # childcare
    ("childcare", "child-benefit", "Child Benefit", "Eligibility, claim, payments"),
    ("childcare", "school-admissions", "School admissions and term dates", "Apply for a school place, appeals"),
    # citizenship
    ("citizenship", "british-citizenship", "Become a British citizen", "Apply, eligibility, ceremonies"),
    ("citizenship", "voting", "Voting and elections", "Register to vote, postal and proxy voting"),
    # crime-justice
    ("crime-justice", "reporting-crime", "Reporting a crime", "Report online, in person, anonymously"),
    ("crime-justice", "courts", "Going to court", "Magistrates, Crown, civil claims, juries"),
    ("crime-justice", "criminal-records", "Criminal records and DBS checks", "Basic, Standard, Enhanced, eligibility"),
    # disabilities
    ("disabilities", "pip", "Personal Independence Payment (PIP)", "Apply, eligibility, assessments"),
    ("disabilities", "blue-badge", "Blue Badge scheme", "Apply for or renew a Blue Badge"),
    # driving
    ("driving", "driving-licences", "Driving licences", "Provisional, full, renewing and replacing"),
    ("driving", "vehicle-tax", "Vehicle tax, MOT and insurance", "Tax your vehicle, MOT, SORN, insurance rules"),
    ("driving", "learning-to-drive", "Learning to drive", "Theory test, driving test, lessons"),
    # education
    ("education", "student-finance", "Student finance", "Loans, grants and applying"),
    ("education", "ucas", "University and higher education", "Applications, courses, UCAS"),
    ("education", "apprenticeships", "Apprenticeships, 14 to 19 education", "Find an apprenticeship, T levels"),
    # employment
    ("employment", "paye", "PAYE for employers", "Register, payroll, deductions"),
    ("employment", "contracts", "Employment contracts", "Statements, working hours, breaks"),
    # environment
    ("environment", "flooding", "Flooding and extreme weather", "Risk, alerts, recovery"),
    ("environment", "wildlife", "Wildlife and animals", "Protected species, licences"),
    # housing
    ("housing", "council-tax", "Council Tax", "Bands, discounts, exemptions"),
    ("housing", "renting", "Renting a home", "Deposits, repairs, eviction"),
    ("housing", "planning-permission", "Planning permission and building rules", "Apply, appeals, building regulations"),
    # money
    ("money", "self-assessment", "Self Assessment", "Register, file, pay, deadlines"),
    ("money", "income-tax", "Income Tax", "Allowances, rates, codes"),
    ("money", "national-insurance", "National Insurance", "Numbers, contributions, voluntary payments"),
    ("money", "capital-gains-tax", "Capital Gains Tax", "Rates, reporting, reliefs"),
    # passports
    ("passports", "apply-renew-passport", "Apply or renew a passport", "Adult, child, urgent, replace"),
    ("passports", "travel-abroad", "Travel abroad", "Foreign travel advice, entry requirements"),
    # visas-immigration
    ("visas-immigration", "visit-uk", "Visit the UK", "Standard Visitor visa, transit"),
    ("visas-immigration", "work-uk", "Work in the UK", "Skilled Worker, Health and Care Worker"),
    ("visas-immigration", "study-uk", "Study in the UK", "Student visa, Child Student visa"),
    ("visas-immigration", "settle-uk", "Settle in the UK", "Indefinite Leave to Remain, family routes"),
    # working
    ("working", "find-job", "Finding a job", "Search vacancies, CVs, interviews"),
    ("working", "state-pension", "State Pension", "Eligibility, claim, top up"),
    ("working", "redundancy", "Redundancy, dismissal and disputes", "Notice, pay, tribunals"),
]


DEPARTMENTS = [
    # slug, name, abbrev, kind, minister, perm sec, employees, established, description
    ("cabinet-office", "Cabinet Office", "CO", "Ministerial department",
     "Rt Hon Pat McFadden MP", "Cat Little CB",
     7800, "1916",
     "Supports the Prime Minister and ensures the effective running of government."),
    ("hm-treasury", "HM Treasury", "HMT", "Ministerial department",
     "Rt Hon Rachel Reeves MP", "James Bowler CB",
     2700, "1066",
     "The government's economic and finance ministry. Maintains control over public spending and sets the direction of the UK's economic policy."),
    ("hm-revenue-customs", "HM Revenue & Customs", "HMRC", "Non-ministerial department",
     "Rt Hon James Murray MP (Exchequer Secretary)", "Sir Jim Harra KCB",
     66000, "2005",
     "Collects taxes, pays some forms of state support and administers other regulatory regimes including the national minimum wage."),
    ("department-for-education", "Department for Education", "DfE", "Ministerial department",
     "Rt Hon Bridget Phillipson MP", "Susan Acland-Hood",
     8400, "1992",
     "Responsible for children's services and education, including early years, schools, higher and further education policy."),
    ("department-of-health-social-care", "Department of Health and Social Care", "DHSC", "Ministerial department",
     "Rt Hon Wes Streeting MP", "Sir Chris Wormald KCB",
     2900, "2018",
     "Helps people live more independent, healthier lives for longer."),
    ("home-office", "Home Office", "HO", "Ministerial department",
     "Rt Hon Yvette Cooper MP", "Sir Matthew Rycroft KCMG CBE",
     38000, "1782",
     "The lead government department for immigration and passports, drugs policy, crime, fire, counter-terrorism and police."),
    ("ministry-of-justice", "Ministry of Justice", "MoJ", "Ministerial department",
     "Rt Hon Shabana Mahmood MP", "Antonia Romeo CB",
     78000, "2007",
     "Works to protect and advance the principles of justice."),
    ("department-for-transport", "Department for Transport", "DfT", "Ministerial department",
     "Rt Hon Louise Haigh MP", "Dame Bernadette Kelly DBE",
     16000, "1919",
     "Works with agencies and partners to support the transport network that helps the UK's businesses and gets people and goods travelling around the country."),
    ("dvla", "Driver and Vehicle Licensing Agency", "DVLA", "Executive agency",
     "(part of DfT)", "Julie Lennard",
     6000, "1965",
     "DVLA maintains registers of drivers and vehicles, and collects vehicle excise duty."),
    ("dwp", "Department for Work and Pensions", "DWP", "Ministerial department",
     "Rt Hon Liz Kendall MP", "Sir Peter Schofield KCB",
     82000, "2001",
     "Responsible for welfare, pensions and child maintenance policy."),
    ("defra", "Department for Environment, Food and Rural Affairs", "Defra", "Ministerial department",
     "Rt Hon Steve Reed MP", "Tamara Finkelstein CB",
     6600, "2001",
     "Responsible for safeguarding the natural environment, supporting the food and farming industry, and sustaining a thriving rural economy."),
    ("foreign-commonwealth-development-office", "Foreign, Commonwealth & Development Office", "FCDO", "Ministerial department",
     "Rt Hon David Lammy MP", "Sir Philip Barton KCMG OBE",
     17000, "2020",
     "Pursues the national interests of the United Kingdom and projects the country as a force for good in the world."),
    ("hm-passport-office", "His Majesty's Passport Office", "HMPO", "Executive agency",
     "(part of Home Office)", "Abi Tierney",
     4500, "1998",
     "The sole issuer of UK passports and responsible for civil registration services through the General Register Office."),
    ("companies-house", "Companies House", "CH", "Executive agency",
     "(part of DBT)", "Louise Smyth CB",
     4000, "1844",
     "Companies House incorporates and dissolves limited companies, registers company information and makes it available to the public."),
    ("nhs-england", "NHS England", "NHSE", "Non-departmental public body",
     "(arms-length body of DHSC)", "Amanda Pritchard",
     14000, "2013",
     "Leads the National Health Service in England and sets the priorities and direction of the NHS."),
]


# Per-subtopic article seeds: (subtopic_slug, dept_slug, [(title, summary, body, kind)])
def _para(*ps):
    return "\n\n".join(ps)


ARTICLES = [
    # ── Money / Self Assessment ──
    ("self-assessment", "hm-revenue-customs", [
        ("File your Self Assessment tax return",
         "Use this service to send your Self Assessment tax return to HMRC online.",
         _para(
            "You can file your Self Assessment tax return online if you have a Government Gateway user ID and password. If you do not have an account, you can create one when you start.",
            "The deadline for online returns is 31 January following the end of the tax year. You'll be charged a penalty if you miss the deadline, even if you do not owe any tax.",
            "Before you start, gather your records: P60, P45, P11D, bank interest statements, dividend vouchers and details of any other income or expenses.",
            "If you need help, you can use the online assistant or contact HMRC by phone. HMRC cannot tell you how much tax you owe — the service calculates that for you when you submit the return.",
         ),
         "service"),
        ("Self Assessment deadlines",
         "When to file your tax return and when to pay any tax you owe.",
         _para(
            "Paper tax returns must reach HMRC by midnight on 31 October following the end of the tax year. Online returns must be filed by midnight on 31 January.",
            "You must pay any tax you owe by 31 January. If you make payments on account, the second payment is due by 31 July.",
            "Penalties start at £100 for filing one day late, with further penalties at 3, 6 and 12 months. Interest is also charged on tax paid late.",
         ),
         "guidance"),
        ("Register for Self Assessment",
         "When and how to register if you need to send a tax return.",
         _para(
            "You must register for Self Assessment if you are self-employed and earned more than £1,000, a partner in a business partnership, or have any other untaxed income.",
            "Register online by 5 October following the end of the tax year in which you became liable. HMRC will send you a Unique Taxpayer Reference (UTR) within 10 working days.",
            "Once registered, you can file your return online using your Government Gateway account.",
         ),
         "guidance"),
        ("Pay your Self Assessment tax bill",
         "Ways to pay including bank transfer, Direct Debit, debit card and at your bank.",
         _para(
            "Same-day or next-day options: online or telephone banking (Faster Payments), CHAPS, debit or corporate credit card online.",
            "3 working days: Bacs, Direct Debit (if you have set one up before), at your bank or building society, by cheque through the post.",
            "5 working days: Direct Debit set up for the first time.",
            "Your bill is your reference. Use your 11-character payment reference — your UTR followed by the letter K.",
         ),
         "guidance"),
    ]),
    # ── Money / Income Tax ──
    ("income-tax", "hm-revenue-customs", [
        ("Income Tax rates and Personal Allowances",
         "How much Income Tax you pay in each tax year depends on how much of your income is above your Personal Allowance and how much falls within each tax band.",
         _para(
            "The standard Personal Allowance is £12,570, which is the amount of income you do not have to pay tax on.",
            "The basic rate of 20% applies to taxable income from £1 to £37,700. The higher rate of 40% applies from £37,701 to £125,140. The additional rate of 45% applies above £125,140.",
            "Your Personal Allowance goes down by £1 for every £2 your adjusted net income is above £100,000. This means it is zero if your income is £125,140 or above.",
         ),
         "guidance"),
        ("Check your Income Tax for the current year",
         "Use this service to estimate your Income Tax, see your tax code, and update your details.",
         _para(
            "You can use this service to check how much Income Tax you should pay between 6 April and 5 April the following year, see your tax code and Personal Allowance, and update your employer or pension provider details.",
            "Sign in with your Government Gateway user ID. If you do not already have one, you can create one when you sign in.",
         ),
         "service"),
        ("Tax codes",
         "What your tax code means and how to update it.",
         _para(
            "Your tax code is used by your employer or pension provider to work out how much Income Tax to take from your pay or pension.",
            "1257L is the most common tax code for 2024 to 2025 — it represents the standard Personal Allowance.",
            "Letters in your code refer to your situation and how it affects your Personal Allowance. For example, BR means all your income is taxed at the basic rate.",
            "If you think your tax code is wrong, you can update your employment details using the check your Income Tax online service.",
         ),
         "guidance"),
    ]),
    # ── Money / National Insurance ──
    ("national-insurance", "hm-revenue-customs", [
        ("National Insurance: introduction",
         "What National Insurance is, who pays it, and how to get a number.",
         _para(
            "You pay National Insurance to qualify for certain benefits and the State Pension. You need a National Insurance number before you can start paying.",
            "You pay mandatory National Insurance if you are 16 or over and either employed and earning above £242 a week, or self-employed and making a profit of more than £6,725 a year.",
            "You stop paying Class 1 and Class 2 contributions when you reach State Pension age.",
         ),
         "guidance"),
        ("Apply for a National Insurance number",
         "How to apply for a National Insurance number if you live in the UK.",
         _para(
            "You can apply for a National Insurance number if you have the right to work or study in the UK. You may already have a National Insurance number if it is printed on the back of your biometric residence permit.",
            "Apply online — you will need to prove your identity. After you apply, you will be told what to do next, including any documents you need to send and any appointments you need to attend.",
            "It usually takes 4 weeks to get your National Insurance number after you have proved your identity.",
         ),
         "service"),
    ]),
    # ── Money / Capital Gains Tax ──
    ("capital-gains-tax", "hm-revenue-customs", [
        ("Capital Gains Tax: what you pay it on, rates and allowances",
         "Overview of Capital Gains Tax including the annual exempt amount and current rates.",
         _para(
            "Capital Gains Tax is a tax on the profit when you sell something — an asset — that has increased in value. It is the gain you make that is taxed, not the amount of money you receive.",
            "The annual exempt amount for the 2024 to 2025 tax year is £3,000 for individuals.",
            "Basic rate taxpayers pay 10% on most gains and 18% on residential property. Higher and additional rate taxpayers pay 20% on most gains and 24% on residential property.",
         ),
         "guidance"),
        ("Report and pay your Capital Gains Tax",
         "How to report Capital Gains Tax on UK property within 60 days of completion.",
         _para(
            "If you sold a UK residential property on or after 27 October 2021, you must report and pay any Capital Gains Tax due within 60 days of the completion date.",
            "Use the Capital Gains Tax on UK property service. You will need a Government Gateway user ID and password.",
            "If you do not pay on time, you may be charged interest and a late payment penalty.",
         ),
         "service"),
    ]),
    # ── Driving / Licences ──
    ("driving-licences", "dvla", [
        ("Apply for your first provisional driving licence",
         "Apply online for a provisional driving licence for a car, moped or motorcycle.",
         _para(
            "You can apply for your first provisional driving licence from the DVLA online. The cost is £34 when you apply online.",
            "You can start learning to drive a car when you are 17. You can apply for a provisional driving licence when you are 15 years and 9 months old.",
            "To apply you need to be a resident of Great Britain, meet the minimum age requirement, meet the minimum eyesight requirement, provide an identity document, and provide addresses where you have lived over the last 3 years.",
         ),
         "service"),
        ("Renew your driving licence",
         "Renew online if your licence is valid for 10 years and you are renewing in your current name.",
         _para(
            "You must renew your photocard driving licence every 10 years. DVLA will send you a reminder before your current licence expires.",
            "It costs £14 to renew online. You will need your old photocard licence, addresses where you have lived for the last 3 years, and your National Insurance number if you know it.",
            "You can also renew at a Post Office that has the Post Office digital photo and signature service.",
         ),
         "service"),
        ("Driving licence categories",
         "What you can drive with each category on your licence.",
         _para(
            "Category B is the standard car category. It lets you drive vehicles up to 3,500kg MAM with up to 8 passenger seats, with a trailer of up to 750kg.",
            "Category A covers motorcycles. Subcategories A1 (light), A2 (medium) and A (unrestricted) depend on age and experience.",
            "Category C is for large goods vehicles over 3,500kg, and category D is for buses and coaches with more than 8 passenger seats.",
         ),
         "guidance"),
    ]),
    # ── Driving / Vehicle tax ──
    ("vehicle-tax", "dvla", [
        ("Tax your vehicle",
         "Tax your car, motorcycle or other vehicle using a reference number from a recent reminder (V11), V5C or new keeper supplement.",
         _para(
            "You can pay vehicle tax online, by phone or at a Post Office that deals with vehicle tax.",
            "Before you tax your vehicle you need to have insurance in place. The MOT must also be valid.",
            "You can pay by Direct Debit, debit or credit card. Direct Debit is available for 6 monthly or 12 monthly payments — a 5% surcharge applies to 6 monthly Direct Debits.",
         ),
         "service"),
        ("Check if a vehicle is taxed",
         "Find out whether a vehicle has up-to-date vehicle tax and when its MOT expires.",
         _para(
            "Use this service to check the tax and MOT status of any vehicle registered in the UK. You only need the vehicle registration number.",
            "If the vehicle is not taxed and is being kept on a public road, you should report it to DVLA.",
         ),
         "service"),
        ("Statutory Off Road Notification (SORN)",
         "Tell DVLA your vehicle is off the road, for example if you are keeping it in a garage.",
         _para(
            "You must register your vehicle as off the road with a Statutory Off Road Notification (SORN) if you are not using it on the road and not paying vehicle tax or insuring it.",
            "You can apply online or by post. There is no charge.",
            "Your SORN lasts indefinitely. You cannot transfer it to a new keeper — they need to make a new SORN if they want to keep the vehicle off the road.",
         ),
         "service"),
    ]),
    # ── Driving / Learning to drive ──
    ("learning-to-drive", "dvla", [
        ("Book your theory test",
         "Book your car, motorcycle, lorry, bus or coach theory test.",
         _para(
            "You can take your theory test at any age once you have a provisional licence.",
            "It costs £23 to book your theory test online. You need your UK driving licence number and an email address.",
            "The theory test has two parts: multiple-choice questions and a hazard perception test. You must pass both parts to pass the theory test.",
         ),
         "service"),
        ("Book your driving test",
         "Book your practical driving test for a car, motorcycle, lorry or bus.",
         _para(
            "You can only book your practical driving test once you have passed the theory test.",
            "It costs £62 on a weekday or £75 on an evening, weekend or bank holiday.",
            "You will need your UK driving licence number, your theory test pass certificate number and a debit or credit card.",
         ),
         "service"),
    ]),
    # ── Visas / Visit ──
    ("visit-uk", "home-office", [
        ("Standard Visitor visa",
         "Apply to come to the UK as a Standard Visitor for tourism, business, study (courses up to 6 months) and other permitted activities.",
         _para(
            "You can usually stay in the UK for up to 6 months. The application fee is £115.",
            "You can apply for a Standard Visitor visa online from outside the UK. You should apply no more than 3 months before you travel.",
            "You will need to prove you will leave the UK at the end of your visit, that you are able to support yourself and your dependants, that you can pay for your return or onward journey, and that you will not live in the UK for extended periods through frequent visits.",
         ),
         "service"),
        ("Electronic Travel Authorisation (ETA)",
         "Get an ETA to travel to the UK if you do not need a visa for short stays.",
         _para(
            "You may need an Electronic Travel Authorisation (ETA) to travel to the UK. It costs £10. An ETA is digitally linked to your passport.",
            "You should apply online before you travel. Most decisions are made within 3 working days, though it can be quicker.",
            "An ETA lets you visit the UK for up to 6 months for tourism, visiting family, business or short-term study. It does not guarantee entry — Border Force may still refuse you.",
         ),
         "service"),
    ]),
    # ── Visas / Work ──
    ("work-uk", "home-office", [
        ("Skilled Worker visa",
         "Apply, extend or switch to a Skilled Worker visa to work for an approved UK employer.",
         _para(
            "You can apply for a Skilled Worker visa if you have been offered a skilled job in the UK by a Home Office approved sponsor.",
            "The job must be on the list of eligible occupations and pay at least £38,700 per year or the going rate for the role, whichever is higher.",
            "The application fee depends on whether you are applying from inside or outside the UK and how long you are staying. You will also need to pay the immigration health surcharge.",
            "A Skilled Worker visa can be granted for up to 5 years before you need to extend it. You can apply to settle permanently in the UK (Indefinite Leave to Remain) once you have lived in the UK for 5 years.",
         ),
         "service"),
        ("Health and Care Worker visa",
         "Apply for a Health and Care Worker visa to work in an eligible health or social care role.",
         _para(
            "The Health and Care Worker visa allows medical professionals to come to or stay in the UK to do an eligible job with the NHS, an NHS supplier or in adult social care.",
            "You'll get reduced visa application fees and you will not need to pay the immigration health surcharge.",
            "You must work for a UK employer that has been approved by the Home Office and have a certificate of sponsorship.",
         ),
         "service"),
    ]),
    # ── Visas / Study ──
    ("study-uk", "home-office", [
        ("Student visa",
         "Apply for a Student visa to study at a UK university or other eligible institution.",
         _para(
            "You can apply for a Student visa to study in the UK if you are 16 or over, have been offered a place on a course by a licensed student sponsor, have enough money to support yourself, and can speak, read, write and understand English.",
            "You can apply for a visa up to 6 months before the start of your course. The decision usually takes 3 weeks.",
            "The application fee from outside the UK is £490. You will also pay the immigration health surcharge.",
         ),
         "service"),
        ("Graduate visa",
         "Apply for a Graduate visa to stay in the UK after successfully completing a course.",
         _para(
            "You can apply for a Graduate visa if you are in the UK, your current visa is a Student visa or Tier 4 (General) student visa, and you have studied a UK bachelor's degree, postgraduate degree or other eligible course for a minimum period of time with your Student visa.",
            "A Graduate visa lasts for 2 years (3 years for PhD graduates). You can work, look for work or take further study.",
            "The application fee is £822 and you must pay the immigration health surcharge.",
         ),
         "service"),
    ]),
    # ── Visas / Settle ──
    ("settle-uk", "home-office", [
        ("Apply to settle in the UK",
         "Indefinite Leave to Remain (ILR) lets you live, work and study here for as long as you like.",
         _para(
            "You can usually apply for Indefinite Leave to Remain once you have lived in the UK for 5 continuous years on certain visas, including the Skilled Worker visa, Spouse visa, Ancestry visa and Global Talent visa.",
            "You will need to pass the Life in the UK Test and prove your knowledge of English.",
            "The application fee is £2,885 per person.",
         ),
         "service"),
    ]),
    # ── Passports ──
    ("apply-renew-passport", "hm-passport-office", [
        ("Apply for or renew an adult passport",
         "Renew, replace or apply for your first adult passport.",
         _para(
            "You can apply for a passport online. It costs £88.50 online or £100 by paper application.",
            "You will need a digital photo and a debit or credit card. You may also need to send your old passport and any other supporting documents.",
            "Most applications are processed within 3 weeks. Use the urgent service if you need a passport quickly — it costs more.",
         ),
         "service"),
        ("Get a child's first passport",
         "Apply for a passport for a child under 16 from the UK or abroad.",
         _para(
            "It costs £61.50 to apply online or £73 to apply by paper form.",
            "You will need a digital photo of the child and details of one parent. The application must be countersigned.",
            "A child passport lasts 5 years. The child does not need to renew it unless they want to.",
         ),
         "service"),
        ("Get a passport urgently",
         "Use the 1 week Fast Track service or the 1 day Premium service.",
         _para(
            "The 1 week Fast Track service costs £166.50 for an adult passport and £146.50 for a child. You attend an appointment at a passport office and collect your new passport 1 week later.",
            "The 1 day Premium service costs £207.50 for an adult passport. You attend an appointment and collect your new passport the same day.",
            "Book the urgent service online before you complete the application. Appointments are limited and book up quickly.",
         ),
         "service"),
    ]),
    # ── Passports / Travel ──
    ("travel-abroad", "foreign-commonwealth-development-office", [
        ("Foreign travel advice",
         "Country-by-country advice covering entry requirements, safety and security, health and natural hazards.",
         _para(
            "FCDO offers travel advice to help you make informed decisions about foreign travel.",
            "Advice is reviewed regularly and changes if our assessment of risks to British people changes.",
            "You can sign up for email alerts to get updates as soon as our advice for a country changes.",
         ),
         "guidance"),
        ("Get an emergency travel document",
         "Apply for an emergency travel document if you are abroad and need to travel within 7 days.",
         _para(
            "An emergency travel document is for one-way travel — getting home, or to a country where you have a visa to enter.",
            "It costs £100. You will need a passport-style photo, evidence of your travel plans, and proof of identity.",
            "Apply online and book an appointment at the nearest British embassy or consulate.",
         ),
         "service"),
    ]),
    # ── Childcare / Child Benefit ──
    ("child-benefit", "hm-revenue-customs", [
        ("Child Benefit: eligibility",
         "When you can claim Child Benefit and how much you get.",
         _para(
            "You get Child Benefit if you are responsible for bringing up a child who is under 16, or under 20 if they stay in approved education or training.",
            "Only one person can get Child Benefit for a child. There is no limit to how many children you can claim for.",
            "It is paid every 4 weeks. The current rate is £25.60 a week for your eldest or only child and £16.95 a week for each additional child.",
         ),
         "guidance"),
        ("High Income Child Benefit Charge",
         "If you or your partner earn more than £60,000 a year, you may have to pay back some of the Child Benefit through a tax charge.",
         _para(
            "You may have to pay the High Income Child Benefit Charge if you or your partner have an individual income that is over £60,000.",
            "Between £60,000 and £80,000 the charge increases gradually. Above £80,000 the charge is equal to the full Child Benefit amount.",
            "You can choose not to receive Child Benefit if you do not want to pay the charge, but you should still complete the claim form so that you protect your State Pension entitlement.",
         ),
         "guidance"),
    ]),
    # ── Childcare / School admissions ──
    ("school-admissions", "department-for-education", [
        ("Apply for a primary school place",
         "Apply for a primary school place through your local council.",
         _para(
            "You apply for a place at a primary school in England through your local council, even if you are applying for a school in a different council area.",
            "Applications open in the autumn. The national closing date is 15 January for primary school places starting in September.",
            "Offers are usually made on 16 April. You will be told how to accept or decline the offer and how to appeal if you are not offered a place at your preferred school.",
         ),
         "service"),
        ("Apply for a secondary school place",
         "Apply for a secondary school place through your local council.",
         _para(
            "Apply for a place through your local council. The national closing date is 31 October.",
            "Offers are made on 1 March. If you are not offered a place at any of your preferred schools, your council will offer you a place at another school within reasonable distance.",
         ),
         "service"),
    ]),
    # ── Benefits / Universal Credit ──
    ("universal-credit", "dwp", [
        ("Universal Credit: how it works",
         "What Universal Credit is, who can claim and what you might get.",
         _para(
            "Universal Credit is a payment to help with your living costs. It is paid monthly, or twice a month for some people in Scotland.",
            "You may be able to get it if you are on a low income, out of work or cannot work.",
            "Universal Credit replaces Jobseeker's Allowance, Income Support, Working Tax Credit, Child Tax Credit, Employment and Support Allowance and Housing Benefit.",
         ),
         "guidance"),
        ("Make a Universal Credit claim",
         "How to claim Universal Credit online.",
         _para(
            "You apply for Universal Credit online. You must make a claim with your partner if you live together.",
            "You will need your bank account details, an email address, information about your housing, details of your income, savings and investments, and details of how much you pay for childcare if you are claiming for help with childcare costs.",
            "You will usually receive your first payment 5 weeks after making a claim. You can apply for an advance if you cannot wait.",
         ),
         "service"),
    ]),
    # ── Benefits / Tax credits ──
    ("tax-credits", "hm-revenue-customs", [
        ("Tax credits: end of award",
         "Tax credits are ending. Most people now claim Universal Credit instead.",
         _para(
            "Tax credits ended on 5 April 2025. You can no longer make a new claim for tax credits.",
            "If you still receive tax credits, HMRC will write to you to explain how to move to Universal Credit or Pension Credit.",
            "Do not make a claim for Universal Credit until you receive a Migration Notice letter — moving across at the right time protects your existing award level.",
         ),
         "guidance"),
    ]),
    # ── Crime / Reporting ──
    ("reporting-crime", "home-office", [
        ("Report a crime",
         "How to report a crime to the police, including online and anonymously.",
         _para(
            "Call 999 if a crime is in progress or someone is in danger. For non-urgent crime, call 101 or report online to your local police force.",
            "You can report anonymously to Crimestoppers on 0800 555 111 or via the Crimestoppers website. They will never ask for your name or take any personal details.",
            "Action Fraud is the national reporting centre for fraud and cybercrime. Report to Action Fraud online or on 0300 123 2040.",
         ),
         "guidance"),
        ("Report online fraud",
         "How to report fraud and cybercrime to Action Fraud.",
         _para(
            "Report fraud to Action Fraud, the national reporting centre for fraud and cybercrime.",
            "Report online at the Action Fraud website or call 0300 123 2040, Monday to Friday between 8am and 8pm.",
            "If you are deaf or hard of hearing, use textphone 0300 123 2050.",
         ),
         "service"),
    ]),
    # ── Crime / Criminal records ──
    ("criminal-records", "home-office", [
        ("Apply for a Basic DBS check",
         "Apply for a Basic DBS check to show your unspent convictions and conditional cautions.",
         _para(
            "A Basic DBS check shows any unspent convictions and conditional cautions you have. Anyone can apply, whatever job they do.",
            "It costs £18 and you apply online via the DBS website.",
            "It can take up to 14 days to receive your certificate.",
         ),
         "service"),
    ]),
    # ── Housing / Council Tax ──
    ("council-tax", "department-for-transport", [
        ("Council Tax",
         "Council Tax is an annual fee your local council charges you for the services it provides.",
         _para(
            "How much Council Tax you pay depends on the property's valuation band and where it is located.",
            "There are 8 bands in England (A to H). The band is based on the value of your property as of 1 April 1991.",
            "You may be able to pay less Council Tax — for example if you live alone, have a low income, or are a full-time student.",
         ),
         "guidance"),
    ]),
    # ── Housing / Renting ──
    ("renting", "department-for-transport", [
        ("Private renting: tenancy agreements",
         "Your rights and responsibilities when you rent a home from a private landlord.",
         _para(
            "Most tenants do not have a right in law to a written tenancy agreement. However, social housing tenants like council and housing association tenants should normally be provided with a written tenancy agreement.",
            "Your landlord must put your deposit in a government-approved tenancy deposit scheme within 30 days of getting it.",
            "Your landlord must keep the property safe and free from health hazards, make sure all gas equipment and electrical equipment is safely installed and maintained, and provide an Energy Performance Certificate.",
         ),
         "guidance"),
    ]),
    # ── Housing / Planning permission ──
    ("planning-permission", "department-for-transport", [
        ("Apply for planning permission",
         "When you need planning permission and how to apply.",
         _para(
            "You need to apply for planning permission for many building works including building something new, making a major change to your building, or changing the use of your building.",
            "Apply through the Planning Portal or your local council. There is a fee, which depends on the type of work.",
            "If you carry out building work without permission when it was needed, you might be asked to undo the work — for example, knock down what you built or restore the building to how it was.",
         ),
         "service"),
    ]),
    # ── Working / State Pension ──
    ("state-pension", "dwp", [
        ("Check your State Pension forecast",
         "Check your State Pension age, your State Pension forecast and ways to increase it.",
         _para(
            "Use this service to find out how much State Pension you could get, when you can get it, and how to increase it if you can.",
            "Sign in with your Government Gateway user ID or use GOV.UK One Login. You will need to prove your identity.",
            "The forecast is based on your current National Insurance record. The actual amount could be different.",
         ),
         "service"),
        ("The new State Pension",
         "Eligibility, what you'll get and how to claim if you reach State Pension age on or after 6 April 2016.",
         _para(
            "The full new State Pension is £221.20 per week for 2024 to 2025. You will get the new State Pension if you reach State Pension age on or after 6 April 2016, and you are a man born on or after 6 April 1951, or a woman born on or after 6 April 1953.",
            "You will usually need at least 10 qualifying years on your National Insurance record to get any new State Pension. They do not have to be 10 qualifying years in a row.",
            "You will usually need 35 qualifying years to get the full new State Pension.",
         ),
         "guidance"),
    ]),
    # ── Working / Find a job ──
    ("find-job", "dwp", [
        ("Find a job through Find a job",
         "Search and apply for jobs in Great Britain on the Find a job service.",
         _para(
            "Find a job is a service from the Department for Work and Pensions. It is free for jobseekers and for employers to post vacancies.",
            "You can search by location, distance, job type and salary, then apply directly through the service.",
            "Create a profile to upload your CV, set up email alerts for new jobs and track your applications.",
         ),
         "service"),
    ]),
    # ── Working / Redundancy ──
    ("redundancy", "dwp", [
        ("Redundancy: your rights",
         "What you are entitled to if you are made redundant, including notice and pay.",
         _para(
            "You have specific rights if you are made redundant, including a statutory redundancy payment if you have worked for your employer for at least 2 years.",
            "Statutory redundancy pay is calculated based on your age, weekly pay and years of service. It is capped at £700 a week and £21,000 in total.",
            "You also have the right to a notice period of at least one week for each year of service, up to a maximum of 12 weeks.",
         ),
         "guidance"),
    ]),
    # ── Education / Student finance ──
    ("student-finance", "department-for-education", [
        ("Student finance for undergraduates",
         "Tuition Fee Loans, Maintenance Loans and extra grants.",
         _para(
            "You can apply for a Tuition Fee Loan to pay for your course. It is paid directly to your university or college and you start repaying after you graduate, when you earn over £27,295 a year.",
            "You can apply for a Maintenance Loan to help with living costs. How much you get depends on where you live and study, and your household income.",
            "Extra grants are available for students with children, an adult dependant or a disability.",
         ),
         "guidance"),
        ("Repaying your student loan",
         "How and when you start to repay your student loan.",
         _para(
            "You start repaying your student loan the April after you finish or leave your course, but only when your income is over the threshold.",
            "For Plan 2 loans (most students starting university in or after 2012), the threshold is £27,295 a year. You repay 9% of your income above the threshold.",
            "Your loan is written off 30 years after you became eligible to repay.",
         ),
         "guidance"),
    ]),
    # ── Education / UCAS ──
    ("ucas", "department-for-education", [
        ("Apply to university",
         "How to apply to a UK university or higher education course.",
         _para(
            "You apply to most UK universities through UCAS (Universities and Colleges Admissions Service). You can apply for up to 5 courses.",
            "The main deadline for most courses is 31 January. For Oxford, Cambridge and most medicine, dentistry and veterinary courses, the deadline is 16 October.",
            "Through UCAS Clearing, you can find a place on a course if you do not have a confirmed offer.",
         ),
         "guidance"),
    ]),
    # ── Education / Apprenticeships ──
    ("apprenticeships", "department-for-education", [
        ("Become an apprentice",
         "Find an apprenticeship and apply to start your career.",
         _para(
            "An apprenticeship is a job with training. As an apprentice you'll earn while you learn and get hands-on experience with an employer.",
            "There are 4 levels — intermediate (level 2) up to degree (levels 6 and 7). They typically take between 1 and 5 years to complete.",
            "Search for apprenticeships on the Find an apprenticeship service. You can apply for as many apprenticeships as you like.",
         ),
         "service"),
    ]),
    # ── Disabilities / PIP ──
    ("pip", "dwp", [
        ("Personal Independence Payment (PIP)",
         "Help with extra living costs if you have a long-term health condition or disability.",
         _para(
            "PIP is for people aged 16 to State Pension age. It has two parts: a daily living part and a mobility part. You may get one or both parts.",
            "You will be assessed by a health professional to work out the level of help you can get. Your rate will be regularly reassessed to make sure you are getting the right support.",
            "You can apply by phone or by post. You will then be asked to complete a 'How your disability affects you' form.",
         ),
         "guidance"),
    ]),
    # ── Disabilities / Blue Badge ──
    ("blue-badge", "department-for-transport", [
        ("Apply for or renew a Blue Badge",
         "Apply for or renew a Blue Badge for free parking.",
         _para(
            "The Blue Badge scheme helps people with disabilities or health conditions park closer to their destination.",
            "You can apply online or contact your local council. It costs up to £10 in England and £20 in Scotland. It is free in Wales.",
            "A Blue Badge usually lasts up to 3 years. You will get a reminder before it runs out.",
         ),
         "service"),
    ]),
    # ── Business / Setting up ──
    ("setting-up", "companies-house", [
        ("Set up a business",
         "Choose the right structure for your business and register with HMRC and Companies House.",
         _para(
            "You can choose to be a sole trader, set up a limited company or form a business partnership.",
            "The simplest way to start a business is to become a sole trader. You run your own business as an individual and are self-employed.",
            "A limited company is a company that is legally separate from the people who run it. It has separate finances from the personal ones of its owners.",
         ),
         "guidance"),
        ("Choose a business name",
         "Rules and restrictions on naming your business.",
         _para(
            "Sole traders do not need to register their business name. However, you must include your name and the business's name on official paperwork.",
            "A limited company's name cannot be the same as an existing registered company. It must usually end in 'Limited' or 'Ltd', or the Welsh equivalents.",
            "Some words and expressions are 'sensitive' and need approval before you can use them — for example 'Royal' or 'Bank'.",
         ),
         "guidance"),
    ]),
    # ── Business / Running a Ltd ──
    ("running-a-limited-company", "companies-house", [
        ("Annual accounts for a limited company",
         "File your company's annual accounts with Companies House.",
         _para(
            "All limited companies must file annual accounts with Companies House. The first accounts must be filed 21 months after the date you registered with Companies House.",
            "Subsequent accounts must be filed 9 months after the end of your company's financial year.",
            "There are penalties for filing late. They start at £150 and go up to £1,500.",
         ),
         "guidance"),
        ("File a confirmation statement",
         "Confirm or update your company's information once a year.",
         _para(
            "Every limited company must file a confirmation statement (form CS01) at least once every 12 months.",
            "The fee is £34 to file online or £62 to file on paper.",
            "You can file a confirmation statement at any time during your review period, but you must do so within 14 days of the end of the period.",
         ),
         "service"),
    ]),
    # ── Business / VAT ──
    ("vat", "hm-revenue-customs", [
        ("Register for VAT",
         "When you must register for VAT and how to register.",
         _para(
            "You must register for VAT if your VAT taxable turnover goes over £90,000 (the threshold), or you know that it will.",
            "You can register voluntarily even if your turnover is below the threshold, which may help you reclaim VAT on goods and services you buy.",
            "Register online using your Government Gateway account. You will get a VAT registration certificate within 30 working days.",
         ),
         "service"),
        ("VAT rates",
         "Standard, reduced and zero rates of VAT and what they apply to.",
         _para(
            "The standard rate of VAT is 20%. It applies to most goods and services.",
            "The reduced rate of 5% applies to some goods and services, including children's car seats and home energy.",
            "The zero rate of 0% applies to most food and children's clothes. Items at the zero rate are still VAT-taxable, but the rate of VAT you charge to your customers is 0%.",
         ),
         "guidance"),
    ]),
    # ── Citizenship / British citizenship ──
    ("british-citizenship", "home-office", [
        ("Become a British citizen",
         "Apply for British citizenship by naturalisation if you have lived in the UK for at least 5 years.",
         _para(
            "You can apply to become a British citizen by naturalisation if you have lived in the UK for at least 5 years (or 3 years if you are married to or in a civil partnership with a British citizen).",
            "You also need to have settled status (Indefinite Leave to Remain), pass the Life in the UK Test, prove your knowledge of English, and meet the good character requirement.",
            "The fee is £1,500 per person, plus £80 for the citizenship ceremony.",
         ),
         "service"),
    ]),
    # ── Citizenship / Voting ──
    ("voting", "cabinet-office", [
        ("Register to vote",
         "Register to vote in UK elections and referendums.",
         _para(
            "You must register if you have been asked to do so and are eligible.",
            "It usually takes about 5 minutes. You will need your National Insurance number, which can be found on your National Insurance card, payslips, P45 or P60, or letters about benefits.",
            "You only need to register once. You will need to register again only if you change your name, address or nationality.",
         ),
         "service"),
        ("Voter ID at polling stations",
         "What ID you need to bring to vote in person at a polling station.",
         _para(
            "You need to show photo ID to vote in person at a polling station for UK Parliamentary general elections, local council elections in England, and other elections.",
            "Accepted IDs include passports, driving licences and Older Person's Bus Pass. The ID must be the original — copies will not be accepted.",
            "If you do not have an accepted ID, you can apply for a free Voter Authority Certificate online.",
         ),
         "guidance"),
    ]),
    # ── Crime / Courts ──
    ("courts", "ministry-of-justice", [
        ("Find a court or tribunal",
         "Search for a court or tribunal in England and Wales by name or postcode.",
         _para(
            "Use this service to find information about a court or tribunal — what cases they deal with, opening times, address and contact details.",
            "The service covers all courts and tribunals in England and Wales. Court services in Scotland and Northern Ireland are listed separately.",
         ),
         "service"),
    ]),
    # ── Births deaths marriages / Register a birth ──
    ("register-a-birth", "home-office", [
        ("Register a birth",
         "How to register a birth in England and Wales — you must do this within 42 days.",
         _para(
            "You must register a baby's birth within 42 days of the day it was born. You normally register the birth in the area where the baby was born.",
            "If you cannot get to the register office in the area where the baby was born, you can go to another register office and they will send your details to the correct office.",
            "You will get a free short birth certificate at the time of registration. You can buy full birth certificates for £12.50 each.",
         ),
         "service"),
    ]),
    # ── Births deaths marriages / Marriage ──
    ("marriage-civil-partnership", "home-office", [
        ("Marriages and civil partnerships in England and Wales",
         "How to give notice to marry or form a civil partnership.",
         _para(
            "You and your partner usually have to give at least 29 days' notice at your local register office before you can get married or form a civil partnership.",
            "Both of you must have lived in the registration district for at least 7 days immediately before giving notice. The notice is then publicly displayed in the register office for 28 days.",
            "Notice is valid for 12 months. The marriage or civil partnership must take place within this period.",
         ),
         "guidance"),
    ]),
    # ── Births deaths marriages / LPA ──
    ("lasting-power-of-attorney", "ministry-of-justice", [
        ("Make, register or end a lasting power of attorney",
         "A lasting power of attorney (LPA) is a legal document that lets you appoint people to help you make decisions if you cannot make them yourself.",
         _para(
            "There are 2 types of LPA: health and welfare, and property and financial affairs. You can choose to make one type or both.",
            "It costs £82 to register each LPA. You may not have to pay if you are on certain benefits or a low income.",
            "It takes up to 20 weeks to register an LPA if there are no mistakes in the application.",
         ),
         "service"),
    ]),
    # ── Employment / PAYE ──
    ("paye", "hm-revenue-customs", [
        ("PAYE for employers",
         "Set up payroll, register as an employer and run payroll for your employees.",
         _para(
            "If you employ someone, you must register as an employer with HMRC. You can do this up to 4 weeks before you pay your new staff.",
            "You will need to operate PAYE as part of your payroll. PAYE is HMRC's system to collect Income Tax and National Insurance from employment.",
            "You must report to HMRC on or before each payday using payroll software. Most employers use commercial software, although HMRC's Basic PAYE Tools is free for businesses with fewer than 10 employees.",
         ),
         "guidance"),
    ]),
    # ── Employment / Contracts ──
    ("contracts", "dwp", [
        ("Employment contracts",
         "What an employment contract must include.",
         _para(
            "All employees have an employment contract with their employer. A contract is an agreement that sets out an employee's employment conditions, rights, responsibilities and duties.",
            "Employees must be given a written statement of employment particulars on or before their first day at work.",
            "The written statement must include pay, hours, holiday entitlement, location and notice period.",
         ),
         "guidance"),
    ]),
    # ── Environment / Flooding ──
    ("flooding", "defra", [
        ("Check the flood risk for an area",
         "Check the long-term flood risk for an area in England.",
         _para(
            "Use this service to find out an area's long-term flood risk from rivers, the sea, surface water and reservoirs.",
            "You can also find out the depth, speed and direction of possible flooding, and what you can do to reduce the risk to you and your property.",
            "For current flood warnings, check the live flood warnings service.",
         ),
         "service"),
        ("Sign up for flood warnings",
         "Sign up to get flood warnings by phone, text or email.",
         _para(
            "The flood warning service is free and available 24 hours a day. You will be warned when flooding is expected so that you have time to prepare.",
            "You can register if your property or business is at risk of flooding from rivers or the sea in England.",
         ),
         "service"),
    ]),
    # ── Environment / Wildlife ──
    ("wildlife", "defra", [
        ("Protected species: licences",
         "Apply for a licence to carry out activities that would otherwise harm protected species.",
         _para(
            "You usually need a licence from Natural England, NatureScot or Natural Resources Wales for activities that might disturb protected species.",
            "Common licences cover bats, great crested newts, badgers and birds. Application fees vary by activity.",
         ),
         "guidance"),
    ]),
    # ── Benefits / Appeals ──
    ("appeals", "dwp", [
        ("Appeal a benefit decision",
         "How to appeal a decision about your benefits — first ask for mandatory reconsideration.",
         _para(
            "If you disagree with a benefits decision, you must first ask for a mandatory reconsideration. You usually have one month from the date of the decision letter to do this.",
            "If the decision is not changed, you can then appeal to a tribunal. The tribunal is independent of DWP.",
            "Fill in form SSCS1 and send it to HM Courts & Tribunals Service. There is no fee.",
         ),
         "guidance"),
    ]),
]


# ─── Seeders ─────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    out = []
    for c in text.lower():
        if c.isalnum():
            out.append(c)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")


def seed_database(db):
    """Top-level idempotent seeder.

    Each sub-seed is gated independently. The check below short-circuits
    the bulk of the work; the per-function gates protect against partial
    runs that leave one table empty.
    """
    # Late import keeps SQLAlchemy model registration in app.py
    from app import Topic, Subtopic, Department, GuidanceArticle, Announcement

    _seed_topics(db, Topic)
    _seed_subtopics(db, Topic, Subtopic)
    _seed_departments(db, Department)
    _seed_articles(db, Topic, Subtopic, Department, GuidanceArticle)
    _seed_announcements(db, Department, Announcement)


def _seed_topics(db, Topic):
    if Topic.query.count() > 0:
        return
    for slug, name, desc, sort in TOPICS:
        db.session.add(Topic(slug=slug, name=name, description=desc, sort_order=sort))
    db.session.commit()


def _seed_subtopics(db, Topic, Subtopic):
    if Subtopic.query.count() > 0:
        return
    for i, (topic_slug, sub_slug, name, desc) in enumerate(SUBTOPICS):
        topic = Topic.query.filter_by(slug=topic_slug).first()
        if not topic:
            continue
        db.session.add(Subtopic(
            topic_id=topic.id, slug=sub_slug, name=name,
            description=desc, sort_order=i * 10,
        ))
    db.session.commit()


def _seed_departments(db, Department):
    if Department.query.count() > 0:
        return
    for slug, name, abbrev, kind, minister, perm_sec, employees, est, desc in DEPARTMENTS:
        db.session.add(Department(
            slug=slug, name=name, abbreviation=abbrev, kind=kind,
            minister=minister, permanent_secretary=perm_sec,
            employees=employees, established=est, description=desc,
            website=f"https://www.gov.uk/government/organisations/{slug}",
        ))
    db.session.commit()


def _seed_articles(db, Topic, Subtopic, Department, GuidanceArticle):
    if GuidanceArticle.query.count() > 0:
        return
    base_date = date(2025, 1, 15)
    counter = 0
    for sub_slug, dept_slug, items in ARTICLES:
        subtopic = Subtopic.query.filter_by(slug=sub_slug).first()
        dept = Department.query.filter_by(slug=dept_slug).first()
        if not subtopic or not dept:
            continue
        topic_id = subtopic.topic_id
        for title, summary, body, kind in items:
            slug = _slugify(title)
            if GuidanceArticle.query.filter_by(slug=slug).first():
                continue
            counter += 1
            last_updated = base_date + timedelta(days=counter * 3 % 70)
            first_published = last_updated - timedelta(days=180 + counter * 7 % 365)
            db.session.add(GuidanceArticle(
                slug=slug, title=title, summary=summary, body=body,
                topic_id=topic_id, subtopic_id=subtopic.id,
                department_id=dept.id, kind=kind,
                audience="Public",
                last_updated=last_updated,
                first_published=first_published,
            ))
    db.session.commit()


ANNOUNCEMENT_TEMPLATES = [
    ("hm-treasury", "Spring Statement update on growth measures",
     "Chancellor sets out the next steps on the government's growth plan.",
     "The Chancellor of the Exchequer today set out further detail on measures to grow the UK economy, "
     "build new infrastructure, and support working families. The statement covered investment, planning reform "
     "and skills, building on commitments made at the Budget.",
     "speech"),
    ("hm-revenue-customs", "Self Assessment: 11.5 million returns filed on time",
     "HMRC thanks customers who filed by the 31 January deadline.",
     "HMRC today confirmed that more than 11.5 million Self Assessment tax returns were filed by the 31 January "
     "deadline. Those who missed the deadline are urged to file as soon as possible to avoid further penalties.",
     "news_story"),
    ("home-office", "ETA scheme expands to new nationalities",
     "Visitors from additional countries will need an Electronic Travel Authorisation to enter the UK.",
     "The Home Office today announced that the Electronic Travel Authorisation (ETA) scheme will expand to "
     "cover visitors from additional countries. The change is part of the UK's wider work to digitise the "
     "border and reduce risks before travel.",
     "press_release"),
    ("department-for-education", "New schools White Paper sets out reading and maths reforms",
     "Government publishes plan to raise standards in primary schools.",
     "The Department for Education today published a White Paper setting out reforms to improve reading "
     "and maths in primary schools, including expanded phonics support and curriculum guidance.",
     "press_release"),
    ("dwp", "Universal Credit migration on track",
     "DWP confirms that the migration of legacy benefits claimants to Universal Credit is on schedule.",
     "DWP today provided an update on the Move to Universal Credit programme. Claimants currently receiving "
     "legacy benefits will receive a Migration Notice and have 3 months to claim Universal Credit.",
     "news_story"),
    ("dvla", "Online vehicle tax service handles record volumes",
     "DVLA confirms 95% of vehicle tax transactions are completed online.",
     "DVLA today reported that 95% of vehicle tax transactions are now completed online or by phone, "
     "with services available 24 hours a day.",
     "news_story"),
    ("hm-passport-office", "Passport application turnaround remains within 3 weeks",
     "His Majesty's Passport Office confirms that 99.7% of applications are completed within 3 weeks.",
     "His Majesty's Passport Office (HMPO) today reported that the standard 3-week turnaround for UK "
     "passport applications has been met for the 12th consecutive month.",
     "news_story"),
    ("defra", "Flood defence schemes protect 600,000 properties",
     "Defra confirms milestone in flood defence investment programme.",
     "The Department for Environment, Food and Rural Affairs (Defra) today confirmed that flood defence "
     "schemes completed in the current investment cycle now protect more than 600,000 properties.",
     "press_release"),
    ("ministry-of-justice", "Court backlog falls for sixth consecutive month",
     "Ministry of Justice publishes latest courts performance statistics.",
     "MoJ today published statistics showing the court backlog has fallen for the sixth consecutive month. "
     "Additional sitting days and new technology have helped courts process more cases.",
     "news_story"),
    ("foreign-commonwealth-development-office", "Foreign Secretary statement on humanitarian aid",
     "Foreign Secretary sets out new funding for humanitarian operations.",
     "The Foreign Secretary today announced new humanitarian funding to support communities affected "
     "by ongoing conflicts and natural disasters.",
     "speech"),
    ("nhs-england", "NHS App reaches 30 million users",
     "NHS England confirms strong growth in NHS App use.",
     "NHS England today confirmed that the NHS App has reached 30 million registered users. The app "
     "lets patients book appointments, order repeat prescriptions and view their health record.",
     "news_story"),
    ("cabinet-office", "Civil Service apprenticeship intake at record high",
     "Cabinet Office publishes latest Civil Service workforce statistics.",
     "The Cabinet Office today published workforce statistics showing the highest ever intake of "
     "apprentices into the Civil Service.",
     "news_story"),
    ("companies-house", "Identity verification rolling out for company directors",
     "Companies House confirms next phase of reforms under the Economic Crime Act.",
     "Companies House today confirmed that mandatory identity verification will be rolled out in stages "
     "for company directors and people with significant control.",
     "press_release"),
    ("department-for-transport", "National roads investment programme update",
     "Department for Transport publishes the latest update on the Road Investment Strategy.",
     "The Department for Transport today published an update on the Road Investment Strategy, including "
     "progress on major schemes and forthcoming work on the strategic road network.",
     "news_story"),
    ("dwp", "State Pension to rise in line with triple lock",
     "DWP confirms that the State Pension will rise next April.",
     "DWP today confirmed that the State Pension will rise in line with the triple lock from April. "
     "Pensioners will see the full new State Pension rise in line with earnings growth.",
     "press_release"),
    ("hm-treasury", "Autumn Budget: key measures at a glance",
     "Treasury publishes summary of Budget decisions.",
     "HM Treasury today published a summary of the key measures announced at the Autumn Budget, "
     "including tax thresholds, public spending and growth measures.",
     "press_release"),
    ("home-office", "Police recruitment campaign launched",
     "Home Office launches the next phase of national police recruitment.",
     "The Home Office today launched the next phase of the national police recruitment campaign, "
     "aimed at increasing diversity and capacity across forces in England and Wales.",
     "press_release"),
    ("department-for-education", "Free school meals expansion",
     "DfE confirms expansion of Free School Meals eligibility.",
     "The Department for Education today confirmed that Free School Meals eligibility will be expanded, "
     "providing additional support to families on low incomes.",
     "press_release"),
    ("hm-revenue-customs", "Crackdown on tax avoidance schemes",
     "HMRC publishes annual update on action against promoters.",
     "HMRC today published its annual update on action taken against promoters and enablers of tax "
     "avoidance schemes, including penalties and disclosures.",
     "news_story"),
    ("ministry-of-justice", "Probation reform: 12-month update",
     "MoJ publishes 12-month update on probation reform.",
     "MoJ today published a 12-month update on the unified probation service, including outcomes for "
     "supervised offenders and workforce growth.",
     "news_story"),
]


def _seed_announcements(db, Department, Announcement):
    if Announcement.query.count() > 0:
        return
    base = datetime(2025, 3, 28, 9, 0, 0)
    for i, (dept_slug, title, summary, body, kind) in enumerate(ANNOUNCEMENT_TEMPLATES):
        dept = Department.query.filter_by(slug=dept_slug).first()
        if not dept:
            continue
        slug = _slugify(title)
        if Announcement.query.filter_by(slug=slug).first():
            continue
        published = base - timedelta(days=i * 2, hours=(i * 3) % 24)
        db.session.add(Announcement(
            slug=slug, title=title, summary=summary, body=body,
            department_id=dept.id, kind=kind, published_at=published,
        ))
    db.session.commit()

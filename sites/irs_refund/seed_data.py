"""Deterministic synthetic seed data for the IRS refund mirror."""
from __future__ import annotations

from datetime import date, timedelta


MIRROR_REFERENCE_DATE = date(2026, 4, 15)

BENCHMARK_USERS = [
    {
        "username": "alice_j",
        "email": "alice.j@test.com",
        "display_name": "Alice Johnson",
        "city": "Springfield",
        "state": "IL",
        "preferred_contact_method": "Email",
        "default_tax_year": 2025,
        "default_last_four": "8110",
        "default_zip_code": "62701",
    },
    {
        "username": "bob_c",
        "email": "bob.c@test.com",
        "display_name": "Bob Chen",
        "city": "Chicago",
        "state": "IL",
        "preferred_contact_method": "SMS",
        "default_tax_year": 2025,
        "default_last_four": "8221",
        "default_zip_code": "60601",
    },
    {
        "username": "carol_d",
        "email": "carol.d@test.com",
        "display_name": "Carol Davis",
        "city": "Portland",
        "state": "OR",
        "preferred_contact_method": "Email",
        "default_tax_year": 2025,
        "default_last_four": "8332",
        "default_zip_code": "97205",
    },
    {
        "username": "david_k",
        "email": "david.k@test.com",
        "display_name": "David Kim",
        "city": "Seattle",
        "state": "WA",
        "preferred_contact_method": "Mail",
        "default_tax_year": 2025,
        "default_last_four": "8443",
        "default_zip_code": "98104",
    },
]

FILING_STATUSES = [
    {
        "name": "Single",
        "slug": "single",
        "description": "For synthetic demo returns filed by one taxpayer.",
    },
    {
        "name": "Married Filing Jointly",
        "slug": "married-filing-jointly",
        "description": "For synthetic demo returns filed together by spouses.",
    },
    {
        "name": "Married Filing Separately",
        "slug": "married-filing-separately",
        "description": "For synthetic demo returns filed separately by married taxpayers.",
    },
    {
        "name": "Head of Household",
        "slug": "head-of-household",
        "description": "For synthetic demo returns filed by a qualifying head of household.",
    },
    {
        "name": "Qualifying Surviving Spouse",
        "slug": "qualifying-surviving-spouse",
        "description": "For synthetic demo returns filed by a qualifying surviving spouse.",
    },
]

STATUS_SCENARIOS = {
    "return_received": {
        "public_label": "Return Received",
        "headline": "We have your synthetic demo return and are reviewing it.",
        "explanation": (
            "The return has been received by the local benchmark mirror. "
            "No additional action is needed right now."
        ),
        "next_step": "Check this demo mirror again after two business days.",
        "notice_code": None,
        "checklist_category": "processing",
        "progress_step": 1,
    },
    "processing": {
        "public_label": "Processing",
        "headline": "Your synthetic demo return is still processing.",
        "explanation": (
            "The mirror has accepted the return, but a final approval decision "
            "has not been posted yet."
        ),
        "next_step": "Wait three business days before re-running the lookup.",
        "notice_code": "PR-216",
        "checklist_category": "processing",
        "progress_step": 1,
    },
    "refund_approved": {
        "public_label": "Refund Approved",
        "headline": "Your synthetic demo refund has been approved.",
        "explanation": (
            "The refund amount is approved and waiting for the selected "
            "delivery method to complete."
        ),
        "next_step": "Monitor the delivery method shown in the result panel.",
        "notice_code": None,
        "checklist_category": "delivery",
        "progress_step": 2,
    },
    "refund_sent": {
        "public_label": "Refund Sent",
        "headline": "Your synthetic demo refund has been issued.",
        "explanation": (
            "The refund has left processing and is on the way through the "
            "selected delivery channel."
        ),
        "next_step": "Allow standard settlement time for the delivery method shown.",
        "notice_code": None,
        "checklist_category": "delivery",
        "progress_step": 3,
    },
    "delayed_identity": {
        "public_label": "Delayed: Identity Verification Needed",
        "headline": "A synthetic identity verification step is delaying this refund.",
        "explanation": (
            "The demo record triggered an identity check before the mirror can "
            "approve the refund."
        ),
        "next_step": "Review the identity checklist and the linked demo notice.",
        "notice_code": "ID-221",
        "checklist_category": "identity",
        "progress_step": 1,
    },
    "delayed_math_error": {
        "public_label": "Delayed: Math Error Review",
        "headline": "A synthetic math review is holding this refund.",
        "explanation": (
            "One or more figures on the return require a manual demo review "
            "before the refund can be approved."
        ),
        "next_step": "Read the math review notice and confirm the adjusted amount.",
        "notice_code": "MR-310",
        "checklist_category": "math",
        "progress_step": 1,
    },
    "offset_review": {
        "public_label": "Delayed: Offset Review",
        "headline": "A synthetic offset review is delaying this refund.",
        "explanation": (
            "Part or all of the refund may be redirected inside the demo "
            "environment for an offset review."
        ),
        "next_step": "Open the linked notice and review the offset explanation.",
        "notice_code": "OF-208",
        "checklist_category": "offset",
        "progress_step": 1,
    },
    "amended_processing": {
        "public_label": "Processing",
        "headline": "This synthetic amended return is still being processed.",
        "explanation": (
            "Amended returns in this local mirror move through a longer demo "
            "review cycle."
        ),
        "next_step": "Use the amended-return help article for follow-up steps.",
        "notice_code": "AM-415",
        "checklist_category": "amended",
        "progress_step": 1,
    },
}

NOTICE_RECORDS = [
    {
        "code": "RV-101",
        "title": "Return Received Confirmation",
        "summary": "Confirms that the synthetic return was accepted into the local mirror.",
        "details": (
            "Use this demo notice when a return has moved into the initial intake queue. "
            "No follow-up action is needed unless another notice appears."
        ),
        "related_stage": "Return Received",
    },
    {
        "code": "PR-216",
        "title": "Still Processing Review",
        "summary": "Explains that the synthetic return remains in processing.",
        "details": (
            "This practice notice appears when the return is still under routine review. "
            "Re-check after the wait period shown on the result page."
        ),
        "related_stage": "Processing",
    },
    {
        "code": "RA-145",
        "title": "Refund Approval Timing",
        "summary": "Explains what happens after a refund is approved in the demo mirror.",
        "details": (
            "The refund is approved and queued for delivery. The delivery method panel "
            "shows whether the mirror expects direct deposit, split deposit, or paper check."
        ),
        "related_stage": "Refund Approved",
    },
    {
        "code": "RS-190",
        "title": "Refund Sent Timing",
        "summary": "Explains settlement timing after the refund is marked sent.",
        "details": (
            "A sent refund has exited processing. Timing depends on the synthetic delivery "
            "method and any verification notes already shown on the record."
        ),
        "related_stage": "Refund Sent",
    },
    {
        "code": "ID-221",
        "title": "Identity Verification Needed",
        "summary": "A synthetic identity-verification review is required before approval.",
        "details": (
            "Open the checklist on the result page, confirm the demo address, and review "
            "the contact preference stored on the benchmark account before trying again."
        ),
        "related_stage": "Delayed: Identity Verification Needed",
    },
    {
        "code": "ID-247",
        "title": "Address Confirmation Follow-up",
        "summary": "Requests a synthetic mailing address confirmation for the demo return.",
        "details": (
            "This notice can appear with identity-related reviews when the stored demo ZIP "
            "code or city needs confirmation."
        ),
        "related_stage": "Delayed: Identity Verification Needed",
    },
    {
        "code": "MR-310",
        "title": "Math Error Review",
        "summary": "One or more synthetic entries require a math review.",
        "details": (
            "Review the refund amount and the notice summary. The result page explains "
            "whether the mirror adjusted the amount or is still validating it."
        ),
        "related_stage": "Delayed: Math Error Review",
    },
    {
        "code": "MR-322",
        "title": "Income Figure Recheck",
        "summary": "A synthetic figure triggered a manual recheck in the mirror.",
        "details": (
            "This demo notice appears when a calculated amount does not align with the "
            "stored practice return record."
        ),
        "related_stage": "Delayed: Math Error Review",
    },
    {
        "code": "OF-208",
        "title": "Offset Review in Progress",
        "summary": "Part of the synthetic refund may be redirected during an offset review.",
        "details": (
            "Open the linked article for offset explanations. The mirror keeps the refund "
            "in review until the simulated offset calculation is complete."
        ),
        "related_stage": "Delayed: Offset Review",
    },
    {
        "code": "OF-230",
        "title": "Treasury Program Offset Detail",
        "summary": "Provides additional synthetic context for an offset-related delay.",
        "details": (
            "Use this practice notice to understand whether the demo return is awaiting "
            "an offset decision or a corrected payment method."
        ),
        "related_stage": "Delayed: Offset Review",
    },
    {
        "code": "AM-415",
        "title": "Amended Return Processing",
        "summary": "The synthetic amended return remains under review.",
        "details": (
            "Amended returns follow a slower demo timeline. Search the amended-return "
            "help topic for detailed guidance."
        ),
        "related_stage": "Processing",
    },
    {
        "code": "AM-440",
        "title": "Amended Return Supporting Items",
        "summary": "Lists the synthetic follow-up items sometimes used for amended returns.",
        "details": (
            "This notice describes supporting documents that may appear in a checklist "
            "for amended demo returns."
        ),
        "related_stage": "Processing",
    },
    {
        "code": "CK-144",
        "title": "Paper Check Delivery Timing",
        "summary": "Explains mailing time for synthetic paper-check refunds.",
        "details": (
            "Paper checks generally take longer than direct deposit in this mirror. "
            "Confirm the ZIP code on the demo profile if a check seems delayed."
        ),
        "related_stage": "Refund Sent",
    },
    {
        "code": "DP-118",
        "title": "Direct Deposit Routing Review",
        "summary": "A synthetic routing review is pending for direct deposit.",
        "details": (
            "Use this notice when the mirror needs to confirm the selected deposit method "
            "before issuing an approved refund."
        ),
        "related_stage": "Refund Approved",
    },
    {
        "code": "SP-177",
        "title": "Split Deposit Allocation",
        "summary": "Explains how a synthetic split deposit is staged in the mirror.",
        "details": (
            "A split deposit record divides the refund across multiple practice accounts. "
            "The detail page shows the expected delivery channel."
        ),
        "related_stage": "Refund Sent",
    },
    {
        "code": "NM-404",
        "title": "Information Mismatch",
        "summary": "Explains what to do when the synthetic lookup data does not match.",
        "details": (
            "If the lookup flow reports a mismatch, compare the tax year, filing status, "
            "refund amount, last four digits, and ZIP code against the public demo record."
        ),
        "related_stage": "Information Mismatch",
    },
    {
        "code": "NF-410",
        "title": "Record Not Found",
        "summary": "No matching synthetic demo return was found.",
        "details": (
            "The lookup service could not locate a return using the supplied practice data. "
            "Use only the public demo cases or seeded benchmark accounts."
        ),
        "related_stage": "Not Found / Information Mismatch",
    },
    {
        "code": "HC-155",
        "title": "History Saved",
        "summary": "Confirms that a signed-in user saved a synthetic lookup to history.",
        "details": (
            "Saved lookup history is only available for benchmark and locally registered "
            "demo accounts in this mirror."
        ),
        "related_stage": "History",
    },
    {
        "code": "SC-109",
        "title": "Synthetic Data Safety Notice",
        "summary": "Reminds users not to enter real taxpayer information.",
        "details": (
            "All records in this environment are synthetic. Use only the published demo "
            "values and seeded benchmark credentials."
        ),
        "related_stage": "General",
    },
    {
        "code": "TX-205",
        "title": "Tax Topic Routing",
        "summary": "Points users toward the correct help topic category.",
        "details": (
            "Use the tax-topics page when you know the subject but not the exact help article."
        ),
        "related_stage": "General",
    },
]

ARTICLE_BLUEPRINTS = [
    (
        "refund-timing-after-approval",
        "When to check after a refund is approved",
        "Refund timing",
        "Learn what the local mirror means when a refund is approved but not yet sent.",
        "timing",
        "Refund Approved",
    ),
    (
        "direct-deposit-vs-paper-check",
        "Compare direct deposit, split deposit, and paper check timing",
        "Delivery methods",
        "Understand how each synthetic delivery method moves through the mirror.",
        "delivery",
        "Refund Sent",
    ),
    (
        "still-processing-what-next",
        "What to do when a synthetic refund is still processing",
        "Refund timing",
        "Review the wait window and the next safe step for still-processing demo returns.",
        "processing",
        "Processing",
    ),
    (
        "identity-verification-checklist",
        "Checklist for identity verification delays",
        "Identity verification",
        "Use the checklist items shown on delayed identity-verification records.",
        "identity",
        "Delayed: Identity Verification Needed",
    ),
    (
        "math-review-adjusted-refund",
        "How math review can change a synthetic refund amount",
        "Math review",
        "Explains what the mirror is reviewing and where to check the adjusted amount.",
        "math",
        "Delayed: Math Error Review",
    ),
    (
        "offset-review-explainer",
        "Understand offset review in the refund tracker",
        "Offset review",
        "A guide to offset-related notices and expected next steps.",
        "offset",
        "Delayed: Offset Review",
    ),
    (
        "amended-return-guidance",
        "Guidance for amended synthetic returns",
        "Amended return",
        "Follow-up guidance for demo returns marked as amended.",
        "amended-return",
        "Processing",
    ),
    (
        "information-mismatch-help",
        "Fixing an information mismatch in the lookup flow",
        "Lookup help",
        "Shows which fields to compare when a public demo case does not match.",
        "lookup",
        "Information Mismatch",
    ),
    (
        "paper-check-trace-steps",
        "How to review a delayed paper check in the demo mirror",
        "Delivery methods",
        "Steps to take when a synthetic paper check has not arrived on time.",
        "delivery",
        "Refund Sent",
    ),
    (
        "split-deposit-routing-help",
        "How split deposit records are shown in this mirror",
        "Delivery methods",
        "Find where the split-deposit method appears and what it means.",
        "delivery",
        "Refund Sent",
    ),
]

FAQ_RECORDS = [
    ("faq-demo-data", "Can I use my real taxpayer information here?", "No. This is a local benchmark mirror with synthetic demo records only.", "Safety"),
    ("faq-where-find-demo-cases", "Where do I find lookup values for the practice cases?", "Use the public demo case cards on the Where's My Refund page or the saved history in benchmark accounts.", "Lookup"),
    ("faq-why-no-full-ssn", "Why does the form ask for only the last four digits?", "The mirror never uses full SSNs or real taxpayer identifiers. It only accepts synthetic last-four values.", "Safety"),
    ("faq-what-processing-means", "What does 'Processing' mean in this mirror?", "It means the return is still under review and no approval date has been posted yet.", "Statuses"),
    ("faq-return-received", "What does 'Return Received' mean?", "The return entered the demo intake queue and is being reviewed.", "Statuses"),
    ("faq-refund-approved", "What does 'Refund Approved' mean?", "The amount is approved and waiting for delivery through the listed method.", "Statuses"),
    ("faq-refund-sent", "What does 'Refund Sent' mean?", "The refund has been issued and is on the way through the selected delivery channel.", "Statuses"),
    ("faq-identity-delay", "What should I do during an identity verification delay?", "Open the notice and follow the identity checklist shown on the result page.", "Delays"),
    ("faq-math-delay", "What should I check during a math review delay?", "Confirm the refund amount and read the math review article linked from the result page.", "Delays"),
    ("faq-offset-delay", "What is an offset review?", "An offset review means the synthetic refund may be redirected before it can be released.", "Delays"),
    ("faq-amended-return", "How are amended returns handled in the mirror?", "They use a longer demo timeline and usually point to amended-return guidance articles.", "Amended return"),
    ("faq-how-long-recheck", "How long should I wait before checking again?", "Use the next-step guidance on the result page. Most processing cases suggest waiting three business days.", "Lookup"),
    ("faq-paper-check", "Do paper checks take longer than direct deposit?", "Yes. The paper-check help article explains the longer settlement window.", "Delivery methods"),
    ("faq-split-deposit", "What is split deposit in this mirror?", "It is a synthetic delivery method that divides the refund across more than one practice destination.", "Delivery methods"),
    ("faq-save-history", "Do I need to sign in to save lookup history?", "Yes. Saved lookup history is tied to local benchmark or registered demo accounts.", "Account"),
    ("faq-edit-profile", "What can I edit in my account profile?", "You can change your preferred contact method, location, default tax year, and saved demo last-four details.", "Account"),
    ("faq-search-help", "Can I search help articles and notices together?", "Yes. The search page returns grouped results across help articles, FAQs, notices, and topics.", "Search"),
    ("faq-notice-codes", "Where can I find notice-code explanations?", "Use the Notices page or open the linked notice from a refund result.", "Notices"),
    ("faq-tax-topics", "What is the Tax Topics page for?", "It groups help content by subject, such as timing, identity verification, and amended returns.", "Search"),
    ("faq-lookup-history", "Where is my saved lookup history?", "Open Lookup History from the account menu after signing in.", "Account"),
    ("faq-contact", "Can I submit a real support request here?", "No. The contact page is a local demo form for benchmark practice only.", "Safety"),
    ("faq-not-found", "What does 'Not Found / Information Mismatch' mean?", "The combination of synthetic fields did not match a practice record.", "Lookup"),
    ("faq-zip-code", "Why does the demo flow ask for a ZIP code?", "The ZIP code adds one more deterministic practice field for the lookup workflow.", "Lookup"),
    ("faq-amount-exact", "Does the refund amount have to match exactly?", "Yes. Use the exact whole-dollar amount shown on the public demo card or saved history.", "Lookup"),
    ("faq-public-vs-account", "What is the difference between public demo cases and benchmark accounts?", "Public demo cases let anyone practice lookups, while benchmark accounts add saved profiles and history.", "Account"),
]

CHECKLIST_ITEMS = [
    {"slug": "identity-photo-id", "title": "Confirm the synthetic photo ID name", "description": "Compare the demo taxpayer name on the profile and the lookup result.", "category": "identity"},
    {"slug": "identity-address", "title": "Verify the stored mailing ZIP code", "description": "Use the public demo case or saved profile to confirm the ZIP code.", "category": "identity"},
    {"slug": "identity-contact", "title": "Review the preferred contact method", "description": "Check whether the profile prefers email, SMS, or mail for demo notices.", "category": "identity"},
    {"slug": "math-amount", "title": "Recheck the exact refund amount", "description": "Use the whole-dollar refund amount stored on the public demo case.", "category": "math"},
    {"slug": "math-status", "title": "Review the adjusted amount note", "description": "Open the math-review article if the result page mentions an adjustment.", "category": "math"},
    {"slug": "offset-notice", "title": "Read the offset explanation notice", "description": "Open the notice linked from the result page to review the offset scenario.", "category": "offset"},
    {"slug": "offset-delivery", "title": "Confirm the listed delivery method", "description": "Offsets can change when the final payment method is shown.", "category": "offset"},
    {"slug": "amended-article", "title": "Open amended-return guidance", "description": "Use the help article linked from amended return results.", "category": "amended"},
    {"slug": "delivery-paper-check", "title": "Allow extra mailing time", "description": "Paper check scenarios take longer in the synthetic environment.", "category": "delivery"},
    {"slug": "delivery-split", "title": "Review the split-deposit article", "description": "Split deposits appear with their own delivery note in the mirror.", "category": "delivery"},
    {"slug": "processing-wait", "title": "Wait before checking again", "description": "Still-processing records usually suggest waiting three business days.", "category": "processing"},
    {"slug": "mismatch-fields", "title": "Compare all lookup fields", "description": "Tax year, filing status, refund amount, last four digits, and ZIP code must match exactly.", "category": "mismatch"},
]

ALERT_RECORDS = [
    {
        "title": "Synthetic demo data only",
        "body": "Use only the public practice records and seeded benchmark accounts. Do not enter real taxpayer information.",
        "level": "warning",
        "audience": "all",
        "order_index": 1,
    },
    {
        "title": "Refund status updates are pinned to April 15, 2026",
        "body": "This mirror uses a fixed reference date so benchmark tasks stay stable across resets.",
        "level": "info",
        "audience": "all",
        "order_index": 2,
    },
    {
        "title": "Help search covers notices, FAQs, and tax topics",
        "body": "Use the search box in the header to find delivery, identity, amended-return, and mismatch guidance.",
        "level": "info",
        "audience": "all",
        "order_index": 3,
    },
    {
        "title": "Saved lookup history is available after sign-in",
        "body": "Benchmark accounts include synthetic practice history across multiple tax years.",
        "level": "success",
        "audience": "signed-in",
        "order_index": 4,
    },
]

EXPLICIT_PROFILES = [
    {"full_name": "Alice Johnson", "city": "Springfield", "state": "IL", "zip_code": "62701", "last_four_id": "8110", "owner_email": "alice.j@test.com"},
    {"full_name": "Bob Chen", "city": "Chicago", "state": "IL", "zip_code": "60601", "last_four_id": "8221", "owner_email": "bob.c@test.com"},
    {"full_name": "Carol Davis", "city": "Portland", "state": "OR", "zip_code": "97205", "last_four_id": "8332", "owner_email": "carol.d@test.com"},
    {"full_name": "David Kim", "city": "Seattle", "state": "WA", "zip_code": "98104", "last_four_id": "8443", "owner_email": "david.k@test.com"},
    {"full_name": "Nora Patel", "city": "Austin", "state": "TX", "zip_code": "78701", "last_four_id": "8554", "owner_email": None},
    {"full_name": "Malik Rivera", "city": "Phoenix", "state": "AZ", "zip_code": "85004", "last_four_id": "8665", "owner_email": None},
    {"full_name": "Priya Shah", "city": "Atlanta", "state": "GA", "zip_code": "30303", "last_four_id": "8776", "owner_email": None},
    {"full_name": "Theo Martinez", "city": "Denver", "state": "CO", "zip_code": "80202", "last_four_id": "8887", "owner_email": None},
    {"full_name": "Elise Romero", "city": "Miami", "state": "FL", "zip_code": "33131", "last_four_id": "8998", "owner_email": None},
    {"full_name": "Grant Okafor", "city": "Detroit", "state": "MI", "zip_code": "48226", "last_four_id": "9009", "owner_email": None},
    {"full_name": "Jade Bennett", "city": "Raleigh", "state": "NC", "zip_code": "27601", "last_four_id": "9120", "owner_email": None},
    {"full_name": "Owen Brooks", "city": "Philadelphia", "state": "PA", "zip_code": "19106", "last_four_id": "9231", "owner_email": None},
]

CITY_POOL = [
    ("Boston", "MA", "02108"),
    ("Minneapolis", "MN", "55401"),
    ("Nashville", "TN", "37201"),
    ("Cleveland", "OH", "44114"),
    ("Madison", "WI", "53703"),
    ("Richmond", "VA", "23219"),
    ("Salt Lake City", "UT", "84111"),
    ("St. Louis", "MO", "63103"),
    ("Newark", "NJ", "07102"),
    ("Tampa", "FL", "33602"),
    ("San Jose", "CA", "95113"),
    ("Columbus", "OH", "43215"),
]

GENERATED_FIRST_NAMES = [
    "Maya", "Jordan", "Leah", "Ethan", "Avery", "Cameron", "Riley", "Noah",
    "Sofia", "Miles", "Naomi", "Isaac", "Claire", "Julian", "Hazel", "Victor",
]
GENERATED_LAST_NAMES = [
    "Turner", "Foster", "Morris", "Greene", "Sanders", "Wallace",
    "Bishop", "Hayes", "Cole", "Baxter", "Mendez", "Quinn",
]

ANCHOR_RETURNS = {
    ("alice-johnson", 2025): {
        "scenario": "refund_approved",
        "filing_status_slug": "single",
        "refund_amount": 1284,
        "delivery_method": "Direct deposit",
        "return_received_on": date(2026, 2, 3),
        "refund_approved_on": date(2026, 2, 12),
        "refund_sent_on": None,
        "showcase_order": 1,
        "showcase_label": "Approved refund practice case",
    },
    ("alice-johnson", 2024): {
        "scenario": "refund_sent",
        "filing_status_slug": "single",
        "refund_amount": 980,
        "delivery_method": "Paper check",
        "return_received_on": date(2025, 2, 18),
        "refund_approved_on": date(2025, 2, 26),
        "refund_sent_on": date(2025, 3, 4),
        "showcase_order": None,
        "showcase_label": None,
    },
    ("bob-chen", 2025): {
        "scenario": "delayed_identity",
        "filing_status_slug": "married-filing-jointly",
        "refund_amount": 2460,
        "delivery_method": "Direct deposit",
        "return_received_on": date(2026, 1, 29),
        "refund_approved_on": None,
        "refund_sent_on": None,
        "showcase_order": 2,
        "showcase_label": "Identity verification practice case",
    },
    ("bob-chen", 2024): {
        "scenario": "refund_sent",
        "filing_status_slug": "married-filing-jointly",
        "refund_amount": 2195,
        "delivery_method": "Direct deposit",
        "return_received_on": date(2025, 2, 11),
        "refund_approved_on": date(2025, 2, 20),
        "refund_sent_on": date(2025, 2, 24),
        "showcase_order": None,
        "showcase_label": None,
    },
    ("carol-davis", 2025): {
        "scenario": "processing",
        "filing_status_slug": "head-of-household",
        "refund_amount": 1742,
        "delivery_method": "Direct deposit",
        "return_received_on": date(2026, 2, 7),
        "refund_approved_on": None,
        "refund_sent_on": None,
        "showcase_order": None,
        "showcase_label": None,
    },
    ("carol-davis", 2023): {
        "scenario": "delayed_math_error",
        "filing_status_slug": "head-of-household",
        "refund_amount": 1520,
        "delivery_method": "Paper check",
        "return_received_on": date(2024, 3, 1),
        "refund_approved_on": None,
        "refund_sent_on": None,
        "showcase_order": 3,
        "showcase_label": "Math review practice case",
    },
    ("david-kim", 2025): {
        "scenario": "return_received",
        "filing_status_slug": "single",
        "refund_amount": 865,
        "delivery_method": "Direct deposit",
        "return_received_on": date(2026, 2, 10),
        "refund_approved_on": None,
        "refund_sent_on": None,
        "showcase_order": None,
        "showcase_label": None,
    },
    ("david-kim", 2024): {
        "scenario": "offset_review",
        "filing_status_slug": "single",
        "refund_amount": 1336,
        "delivery_method": "Paper check",
        "return_received_on": date(2025, 2, 14),
        "refund_approved_on": None,
        "refund_sent_on": None,
        "showcase_order": 4,
        "showcase_label": "Offset review practice case",
    },
    ("nora-patel", 2024): {
        "scenario": "refund_sent",
        "filing_status_slug": "married-filing-jointly",
        "refund_amount": 3106,
        "delivery_method": "Split deposit",
        "return_received_on": date(2025, 1, 30),
        "refund_approved_on": date(2025, 2, 12),
        "refund_sent_on": date(2025, 2, 18),
        "showcase_order": 5,
        "showcase_label": "Split deposit practice case",
    },
    ("malik-rivera", 2025): {
        "scenario": "processing",
        "filing_status_slug": "single",
        "refund_amount": 642,
        "delivery_method": "Direct deposit",
        "return_received_on": date(2026, 2, 13),
        "refund_approved_on": None,
        "refund_sent_on": None,
        "showcase_order": 6,
        "showcase_label": "Mismatch practice case",
    },
    ("priya-shah", 2025): {
        "scenario": "delayed_identity",
        "filing_status_slug": "head-of-household",
        "refund_amount": 2218,
        "delivery_method": "Direct deposit",
        "return_received_on": date(2026, 2, 5),
        "refund_approved_on": None,
        "refund_sent_on": None,
        "showcase_order": 7,
        "showcase_label": "Identity checklist practice case",
    },
    ("theo-martinez", 2023): {
        "scenario": "refund_approved",
        "filing_status_slug": "qualifying-surviving-spouse",
        "refund_amount": 2864,
        "delivery_method": "Paper check",
        "return_received_on": date(2024, 2, 9),
        "refund_approved_on": date(2024, 2, 22),
        "refund_sent_on": None,
        "showcase_order": 8,
        "showcase_label": "Printable summary practice case",
    },
    ("elise-romero", 2022): {
        "scenario": "amended_processing",
        "filing_status_slug": "single",
        "refund_amount": 1186,
        "delivery_method": "Paper check",
        "return_received_on": date(2023, 4, 4),
        "refund_approved_on": None,
        "refund_sent_on": None,
        "showcase_order": 9,
        "showcase_label": "Amended return practice case",
    },
    ("grant-okafor", 2024): {
        "scenario": "return_received",
        "filing_status_slug": "head-of-household",
        "refund_amount": 2075,
        "delivery_method": "Direct deposit",
        "return_received_on": date(2025, 2, 21),
        "refund_approved_on": None,
        "refund_sent_on": None,
        "showcase_order": 10,
        "showcase_label": "Fresh intake practice case",
    },
    ("jade-bennett", 2025): {
        "scenario": "refund_sent",
        "filing_status_slug": "single",
        "refund_amount": 2744,
        "delivery_method": "Direct deposit",
        "return_received_on": date(2026, 1, 27),
        "refund_approved_on": date(2026, 2, 6),
        "refund_sent_on": date(2026, 2, 10),
        "showcase_order": 11,
        "showcase_label": "Direct deposit practice case",
    },
    ("owen-brooks", 2024): {
        "scenario": "delayed_math_error",
        "filing_status_slug": "single",
        "refund_amount": 1968,
        "delivery_method": "Split deposit",
        "return_received_on": date(2025, 2, 16),
        "refund_approved_on": None,
        "refund_sent_on": None,
        "showcase_order": 12,
        "showcase_label": "Notice-code practice case",
    },
}


def slugify(value: str) -> str:
    return value.lower().replace("'", "").replace(".", "").replace(" ", "-")


def build_profiles() -> list[dict]:
    profiles: list[dict] = []
    for record in EXPLICIT_PROFILES:
        profiles.append(
            {
                "full_name": record["full_name"],
                "slug": slugify(record["full_name"]),
                "city": record["city"],
                "state": record["state"],
                "zip_code": record["zip_code"],
                "last_four_id": record["last_four_id"],
                "owner_email": record["owner_email"],
                "contact_preference": "Email",
                "notes": "Synthetic practice profile for the WebHarbor IRS refund mirror.",
            }
        )

    name_index = 0
    last_four_base = 9342
    while len(profiles) < 60:
        first = GENERATED_FIRST_NAMES[name_index % len(GENERATED_FIRST_NAMES)]
        last = GENERATED_LAST_NAMES[(name_index // len(GENERATED_FIRST_NAMES)) % len(GENERATED_LAST_NAMES)]
        full_name = f"{first} {last}"
        slug = slugify(full_name)
        if any(existing["slug"] == slug for existing in profiles):
            name_index += 1
            continue
        city, state, zip_code = CITY_POOL[name_index % len(CITY_POOL)]
        profiles.append(
            {
                "full_name": full_name,
                "slug": slug,
                "city": city,
                "state": state,
                "zip_code": zip_code,
                "last_four_id": f"{last_four_base + name_index:04d}"[-4:],
                "owner_email": None,
                "contact_preference": "Email" if name_index % 2 == 0 else "Mail",
                "notes": "Synthetic practice profile for the WebHarbor IRS refund mirror.",
            }
        )
        name_index += 1
    return profiles


def scenario_dates(tax_year: int, scenario_key: str, offset: int) -> tuple[date, date | None, date | None]:
    season_year = tax_year + 1
    received = date(season_year, 1, 24) + timedelta(days=offset)
    approved = None
    sent = None
    if scenario_key in {"refund_approved", "refund_sent"}:
        approved = received + timedelta(days=8 + (offset % 4))
    if scenario_key == "refund_sent" and approved is not None:
        sent = approved + timedelta(days=2 + (offset % 3))
    return received, approved, sent


def timeline_for_return(return_record: dict) -> list[dict]:
    scenario_key = return_record["scenario"]
    scenario = STATUS_SCENARIOS[scenario_key]
    received = return_record["return_received_on"]
    approved = return_record["refund_approved_on"]
    sent = return_record["refund_sent_on"]
    delivery_method = return_record["delivery_method"]
    events = [
        {
            "event_date": received,
            "label": "Return received",
            "description": "The synthetic return entered the local benchmark intake queue.",
        }
    ]
    if scenario_key == "processing":
        events.append(
            {
                "event_date": received + timedelta(days=4),
                "label": "Processing review opened",
                "description": "The return is still processing and awaiting a final decision.",
            }
        )
    elif scenario_key == "return_received":
        events.append(
            {
                "event_date": received + timedelta(days=2),
                "label": "Initial validation passed",
                "description": "The mirror completed a basic demo validation pass.",
            }
        )
    elif scenario_key == "refund_approved":
        events.append(
            {
                "event_date": approved,
                "label": "Refund approved",
                "description": f"The refund is approved and queued for {delivery_method.lower()}.",
            }
        )
    elif scenario_key == "refund_sent":
        events.append(
            {
                "event_date": approved,
                "label": "Refund approved",
                "description": f"The refund cleared review and prepared for {delivery_method.lower()}.",
            }
        )
        events.append(
            {
                "event_date": sent,
                "label": "Refund sent",
                "description": f"The refund was issued through {delivery_method.lower()}.",
            }
        )
    elif scenario_key == "delayed_identity":
        events.append(
            {
                "event_date": received + timedelta(days=7),
                "label": "Identity review requested",
                "description": "The mirror requested an identity-verification follow-up.",
            }
        )
        events.append(
            {
                "event_date": received + timedelta(days=9),
                "label": "Demo notice posted",
                "description": f"Notice {scenario['notice_code']} is available on the result page.",
            }
        )
    elif scenario_key == "delayed_math_error":
        events.append(
            {
                "event_date": received + timedelta(days=5),
                "label": "Math review triggered",
                "description": "The mirror flagged a numeric entry for manual review.",
            }
        )
        events.append(
            {
                "event_date": received + timedelta(days=7),
                "label": "Demo notice posted",
                "description": f"Notice {scenario['notice_code']} explains the review step.",
            }
        )
    elif scenario_key == "offset_review":
        events.append(
            {
                "event_date": received + timedelta(days=6),
                "label": "Offset review started",
                "description": "The refund entered an offset-review branch in the mirror.",
            }
        )
    elif scenario_key == "amended_processing":
        events.append(
            {
                "event_date": received + timedelta(days=10),
                "label": "Amended return review opened",
                "description": "This amended return is on a longer synthetic processing track.",
            }
        )
    return events


def build_returns(profiles: list[dict]) -> list[dict]:
    returns: list[dict] = []
    scenario_cycle = [
        "refund_sent",
        "refund_approved",
        "processing",
        "return_received",
        "delayed_identity",
        "delayed_math_error",
        "offset_review",
        "amended_processing",
    ]
    delivery_cycle = ["Direct deposit", "Paper check", "Split deposit"]

    for profile_index, profile in enumerate(profiles):
        target_count = 2 if profile_index < 40 else 1
        years_seen: list[int] = []
        anchor_count = 0
        for year in (2025, 2024, 2023, 2022, 2021):
            anchor = ANCHOR_RETURNS.get((profile["slug"], year))
            if not anchor:
                continue
            record = {
                "profile_slug": profile["slug"],
                "tax_year": year,
                "filing_status_slug": anchor.get(
                    "filing_status_slug",
                    FILING_STATUSES[(profile_index + year) % len(FILING_STATUSES)]["slug"],
                ),
                "refund_amount": anchor["refund_amount"],
                "delivery_method": anchor["delivery_method"],
                "scenario": anchor["scenario"],
                "return_received_on": anchor["return_received_on"],
                "refund_approved_on": anchor["refund_approved_on"],
                "refund_sent_on": anchor["refund_sent_on"],
                "showcase_order": anchor["showcase_order"],
                "showcase_label": anchor["showcase_label"],
                "reference_code": f"WMR-{year}-{profile['last_four_id']}",
                "is_public_demo": anchor["showcase_order"] is not None,
                "is_amended": anchor["scenario"] == "amended_processing",
            }
            returns.append(record)
            years_seen.append(year)
            anchor_count += 1

        year_cycle = [2025, 2024, 2023, 2022, 2021]
        year_pointer = 0
        while anchor_count < target_count:
            year = year_cycle[(profile_index + year_pointer) % len(year_cycle)]
            year_pointer += 1
            if year in years_seen:
                continue
            scenario_key = scenario_cycle[(profile_index + year) % len(scenario_cycle)]
            delivery_method = delivery_cycle[(profile_index + year) % len(delivery_cycle)]
            offset = (profile_index * 5 + year) % 41
            received, approved, sent = scenario_dates(year, scenario_key, offset)
            returns.append(
                {
                    "profile_slug": profile["slug"],
                    "tax_year": year,
                    "filing_status_slug": FILING_STATUSES[(profile_index + year) % len(FILING_STATUSES)]["slug"],
                    "refund_amount": 650 + ((profile_index * 143 + year * 17) % 2950),
                    "delivery_method": delivery_method,
                    "scenario": scenario_key,
                    "return_received_on": received,
                    "refund_approved_on": approved,
                    "refund_sent_on": sent,
                    "showcase_order": None,
                    "showcase_label": None,
                    "reference_code": f"WMR-{year}-{profile['last_four_id']}",
                    "is_public_demo": False,
                    "is_amended": scenario_key == "amended_processing",
                }
            )
            years_seen.append(year)
            anchor_count += 1
    return returns


def build_help_articles() -> list[dict]:
    articles: list[dict] = []
    variants = [
        "Use the result-page timeline and the linked notice if one appears.",
        "The tax-topics page groups related guidance so the next step is easier to find.",
        "Benchmark tasks rely on these stable synthetic explanations and not on live IRS services.",
    ]
    for index, blueprint in enumerate(ARTICLE_BLUEPRINTS):
        slug, title, category, summary, topic, related_stage = blueprint
        body = (
            f"{summary} This local benchmark mirror uses only synthetic demo data. "
            f"{variants[index % len(variants)]} "
            "Public demo cases appear on the lookup flow so users can practice without real records."
        )
        articles.append(
            {
                "slug": slug,
                "title": title,
                "category": category,
                "summary": summary,
                "body": body,
                "tax_topic": topic,
                "related_stage": related_stage,
            }
        )
    extra_topics = [
        ("lookup-history-best-practices", "How saved lookup history works", "Account", "Understand how benchmark users store synthetic lookup records.", "account"),
        ("using-the-public-demo-library", "Using the public demo case library", "Lookup help", "Use the public practice cards instead of entering personal information.", "lookup"),
        ("when-paper-checks-arrive", "When synthetic paper checks are expected to arrive", "Delivery methods", "Paper-check scenarios follow a longer delivery window.", "delivery"),
        ("compare-two-tax-years", "Compare refund progress across two tax years", "Refund timing", "Use saved history to compare stages across more than one tax year.", "timing"),
        ("identity-delay-contact-options", "Contact options during identity review", "Identity verification", "Review which synthetic contact preference is saved on the account.", "identity"),
        ("mismatch-zip-code-guidance", "What to do if the ZIP code does not match", "Lookup help", "A mismatch result often points to one incorrect practice field.", "lookup"),
        ("understanding-public-notice-codes", "How to read synthetic notice codes", "Notices", "Notice codes in this mirror are synthetic and used only for local benchmark tasks.", "notices"),
        ("offset-review-delivery-methods", "How offset review affects delivery methods", "Offset review", "Offset-related cases may delay a direct deposit or paper check.", "offset"),
        ("approved-vs-sent-refunds", "Approved versus sent refunds", "Refund timing", "Approved means queued for delivery, while sent means issued.", "timing"),
        ("safe-demo-lookup-reminder", "Why the mirror uses only synthetic last-four identifiers", "Safety", "The lookup flow never uses full identifiers or live services.", "safety"),
        ("amended-return-wait-times", "What to expect from amended return timing", "Amended return", "Amended synthetic returns stay in review longer than standard returns.", "amended-return"),
        ("searching-help-and-faqs", "Search tips for help articles and FAQs", "Search", "The combined search page surfaces articles, FAQs, notices, and topics together.", "search"),
        ("delivery-method-summary-cards", "Reading the delivery method summary card", "Delivery methods", "Each result includes a delivery summary that matches the stored demo return.", "delivery"),
        ("still-processing-follow-up", "Follow-up guidance for still-processing cases", "Refund timing", "Processing cases usually tell users to wait before checking again.", "processing"),
        ("identity-checklist-summary", "Identity checklist summary", "Identity verification", "Identity-review results link to a checklist of synthetic follow-up steps.", "identity"),
        ("math-review-notice-summary", "Math review notice summary", "Math review", "Open the linked notice to understand the synthetic review explanation.", "math"),
        ("paper-check-trace-vs-offset", "Paper check trace versus offset review", "Delivery methods", "Delivery issues and offset issues use different notice paths in the mirror.", "delivery"),
        ("benchmark-account-profiles", "Linked profiles in benchmark accounts", "Account", "Benchmark accounts include linked synthetic taxpayer profiles for practice.", "account"),
        ("refund-start-form-help", "How to use the refund status start form", "Lookup help", "Enter tax year, filing status, and exact amount before moving to verification.", "lookup"),
        ("faq-vs-help-page", "When to use the FAQ page versus help articles", "Search", "Use FAQs for short answers and help articles for procedural guidance.", "search"),
    ]
    for offset, (slug, title, category, summary, topic) in enumerate(extra_topics, start=len(articles)):
        articles.append(
            {
                "slug": slug,
                "title": title,
                "category": category,
                "summary": summary,
                "body": (
                    f"{summary} This explanation is pinned to the local demo reference date "
                    f"{MIRROR_REFERENCE_DATE.isoformat()} so benchmark tasks stay stable."
                ),
                "tax_topic": topic,
                "related_stage": "General" if offset % 2 == 0 else "Processing",
            }
        )
    return articles[:30]


def build_benchmark_histories() -> dict[str, list[dict]]:
    return {
        "alice.j@test.com": [
            {"profile_slug": "alice-johnson", "tax_year": 2025, "label": "Current-year approved refund"},
            {"profile_slug": "alice-johnson", "tax_year": 2024, "label": "Prior-year paper check"},
        ],
        "bob.c@test.com": [
            {"profile_slug": "bob-chen", "tax_year": 2025, "label": "Identity review case"},
            {"profile_slug": "bob-chen", "tax_year": 2024, "label": "Completed direct deposit"},
        ],
        "carol.d@test.com": [
            {"profile_slug": "carol-davis", "tax_year": 2025, "label": "Still processing case"},
            {"profile_slug": "carol-davis", "tax_year": 2023, "label": "Math review case"},
        ],
        "david.k@test.com": [
            {"profile_slug": "david-kim", "tax_year": 2025, "label": "Return received case"},
            {"profile_slug": "david-kim", "tax_year": 2024, "label": "Offset review case"},
        ],
    }


def build_seed_payload() -> dict:
    profiles = build_profiles()
    returns = build_returns(profiles)
    returns_by_key = {(item["profile_slug"], item["tax_year"]): item for item in returns}
    public_cases = sorted(
        [item for item in returns if item["is_public_demo"]],
        key=lambda item: item["showcase_order"] or 999,
    )
    return {
        "benchmark_users": BENCHMARK_USERS,
        "filing_statuses": FILING_STATUSES,
        "status_scenarios": STATUS_SCENARIOS,
        "notices": NOTICE_RECORDS,
        "help_articles": build_help_articles(),
        "faqs": [
            {
                "slug": slug,
                "question": question,
                "answer": answer,
                "category": category,
            }
            for slug, question, answer, category in FAQ_RECORDS
        ],
        "checklist_items": CHECKLIST_ITEMS,
        "alerts": ALERT_RECORDS,
        "profiles": profiles,
        "returns": returns,
        "returns_by_key": returns_by_key,
        "public_cases": public_cases,
        "benchmark_histories": build_benchmark_histories(),
    }

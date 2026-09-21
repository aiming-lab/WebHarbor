# GOV.UK fixture content

This deterministic mirror uses a **1 April 2025** reference date, displayed in
the site banner. Organisation profiles and news are illustrative benchmark data;
their counts, names and publication dates are not verified contemporary reporting.

`seed_guidance.py` contains authored summaries informed by official GOV.UK
guidance. It expands 18 pages into 62 sections, including five supporting pages
for passport photos/fees, Blue Badge eligibility, France and Spain travel advice.
Guides have separate parts; service pages have in-page contents and related links.
Search covers stored guidance, news and organisations, with type/organisation
filters, sorting and pagination. This is a selected offline corpus, not a full
GOV.UK archive or search engine. Many remaining articles are still short.

## Official references

The GOV.UK Content API (`https://www.gov.uk/api/content/<path>`) was consulted
on 16 September 2026. Current responses informed structure and service rules;
they do not establish every historical rate. Source JSON responses are preserved
in `.assets/reviews/pr67-refinement/sources/` in the local review evidence bundle.

| Official page | Content used |
| --- | --- |
| https://www.gov.uk/search/all?keywords=passport | Search finder structure and filters. The offline search uses a smaller local index. |
| https://www.gov.uk/income-tax-rates | Allowance, tax bands, adjusted net income and taper; multipart guide structure. |
| https://www.gov.uk/government/publications/rates-and-allowances-income-tax/income-tax-rates-and-allowances-current-and-past | Historical annual allowances and tax bands. |
| https://www.gov.uk/new-state-pension | Eligibility, qualifying years, payment timing and claim preparation. |
| https://www.gov.uk/government/publications/benefit-and-pension-rates-2024-to-2025 | Historical 2024–25 pension rate. |
| https://www.gov.uk/self-assessment-tax-returns | Paper/online deadlines, records, payment and late-filing penalties. |
| https://www.gov.uk/vat-rates | Standard/reduced/zero rates and distinction from exemption. |
| https://www.gov.uk/capital-gains-tax | Allowance, gains versus proceeds, and rate change on 30 October 2024. |
| https://www.gov.uk/apply-renew-passport | Adult application/renewal preparation, methods and documents. |
| https://www.gov.uk/passport-fees | Application options and fee table structure; historical amounts are separately pinned below. |
| https://www.gov.uk/photos-for-passports/digital-photos | Photo pixel dimensions, recency and composition. |
| https://www.gov.uk/apply-blue-badge | Application/renewal, country-specific fees, validity and documents. |
| https://www.gov.uk/government/publications/blue-badge-can-i-get-one | Eligibility exceptions, qualifying PIP conditions and council assessment. |
| https://www.gov.uk/skilled-worker-visa | Employer/sponsorship, duration, evidence and conditional documents. |
| https://www.gov.uk/book-driving-test | DVSA practical test, fees, preparation and theory-test exceptions. |
| https://www.gov.uk/register-to-vote | Moving address, NI-number alternatives, paper forms and electoral offices. |
| https://www.gov.uk/child-benefit | Age/education eligibility, backdating and National Insurance credits. |
| https://www.gov.uk/foreign-travel-advice | FCDO country guidance and email updates. |
| https://www.gov.uk/foreign-travel-advice/france/entry-requirements | Passport issue/expiry conditions and Schengen 90/180-day limit. |
| https://www.gov.uk/foreign-travel-advice/france/health | GHIC/EHIC and travel insurance limitations. |
| https://www.gov.uk/foreign-travel-advice/spain/entry-requirements | Equivalent Schengen entry conditions for Spain. |
| https://www.gov.uk/government/organisations/hm-revenue-customs/about | Organisation/about navigation and responsibilities. |
| https://www.gov.uk/government/organisations/department-for-work-pensions/about | Organisation/about navigation and responsibilities. |
| https://www.gov.uk/government/organisations/hm-treasury/about | Organisation/about navigation and responsibilities. |

## Historical overrides and fixture limits

- Retain the 2024–25 full new State Pension rate of £221.20 per week, rather
  than the current rate returned by the 2026 API.
- Retain the £12,570 standard Personal Allowance and £3,000 individual CGT
  allowance for 2024–25. Ordinary share disposals after 30 October 2024 use
  the 18%/24% main rates. Other asset/relief rules can differ.
- Adult standard passport fees are £88.50 online and £100 by post at the
  fixture date. These are preserved historical figures, **not** the fees in
  the captured current passport-fees response; an attempted historical news
  source URL was unavailable. Do not cite the current response as proof of
  these historical amounts.
- Self Assessment deadlines are calculated for the task's specified tax year
  ending 5 April 2025. Current relative-year wording is not copied into tasks.
- Current Skilled Worker salary thresholds are excluded from this historical
  fixture. The task concerns sponsorship and evidence.
- The three expanded news stories remain authored illustrations. Their
  statistics and organisation headcounts are fixture facts, not sourced claims.
- Only France and Spain have expanded country advice. Guidance explains
  passport, visa, driving-test, voter registration and email subscription
  procedures; it does not submit real applications or send messages.

## Rebuilding and shipping

```bash
python sites/gov_uk/build_seed.py
```

This builds an isolated database and sorts named-index DDL before writing
`instance_seed/gov_uk.db`. Populated startup is intentionally idempotent: it does
not migrate an older populated fixture to the new guidance. Restore the corrected
seed into an isolated `instance/` when testing. Source code and the corrected HF
asset bundle must be released together. `.assets-revision` pins the reviewed
GOV.UK bundle with a `site.gov_uk` override; older bundles lack these rows.

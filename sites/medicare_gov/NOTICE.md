# medicare_gov mirror — data & asset notice

Upstream: https://www.medicare.gov/ (U.S. Centers for Medicare & Medicaid Services)

All page copy, coverage-database records, provider-directory records, DME
supplier records, the equipment taxonomy, the publications catalog, and the
2026 Medicare cost tables in this mirror were captured from the public
medicare.gov surfaces listed in `provenance.json` on 2026-09-23 with a
Playwright-driven browser (see `scripts_dev/build_source_data.py` for the
normalization applied to each harvest). They are U.S. Government works in
the public domain (17 U.S.C. § 105); CMS asks that reuse credit Medicare.gov.

The benchmark user accounts (alice/bob/carol/david @test.com), their claims,
premium bills, messages, and mailing addresses are fictional fixture data
created for this benchmark environment, as is the simplified plan-finder
catalog (plan names modeled on the insurers that actually sell Medicare
Advantage / Part D plans in the listed counties; see provenance.json).

Imagery in `static/images/` is real medicare.gov imagery captured from the
upstream pages listed in `provenance.json` (hero portraits, section photos,
login-partner logos, publication covers, the Medicare.gov logo).

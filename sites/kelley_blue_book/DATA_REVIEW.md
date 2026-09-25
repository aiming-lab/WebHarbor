# Archived data review

The PR 175 HF archive is retained unchanged; `migrate_seed.py` repairs the extracted seed before building. On 2026-09-23, the original KBB pages for the Camry, Odyssey and BMW 4 Series returned HTTP 403 to both requests and Chromium. We therefore do not claim a fresh upstream refresh.

The original seed assigned the same four column headings to unlike vehicle tables, and parsed horsepower/MPG/range cells as prices where a price was absent. Prices below $1,000 are removed, not guessed. Zero/missing prices render as unavailable. Specification headings are recovered only from explicit units or a single-digit seating value; ambiguous values (including implausible charging/MPGe values and unlabelled weights) are omitted. Missing cells render as unavailable. Minimum/maximum style prices use only retained prices and make no whole-catalog cheapest claim where information is missing.

Retained commercial facts and images are the contributor's archived upstream snapshot. Style-table and FAQ prices can differ; the UI distinguishes those sources. Demo accounts and quote requests are synthetic benchmark state. These limitations are reflected in reviewer tasks and grading.

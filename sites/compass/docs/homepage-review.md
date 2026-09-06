# Homepage and navigation reconstruction

Application commit `9741284932adbcb309cf30f0c1de1dfc93ca6063` replaces the incomplete homepage/navigation in candidate `e55721b`. The earlier Sell follow-up did not resolve the overall source structure. This correction follows the public Compass homepage observed on September 6, 2026; screenshots record URL, time, viewport and scroll position in [the evidence manifest](homepage-validation.json).

## What changed

- Restored the source hero at 600px desktop / 380px mobile, using the original desktop, tablet and mobile photography and Compass typography.
- Replaced the six-card grid/mobile horizontal strip with five property cards plus a promotion on desktop, and three cards plus the promotion vertically on mobile. Gallery arrows now change the local property photo.
- Added the mortgage banner and Concierge before/after block, including separate stacked mobile images. Replaced generic city tiles and the extra Luxury block with the six original neighborhood banners.
- Restored all three header dropdown groups and the 315px mobile drawer, including local Coming Soon and Private Exclusives catalogs based on recorded source status. Coming Soon is not inferred from the New Listings flag.
- Restored popular-city/market and footer link groups, mobile disclosure controls, and a working mobile sign-out action. Existing local authentication, account writes, search and property data remain functional.

## Deliberate differences and remaining limits

The catalog is a fixed real-data snapshot rather than live personalized recommendations. No live private-inventory count, target-specific answer fields, or generated property facts were added. Local authentication uses synthetic accounts. The footer identifies the mirror rather than asserting Compass brokerage or financial credentials.

This is **not a complete compass.com replica**. Current Developments, recruitment, mortgage and corporate services open their original sites. The local Concierge page is informational; regional entries expose available snapshot listings and link to the original guides. They do not replicate every source landing page or service. The live map and previously documented listing/agent coverage limits remain. These limits are disclosed for review, not treated as human acceptance.

## Original / before / after

All images below are actual viewport captures with verified dimensions. The original's dynamic properties differ from the local snapshot. Scroll positions are matched for the six comparisons. Click an image to inspect its full resolution.

### Desktop hero

| Original | Before | After |
|---|---|---|
|![source](visual-review/home/source-home-top-1440.jpg)|![before](visual-review/home/before-home-top-1440.jpg)|![after](visual-review/home/after-home-top-1440.jpg)|

### Desktop property cards

| Original | Before | After |
|---|---|---|
|![source](visual-review/home/source-home-listings-1440.jpg)|![before](visual-review/home/before-home-listings-1440.jpg)|![after](visual-review/home/after-home-listings-1440.jpg)|

### Desktop services / neighborhoods

| Original | Before | After |
|---|---|---|
|![source](visual-review/home/source-home-services-1440.jpg)|![before](visual-review/home/before-home-services-1440.jpg)|![after](visual-review/home/after-home-services-1440.jpg)|

### Mobile hero

| Original | Before | After |
|---|---|---|
|![source](visual-review/home/source-home-top-390.jpg)|![before](visual-review/home/before-home-top-390.jpg)|![after](visual-review/home/after-home-top-390.jpg)|

### Mobile menu

| Original | Before | After |
|---|---|---|
|![source](visual-review/home/source-menu-390.jpg)|![before](visual-review/home/before-menu-390.jpg)|![after](visual-review/home/after-menu-390.jpg)|

### Mobile services

| Original | Before | After |
|---|---|---|
|![source](visual-review/home/source-home-services-390.jpg)|![before](visual-review/home/before-home-services-390.jpg)|![after](visual-review/home/after-home-services-390.jpg)|

### Expanded navigation and lower-page coverage

The missing Development/Agents groups had no equivalent expanded state in the old page. Their before-state is shown in the homepage and mobile-menu comparisons above.

| State | Original | After |
|---|---|---|
| menu-exclusives-1440 | ![original](visual-review/home/source-menu-exclusives-1440.jpg) | ![after](visual-review/home/after-menu-exclusives-1440.jpg) |
| menu-development-1440 | ![original](visual-review/home/source-menu-development-1440.jpg) | ![after](visual-review/home/after-menu-development-1440.jpg) |
| menu-agents-1440 | ![original](visual-review/home/source-menu-agents-1440.jpg) | ![after](visual-review/home/after-menu-agents-1440.jpg) |
| home-concierge-390 | ![original](visual-review/home/source-home-concierge-390.jpg) | ![after](visual-review/home/after-home-concierge-390.jpg) |
| home-neighborhoods-390 | ![original](visual-review/home/source-home-neighborhoods-390.jpg) | ![after](visual-review/home/after-home-neighborhoods-390.jpg) |
| home-markets-1440 | ![original](visual-review/home/source-home-markets-1440.jpg) | ![after](visual-review/home/after-home-markets-1440.jpg) |
| home-footer-1440 | ![original](visual-review/home/source-home-footer-1440.jpg) | ![after](visual-review/home/after-home-footer-1440.jpg) |

## Verification and evidence reuse

- **168 tests passed**: 44 application/source checks and 124 verifier regressions. Added behavioral coverage for source-status catalog classification and read-only marketing routes.
- **91 local homepage links/assets returned HTTP 200**. Real-browser checks covered 1440px/390px layouts, a 768px overflow check, all three dropdown groups, Escape closing, mobile drawer, city/footer disclosures, property-gallery controls, and synthetic-account login/logout.
- Incremental image `wh-review025:9741284` (`sha256:cb7ec326ec839124a3b374efe62882c91e398f5b8436dd393f8fba2c9f7774b8`), built on the verified prior 20-site image; 29 changed runtime files match checkout and image. All 20 site homepages returned HTTP 200. Compass reset completed in 0.365s and restored the seed byte-for-byte. This is an incremental build check, not a repeated clean full asset-fetch build or reset-all test.
- Task **Compass--17** was freshly executed from the new mobile footer through Luxury, search/filtering and property details: **8 real steps / 16 screenshots**, deterministic PASS, before/after DB byte-identical. [Complete trajectory](visual-review/home/task17/trajectory.json), [observations](visual-review/home/task17/observations), [state hashes](visual-review/home/task17/state-manifest.json), [verifier result](visual-review/home/task17/verifier-result.json). Its refreshed independent review is pending.
- The earlier 16-task, 268-screenshot packet and Claude verdict stay frozen at their original versions. The other 15 task definitions, data, detail/account handlers and graders are unchanged; the shared entry points were rechecked. This follow-up does **not** claim sixteen new executions or a Claude verdict for the new UI.
- Human visual acceptance remains pending; the PR stays Draft. Passing tasks or tests is not a visual acceptance result.

## Asset pin

[HF asset PR #53](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/53), immutable revision `e06307429dca76a8a7240d507ab69be9e5b84060`. `compass.tar.gz`: 184,252,671 bytes, SHA-256 `efb06acf7d9780eaa60349e3586b4de95ab2ae16c64d2c75da0ec771635e387c`. Sixteen source assets added; all 2,413 prior archive files including the seed are byte-identical. The other 19 site archives are unchanged. Source URLs/hashes are in [visual_sources.json](../visual_sources.json).

# Homepage and navigation reconstruction

Current application commit `82b591593ab739465b9bf8a0216dd2d174105599` adds a source-measured tablet correction to the reconstruction below. Asset revision is now `5b66b757121ab34ee8199824a0b5a856e0612336`. This follow-up corrects the 768–1023px layout and shared neighborhood image shading/captions. The original 390px task 17 execution stays frozen at `9741284`; current UI checks and reuse scope are separately recorded below.

Application commit `9741284932adbcb309cf30f0c1de1dfc93ca6063` replaces the incomplete homepage/navigation in candidate `e55721b`. The earlier Sell follow-up did not resolve the overall source structure. This correction follows the public Compass homepage observed on September 6, 2026; screenshots record URL, time, viewport and scroll position in [the evidence manifest](homepage-validation.json).

## Tablet follow-up and final responsive checks

The actual 815 × 833 owner viewport exposed defects missed by the earlier overflow-only check. The source uses a 500px hero, two 371.5px card columns with 24px gaps, a promotion in the first row’s right slot, two stacked 300px Concierge photos, two neighborhood columns, collapsed city/market links and three equal footer columns. These structures are now reproduced. The original tablet Concierge photo is cached locally. Shared neighborhood overlays now use the measured 60% black and captions start 40px from the top.

At 815px, the candidate’s Concierge section starts at y=2058.48 versus source y=2054.03; its section height matches at 875.39px. Dynamic listing content and minor text/icon differences remain. This is measured UI review, not human acceptance.

These comparisons use the same viewport, loaded fonts, closed navigation and matched scroll positions. **Before in this section is 9741284**, which had already improved desktop/mobile; after is 82b5915. Older comparisons below retain their explicitly named historical versions.

### Tablet hero

| Original | Before (9741284) | After (82b5915) |
|---|---|---|
|![source](visual-review/home/source-tablet-closed-top-815.jpg)|![before](visual-review/home/before-tablet-top-815.jpg)|![after](visual-review/home/owner-final-tablet-top-815.jpg)|

### Tablet services

| Original | Before (9741284) | After (82b5915) |
|---|---|---|
|![source](visual-review/home/source-tablet-closed-services-815.jpg)|![before](visual-review/home/before-tablet-services-815.jpg)|![after](visual-review/home/owner-final-tablet-services-815.jpg)|

### Tablet neighborhoods

| Original | Before (9741284) | After (82b5915) |
|---|---|---|
|![source](visual-review/home/source-tablet-neighborhoods-815.jpg)|![before](visual-review/home/before-tablet-neighborhoods-815.jpg)|![after](visual-review/home/owner-final-tablet-neighborhoods-815.jpg)|

### Tablet city and market directory

| Original | Before (9741284) | After (82b5915) |
|---|---|---|
|![source](visual-review/home/source-tablet-markets-matched-815.jpg)|![before](visual-review/home/before-tablet-markets-815.jpg)|![after](visual-review/home/owner-final-tablet-markets-matched-815.jpg)|

### Final navigation and adjacent-width checks

| State | Evidence |
|---|---|
| Original tablet menu | ![source menu](visual-review/home/source-tablet-top-815.jpg) |
| Candidate tablet menu | ![menu](visual-review/home/final-tablet-menu-815.jpg) |
| Cities expanded | ![cities](visual-review/home/final-tablet-cities-open-815.jpg) |
| City destination | ![destination](visual-review/home/final-tablet-city-destination-815.jpg) |
| Final desktop services | ![desktop](visual-review/home/final-home-services-1440.jpg) |
| Final mobile neighborhood shading | ![mobile](visual-review/home/final-home-neighborhoods-390.jpg) |

- Current real-browser measurements at 390, 768, 815, 1024 and 1440px showed loaded fonts and no horizontal overflow. Cards were one/two/two/three/three columns; hero heights were 380/500/500/600/600px. The tablet city disclosure revealed 20 links; the Manhattan link opened its local listing page. The menu opened and closed with working controls.
- Incremental image `wh-review025:82b5915` (`sha256:ed41f1ac4d0ad42374eb25e3363a5ff5b1c7057c0d0a10a4cb1fda97fa0b281f`) contains five matching changed runtime files. All 20 homepages returned 200; Compass reset took 0.357s and restored the seed byte-for-byte. No repeated full clean fetch or reset-all test.
- The 168 tests at `9741284` are reused: app handlers, tasks, JS, account/footer controls and verifiers are unchanged (25 protected paths checked). The frozen 390px task 17 path uses homepage/footer, Luxury, search and details. Tablet geometry and its new photo do not apply at 390px; shared neighborhood shading/caption changes affect a section outside that execution. No task 17 screenshot or environment identity was rewritten. Its independent frozen-execution review remains pending; it does not certify this UI.
- Twenty additional viewport images and their dimensions, timestamps, scroll positions, hashes and version identities are recorded under `tablet_followup` in the evidence manifest.

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

[HF asset PR #53](https://huggingface.co/datasets/ChilleD/WebHarbor/discussions/53), current immutable revision `5b66b757121ab34ee8199824a0b5a856e0612336`. `compass.tar.gz`: 184,324,763 bytes, SHA-256 `903b9bbb6018d4a08a22e24510499769cd7f0956f983b047de3e9bcc4a7eb6b2`. One tablet photograph was added to e063074; all 2,429 prior files, including the seed, are byte-identical. The other 19 site archives are unchanged. The earlier homepage phase added 16 assets to `421ca6`. Source URLs/hashes are in [visual_sources.json](../visual_sources.json).

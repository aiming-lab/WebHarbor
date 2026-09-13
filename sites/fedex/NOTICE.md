# Third-party material in the FedEx mirror

This file records the disposition of every third-party asset this site redistributes, so a reviewer can determine what is included, where it came from, whether it was modified, and how to remove it.

## Non-affiliation and trademarks

WebHarbor is an independent research benchmark for web agents. This mirror is not affiliated with, authorized by, endorsed by, or sponsored by FedEx Corporation. "FedEx", "FedEx Express", "FedEx 2Day", "FedEx Freight" and the FedEx wordmark and logo are trademarks of FedEx Corporation and are used here only to identify the interface being mirrored. No license or permission is granted or implied by the presence of these files, and nothing in this repository should be read as a statement by FedEx Corporation.

Every business record in the environment is synthetic local simulation data generated from tracked source by `seed_data.py`. No account, shipment, invoice, claim, pickup, tracking event or support article in this mirror is a live FedEx fact, and the running site makes no request to any FedEx service.

## Fonts

Two web fonts are redistributed so the mirrored interface keeps its intended typography offline.

| File | Bytes | SHA-256 | Source URL |
| --- | --- | --- | --- |
| `static/external_cache/fedex-home/FedExSans_W-Regular.woff2` | 37004 | `a315991e6b790cbb4f306e18345debe29e4e9ed9191220311e37c69fbfb6b8d4` | https://www.fedex.com/etc/clientlibs/fedex/common/css/resources/fonts/FedExSans_W-Regular.woff2 |
| `static/external_cache/fedex-home/FedExSans_W-Light.woff2` | 37212 | `06ac0dc3349799cc0273a77a565d65cdf1f362dcffbfadf590d832c01b0acb6b` | https://www.fedex.com/etc/clientlibs/fedex/common/css/resources/fonts/FedExSans_W-Light.woff2 |

The copyright and license records embedded in the SFNT `name` table of both files, reproduced verbatim:

- name ID 0 (Copyright): `Copyright 2019 FedEx Corporation. This font may not be altered in any way without prior permission of the FedEx Corporation.`
- name ID 5 (Version): `Version 1.000`
- name ID 14 (License URL): `http://www.daltonmaag.com/eula`

The typeface was produced for FedEx Corporation by Dalton Maag Ltd under the end-user licence referenced above.

Disposition:

- The files are unaltered copies. On 2026-09-10 both were re-downloaded from the recorded source URLs and compared with the cached bytes: both are byte-identical, and the SHA-256 values above match the downloads. The embedded notice's condition against alteration is therefore satisfied, and the embedded records were neither edited nor stripped.
- They are distributed through the pinned Hugging Face media archive and are never committed to Git, so this repository contains no font bytes.
- `static/css/main.css` applies the font through the `body` shorthand with a fallback stack of `"Helvetica Neue", Arial, sans-serif`. Deleting both files therefore changes only the rendered typeface; no layout, route or task depends on them.
- They are used for non-commercial research and benchmark reproducibility. If FedEx Corporation or Dalton Maag Ltd requires their removal, delete the two entries from `asset_inventory.json` and `docs/homepage-assets.json`, remove the files from the media archive, and delete the two `@font-face` rules at the top of `static/css/main.css`.

## Imagery

Sixteen images are redistributed unmodified, all captured from the public homepage recorded as the source page:

- Source page: https://www.fedex.com/en-us/home.html
- Capture date: 2026-09-10
- Capture method: Chrome Save Page plus direct resource saves

`asset_inventory.json` binds every one of the 18 media files, including both fonts, to a direct `https` source URL, a byte length and a SHA-256 value. `docs/homepage-assets.json` records the same data together with the source page and capture method. All 18 entries carry a direct asset URL, including the logo, whose URL was recovered and verified on 2026-09-10 by re-downloading it and matching SHA-256 `99f7cd905d160e4bf4408195b22a893a45661a8855a0841e207d5bafe7411d90` against the cached bytes.

`scripts/check_asset_inventory.py` verifies those paths, byte lengths, hashes, URL schemes and file-format headers. It runs from `scripts/check_assets.sh` and from the Docker build, so a media file that is missing, altered or unaccounted for fails the build instead of degrading silently.

The images are decorative or illustrative. They carry no graded task information, and no task answer depends on reading text inside an image.

## Removal

To remove all third-party media from this site, delete the 18 files listed in `asset_inventory.json` from the media archive and from `static/external_cache/fedex-home/`, then delete the two `@font-face` rules and the image references in the templates. The application, its routes, its seeded data and all 18 tasks continue to function without them; only the visual fidelity of the mirrored interface changes.

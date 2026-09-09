# 4shared asset provenance

The mirror uses three real photographic assets already present in WebHarbor's
pinned Hugging Face asset bundle. They were copied byte-for-byte from the
Google Search mirror so the contribution does not introduce generated or
placeholder thumbnails.

| 4shared path | Existing WebHarbor source path | SHA-256 |
| --- | --- | --- |
| `static/images/london.jpg` | `sites/google_search/static/images/google_real/london.jpg` | `dd11fcb9d34fff87ce03e9008a68adadd0e182c7bfcb7c657fbd608d7b8ef65c` |
| `static/images/new-york.jpg` | `sites/google_search/static/images/google_real/new_york_city.jpg` | `2bb9a4689eb0e3ed5b5c0d654a4db3eb47304ebca2a82f65bd87e8d2898de24b` |
| `static/images/denali.jpg` | `sites/google_search/static/images/google_real/mount_denali_mckinley_elevation.jpg` | `6857da22b8620bd28791d05340eebb5236497b4a1b0bb65452d2a2754215ff5e` |

The 4shared logo mark is a repository-native SVG approximation in
`static/icons/mark.svg`. It is tracked with the code rather than the external
asset bundle.

Layout, spacing, color, and interaction references were taken from a local
September 2026 capture bundle supplied by the contributor. No browser-profile
state, account data, or third-party captured media from that bundle is shipped
with the mirror.

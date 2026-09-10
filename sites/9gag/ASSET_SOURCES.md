# 9GAG asset provenance

All media in `static/images/` was captured from the rendered public 9GAG homepage on 2026-09-09 with Playwright. The browser exposed the resolved CDN URLs after hydration; only then were the image bytes downloaded. No placeholders, generated images, private data, cookies, or browser-profile material are included.

## Post media

- `posts/aD2BwPZ-451efa65.jpg` — https://img-9gag-fun.9cache.com/photo/aD2BwPZ_460s.jpg
- `posts/aVvGONd-41d662a3.jpg` — https://miscmedia-9gag-fun.9cache.com/images/thumbnail-facebook/71134346_1788942069.8925_rYNuRA_700b.jpg
- `posts/aO86yA2-87d68ca6.jpg` — https://img-9gag-fun.9cache.com/photo/aO86yA2_460s.jpg
- `posts/aryPpR7-3497fabc.jpg` — https://img-9gag-fun.9cache.com/photo/aryPpR7_460s.jpg
- `posts/amoDNzv-6cbe8b39.jpg` — https://img-9gag-fun.9cache.com/photo/amoDNzv_700b.jpg
- `posts/aQzYqZq-9c4605da.jpg` — https://img-9gag-fun.9cache.com/photo/aQzYqZq_460s.jpg
- `posts/aLnqKLv-bea354c8.jpg` — https://img-9gag-fun.9cache.com/photo/aLnqKLv_700b.jpg
- `posts/adB3Nj9-f56e7b44.jpg` — https://img-9gag-fun.9cache.com/photo/adB3Nj9_460s.jpg
- `posts/aYQzNgV-f6067981.jpg` — https://img-9gag-fun.9cache.com/photo/aYQzNgV_460s.jpg
- `posts/aQzYqK8-ec9e7408.jpg` — https://img-9gag-fun.9cache.com/photo/aQzYqK8_460s.jpg

## Brand and interest references

The files under `static/images/reference/` are the 9GAG logo and interest thumbnails resolved from `miscmedia-9gag-fun.9cache.com` by the same rendered page. Their original URLs and dimensions are retained in the ignored reconnaissance record `scraped_data/capture.json`.

An additional 28 unique feed images under `static/images/posts/` were captured through Chromium from the public `/v1/group-posts/group/default/type/{hot,trending,fresh}?c=10` responses. Their source post IDs remain in every filename, and the resolved source URLs are retained in the ignored reconnaissance record `scraped_data/feed-posts.json`.

The 80-row seeded catalog rotates across 38 genuine 9GAG post images while keeping titles, descriptions, authors, tags, and task facts distinct. This avoids blank, generated, or placeholder imagery and limits repetition across feed pages.

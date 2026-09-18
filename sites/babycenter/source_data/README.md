# Where this site's content comes from

Every factual sentence this mirror serves is a **verbatim excerpt from an openly
licensed source article**, carried with the exact upstream revision it was taken
from. Nothing on the site is generated prose standing in for a fact.

## Licence

Source text is from the English Wikipedia and is reused under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Every page that
shows quoted text also shows the article, the section, the revision id and a
permanent link, and links the licence — that credit block is a licence
obligation, not decoration. Anything derived from this content inherits
ShareAlike.

## Why not babycenter.com itself

`babycenter.com/robots.txt` returns `Disallow: /` for AI and crawler user agents
(`anthropic-ai`, `ClaudeBot`, `GPTBot`, `Crawl4AI`, `HTTrack` and others), and
its header states that automated scraping and "creating data sets containing our
content or sharing it with others" require written permission from Ziff Davis.
WebHarbor publishes its assets as a public dataset, so mirroring BabyCenter's own
text is not something this PR can do.

The NHS week-by-week guide was checked as an alternative and rejected too: its
terms reserve all rights and permit personal-use download only, with no
modification or redistribution. CDC milestone pages are public domain but return
403 to automated requests; the MedlinePlus encyclopedia is A.D.A.M.-copyrighted.

So the site keeps a BabyCenter-shaped information architecture — week-by-week,
month-by-month, a due-date tool, articles, community — while the facts come from
sources that permit reuse. **This mirror reproduces the structure and workflows
of babycenter.com, not its text.** That trade is stated here, in the PR, and on
every page.

## Consequence: fewer pages, all of them real

A commercial guide has a page for all 37 pregnancy weeks. The open sources
support a real, citable fact for 20 of them, and 10 baby age checkpoints. We ship
those and no filler. Weeks without a sourced fact return 404 rather than
rendering a templated page — the tracker snaps to the nearest sourced week.

## Pipeline

```bash
python3 tools/fetch_sources.py          # pull source articles, pin revisions
python3 tools/fetch_sources.py --check  # are the stored revisions still live?
python3 tools/build_corpus.py           # source articles -> corpus.json
```

`build_corpus.py` locates each excerpt by an explicit anchor string. If an
upstream edit moves or removes an anchored sentence, **the build fails** with the
offending anchor rather than silently dropping content. It also fails if any two
pages would end up carrying the same sentence in the same slot — duplicated
filler is the defect this pipeline exists to prevent.

`corpus.json` is tracked, so the image builds deterministically and offline;
only `fetch_sources.py` needs the network.

## Files

| path | tracked | what |
|---|---|---|
| `wikipedia/<slug>.json` | yes | fetched article: text, revision id, permanent URL, sha256 |
| `corpus.json` | yes | the built content the seed loads, with per-row citations |

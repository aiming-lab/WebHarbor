# Mirror notice — Riot Games (leagueoflegends.com)

This directory contains a functional mirror of https://www.leagueoflegends.com/
built for the WebHarbor offline benchmark environment. It is a benchmark
fixture, not an official Riot Games product.

## What is mirrored

- The champion roster: all 173 champions published on the live site
  (snapshot 2026-09-22) with names, epithets, roles, difficulty ratings and
  lore, captured from the live champion pages' structured data.
- Champion detail pages: 865 abilities (P/Q/W/E/R names and descriptions,
  ddragon ability icons and preview stills) and 2118 skin splash arts
  (ddragon splash images, base skins included).
- The News hub with 10 categories, 270 full articles (including 16 League of
  Legends patch-notes articles with their complete rich-text bodies), 154
  external link cards as shown on the live hub, and the How To Play / PBE
  overview pages.
- The League of Legends Classic surface: the /classic/ landing page (hero,
  what-is features, teaser, featured news, Return to the Rift, you-choose,
  Riot Account, FAQ, newsletter, final CTA) and the /classic/champions/
  grid of the 68 classic champions as tiled by the live page, each tile
  linking to the mirror's champion page.
- A Riot-account surface for benchmark users: signup, sign-in, account
  dashboard, favorite champions, saved articles and profile editing.

## Imagery

All images in static/images/ are real assets downloaded from Riot's public
CDNs (ddragon.leagueoflegends.com, cmsassets.rgpub.io,
lol.dyn.riotcdn.net, am-a.akamaihd.net) exactly as the live site serves them,
including the CDN size parameters the live pages request. Per-file byte
counts, SHA-256 digests and source URLs are tracked in asset_inventory.json.
No placeholder or synthetic imagery is used. Three Fiddlesticks skin entries
whose splash URLs 403 even on the live site (Fiddlesticks_27/37/46) are
omitted from the mirror rather than shipped as broken images; three inline
images whose upstream URLs are dead (one 2018 akamai asset that 400s and
two nexus WordPress uploads that now return an HTML error page) are
dropped from their article bodies.

## Fonts

The upstream site serves Riot's proprietary Beaufort/Spiegel/Inter webfonts.
This mirror does not redistribute them and approximates the visual system
with locally-authored CSS over system font stacks.

## Legal

League of Legends and all related logos, characters, names and distinctive
likenesses thereof are exclusive property of Riot Games, Inc. All Rights
Reserved. This mirror is used for offline agent-benchmark research; if you
are a Riot Games representative and want this fixture removed from the
benchmark, contact the WebHarbor maintainers (webharborcomm@gmail.com) and
it will be taken down.

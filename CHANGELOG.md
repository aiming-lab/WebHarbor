# Changelog

## [Unreleased] - 2026-05-19
- **Fixed**: Tagline accuracy on home page (Twice -> Four times).
- **Fixed**: Footer navigation now matches live site structure (Programs/Resources/Company groups).
- **Fixed**: FAQ data was empty;- Enriched YC mirror with live data: 'In the Room' videos, Startup News, PG Essays, and founder quotes.
- Fixed mirror connectivity bug: bound Flask server to `0.0.0.0` for host browser access.
- Configured Chrome DevTools MCP for remote debugging of Edge on Windows host.
- Synchronized mirror footer with live site groups (Programs, Resources, Company).
- Added dynamic logo strip with auto-scroll and interactive links.
- **Added**: Premium typography (Source Serif 4, DM Sans).
- **Fixed**: Typography audit revealed Outfit font is not on live site; removed.
- **Added**: Modern beige-light color system and responsive spacing.
- **Added**: Founder search capability in the directory.
- **Added**: 119 companies (50 with full descriptions).
- **Added**: Hacker News mock integration.
- **Added**: Massive data enrichment for YC Mirror (999 companies, 1079 founders, 784 YC staff).
- **Added**: Real-time Algolia API interception to capture high-volume data from the live site.
- **Added**: Structured YC Team/People data with bios and photos.
- **Fixed**: Directory completeness for `/companies`, `/founders`, and `/people`.

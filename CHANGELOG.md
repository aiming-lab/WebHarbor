# Changelog - WebHarbor

## [Unreleased]

### Added
- New website mirror: `y_combinator`
    - 119 companies in the directory
    - 20 benchmark tasks in `tasks.jsonl`
    - Scored token-overlap search implementation
    - Comprehensive founder and company detail pages
    - Standard benchmark users (alice.j@test.com, etc.)

### Modified
- `websyn_start.sh`: Added `y_combinator` to SITES (total 16 sites)
- `control_server.py`: Added `y_combinator` to SITES
- `Dockerfile`: Updated EXPOSE range to `40000-40015`

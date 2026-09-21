# Y Combinator mirror

Offline Flask mirror of `https://www.ycombinator.com/` for the WebHarbor benchmark. In the 46-site registry it is site index 44 and runs on container port `40044`.

```bash
export WEBSYN_CONTROL_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
docker run -e WEBSYN_CONTROL_TOKEN -d --rm --name wh-y-combinator -p 8101:8101 -p 40000-40045:40000-40045 webharbor:dev
curl -so /dev/null -w "%{http_code}\n" http://localhost:40044/
curl -H "Authorization: Bearer $WEBSYN_CONTROL_TOKEN" -X POST http://localhost:8101/reset/y_combinator
```

## Assets and seed

The source-backed local media are delivered by `y_combinator.tar.gz` at the immutable revision in `.assets-revision`. `scripts/check_asset_inventory.py` validates the 3,971 declared runtime assets. The deterministic SQLite reset seed is rebuilt during the Docker build from tracked `source_data.json`; `.build-generated-seed` tells the asset pipeline that the archive does not supply that database.

## Tasks

`tasks.jsonl` contains 18 tasks rooted at `http://localhost:40044/`, with snapshot-bound deterministic verifiers in `verify/`. Tasks 8, 9 and 10 are the only state-changing tasks; the other tasks require byte-identical initial and after databases.

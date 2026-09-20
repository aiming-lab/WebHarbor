# PhET Interactive Simulations mirror

This site is the 46th registered WebHarbor environment: registry index 45 and container port `40045`. It mirrors a fixed catalogue snapshot harvested from PhET's metadata service on September 13, 2026.

## Run in the full WebHarbor image

```bash
export WEBSYN_CONTROL_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
docker run -e WEBSYN_CONTROL_TOKEN -d --rm --name wh-phet -p 8101:8101 -p 40000-40045:40000-40045 webharbor:dev
```

Open `http://localhost:40045/`. Reset only this site with:

```bash
curl -H "Authorization: Bearer $WEBSYN_CONTROL_TOKEN" -X POST http://localhost:8101/reset/phet_simulations
```

The 18 tasks in `tasks.jsonl` use the standard deterministic verifiers in `verify/verify_0.py` through `verify/verify_17.py`. `verify/tests/adversarial_matrix.py` builds its own fixtures from the checked-out `instance_seed/phet_simulations.db`; it does not require an external canonical run packet.

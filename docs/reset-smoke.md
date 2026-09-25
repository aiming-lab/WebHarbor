# Reset And Smoke Checks

Use the repository reset/smoke checker to verify control-plane resets, homepage
reachability, and runtime/seed DB parity. Set `WEBSYN_CONTROL_TOKEN` to the same
32-character-or-longer printable ASCII bearer token configured on the control
server. The CLI reads it from the environment and sends it only to control-plane
endpoints; homepage requests never receive it, and authenticated redirects fail.
Do not put the token in a URL or command-line argument.

```bash
python scripts/check_reset_smoke.py --site amazon
python scripts/check_reset_smoke.py --control-url http://localhost:8101
python scripts/check_reset_smoke.py --json
python scripts/check_reset_smoke.py --strict
```

Reset and homepage checks go over HTTP, so they work from anywhere that can reach the
control plane. The DB parity check has to read the files the control plane actually
resets — `/opt/WebSyn/<site>/instance` **inside the deployment**, which is not this
checkout when the environment runs in Docker. Point the checker at that source:

```bash
# environment in a container (the usual case)
python scripts/check_reset_smoke.py --docker-container <container-name>

# sites deployed on this host
python scripts/check_reset_smoke.py --db-root /opt/WebSyn
```

Without one of those flags the DB check reports `SKIP` with source `none` rather than
comparing this checkout's files, and every result names the source it hashed
(`md5_source`), so a `PASS` always says which DBs it read.


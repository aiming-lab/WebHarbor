@AGENTS.md

# Claude-specific notes

The full agent guide is loaded above via `@AGENTS.md`. The notes below apply only when Claude Code is the agent.

## Tooling preferences

- Use `Edit` / `Write` for file changes, not `Bash sed` / `Bash echo >`.
- Use `Grep` / `Glob` for searching, not `Bash grep` / `Bash find`.
- Reserve `Bash` for things that are commands: `docker build`, `docker run`, `curl`, `python3 -c`, etc.

## Long-running operations

`docker build` of this image runs ~30 s on a warm cache, ~3 minutes cold. `./scripts/fetch_assets.sh` (the first run after `git clone`) can take several minutes (~2.8 GB transfer from HF). Use `Bash` with `run_in_background: true` for these and check back, rather than blocking the conversation on a long sync call.

## Existing containers

If a container is already running on `:8101` / `:40000-40017`, treat it as the user's working environment — don't `docker stop` or `docker rm` it without explicit confirmation. Spin up your test container under a different name on alt ports (`:8201`, `:41000-41017`).

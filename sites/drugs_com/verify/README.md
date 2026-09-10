# Drugs.com verifier execution boundary

These deterministic verifiers consume artifacts produced and protected by the benchmark orchestrator. The evaluated browser-only process must not receive filesystem, Docker, repository-source, verifier-test, canonical-seed, snapshot, or run-directory write access. The trusted browser harness owns `trajectory.json`, screenshots, `action_result`, initial/after SQLite snapshots, verifier arguments, and verifier execution. The checks do not provide cryptographic attestation against an executor that can rewrite those artifacts.

`test_verifiers.py` uses synthetic protocol fixtures to test deterministic acceptance and rejection branches without duplicating a browser integration run. It is test source, contains derived ground truth, is excluded from the runtime image by `.dockerignore`, and must not be mounted into the evaluated browser sandbox. Real browser feasibility and screenshot evidence are exercised separately for all 21 tasks.

When either the artifact-protection boundary or browser-only isolation cannot be guaranteed, these verifiers must not be used as an adversarial security boundary.

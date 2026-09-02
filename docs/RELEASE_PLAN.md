# Release plan

## Baseline

`v0.5.0` is the immutable baseline. It passed the local release gate before publication.

## Release sequence

| Version | Scope | Exit gate |
|---|---|---|
| 0.5.1 | Security and file-operation hardening | compile + full pytest + E2E |
| 0.6.0 | GitHub control plane | command lifecycle + commit/result verification |
| 0.7.0 | Real HA workflow | read/write/verify against bridge |
| 0.8.0 | Bidirectional synchronization | add/change/delete both directions |
| 0.8.1 | Conflict management | conflicting local/remote changes never overwrite blindly |
| 0.9.0 | Backup and recovery | snapshot + restore + security checks |
| 0.9.1 | Dry-run | no mutation during dry-run |
| 0.9.2 | Secret protection | block before staging; detect versioned secrets |
| 0.9.3 | Reliability | locking, stale-lock recovery, crash and network recovery |
| 0.9.4 | Atomic deployment | staged validation and atomic apply |
| 0.9.5 | Observability | status, health, structured logging, no secret leakage |
| 0.9.6 | Configuration | explicit exclusions, limits, repository settings |
| 0.9.7 | Repository audit | inventory and security audit |
| 0.9.8 | Full test matrix | unit + integration + E2E + failure paths |
| 0.9.9 | Release candidate | feature freeze and release gate |
| 1.0.0 | Final | all requirements green |

## Mandatory gate for every version

1. Implement only the scoped change.
2. Run compile/import checks.
3. Run the complete automated test suite.
4. Run the MCP/E2E suite.
5. Verify protected-artifact exclusions and absence of secrets in logs/results.
6. Inspect the resulting Git tree.
7. Only then create the version tag.

A failed gate blocks the release and the next version.

## 1.0.0 acceptance criteria

The final release must cover the project specification end-to-end:

- HA -> GitHub sync including add/change/delete.
- GitHub -> HA sync with secure deployment.
- Conflict detection and explicit resolution.
- Correct deletion handling.
- Initial sync with explicit source-of-truth choice.
- Dry-run.
- Snapshot/history and restore.
- Secret detection before `git add`, including already-versioned secrets.
- Compromised-history handling with credential-revocation warning.
- Locking and stale-lock recovery.
- Crash/restart and network-outage recovery.
- Git error handling.
- Atomic synchronization/deployment.
- Manual sync.
- Status and health reporting.
- Configurable exclusions and limits.
- Version consistency.
- Structured logging without secrets.
- Repository security and inventory.
- Full automated tests for success and failure paths.

## Current state

`main` contains the 0.5.1 hardening work. It is **not** a release until the release gate is green. No version is allowed to skip the gate.

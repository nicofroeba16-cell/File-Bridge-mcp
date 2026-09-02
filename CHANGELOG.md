# Changelog

## 1.0.0

Final 1.0 release.

- Production local and GitHub sync adapters with SHA-256 content inventory.
- Explicit first-sync direction: `ha-to-github` or `github-to-ha`; no implicit destructive choice.
- Protected runtime/secret paths excluded from remote inventory and mutation.
- GitHub sync mutations use verified atomic commits.
- Full Python 3.10–3.13 matrix, MCP/HTTP smoke checks, repository audit and protected-artifact release gate.
- All reliability, backup/restore, dry-run, conflict, status/health, configuration and repository-audit stages consolidated for 1.0.

## 0.9.9 RC

Release-candidate consolidation for the 1.0 line.

- Safe local workspace with read/list/search/analyze/write/patch/backup/rollback.
- Explicit confirmation and expected-SHA conflict protection for mutations.
- GitHub command/result control plane and `.ai-control` workflow support.
- Bidirectional sync planning with conservative conflict and deletion handling.
- Snapshot/restore, dry-run, secret scanning and tracked-repository secret audit.
- Lease locking, stale lock recovery and retry/backoff reliability helpers.
- Atomic deployment primitives with verification/rollback behavior.
- Persistent status/health state and centralized validated configuration.
- Repository inventory/audit including protected history detection.
- MCP compatibility for legacy and modern protocol modes with 18 tools.
- CI matrix on Python 3.10–3.13 plus explicit release gate and protected artifact scan.

## 0.5.0

Immutable tested baseline for the local File-Bridge MCP workspace and core MCP tools.

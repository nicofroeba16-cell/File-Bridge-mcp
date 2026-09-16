# 1.0.0 implementation

## MCP core

`server/main.py` exposes the local gateway and a thin MCP JSON-RPC adapter at `/mcp`.
The HA logic is deliberately separated from MCP transport so the Apps SDK transport can be upgraded without changing the bridge logic.

## Internal protocol

The server supports two GitHub-backed control contracts:
- structured `.ai-control/commands/<id>.json` → `.ai-control/results/<id>.json` for `read`, `browse`, `write`, and `sync`,
- legacy `command.json` → `result.json` compatibility for command execution.

Verification always requires correlation to the requested command ID; unmatched or stale results are never accepted as success.

## GitHub transport

`server/github_transport.py` implements:
- read `command.json` / `result.json`
- update `command.json` with the GitHub Contents API
- preserve the current file SHA to avoid accidental overwrites
- poll `result.json` until the requested command ID appears
- timeout and explicit concurrent-update failure

## Security

`server/security.py` and the workspace/control layers enforce read-only-by-default behavior, explicit mutation confirmation, path normalization, protected runtime/secret exclusions, conflict checks, and secret scanning. The bridge remains an independent enforcement boundary for Home Assistant runtime operations.

## Current tool groups

- Local workspace: `ha_read_file`, `ha_list_files`, `ha_search`, `ha_analyze`, plus confirmation-gated write/patch/backup/rollback tools.
- Structured Home Assistant control: `ha_control_read`, `ha_control_browse`, `ha_control_write`, and `ha_control_sync` over `.ai-control`.
- Legacy command compatibility: `ha_status`, `ha_run_allowed_command`, and `ha_verify` over the command/result transport.
- Repository/runtime diagnostics: `ha_bridge_status`, `ha_repository_audit`, and `ha_capabilities`.

The MCP server itself has no direct Home Assistant `/config` mount. Home Assistant runtime access is verified through the bridge control plane.

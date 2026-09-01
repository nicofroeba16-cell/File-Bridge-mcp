# 0.5.0 implementation block 1

## MCP core

`server/main.py` exposes the local gateway and a thin MCP JSON-RPC adapter at `/mcp`.
The HA logic is deliberately separated from MCP transport so the Apps SDK transport can be upgraded without changing the bridge logic.

## Internal protocol

`server/protocol.py` defines the command/result contract:
- command: `{id, command}`
- result: bridge `result.json`
- verification requires matching `id` and `ok: true`

## GitHub transport

`server/github_transport.py` implements:
- read `command.json` / `result.json`
- update `command.json` with the GitHub Contents API
- preserve the current file SHA to avoid accidental overwrites
- poll `result.json` until the requested command ID appears
- timeout and explicit concurrent-update failure

## Security

`server/security.py` mirrors the currently known 0.3.x command allowlist and rejects shell chaining/redirection. Paths are relative to `/config`; protected runtime and secret paths are denied.

## Phase-1 read tools

- `ha_status` -> `ha info`
- `ha_read_file` -> tracked-file `git -C /config show HEAD:path`
- `ha_list_files` -> tracked-file `git -C /config ls-tree -r --name-only HEAD -- path`
- `ha_run_allowed_command` -> server allowlist + bridge allowlist
- `ha_verify` -> current `result.json` correlation

The server has no `/config` mount and does not directly access the Home Assistant filesystem.

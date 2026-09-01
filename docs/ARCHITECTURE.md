# 0.5.0 local architecture

## Runtime boundary

The MCP/API layer never receives a `/config` mount. It can only create a GitHub `command.json` and consume `result.json`. The existing bridge remains the execution boundary.

## Read path

1. KI requests a read/list/status tool.
2. Local server validates the requested operation.
3. Server creates a unique command ID.
4. Server updates `command.json` in the bridge repository.
5. Bridge 0.3.x polls GitHub and executes the command if its own whitelist permits it.
6. Bridge writes `result.json`.
7. Server polls `result.json` until the ID matches.
8. Only a matching result with `ok: true` is reported as verified.

## Mutation path

Mutations are disabled by default. A caller must explicitly set `allow_mutation=true`, and the command must still pass the server allowlist and the bridge allowlist.

## Known Phase-1 limitation

The current 0.3.x bridge is command-based. It does not expose a native file-read API. Therefore Phase 1 uses the bridge's existing allowed `git -C /config ...` capability for tracked project files. A future 0.5.x bridge-native API should replace this with structured `browse/read/search/patch` operations rather than shell commands.

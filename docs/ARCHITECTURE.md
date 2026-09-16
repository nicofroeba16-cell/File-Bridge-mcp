# 1.0.0 architecture

## Runtime boundary

The MCP/API layer never receives a `/config` mount. It can only create a GitHub `command.json` and consume `result.json`. The existing bridge remains the execution boundary.

## Read path

1. KI requests a read/list/status tool.
2. The server validates the operation and protected-path policy.
3. For structured Home Assistant access, the server creates a unique command ID under `.ai-control/commands/`.
4. The active HA File Sync Bridge processes permitted `read`, `browse`, `write`, or `sync` actions.
5. The bridge writes the correlated result under `.ai-control/results/`.
6. Only the matching command ID is accepted as verified.

Legacy `command.json` / `result.json` transport remains available for compatibility, but it is no longer the only file-access path.

## Mutation path

Mutations are disabled by default. A caller must explicitly set `allow_mutation=true`, and the command must still pass the server allowlist and the bridge allowlist.

## Current boundary

The MCP service intentionally has no direct `/config` mount. Structured Home Assistant file operations are delegated through the bridge control plane, while local workspace operations remain separately policy-gated. Runtime state must therefore be verified through correlated bridge results rather than inferred from Git alone.

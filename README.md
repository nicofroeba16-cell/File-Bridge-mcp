# HA Grok Bridge / File-Bridge MCP 1.0.0

Current production source for the File-Bridge MCP gateway. Version `1.0.0` is the released baseline.

## Scope

- MCP JSON-RPC adapter with current stateless MCP 2026-07-28 envelope support
- legacy MCP 2025-06-18 initialize compatibility
- strict tool input/output schemas
- structured tool results and tool-level errors
- read-only-by-default safety policy
- explicit mutation gate
- GitHub `command.json` / `result.json` transport
- command-ID correlation and verification
- protected `/config` path policy

## Local test

```bash
cd server
python -m pip install -r requirements.txt
cd ..
pytest -q
```

The test suite covers MCP discovery/list/call behavior, header routing, schema validity,
argument errors, security policy, and a mocked bridge execution path.

## Runtime boundary

The MCP/API process does not mount Home Assistant `/config` directly. It operates through the GitHub control plane and keeps mutations behind explicit confirmation and policy checks.

The preferred current bridge workflow is the structured `.ai-control/commands` → `.ai-control/results` channel. Legacy `command.json` / `result.json` support remains for compatibility where required.

A green File-Bridge CI run proves this repository commit, not a Home Assistant deployment. Runtime deployment must be verified separately.

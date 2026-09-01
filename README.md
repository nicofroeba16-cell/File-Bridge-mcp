# HA Grok Bridge 0.5.0 — local MCP development build

Local-only development build for the KI-fähige HA Grok Bridge.

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

## Important

This is a local 0.5.0 development build. It does **not** replace the live bridge,
does not modify `/config`, and is not pushed to the production GitHub repository.

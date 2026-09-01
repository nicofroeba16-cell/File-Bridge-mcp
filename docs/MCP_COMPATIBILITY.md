# MCP compatibility test status

Target: MCP 2026-07-28 stateless Streamable HTTP request model, while retaining legacy
2025-06-18 initialize compatibility for older clients.

Implemented locally:

- `server/discover`
- `tools/list`
- `tools/call`
- `MCP-Protocol-Version` validation on modern requests
- `Mcp-Method` routing-header validation
- `Mcp-Name` validation for `tools/call`
- structured tool results
- tool-level `isError` results for invalid arguments and execution failures
- strict `additionalProperties: false` input/output schemas
- tool safety annotations

The local suite does not claim certification against an external MCP SDK unless that
SDK is installed in the test environment. The official SDK could not be installed in
this isolated runtime, so compatibility is validated against the published protocol
shape plus local HTTP/JSON-RPC tests.

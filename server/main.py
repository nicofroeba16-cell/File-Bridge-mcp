#!/usr/bin/env python3
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

try:
    from .github_transport import GitHubTransport
    from .mcp_server import tool_list
    from .protocol import BridgeCommand
    from .security import command_allowed, command_is_mutating, safe_config_path
    from .local_workspace import LocalWorkspace
    from .control_mcp import dispatch_control
except ImportError:
    from github_transport import GitHubTransport
    from mcp_server import tool_list
    from protocol import BridgeCommand
    from security import command_allowed, command_is_mutating, safe_config_path
    from local_workspace import LocalWorkspace
    from control_mcp import dispatch_control

APP_VERSION = "0.9.3-dev"
DEFAULT_TIMEOUT = 180
transport = GitHubTransport()
workspace = LocalWorkspace(__import__("os").environ.get("HA_LOCAL_WORKSPACE", "/tmp/ha-grok-bridge-0.5.0-workspace"))
app = FastAPI(title="HA Grok Bridge 0.9.3", version=APP_VERSION)

class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=1000)
    allow_mutation: bool = False
    timeout: int = Field(default=DEFAULT_TIMEOUT, ge=5, le=600)

class FileRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    timeout: int = Field(default=DEFAULT_TIMEOUT, ge=5, le=600)

class VerifyRequest(BaseModel):
    command_id: str = Field(min_length=1, max_length=100)

def new_id() -> str:
    return f"ha-093-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}"

async def execute(command: str, allow_mutation: bool, timeout: int) -> dict[str, Any]:
    command = command.strip()
    if not command_allowed(command):
        raise HTTPException(403, "command is not allowed by the 0.9.3 server policy")
    if command_is_mutating(command) and not allow_mutation:
        raise HTTPException(409, "mutation requires explicit allow_mutation=true")
    command_id = new_id()
    result = await transport.execute(BridgeCommand(command_id, command), timeout)
    return {"verified": result.verified_for(command_id), "command_id": command_id, "result": result.raw}

@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "version": APP_VERSION, "repository": transport.repo, "branch": transport.branch, "github_configured": bool(transport.token), "mode": "read-only-default"}

@app.get("/capabilities")
async def capabilities() -> dict[str, Any]:
    return {"version": APP_VERSION, "mode": "read-only-default", "transport": "github-command-result", "tools": tool_list()["tools"], "mutations": "explicit-confirmation-required", "backup_restore": True, "dry_run": True, "secret_audit": True, "reliability": True}

@app.post("/ha/status")
async def ha_status(req: CommandRequest | None = None) -> dict[str, Any]:
    timeout = req.timeout if req else DEFAULT_TIMEOUT
    return await execute("ha info", False, timeout)

@app.post("/ha/read")
async def ha_read(req: FileRequest) -> dict[str, Any]:
    path = safe_config_path(req.path)
    return await execute(f"git -C /config show HEAD:{path}", False, req.timeout)

@app.post("/ha/list")
async def ha_list(req: FileRequest) -> dict[str, Any]:
    path = safe_config_path(req.path)
    return await execute(f"git -C /config ls-tree -r --name-only HEAD -- {path}", False, req.timeout)

@app.post("/ha/run")
async def ha_run(req: CommandRequest) -> dict[str, Any]:
    return await execute(req.command, req.allow_mutation, req.timeout)

@app.post("/ha/verify")
async def ha_verify(req: VerifyRequest) -> dict[str, Any]:
    data = await transport.read_file("result.json")
    if not data or not data.get("content"):
        return {"verified": False, "command_id": req.command_id, "reason": "no result.json"}
    try:
        from .protocol import parse_result
    except ImportError:
        from protocol import parse_result
    result = parse_result(data["content"])
    if not result:
        return {"verified": False, "command_id": req.command_id, "reason": "invalid result.json"}
    return {"verified": result.verified_for(req.command_id), "command_id": req.command_id, "result": result.raw}

async def local_read(path: str) -> dict[str, Any]: return workspace.read(path)
async def local_list(path: str = ".") -> dict[str, Any]: return {"files": workspace.list(path)}
async def local_search(query: str, path: str = ".", regex: bool = False, max_results: int = 100) -> dict[str, Any]: return {"matches": workspace.search(query, path, regex, max_results)}
async def local_analyze(path: str) -> dict[str, Any]: return {"analysis": workspace.analyze(path)}
async def require_confirm(confirm: bool) -> None:
    if not confirm: raise HTTPException(409, "mutation requires explicit confirm=true")
async def local_write(path: str, content: str, expected_sha256: str | None, confirm: bool) -> dict[str, Any]:
    await require_confirm(confirm)
    if workspace.path(path).exists(): workspace.backup(path)
    return workspace.write(path, content, expected_sha256)
async def local_patch(path: str, old: str, new: str, expected_sha256: str | None, count: int, confirm: bool) -> dict[str, Any]:
    await require_confirm(confirm); workspace.backup(path); return workspace.patch(path, old, new, expected_sha256, count)
async def local_backup(path: str, confirm: bool) -> dict[str, Any]:
    await require_confirm(confirm); return workspace.backup(path)
async def local_rollback(backup_id: str, confirm: bool) -> dict[str, Any]:
    await require_confirm(confirm); return workspace.rollback(backup_id)

MCP_MODERN = "2026-07-28"
MCP_LEGACY = "2025-06-18"

def _mcp_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

def _tool_error(request_id: Any, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": message}], "isError": True, "structuredContent": {"error": message}}}

def _validate_modern_headers(message: dict[str, Any], headers: dict[str, str]) -> str | None:
    version = headers.get("mcp-protocol-version"); method_header = headers.get("mcp-method"); name_header = headers.get("mcp-name")
    if version != MCP_MODERN: return f"MCP-Protocol-Version must be {MCP_MODERN}"
    if method_header != message.get("method"): return "Mcp-Method does not match JSON-RPC method"
    method = message.get("method"); params = message.get("params") or {}
    if method == "tools/call" and name_header != params.get("name"): return "Mcp-Name does not match tools/call name"
    return None

async def _dispatch_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name in {"ha_control_read", "ha_control_write", "ha_control_browse", "ha_control_sync"}: return await dispatch_control(name, args, transport)
    if name == "ha_capabilities": return await capabilities()
    if name == "ha_status": return await ha_status(CommandRequest(command="ha info"))
    if name == "ha_read_file":
        if "path" not in args: raise ValueError("path is required")
        return await local_read(args["path"])
    if name == "ha_list_files": return await local_list(args.get("path", "."))
    if name == "ha_run_allowed_command": return await ha_run(CommandRequest(**args))
    if name == "ha_verify": return await ha_verify(VerifyRequest(**args))
    if name == "ha_search": return await local_search(args["query"], args.get("path", "."), args.get("regex", False), args.get("max_results", 100))
    if name == "ha_analyze": return await local_analyze(args["path"])
    if name == "ha_write_file": return await local_write(args["path"], args["content"], args.get("expected_sha256"), args.get("confirm", False))
    if name == "ha_patch_file": return await local_patch(args["path"], args["old"], args["new"], args.get("expected_sha256"), args.get("count", 1), args.get("confirm", False))
    if name == "ha_backup": return await local_backup(args.get("path", "."), args.get("confirm", False))
    if name == "ha_rollback": return await local_rollback(args["backup_id"], args.get("confirm", False))
    raise KeyError(name)

async def _mcp_dispatch(message: dict[str, Any], request_headers: dict[str, str] | None = None) -> dict[str, Any] | None:
    request_headers = {k.lower(): v for k, v in (request_headers or {}).items()}
    method = message.get("method"); request_id = message.get("id")
    if request_headers.get("mcp-protocol-version") == MCP_MODERN:
        header_error = _validate_modern_headers(message, request_headers)
        if header_error: return _mcp_error(request_id, -32020, header_error)
    if method == "initialize": return {"jsonrpc":"2.0","id":request_id,"result":{"protocolVersion":MCP_LEGACY,"capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"ha-grok-bridge","version":APP_VERSION}}}
    if method == "notifications/initialized": return None
    if method == "server/discover": return {"jsonrpc":"2.0","id":request_id,"result":{"protocolVersion":MCP_MODERN,"capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"ha-grok-bridge","version":APP_VERSION}}}
    if method == "tools/list": return {"jsonrpc":"2.0","id":request_id,"result":tool_list()}
    if method == "tools/call":
        params = message.get("params") or {}; name = params.get("name"); args = params.get("arguments") or {}
        try: value = await _dispatch_tool(name, args)
        except KeyError: return _tool_error(request_id, f"unknown tool: {name}")
        except (TypeError, ValueError) as exc: return _tool_error(request_id, str(exc) or "invalid tool arguments")
        except HTTPException as exc: return _tool_error(request_id, str(exc.detail))
        except Exception as exc: return _tool_error(request_id, f"tool execution failed: {exc}")
        import json
        return {"jsonrpc":"2.0","id":request_id,"result":{"content":[{"type":"text","text":json.dumps(value,ensure_ascii=False,indent=2)}],"structuredContent":value,"isError":not bool(value.get("verified",True))}}
    return _mcp_error(request_id, -32601, f"method not found: {method}")

@app.post("/mcp")
async def mcp_http(request: Request):
    from fastapi.responses import JSONResponse
    message = await request.json(); headers = {k.lower(): v for k,v in request.headers.items()}
    result = await _mcp_dispatch(message, headers)
    if result is None: return JSONResponse(status_code=202, content=None)
    return JSONResponse(content=result)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8787)

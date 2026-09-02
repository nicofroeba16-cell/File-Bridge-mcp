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

APP_VERSION = "0.9.4-dev"
DEFAULT_TIMEOUT = 180
transport = GitHubTransport()
workspace = LocalWorkspace(__import__("os").environ.get("HA_LOCAL_WORKSPACE", "/tmp/ha-grok-bridge-0.5.0-workspace"))
app = FastAPI(title="HA Grok Bridge 0.9.4", version=APP_VERSION)

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
    return f"ha-094-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}"

async def execute(command: str, allow_mutation: bool, timeout: int) -> dict[str, Any]:
    command = command.strip()
    if not command_allowed(command):
        raise HTTPException(403, "command is not allowed by the 0.9.4 server policy")
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
    return {"version": APP_VERSION, "mode": "read-only-default", "transport": "github-command-result", "tools": tool_list()["tools"], "mutations": "explicit-confirmation-required", "backup_restore": True, "dry_run": True, "secret_audit": True, "reliability": True, "atomic_deployment": True}

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
        raise HTTPException(404, "result.json not available")
    result = __import__("server.protocol", fromlist=["parse_result"]).parse_result(data["content"])
    if not result or result.id != req.command_id:
        raise HTTPException(409, "result does not match command id")
    return {"verified": result.verified_for(req.command_id), "command_id": req.command_id, "result": result.raw}

@app.post("/mcp")
async def mcp(request: Request) -> Any:
    body = await request.json()
    if body.get("method") == "tools/call":
        name = body.get("params", {}).get("name", "")
        arguments = body.get("params", {}).get("arguments", {}) or {}
        if name.startswith("ha_control_"):
            return {"jsonrpc": "2.0", "id": body.get("id"), "result": await dispatch_control(name, arguments, transport)}
    from .mcp_server import handle_rpc
    return handle_rpc(body)

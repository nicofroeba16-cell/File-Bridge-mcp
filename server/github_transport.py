from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx
from fastapi import HTTPException

try:
    from .protocol import BridgeCommand, BridgeResult, encode_content, parse_result
except ImportError:
    from protocol import BridgeCommand, BridgeResult, encode_content, parse_result


class GitHubTransport:
    def __init__(self) -> None:
        self.repo = os.environ.get("GITHUB_REPOSITORY", "nicofroeba16-cell/ha-grok-bridge")
        self.branch = os.environ.get("GITHUB_BRANCH", "main")
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.timeout = int(os.environ.get("GITHUB_HTTP_TIMEOUT", "30"))
        self.poll_seconds = float(os.environ.get("BRIDGE_POLL_SECONDS", "3"))

    def headers(self) -> dict[str, str]:
        if not self.token:
            raise HTTPException(503, "GITHUB_TOKEN is not configured")
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def url(self, path: str) -> str:
        return f"https://api.github.com/repos/{self.repo}/contents/{path.lstrip('/')}"

    async def read_file(self, path: str) -> dict[str, Any] | None:
        params = {"ref": self.branch}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(self.url(path), headers=self.headers(), params=params)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    async def put_file(self, path: str, text: str, message: str) -> dict[str, Any]:
        current = await self.read_file(path)
        body: dict[str, Any] = {
            "message": message,
            "content": encode_content(text),
            "branch": self.branch,
        }
        if current and current.get("sha"):
            body["sha"] = current["sha"]
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.put(self.url(path), headers=self.headers(), json=body)
        if r.status_code == 409:
            raise HTTPException(409, "GitHub command.json changed concurrently; retry the operation")
        r.raise_for_status()
        return r.json()

    async def send_command(self, command: BridgeCommand) -> dict[str, Any]:
        return await self.put_file("command.json", command.to_json(), f"bridge command {command.id}")

    async def wait_result(self, command_id: str, timeout: int) -> BridgeResult:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            data = await self.read_file("result.json")
            if data and data.get("content"):
                result = parse_result(data["content"])
                if result and result.id == command_id:
                    return result
            await asyncio.sleep(self.poll_seconds)
        raise HTTPException(504, f"bridge result timeout for command {command_id}")

    async def execute(self, command: BridgeCommand, timeout: int) -> BridgeResult:
        await self.send_command(command)
        return await self.wait_result(command.id, timeout)

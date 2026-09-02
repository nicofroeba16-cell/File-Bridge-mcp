from __future__ import annotations

import asyncio
import os
import json
from typing import Any

import httpx
from fastapi import HTTPException

try:
    from .protocol import BridgeCommand, BridgeResult, encode_content, parse_result, decode_content
except ImportError:
    from protocol import BridgeCommand, BridgeResult, encode_content, parse_result, decode_content


class GitHubTransport:
    def __init__(self) -> None:
        self.repo = os.environ.get("GITHUB_REPOSITORY", "nicofroeba16-cell/ha-grok-bridge")
        self.branch = os.environ.get("GITHUB_BRANCH", "main")
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.timeout = int(os.environ.get("GITHUB_HTTP_TIMEOUT", "30"))
        self.poll_seconds = float(os.environ.get("BRIDGE_POLL_SECONDS", "3"))
        self.retries = int(os.environ.get("GITHUB_RETRIES", "3"))
        self.last_command_commit_sha: str | None = None
        self.last_control_commit_sha: str | None = None

    def headers(self) -> dict[str, str]:
        if not self.token:
            raise HTTPException(503, "GITHUB_TOKEN is not configured")
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

    def url(self, path: str) -> str:
        return f"https://api.github.com/repos/{self.repo}/contents/{path.lstrip('/')}"

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(method, url, headers=self.headers(), **kwargs)
                if response.status_code not in (408, 429) and response.status_code < 500:
                    return response
                last = HTTPException(502, f"GitHub temporary error: HTTP {response.status_code}")
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last = exc
            if attempt + 1 < self.retries:
                await asyncio.sleep(0.5 * (2 ** attempt))
        if isinstance(last, HTTPException):
            raise last
        raise HTTPException(503, f"GitHub unavailable after {self.retries} attempts") from last

    async def read_file(self, path: str) -> dict[str, Any] | None:
        r = await self._request("GET", self.url(path), params={"ref": self.branch})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    async def branch_sha(self) -> str:
        url = f"https://api.github.com/repos/{self.repo}/git/ref/heads/{self.branch}"
        r = await self._request("GET", url)
        r.raise_for_status()
        return str(r.json()["object"]["sha"])

    async def put_file(self, path: str, text: str, message: str) -> dict[str, Any]:
        current = await self.read_file(path)
        body: dict[str, Any] = {"message": message, "content": encode_content(text), "branch": self.branch}
        if current and current.get("sha"):
            body["sha"] = current["sha"]
        r = await self._request("PUT", self.url(path), json=body)
        if r.status_code == 409:
            raise HTTPException(409, "GitHub control file changed concurrently; retry the operation")
        r.raise_for_status()
        return r.json()

    async def send_command(self, command: BridgeCommand) -> dict[str, Any]:
        response = await self.put_file("command.json", command.to_json(), f"bridge command {command.id}")
        commit_sha = response.get("commit", {}).get("sha")
        if not commit_sha:
            raise HTTPException(502, "GitHub did not return the command commit SHA")
        self.last_command_commit_sha = str(commit_sha)
        current_sha = await self.branch_sha()
        if current_sha != self.last_command_commit_sha:
            raise HTTPException(502, "GitHub branch SHA does not match command commit SHA")
        return response

    async def send_control_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        cid = str(payload.get("id", ""))
        if not cid:
            raise HTTPException(400, "control command id is required")
        response = await self.put_file(f".ai-control/commands/{cid}.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n", f"control command {cid}")
        commit_sha = response.get("commit", {}).get("sha")
        if not commit_sha:
            raise HTTPException(502, "GitHub did not return the control commit SHA")
        self.last_control_commit_sha = str(commit_sha)
        return response

    async def wait_control_result(self, command_id: str, timeout: int) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        path = f".ai-control/results/{command_id}.json"
        while asyncio.get_running_loop().time() < deadline:
            data = await self.read_file(path)
            if data and data.get("content"):
                try:
                    result = json.loads(decode_content(data["content"]))
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    result = None
                if isinstance(result, dict) and result.get("id") == command_id:
                    return result
            await asyncio.sleep(self.poll_seconds)
        raise HTTPException(504, f"control result timeout for command {command_id}")

    async def execute_control(self, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        await self.send_control_command(payload)
        return await self.wait_control_result(str(payload["id"]), timeout)

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

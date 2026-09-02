from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from fastapi import HTTPException

try:
    from .atomic_deploy import DeploymentFile
    from .local_workspace import LocalWorkspace
    from .security import safe_config_path, validate_text_content
    from .secret_scanner import assert_safe
    from .sync_engine import FileState, sha256_text
except ImportError:
    from atomic_deploy import DeploymentFile
    from local_workspace import LocalWorkspace
    from security import safe_config_path, validate_text_content
    from secret_scanner import assert_safe
    from sync_engine import FileState, sha256_text


class LocalWorkspaceSyncAdapter:
    """Async sync adapter for a validated LocalWorkspace."""

    def __init__(self, workspace: LocalWorkspace) -> None:
        self.workspace = workspace

    async def inventory(self) -> dict[str, FileState]:
        result: dict[str, FileState] = {}
        for path in self.workspace.list("."):
            item = self.workspace.read(path)
            result[path] = FileState(path, item["sha256"], item["content"])
        return result

    async def write(self, path: str, content: str) -> None:
        safe = safe_config_path(path)
        target = self.workspace.path(safe)
        if target.exists():
            self.workspace.backup(safe)
        self.workspace.write(safe, content)

    async def delete(self, path: str) -> None:
        safe = safe_config_path(path)
        target = self.workspace.path(safe)
        if not target.exists():
            return
        if not target.is_file():
            raise HTTPException(409, f"sync delete target is not a file: {safe}")
        self.workspace.backup(safe)
        target.unlink()


class GitHubSyncAdapter:
    """GitHub Git-data adapter that exposes inventory/write/delete to sync_engine.

    Inventory is computed from decoded UTF-8 blob contents so SHA-256 values match
    the local workspace. Mutations use GitHubTransport.atomic_commit, ensuring each
    ref update is verified and never partially stages a file mutation.
    """

    def __init__(self, transport: Any) -> None:
        self.transport = transport

    async def inventory(self) -> dict[str, FileState]:
        parent = await self.transport.branch_sha()
        commit_response = await self.transport._request("GET", self.transport.git_url(f"commits/{parent}"))
        commit_response.raise_for_status()
        tree_sha = str(commit_response.json()["tree"]["sha"])
        tree_response = await self.transport._request(
            "GET", self.transport.git_url(f"trees/{tree_sha}"), params={"recursive": "1"}
        )
        tree_response.raise_for_status()
        tree = tree_response.json()
        if tree.get("truncated"):
            raise HTTPException(502, "GitHub recursive tree was truncated; refusing incomplete sync inventory")

        result: dict[str, FileState] = {}
        for entry in tree.get("tree", []):
            if entry.get("type") != "blob":
                continue
            path = str(entry.get("path", ""))
            try:
                safe = safe_config_path(path)
            except HTTPException:
                continue
            blob_sha = str(entry.get("sha", ""))
            if not blob_sha:
                continue
            blob_response = await self.transport._request("GET", self.transport.git_url(f"blobs/{blob_sha}"))
            blob_response.raise_for_status()
            blob = blob_response.json()
            if blob.get("encoding") != "base64" or not isinstance(blob.get("content"), str):
                continue
            try:
                raw = base64.b64decode(blob["content"], validate=False)
                content = raw.decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                continue
            try:
                validate_text_content(content)
            except HTTPException:
                continue
            result[safe] = FileState(safe, sha256_text(content), content)
        return dict(sorted(result.items()))

    async def write(self, path: str, content: str) -> None:
        safe = safe_config_path(path)
        validate_text_content(content)
        try:
            assert_safe(safe, content)
        except ValueError as exc:
            raise HTTPException(403, str(exc))
        await self.transport.atomic_commit(
            [DeploymentFile(safe, content)], message=f"sync: update {safe}"
        )

    async def delete(self, path: str) -> None:
        safe = safe_config_path(path)
        await self.transport.atomic_commit(
            [DeploymentFile(safe, None)], message=f"sync: delete {safe}"
        )

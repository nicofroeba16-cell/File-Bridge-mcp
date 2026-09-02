from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from server.local_workspace import LocalWorkspace
from server.sync_adapters import GitHubSyncAdapter, LocalWorkspaceSyncAdapter
from server.sync_engine import FileState, plan_initial_sync


class Response:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class FakeTransport:
    def __init__(self):
        self.commits = []

    async def branch_sha(self):
        return "parent"

    def git_url(self, path):
        return path

    async def _request(self, method, url, **kwargs):
        if url == "commits/parent":
            return Response({"tree": {"sha": "tree"}})
        if url == "trees/tree":
            return Response({"truncated": False, "tree": [
                {"type": "blob", "path": "configuration.yaml", "sha": "blob-safe"},
                {"type": "blob", "path": "secrets.yaml", "sha": "blob-secret"},
            ]})
        if url == "blobs/blob-safe":
            return Response({"encoding": "base64", "content": base64.b64encode(b"safe: true\n").decode()})
        if url == "blobs/blob-secret":
            raise AssertionError("protected files must not be fetched")
        raise AssertionError(url)

    async def atomic_commit(self, files, *, message, expected_parent=None):
        items = tuple(files)
        self.commits.append((items, message))
        return {"verified": True}


def test_initial_sync_requires_explicit_direction():
    local = {"a.yaml": FileState("a.yaml", "local", "x")}
    remote = {"b.yaml": FileState("b.yaml", "remote", "y")}
    try:
        plan_initial_sync(local, remote, direction="auto")
    except ValueError as exc:
        assert "initial sync direction" in str(exc)
    else:
        raise AssertionError("ambiguous initial sync direction accepted")


def test_initial_ha_to_github_mirrors_additions_and_deletions():
    local = {"a.yaml": FileState("a.yaml", "local", "x")}
    remote = {"b.yaml": FileState("b.yaml", "remote", "y")}
    plan = plan_initial_sync(local, remote, direction="ha-to-github")
    assert [(x.action, x.path) for x in plan] == [("push", "a.yaml"), ("delete_remote", "b.yaml")]


def test_local_sync_adapter_inventory_write_delete(tmp_path: Path):
    async def run():
        ws = LocalWorkspace(tmp_path)
        ws.write("configuration.yaml", "safe: true\n")
        adapter = LocalWorkspaceSyncAdapter(ws)
        inventory = await adapter.inventory()
        assert inventory["configuration.yaml"].content == "safe: true\n"
        await adapter.write("configuration.yaml", "safe: false\n")
        assert ws.read("configuration.yaml")["content"] == "safe: false\n"
        await adapter.delete("configuration.yaml")
        assert not (tmp_path / "configuration.yaml").exists()
    asyncio.run(run())


def test_github_sync_adapter_inventory_filters_protected_files():
    async def run():
        adapter = GitHubSyncAdapter(FakeTransport())
        inventory = await adapter.inventory()
        assert list(inventory) == ["configuration.yaml"]
        assert inventory["configuration.yaml"].content == "safe: true\n"
    asyncio.run(run())


def test_github_sync_adapter_mutations_use_atomic_commits():
    async def run():
        transport = FakeTransport()
        adapter = GitHubSyncAdapter(transport)
        await adapter.write("configuration.yaml", "safe: true\n")
        await adapter.delete("configuration.yaml")
        first, second = transport.commits
        assert first[0][0].path == "configuration.yaml" and first[0][0].content == "safe: true\n"
        assert second[0][0].path == "configuration.yaml" and second[0][0].content is None
    asyncio.run(run())

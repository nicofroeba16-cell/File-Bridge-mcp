from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from server.atomic_deploy import AtomicWorkspaceDeployer, DeploymentFile, validate_deployment
from server.github_transport import GitHubTransport


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_validate_all_files_before_staging(tmp_path: Path):
    with pytest.raises(ValueError, match="secret"):
        validate_deployment([
            DeploymentFile("ok.yaml", "ok: true\n"),
            DeploymentFile("secrets.yaml", "token: abc\n"),
        ])
    assert not list(tmp_path.iterdir())


def test_atomic_workspace_deploys_multiple_files(tmp_path: Path):
    (tmp_path / "a.yaml").write_text("old-a\n")
    (tmp_path / "b.yaml").write_text("old-b\n")
    result = AtomicWorkspaceDeployer(tmp_path).apply([
        DeploymentFile("a.yaml", "new-a\n", sha("old-a\n")),
        DeploymentFile("b.yaml", "new-b\n", sha("old-b\n")),
    ])
    assert result.verified is True
    assert result.rolled_back is False
    assert (tmp_path / "a.yaml").read_text() == "new-a\n"
    assert (tmp_path / "b.yaml").read_text() == "new-b\n"


def test_atomic_workspace_deletes_file(tmp_path: Path):
    (tmp_path / "remove.yaml").write_text("old\n")
    result = AtomicWorkspaceDeployer(tmp_path).apply([
        DeploymentFile("remove.yaml", None, sha("old\n")),
    ])
    assert result.verified is True
    assert not (tmp_path / "remove.yaml").exists()


def test_sha_conflict_prevents_any_change(tmp_path: Path):
    (tmp_path / "a.yaml").write_text("current\n")
    (tmp_path / "b.yaml").write_text("old-b\n")
    with pytest.raises(ValueError, match="sha256 conflict"):
        AtomicWorkspaceDeployer(tmp_path).apply([
            DeploymentFile("a.yaml", "new-a\n", sha("stale\n")),
            DeploymentFile("b.yaml", "new-b\n", sha("old-b\n")),
        ])
    assert (tmp_path / "a.yaml").read_text() == "current\n"
    assert (tmp_path / "b.yaml").read_text() == "old-b\n"


def test_mid_deployment_failure_rolls_back(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    (tmp_path / "a.yaml").write_text("old-a\n")
    (tmp_path / "b.yaml").write_text("old-b\n")
    original_replace = __import__("os").replace
    calls = {"n": 0}

    def failing_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated deployment failure")
        return original_replace(src, dst)

    monkeypatch.setattr("os.replace", failing_replace)
    with pytest.raises(OSError, match="simulated deployment failure"):
        AtomicWorkspaceDeployer(tmp_path).apply([
            DeploymentFile("a.yaml", "new-a\n"),
            DeploymentFile("b.yaml", "new-b\n"),
        ])
    assert (tmp_path / "a.yaml").read_text() == "old-a\n"
    assert (tmp_path / "b.yaml").read_text() == "old-b\n"


class FakeGitHubTransport(GitHubTransport):
    def __init__(self):
        super().__init__()
        self.current = "parent-sha"
        self.calls: list[tuple[str, str, dict]] = []
        self.counter = 0

    async def branch_sha(self) -> str:
        return self.current

    async def _request(self, method: str, url: str, **kwargs):
        self.calls.append((method, url, kwargs.get("json", {})))
        if url.endswith("/git/commits/parent-sha"):
            return FakeResponse(200, {"tree": {"sha": "base-tree"}})
        if url.endswith("/git/blobs"):
            self.counter += 1
            return FakeResponse(201, {"sha": f"blob-{self.counter}"})
        if url.endswith("/git/trees"):
            return FakeResponse(201, {"sha": "new-tree"})
        if url.endswith("/git/commits"):
            return FakeResponse(201, {"sha": "new-commit"})
        if url.endswith("/git/refs/heads/main"):
            self.current = "new-commit"
            return FakeResponse(200, {})
        raise AssertionError(url)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


@pytest.mark.asyncio
async def test_github_atomic_commit_uses_one_tree_and_one_commit():
    transport = FakeGitHubTransport()
    result = await transport.atomic_commit(
        [DeploymentFile("a.yaml", "a\n"), DeploymentFile("gone.yaml", None)],
        message="atomic deployment",
        expected_parent="parent-sha",
    )
    assert result["verified"] is True
    assert result["commit_sha"] == "new-commit"
    tree_payload = next(payload for method, url, payload in transport.calls if url.endswith("/git/trees"))
    assert tree_payload["base_tree"] == "base-tree"
    assert len(tree_payload["tree"]) == 2
    assert any(item["sha"] is None for item in tree_payload["tree"])
    assert sum(url.endswith("/git/commits") for _, url, _ in transport.calls) == 1
    assert sum(url.endswith("/git/refs/heads/main") for _, url, _ in transport.calls) == 1

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

try:
    from .security import safe_config_path, validate_text_content
    from .secret_scanner import assert_safe
except ImportError:
    from security import safe_config_path, validate_text_content
    from secret_scanner import assert_safe


@dataclass(frozen=True)
class DeploymentFile:
    path: str
    content: str | None
    expected_sha256: str | None = None


@dataclass(frozen=True)
class DeploymentResult:
    applied: tuple[str, ...]
    verified: bool
    rolled_back: bool


class AtomicRemote(Protocol):
    async def atomic_commit(
        self, files: Iterable[DeploymentFile], *, message: str, expected_parent: str | None = None
    ) -> dict[str, object]: ...


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def validate_deployment(files: Iterable[DeploymentFile]) -> tuple[DeploymentFile, ...]:
    normalized: list[DeploymentFile] = []
    seen: set[str] = set()
    for item in files:
        path = safe_config_path(item.path)
        if path in seen:
            raise ValueError(f"duplicate deployment path: {path}")
        seen.add(path)
        if item.content is not None:
            validate_text_content(item.content)
            assert_safe(path, item.content)
        if item.expected_sha256 is not None and len(item.expected_sha256) != 64:
            raise ValueError(f"invalid expected sha256: {path}")
        normalized.append(DeploymentFile(path, item.content, item.expected_sha256))
    if not normalized:
        raise ValueError("deployment must contain at least one file")
    return tuple(normalized)


class AtomicWorkspaceDeployer:
    """All-or-rollback local deployment with pre-validation and post-verification."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def apply(self, files: Iterable[DeploymentFile]) -> DeploymentResult:
        items = validate_deployment(files)
        snapshots: dict[Path, bytes | None] = {}
        staged: list[tuple[Path, Path]] = []
        applied: list[str] = []
        try:
            with tempfile.TemporaryDirectory(prefix=".ai-deploy-", dir=self.root) as tmp:
                stage_root = Path(tmp)
                for item in items:
                    target = (self.root / item.path).resolve()
                    if self.root not in target.parents:
                        raise ValueError(f"path escapes workspace: {item.path}")
                    if target.exists() and not target.is_file():
                        raise ValueError(f"deployment target is not a regular file: {item.path}")
                    snapshots[target] = target.read_bytes() if target.exists() else None
                    if item.expected_sha256 is not None:
                        actual = _sha256(target.read_text(encoding="utf-8")) if target.exists() else None
                        if actual != item.expected_sha256:
                            raise ValueError(f"sha256 conflict: {item.path}")
                    if item.content is not None:
                        staged_path = stage_root / item.path
                        staged_path.parent.mkdir(parents=True, exist_ok=True)
                        staged_path.write_text(item.content, encoding="utf-8")
                        with staged_path.open("rb") as fh:
                            os.fsync(fh.fileno())
                        staged.append((target, staged_path))
                    else:
                        staged.append((target, Path()))

                for target, staged_path in staged:
                    if staged_path:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(staged_path, target)
                    else:
                        target.unlink(missing_ok=True)
                    applied.append(str(target.relative_to(self.root)))

                for item in items:
                    target = self.root / item.path
                    if item.content is None:
                        if target.exists():
                            raise IOError(f"post-deployment verification failed: {item.path}")
                    elif not target.is_file() or _sha256(target.read_text(encoding="utf-8")) != _sha256(item.content):
                        raise IOError(f"post-deployment verification failed: {item.path}")
        except Exception:
            for target, original in snapshots.items():
                try:
                    if original is None:
                        target.unlink(missing_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(original)
                        with target.open("rb") as fh:
                            os.fsync(fh.fileno())
                except OSError:
                    pass
            raise
        return DeploymentResult(tuple(sorted(applied)), True, False)


async def deploy_remote_atomically(
    remote: AtomicRemote,
    files: Iterable[DeploymentFile],
    *,
    message: str,
    expected_parent: str | None = None,
) -> dict[str, object]:
    items = validate_deployment(files)
    return await remote.atomic_commit(items, message=message, expected_parent=expected_parent)

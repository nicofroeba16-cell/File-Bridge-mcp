from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


_BACKUP_ID = re.compile(r"\d{8}T\d{6}Z(?:-\d{2})?")


@dataclass(frozen=True)
class Snapshot:
    backup_id: str
    files: dict[str, str]
    manifest_sha256: str


class BackupManager:
    """Snapshot/restore manager for the safe project workspace.

    Snapshots contain only the supplied project inventory; runtime/protected paths
    must already have been filtered by the workspace inventory implementation.
    Restore is fail-closed: every restored file is hash-verified before success.
    """

    def __init__(self, root: str | Path, backup_root: str | Path | None = None, retention: int = 10):
        if retention < 1 or retention > 1000:
            raise ValueError("retention must be between 1 and 1000")
        self.root = Path(root).resolve()
        self.backup_root = (Path(backup_root) if backup_root else self.root / ".ai-backups").resolve()
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.retention = retention

    @staticmethod
    def _sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _manifest(files: Mapping[str, str]) -> str:
        payload = json.dumps(dict(sorted(files.items())), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def create(self, files: Mapping[str, str]) -> Snapshot:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snap = self.backup_root / stamp
        suffix = 0
        while snap.exists():
            suffix += 1
            snap = self.backup_root / f"{stamp}-{suffix:02d}"
        snap.mkdir(parents=True)
        normalized: dict[str, str] = {}
        for rel, source in sorted(files.items()):
            src = Path(source).resolve()
            if not src.is_file():
                raise FileNotFoundError(str(src))
            try:
                src.relative_to(self.root)
            except ValueError as exc:
                raise ValueError(f"snapshot source escapes workspace: {rel}") from exc
            dst = snap / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            normalized[rel] = self._sha(src)
        manifest = self._manifest(normalized)
        (snap / "manifest.json").write_text(
            json.dumps({"backup_id": snap.name, "files": normalized, "manifest_sha256": manifest}, indent=2) + "\n",
            encoding="utf-8",
        )
        self.prune()
        return Snapshot(snap.name, normalized, manifest)

    def list(self) -> list[str]:
        return sorted(
            (p.name for p in self.backup_root.iterdir() if p.is_dir() and _BACKUP_ID.fullmatch(p.name)),
            reverse=True,
        )

    def load(self, backup_id: str) -> Snapshot:
        if not _BACKUP_ID.fullmatch(backup_id):
            raise ValueError("invalid backup_id")
        snap = self.backup_root / backup_id
        manifest_path = snap / "manifest.json"
        if not snap.is_dir() or not manifest_path.is_file():
            raise FileNotFoundError(backup_id)
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = {str(k): str(v) for k, v in data.get("files", {}).items()}
        expected = self._manifest(files)
        if data.get("manifest_sha256") != expected:
            raise ValueError("backup manifest integrity check failed")
        for rel, expected_sha in files.items():
            path = snap / rel
            if not path.is_file() or self._sha(path) != expected_sha:
                raise ValueError(f"backup file integrity check failed: {rel}")
        return Snapshot(backup_id, files, expected)

    def restore(self, backup_id: str) -> Snapshot:
        snapshot = self.load(backup_id)
        snap = self.backup_root / backup_id
        restored: dict[str, str] = {}
        for rel, expected_sha in snapshot.files.items():
            src = snap / rel
            dst = (self.root / rel).resolve()
            try:
                dst.relative_to(self.root)
            except ValueError as exc:
                raise ValueError(f"restore path escapes workspace: {rel}") from exc
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".restore-tmp")
            shutil.copy2(src, tmp)
            if self._sha(tmp) != expected_sha:
                tmp.unlink(missing_ok=True)
                raise ValueError(f"restore verification failed: {rel}")
            tmp.replace(dst)
            restored[rel] = self._sha(dst)
        if restored != snapshot.files:
            raise ValueError("restore verification failed: manifest mismatch")
        return snapshot

    def prune(self) -> list[str]:
        ids = self.list()
        removed = ids[self.retention :]
        for backup_id in removed:
            shutil.rmtree(self.backup_root / backup_id)
        return removed

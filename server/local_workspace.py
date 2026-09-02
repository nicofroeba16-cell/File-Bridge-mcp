from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

try:
    from .security import safe_config_path, validate_text_content
    from .secret_scanner import assert_safe
except ImportError:
    from security import safe_config_path, validate_text_content
    from secret_scanner import assert_safe


class LocalWorkspace:
    """Local-only /config simulator used for development and E2E tests."""
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.backups = self.root / ".ai-backups"
        self.backups.mkdir(parents=True, exist_ok=True)

    def path(self, rel: str) -> Path:
        safe = safe_config_path(rel)
        p = (self.root / safe).resolve()
        if self.root not in p.parents and p != self.root:
            raise HTTPException(400, "path escapes workspace")
        candidate = self.root / safe
        if candidate.is_symlink():
            raise HTTPException(403, "symlink paths are not allowed")
        return p

    def read(self, rel: str) -> dict[str, Any]:
        p = self.path(rel)
        if not p.is_file():
            raise HTTPException(404, f"file not found: {rel}")
        data = p.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(415, "file is not valid UTF-8 text")
        return {"path": safe_config_path(rel), "content": text, "sha256": hashlib.sha256(data).hexdigest()}

    def list(self, rel: str = ".") -> list[str]:
        if rel in (".", ""):
            base = self.root
        else:
            base = self.path(rel)
        if not base.exists():
            raise HTTPException(404, f"path not found: {rel}")
        if base.is_file():
            return [safe_config_path(rel)]
        out = []
        for p in base.rglob("*"):
            if not p.is_file() or ".ai-backups" in p.parts or p.is_symlink():
                continue
            try:
                relative = p.relative_to(self.root)
                safe_config_path(str(relative))
            except HTTPException:
                continue
            out.append(str(relative))
        return sorted(out)

    def search(self, query: str, path: str = ".", regex: bool = False, max_results: int = 100) -> list[dict[str, Any]]:
        if not query:
            raise HTTPException(400, "query must not be empty")
        if max_results < 1 or max_results > 1000:
            raise HTTPException(400, "max_results must be between 1 and 1000")
        files = self.list(path)
        try:
            rx = re.compile(query, re.MULTILINE) if regex else None
        except re.error as exc:
            raise HTTPException(400, f"invalid regex: {exc}")
        out = []
        for rel in files:
            text = self.read(rel)["content"]
            for n, line in enumerate(text.splitlines(), 1):
                matched = bool(rx.search(line)) if rx else query.casefold() in line.casefold()
                if matched:
                    out.append({"path": rel, "line": n, "text": line})
                    if len(out) >= max_results:
                        return out
        return out

    def analyze(self, rel: str) -> dict[str, Any]:
        item = self.read(rel)
        text = item["content"]
        lines = text.splitlines()
        nonempty = [x for x in lines if x.strip()]
        result: dict[str, Any] = {
            "path": item["path"], "sha256": item["sha256"], "bytes": len(text.encode()),
            "lines": len(lines), "nonempty_lines": len(nonempty),
            "empty_lines": len(lines) - len(nonempty), "ends_with_newline": text.endswith("\n"),
        }
        suffix = Path(rel).suffix.lower()
        if suffix == ".json":
            try:
                obj = json.loads(text)
                result["syntax"] = "valid-json"
                result["top_level_type"] = type(obj).__name__
            except json.JSONDecodeError as exc:
                result["syntax"] = "invalid-json"
                result["syntax_error"] = str(exc)
        elif suffix in {".yaml", ".yml"}:
            result["syntax"] = "yaml-parse-not-enabled-local"
        else:
            result["syntax"] = "text"
        return result

    def write(self, rel: str, content: str, expected_sha256: str | None = None) -> dict[str, Any]:
        validate_text_content(content)
        safe = safe_config_path(rel)
        try:
            assert_safe(safe, content)
        except ValueError as exc:
            raise HTTPException(403, str(exc))
        p = self.path(safe)
        if expected_sha256 is not None and p.exists():
            actual = hashlib.sha256(p.read_bytes()).hexdigest()
            if actual != expected_sha256:
                raise HTTPException(409, "file changed since it was read (sha256 conflict)")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return self.read(safe)

    def patch(self, rel: str, old: str, new: str, expected_sha256: str | None = None, count: int = 1) -> dict[str, Any]:
        if not old:
            raise HTTPException(400, "old text must not be empty")
        if count < 1 or count > 100:
            raise HTTPException(400, "count must be between 1 and 100")
        validate_text_content(old)
        validate_text_content(new)
        current = self.read(rel)
        if expected_sha256 and current["sha256"] != expected_sha256:
            raise HTTPException(409, "file changed since it was read (sha256 conflict)")
        occurrences = current["content"].count(old)
        if occurrences < count:
            raise HTTPException(409, f"patch target occurs {occurrences} times; required at least {count}")
        updated = current["content"].replace(old, new, count)
        return self.write(rel, updated, expected_sha256=current["sha256"])

    def backup(self, rel: str = ".") -> dict[str, Any]:
        files = self.list(rel)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snap = self.backups / stamp
        suffix = 0
        while snap.exists():
            suffix += 1
            snap = self.backups / f"{stamp}-{suffix:02d}"
        snap.mkdir(parents=True)
        for f in files:
            src = self.path(f)
            dst = snap / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return {"backup_id": snap.name, "files": files, "path": str(snap)}

    def rollback(self, backup_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"\d{8}T\d{6}Z(?:-\d{2})?", backup_id):
            raise HTTPException(400, "invalid backup_id")
        snap = self.backups / backup_id
        if not snap.is_dir():
            raise HTTPException(404, f"backup not found: {backup_id}")
        restored = []
        for src in snap.rglob("*"):
            if not src.is_file():
                continue
            rel = src.relative_to(snap)
            dst = self.path(str(rel))
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            restored.append(str(rel))
        return {"backup_id": backup_id, "restored": sorted(restored)}

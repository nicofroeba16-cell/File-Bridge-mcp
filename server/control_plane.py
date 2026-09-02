from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")

@dataclass(frozen=True)
class ControlCommand:
    id: str
    action: str
    path: str | None = None
    content: str | None = None

    def as_payload(self) -> dict[str, Any]:
        if not _SAFE_ID.fullmatch(self.id):
            raise HTTPException(400, "invalid command id")
        if self.action not in {"read", "write", "browse", "sync"}:
            raise HTTPException(400, "unsupported control action")
        payload: dict[str, Any] = {"id": self.id, "action": self.action}
        if self.path is not None:
            payload["path"] = self.path
        if self.content is not None:
            payload["content"] = self.content
        return payload


def verify_result(result: dict[str, Any], command_id: str) -> bool:
    return result.get("id") == command_id and result.get("ok") is True


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

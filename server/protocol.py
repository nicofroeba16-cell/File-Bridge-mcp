from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class BridgeCommand:
    id: str
    command: str

    def to_json(self) -> str:
        return json.dumps({"id": self.id, "command": self.command}, indent=2) + "\n"


@dataclass(frozen=True)
class BridgeResult:
    raw: dict[str, Any]

    @property
    def id(self) -> str | None:
        return self.raw.get("id")

    @property
    def ok(self) -> bool:
        return self.raw.get("ok") is True

    def verified_for(self, command_id: str) -> bool:
        return self.id == command_id and self.ok


def encode_content(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def decode_content(value: str) -> str:
    return base64.b64decode(value).decode("utf-8")


def parse_result(content: str) -> BridgeResult | None:
    try:
        obj = json.loads(decode_content(content))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return BridgeResult(obj) if isinstance(obj, dict) else None

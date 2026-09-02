from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from .main import _mcp_dispatch


async def _serve() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError("JSON-RPC message must be an object")
            result = await _mcp_dispatch(message, {})
        except json.JSONDecodeError as exc:
            result = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"invalid JSON: {exc.msg}"}}
        except Exception as exc:
            result = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(exc)}}
        if result is not None:
            sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()

from __future__ import annotations
from typing import Any

from fastapi import HTTPException

try:
    from .ha_workflow import HAWorkflow
    from .secret_scanner import assert_safe
    from .security import validate_text_content
except ImportError:
    from ha_workflow import HAWorkflow
    from secret_scanner import assert_safe
    from security import validate_text_content

async def dispatch_control(name: str, args: dict[str, Any], transport: Any) -> dict[str, Any]:
    workflow = HAWorkflow(transport)
    cid = str(args.get("command_id", ""))
    if name == "ha_control_read":
        return {"result": await workflow.read(cid, args["path"])}
    if name == "ha_control_write":
        if not args.get("confirm", False):
            raise HTTPException(409, "mutation requires explicit confirm=true")
        validate_text_content(args["content"])
        assert_safe(args["path"], args["content"])
        return {"result": await workflow.write(cid, args["path"], args["content"])}
    if name == "ha_control_browse":
        return {"result": await workflow.browse(cid, args.get("path", "."))}
    if name == "ha_control_sync":
        if not args.get("confirm", False):
            raise HTTPException(409, "mutation requires explicit confirm=true")
        return {"result": await workflow.sync(cid)}
    raise KeyError(name)

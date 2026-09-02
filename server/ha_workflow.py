from __future__ import annotations
from typing import Any, Protocol

try:
    from .control_plane import ControlCommand, sha256_text, verify_result
    from .security import safe_config_path, validate_text_content
except ImportError:
    from control_plane import ControlCommand, sha256_text, verify_result
    from security import safe_config_path, validate_text_content

class ControlTransport(Protocol):
    async def execute_control(self, payload: dict[str, Any], timeout: int) -> dict[str, Any]: ...

class HAWorkflow:
    """Structured HA file workflow over the GitHub .ai-control channel."""
    def __init__(self, transport: ControlTransport):
        self.transport = transport

    async def read(self, command_id: str, path: str, timeout: int = 180) -> dict[str, Any]:
        path = safe_config_path(path)
        result = await self.transport.execute_control(ControlCommand(command_id, "read", path=path).as_payload(), timeout)
        if not verify_result(result, command_id): raise RuntimeError("control result verification failed")
        return result

    async def browse(self, command_id: str, path: str = ".", timeout: int = 180) -> dict[str, Any]:
        if path not in ("", "."): path = safe_config_path(path)
        result = await self.transport.execute_control(ControlCommand(command_id, "browse", path=path).as_payload(), timeout)
        if not verify_result(result, command_id): raise RuntimeError("control result verification failed")
        return result

    async def write(self, command_id: str, path: str, content: str, timeout: int = 180) -> dict[str, Any]:
        path = safe_config_path(path); validate_text_content(content)
        result = await self.transport.execute_control(ControlCommand(command_id, "write", path=path, content=content).as_payload(), timeout)
        if not verify_result(result, command_id): raise RuntimeError("control result verification failed")
        return result

    async def sync(self, command_id: str, timeout: int = 180) -> dict[str, Any]:
        result = await self.transport.execute_control(ControlCommand(command_id, "sync").as_payload(), timeout)
        if not verify_result(result, command_id): raise RuntimeError("control result verification failed")
        return result

    @staticmethod
    def expected_sha(content: str) -> str: return sha256_text(content)

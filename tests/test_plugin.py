from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_package_metadata_and_entrypoint_exist() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "file-bridge-mcp"' in text
    assert 'version = "1.0.0"' in text
    assert 'file-bridge-mcp = "server.stdio:main"' in text


def test_stdio_initialize_and_tools_list() -> None:
    payload = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
    ]) + "\n"
    proc = subprocess.run([sys.executable, "-m", "server.stdio"], input=payload, text=True, capture_output=True, check=True, timeout=30)
    lines = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert lines[0]["result"]["serverInfo"]["version"] == "1.0.0"
    names = {tool["name"] for tool in lines[1]["result"]["tools"]}
    assert {"ha_capabilities", "ha_read_file", "ha_write_file", "ha_patch_file"} <= names
    assert {"ha_control_read", "ha_control_write", "ha_control_browse", "ha_control_sync", "ha_bridge_status", "ha_repository_audit"} <= names
    assert len(names) == 18
    assert proc.stderr == ""

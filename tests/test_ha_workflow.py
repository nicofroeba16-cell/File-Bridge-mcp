import pytest
from server.ha_workflow import HAWorkflow

class FakeTransport:
    def __init__(self):
        self.commands = []
    async def execute_control(self, payload, timeout):
        self.commands.append(payload)
        if payload["action"] == "read":
            return {"id": payload["id"], "ok": True, "path": payload["path"], "content": "mode: old\n"}
        return {"id": payload["id"], "ok": True, "action": payload["action"]}

@pytest.mark.asyncio
async def test_ha_workflow_read_write_browse_sync():
    transport = FakeTransport()
    workflow = HAWorkflow(transport)
    assert (await workflow.read("read-001", "packages/test.yaml"))["ok"]
    assert (await workflow.write("write-002", "packages/test.yaml", "mode: new\n"))["ok"]
    assert (await workflow.browse("browse-003", "packages"))["ok"]
    assert (await workflow.sync("sync-004"))["ok"]
    assert [c["id"] for c in transport.commands] == ["read-001", "write-002", "browse-003", "sync-004"]

@pytest.mark.asyncio
async def test_workflow_rejects_unsafe_path():
    with pytest.raises(Exception):
        await HAWorkflow(FakeTransport()).read("bad-001", "../secrets.yaml")

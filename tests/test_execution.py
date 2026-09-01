import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'server'))
from fastapi.testclient import TestClient
import main
from protocol import BridgeResult

class FakeTransport:
    repo='test/repo'
    branch='main'
    token='test'
    async def execute(self, command, timeout):
        return BridgeResult({'id': command.id, 'ok': True, 'exit_code': 0, 'output': 'ok'})
    async def read_file(self, path):
        return None


def test_read_tool_executes_and_verifies(monkeypatch):
    monkeypatch.setattr(main, 'transport', FakeTransport())
    c=TestClient(main.app)
    r=c.post('/mcp', headers={'MCP-Protocol-Version':main.MCP_MODERN,'Mcp-Method':'tools/call','Mcp-Name':'ha_status'}, json={'jsonrpc':'2.0','id':10,'method':'tools/call','params':{'name':'ha_status','arguments':{}}})
    assert r.status_code == 200
    body=r.json()['result']
    assert body['isError'] is False
    assert body['structuredContent']['verified'] is True


def test_mutation_requires_explicit_confirmation(monkeypatch):
    monkeypatch.setattr(main, 'transport', FakeTransport())
    c=TestClient(main.app)
    r=c.post('/mcp', headers={'MCP-Protocol-Version':main.MCP_MODERN,'Mcp-Method':'tools/call','Mcp-Name':'ha_run_allowed_command'}, json={'jsonrpc':'2.0','id':11,'method':'tools/call','params':{'name':'ha_run_allowed_command','arguments':{'command':'ha core restart'}}})
    assert r.json()['result']['isError'] is True
    assert 'allow_mutation' in r.json()['result']['content'][0]['text']

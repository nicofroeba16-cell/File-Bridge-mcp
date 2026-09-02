import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'server'))
from main import app, _mcp_dispatch, MCP_MODERN
from fastapi.testclient import TestClient

client = TestClient(app)

def test_initialize_legacy():
    r = client.post('/mcp', json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})
    assert r.status_code == 200
    assert r.json()['result']['protocolVersion'] == '2025-06-18'

def test_discover_modern():
    r = client.post('/mcp', headers={'MCP-Protocol-Version':MCP_MODERN,'Mcp-Method':'server/discover'}, json={'jsonrpc':'2.0','id':1,'method':'server/discover'})
    assert r.status_code == 200
    assert r.json()['result']['protocolVersion'] == MCP_MODERN

def test_tools_list_modern():
    r = client.post('/mcp', headers={'MCP-Protocol-Version':MCP_MODERN,'Mcp-Method':'tools/list'}, json={'jsonrpc':'2.0','id':2,'method':'tools/list'})
    data=r.json()['result']['tools']
    assert len(data) == 18
    for t in data:
        assert t['inputSchema']['additionalProperties'] is False
        assert 'outputSchema' in t
        assert 'annotations' in t

def test_tools_list_headers_mismatch():
    r = client.post('/mcp', headers={'MCP-Protocol-Version':MCP_MODERN,'Mcp-Method':'tools/call','Mcp-Name':'ha_status'}, json={'jsonrpc':'2.0','id':3,'method':'tools/list'})
    assert r.json()['error']['code'] == -32020

def test_tool_argument_error_is_tool_error():
    r = client.post('/mcp', headers={'MCP-Protocol-Version':MCP_MODERN,'Mcp-Method':'tools/call','Mcp-Name':'ha_read_file'}, json={'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'ha_read_file','arguments':{}}})
    body=r.json()['result']
    assert body['isError'] is True
    assert 'path' in body['content'][0]['text']

def test_unknown_tool_is_tool_error():
    r = client.post('/mcp', headers={'MCP-Protocol-Version':MCP_MODERN,'Mcp-Method':'tools/call','Mcp-Name':'does_not_exist'}, json={'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'does_not_exist','arguments':{}}})
    assert r.json()['result']['isError'] is True

def test_modern_requires_protocol_headers():
    r = client.post('/mcp', headers={'Mcp-Method':'tools/list'}, json={'jsonrpc':'2.0','id':6,'method':'tools/list'})
    assert r.status_code == 200
    assert 'result' in r.json()

def test_modern_header_mismatch_rejected():
    r = client.post('/mcp', headers={'MCP-Protocol-Version':MCP_MODERN,'Mcp-Method':'tools/call','Mcp-Name':'ha_status'}, json={'jsonrpc':'2.0','id':7,'method':'tools/list'})
    assert r.status_code == 200
    assert r.json()['error']['code'] == -32020

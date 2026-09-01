import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from fastapi.testclient import TestClient
import server.main as main

client=TestClient(main.app)
H=lambda n:{'MCP-Protocol-Version':main.MCP_MODERN,'Mcp-Method':'tools/call','Mcp-Name':n}
def call(n,args,i=1):
    r=client.post('/mcp',headers=H(n),json={'jsonrpc':'2.0','id':i,'method':'tools/call','params':{'name':n,'arguments':args}})
    assert r.status_code==200
    return r.json()['result']

def setup():
    main.workspace.root.mkdir(parents=True,exist_ok=True)
    (main.workspace.root/'test.yaml').write_text('mode: old\nvalue: 1\n',encoding='utf8')

def test_full_local_ai_workflow():
    setup()
    listed=call('ha_list_files',{'path':'.'},1); assert 'test.yaml' in listed['structuredContent']['files']
    read=call('ha_read_file',{'path':'test.yaml'},2)['structuredContent']; oldsha=read['sha256']; assert 'mode: old' in read['content']
    matches=call('ha_search',{'query':'mode: old'},3)['structuredContent']['matches']; assert matches
    analysis=call('ha_analyze',{'path':'test.yaml'},4)['structuredContent']['analysis']; assert analysis['lines']==2
    denied=call('ha_write_file',{'path':'test.yaml','content':'mode: new\nvalue: 1\n','confirm':False},5); assert denied['isError'] and 'confirm' in denied['content'][0]['text']
    written=call('ha_write_file',{'path':'test.yaml','content':'mode: written\nvalue: 1\n','expected_sha256':oldsha,'confirm':True},6); assert written['structuredContent']['content'].startswith('mode: written')
    newsha=written['structuredContent']['sha256']
    backup=call('ha_backup',{'path':'test.yaml','confirm':True},7)['structuredContent']['backup_id']
    patched=call('ha_patch_file',{'path':'test.yaml','old':'mode: written','new':'mode: new','expected_sha256':newsha,'confirm':True},9)['structuredContent']; assert 'mode: new' in patched['content']
    verified=call('ha_read_file',{'path':'test.yaml'},9)['structuredContent']; assert 'mode: new' in verified['content']
    conflict=call('ha_patch_file',{'path':'test.yaml','old':'value: 1','new':'value: 2','expected_sha256':oldsha,'confirm':True},10); assert conflict['isError']
    rolled=call('ha_rollback',{'backup_id':backup,'confirm':True},12)['structuredContent']; assert 'test.yaml' in rolled['restored']
    final=call('ha_read_file',{'path':'test.yaml'},12)['structuredContent']; assert final['sha256']==newsha and 'mode: written' in final['content']

def test_protected_write_blocked():
    r=call('ha_write_file',{'path':'secrets.yaml','content':'x','confirm':True},12); assert r['isError']

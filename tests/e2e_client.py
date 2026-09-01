import json, os, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PORT=8791
BASE=f'http://127.0.0.1:{PORT}'

def req(method,path,payload=None,headers=None):
    data=None if payload is None else json.dumps(payload).encode()
    h={'Content-Type':'application/json'}; h.update(headers or {})
    r=urllib.request.Request(BASE+path,data=data,headers=h,method=method)
    try:
        with urllib.request.urlopen(r,timeout=8) as x:
            body=x.read()
            return x.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        body=e.read()
        return e.code, json.loads(body) if body else None

def main():
    env=os.environ.copy(); env['PYTHONPATH']=str(ROOT)
    code="""
import json, os
from server.main import app
from pathlib import Path
import server.main as m
from server.protocol import BridgeResult
class MockTransport:
    repo='mock/repo'; branch='main'; token='mock'
    async def execute(self, command, timeout):
        out={'ha info':'Home Assistant mock OK','git -C /config show HEAD:configuration.yaml':'homeassistant:\\n  name: Test HA\\n','git -C /config ls-tree -r --name-only HEAD -- packages':'packages/a.yaml\\npackages/b.yaml\\n'}
        return BridgeResult({'id':command.id,'command':command.command,'exit_code':0,'ok':True,'output':out.get(command.command,'mock OK'),'timestamp':'2026-09-01T00:00:00Z','via':'mock'})
    async def read_file(self,path):
        return {'content': json.dumps({'id':'verify-id','command':'ha info','exit_code':0,'ok':True,'output':'mock OK'})}
m.transport=MockTransport(); m.workspace.root=Path('/tmp/ha-grok-bridge-0.5.0-e2e-workspace'); m.workspace.root.mkdir(parents=True,exist_ok=True)
import uvicorn
uvicorn.run(app,host='127.0.0.1',port=%d,log_level='error')
""" % PORT
    p=subprocess.Popen([sys.executable,'-c',code],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        for _ in range(80):
            try:
                s,b=req('GET','/health')
                if s==200: break
            except Exception: pass
            time.sleep(.1)
        ws=Path('/tmp/ha-grok-bridge-0.5.0-e2e-workspace'); ws.mkdir(parents=True,exist_ok=True); (ws/'workflow.yaml').write_text('mode: old\nvalue: 1\n',encoding='utf-8')
        checks=[]
        def check(name, cond, detail=''):
            checks.append((name,bool(cond),detail))
        s,h=req('GET','/health'); check('health',s==200 and h['ok'] and h['version']=='0.5.0-local',str(h))
        modern={'MCP-Protocol-Version':'2026-07-28','Mcp-Method':'server/discover'}
        s,d=req('POST','/mcp',{'jsonrpc':'2.0','id':1,'method':'server/discover','params':{}},modern); check('server/discover',s==200 and d['result']['protocolVersion']=='2026-07-28',str(d))
        modern={'MCP-Protocol-Version':'2026-07-28','Mcp-Method':'resources/list'}
        s,d=req('POST','/mcp',{'jsonrpc':'2.0','id':2,'method':'resources/list','params':{}},modern); check('resources/list unsupported is explicit',s==200 and d['error']['code']==-32601,str(d))
        modern={'MCP-Protocol-Version':'2026-07-28','Mcp-Method':'tools/list'}
        s,d=req('POST','/mcp',{'jsonrpc':'2.0','id':3,'method':'tools/list','params':{}},modern); tools=d.get('result',{}).get('tools',[]); check('tools/list',s==200 and len(tools)==12,str([t['name'] for t in tools]))
        valid=True
        for t in tools:
            valid &= all(k in t for k in ('name','description','inputSchema','outputSchema','annotations'))
            valid &= t['inputSchema'].get('additionalProperties') is False
        check('all tool schemas hardened',valid)
        def call(i,name,args):
            hd={'MCP-Protocol-Version':'2026-07-28','Mcp-Method':'tools/call','Mcp-Name':name}
            return req('POST','/mcp',{'jsonrpc':'2.0','id':i,'method':'tools/call','params':{'name':name,'arguments':args}},hd)
        s,d=call(4,'ha_capabilities',{}); check('tool ha_capabilities',s==200 and not d['result'].get('isError') and d['result']['structuredContent']['version']=='0.5.0-local',str(d))
        s,d=call(5,'ha_status',{}); check('tool ha_status',s==200 and d['result']['structuredContent']['verified'] is True,str(d))
        s,d=call(6,'ha_list_files',{'path':'.'}); check('workflow list',s==200 and 'workflow.yaml' in d['result']['structuredContent']['files'],str(d))
        s,d=call(7,'ha_read_file',{'path':'workflow.yaml'}); read=d['result']['structuredContent']; oldsha=read['sha256']; check('workflow read',s==200 and 'mode: old' in read['content'],str(d))
        s,d=call(8,'ha_search',{'query':'mode: old'}); check('workflow search',s==200 and bool(d['result']['structuredContent']['matches']),str(d))
        s,d=call(9,'ha_analyze',{'path':'workflow.yaml'}); check('workflow analyze',s==200 and d['result']['structuredContent']['analysis']['lines']==2,str(d))
        s,d=call(10,'ha_write_file',{'path':'workflow.yaml','content':'mode: new\nvalue: 1\n','confirm':False}); check('write confirmation gate',s==200 and d['result']['isError'] is True,str(d))
        s,d=call(11,'ha_backup',{'path':'workflow.yaml','confirm':True}); backup=d.get('result',{}).get('structuredContent',{}).get('backup_id'); check('backup',s==200 and bool(backup),str(d))
        s,d=call(12,'ha_patch_file',{'path':'workflow.yaml','old':'mode: old','new':'mode: new','expected_sha256':oldsha,'confirm':True}); check('patch + sha verification',s==200 and 'mode: new' in d['result']['structuredContent']['content'],str(d))
        s,d=call(13,'ha_read_file',{'path':'workflow.yaml'}); check('post-write verify',s==200 and 'mode: new' in d['result']['structuredContent']['content'],str(d))
        s,d=call(14,'ha_patch_file',{'path':'workflow.yaml','old':'value: 1','new':'value: 2','expected_sha256':oldsha,'confirm':True}); check('stale-sha conflict',s==200 and d['result']['isError'] is True,str(d))
        s,d=call(15,'ha_rollback',{'backup_id':backup,'confirm':True}); check('rollback',s==200 and 'workflow.yaml' in d['result']['structuredContent']['restored'],str(d))
        s,d=call(16,'ha_read_file',{'path':'workflow.yaml'}); final=d['result']['structuredContent']; check('rollback verify',s==200 and final['sha256']==oldsha and 'mode: old' in final['content'],str(d))
        s,d=call(17,'ha_write_file',{'path':'secrets.yaml','content':'x','confirm':True}); check('protected file blocked',s==200 and d['result']['isError'] is True,str(d))
        print('E2E RESULT')
        for n,ok,de in checks: print(('PASS' if ok else 'FAIL')+' | '+n+((' | '+de) if de and not ok else ''))
        print(f'SUMMARY: {sum(x[1] for x in checks)}/{len(checks)} PASS')
        if not all(x[1] for x in checks): return 2
    finally:
        p.terminate()
        try: p.wait(timeout=5)
        except subprocess.TimeoutExpired: p.kill()
    return 0
if __name__=='__main__': raise SystemExit(main())

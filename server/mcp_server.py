from __future__ import annotations
from typing import Any

_READONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
_DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False}

def obj_schema(properties=None, required=None):
    return {"type":"object","properties":properties or {},"required":required or [],"additionalProperties":False}

def output_schema(fields):
    return {"type":"object","properties":fields,"required":list(fields),"additionalProperties":False}

COMMON_OUTPUT={"command_id":{"type":"string"},"verified":{"type":"boolean"},"result":{"type":"object"}}
TEXT_OUTPUT={"path":{"type":"string"},"content":{"type":"string"},"sha256":{"type":"string"}}

def _tool(name, description, props=None, req=None, out=None, annotations=_READONLY):
    return {"name":name,"description":description,"inputSchema":obj_schema(props,req),"outputSchema":output_schema(out or {"ok":{"type":"boolean"}}),"annotations":annotations}

TOOLS=[
 _tool("ha_capabilities","Describe Bridge capabilities and safety mode.",out={"version":{"type":"string"},"mode":{"type":"string"},"transport":{"type":"string"},"tools":{"type":"array"},"mutations":{"type":"string"}}),
 _tool("ha_status","Query Home Assistant status through the bridge. Read-only.",out=COMMON_OUTPUT),
 _tool("ha_read_file","Read a permitted project file.",{"path":{"type":"string","minLength":1,"maxLength":500}},["path"],TEXT_OUTPUT),
 _tool("ha_list_files","List permitted project files.",{"path":{"type":"string","default":"."}},out={"files":{"type":"array"}}),
 _tool("ha_search","Search permitted project files for text or regex.",{"query":{"type":"string","minLength":1},"path":{"type":"string","default":"."},"regex":{"type":"boolean","default":False},"max_results":{"type":"integer","minimum":1,"maximum":1000,"default":100}},["query"],{"matches":{"type":"array"}}),
 _tool("ha_analyze","Analyze one permitted project file without modifying it.",{"path":{"type":"string","minLength":1}},["path"],{"analysis":{"type":"object"}}),
 _tool("ha_write_file","Write a permitted project file. Explicit confirmation required.",{"path":{"type":"string","minLength":1},"content":{"type":"string"},"expected_sha256":{"type":"string"},"confirm":{"type":"boolean","default":False}},["path","content","confirm"],TEXT_OUTPUT,_DESTRUCTIVE),
 _tool("ha_patch_file","Apply an exact text patch. Explicit confirmation required.",{"path":{"type":"string"},"old":{"type":"string","minLength":1},"new":{"type":"string"},"expected_sha256":{"type":"string"},"count":{"type":"integer","minimum":1,"default":1},"confirm":{"type":"boolean","default":False}},["path","old","new","confirm"],TEXT_OUTPUT,_DESTRUCTIVE),
 _tool("ha_backup","Create a local snapshot before mutation. Explicit confirmation required.",{"path":{"type":"string","default":"."},"confirm":{"type":"boolean","default":False}},["confirm"],{"backup_id":{"type":"string"}},_DESTRUCTIVE),
 _tool("ha_rollback","Restore a previous local snapshot. Explicit confirmation required.",{"backup_id":{"type":"string"},"confirm":{"type":"boolean","default":False}},["backup_id","confirm"],{"backup_id":{"type":"string"},"restored":{"type":"array"}},_DESTRUCTIVE),
 _tool("ha_run_allowed_command","Run a command permitted by the bridge allowlist. Mutations require confirmation.",{"command":{"type":"string"},"allow_mutation":{"type":"boolean","default":False},"timeout":{"type":"integer","minimum":5,"maximum":600,"default":180}},["command"],COMMON_OUTPUT,_DESTRUCTIVE),
 _tool("ha_verify","Verify a bridge result by command ID.",{"command_id":{"type":"string"}},["command_id"],{"verified":{"type":"boolean"},"command_id":{"type":"string"}}),
]

def tool_list(): return {"tools":TOOLS}

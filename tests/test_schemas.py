import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'server'))
from mcp_server import tool_list
from jsonschema import Draft202012Validator


def check_schema(s):
    assert s['type'] == 'object'
    assert s['additionalProperties'] is False
    props=s.get('properties',{})
    for k in s.get('required',[]): assert k in props


def test_schemas():
    for t in tool_list()['tools']:
        check_schema(t['inputSchema'])
        check_schema(t['outputSchema'])
        assert isinstance(t['description'], str) and t['description']
        assert isinstance(t['annotations'], dict)


def test_schemas_are_valid_json_schema():
    for t in tool_list()['tools']:
        Draft202012Validator.check_schema(t['inputSchema'])
        Draft202012Validator.check_schema(t['outputSchema'])

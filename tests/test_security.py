import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'server'))
from security import command_allowed, command_is_mutating, safe_config_path


def test_allowlist():
    assert command_allowed('ha info')
    assert command_allowed('git -C /config status')
    assert not command_allowed('ha info && whoami')
    assert not command_allowed('ha info; whoami')

def test_mutation_gate():
    assert command_is_mutating('ha core restart')
    assert command_is_mutating('bash /config/deploy.sh')
    assert not command_is_mutating('ha core info')

def test_paths():
    assert safe_config_path('configuration.yaml') == 'configuration.yaml'
    assert safe_config_path('/config/packages/test.yaml') == 'packages/test.yaml'
    for bad in ('../x', 'a/../x', '/config/.storage/x', 'secrets.yaml', 'x.db'):
        try:
            safe_config_path(bad)
            assert False, bad
        except Exception:
            pass

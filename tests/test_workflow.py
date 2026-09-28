import re

WORKFLOW = '.github/workflows/build.yaml'
NODE24_ACTIONS = ('actions/checkout@v6', 'actions/setup-python@v6')


def workflow_content():
    return open(WORKFLOW, encoding='utf-8').read()


def test_actions_run_on_node24_majors():
    # node20-based majors (checkout@v4, setup-python@v5) trigger deprecation warnings
    content = workflow_content()
    uses = re.findall(r'uses:\s*(\S+)', content)
    assert uses, 'no actions found in workflow'
    for action in NODE24_ACTIONS:
        assert action in uses, f'{action} missing; found {uses}'


def test_no_node20_era_action_pins():
    content = workflow_content()
    stale = re.findall(r'uses:\s*actions/\w+@v[45]\b', content)
    assert not stale, f'node20-era action pins found: {stale}'


def test_workflow_still_has_no_push_trigger():
    # on: push re-enabled the self-trigger loop; schedule + dispatch only
    content = workflow_content()
    on_block = re.search(r'\non:\n(.*?)(?=\n\w|\Z)', content, re.S)
    assert on_block, 'no on: block found'
    assert 'workflow_dispatch' in on_block.group(1)
    assert 'schedule:' in on_block.group(1)
    assert not re.search(r'^\s+push:', on_block.group(1), re.M)

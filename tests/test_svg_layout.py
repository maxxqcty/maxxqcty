import re

TAG = re.compile(r'<[^>]+>')
ROW_WIDTH = 60  # matches the dynamic Uptime row: justify_format(length=49) + prefix

INFO_ROWS = [
    ('OS', 'CachyOS, Windows 11'),
    ('Machine', 'ThinkPad T460p'),
    ('Role', 'Computer Science Student'),
    ('Editor', 'Neovim, VS Code'),
    ('Agents', 'Claude Code, OpenCode'),
    ('Shell', 'zsh, fish, PowerShell'),
    ('Languages', 'English, Filipino'),
    ('Hobbies', 'Linux, Homelab, Vibe Coding'),
]


def right_column_rows(filename):
    lines = open(filename, encoding='utf-8').read().splitlines()
    start = next(i for i, line in enumerate(lines) if '<text x="390"' in line)
    end = next(i for i, line in enumerate(lines[start:], start) if line.strip() == '</text>')
    return lines[start + 1:end]


def test_static_info_rows_exist_and_are_aligned_in_both_svgs():
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        rows = right_column_rows(filename)
        visible = {key: None for key, _ in INFO_ROWS}
        for line in rows:
            text = TAG.sub('', line)
            for key, value in INFO_ROWS:
                if text.startswith('. ' + key + ':'):
                    visible[key] = text
        for key, value in INFO_ROWS:
            assert visible[key] is not None, f'{filename}: row {key!r} missing'
            assert visible[key].endswith(value), f'{filename}: {key} -> {visible[key]!r}'
            assert len(visible[key]) == ROW_WIDTH, \
                f'{filename}: {key} row width {len(visible[key])} != {ROW_WIDTH}: {visible[key]!r}'


def test_contact_section_is_gone_and_stats_section_moved_up():
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        content = open(filename, encoding='utf-8').read()
        assert 'Email' not in content and 'LinkedIn' not in content and 'Discord' not in content
        rows = right_column_rows(filename)
        header = next(line for line in rows if '- GitHub Stats' in line)
        assert 'y="327"' in header
        assert 'y="510"' not in '\n'.join(rows)  # stats block no longer sits at the bottom


def test_computed_stat_ids_survive_in_both_svgs():
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        content = open(filename, encoding='utf-8').read()
        for element_id in ('age_data', 'repo_data', 'star_data', 'commit_data',
                           'follower_data', 'contrib_data', 'loc_data', 'loc_add', 'loc_del'):
            assert f'id="{element_id}"' in content, f'{filename}: lost id {element_id}'

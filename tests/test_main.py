import pytest

import today


def test_main_reads_username_from_config_and_renders_both_svgs(tmp_path, monkeypatch, capsys):
    config = tmp_path / 'config.json'
    config.write_text('{"username": "maxxqcty", "birthday": "2004-09-13"}', encoding='utf-8')

    monkeypatch.setattr(today, 'user_getter', lambda username: ({'id': 'MDQ6Test'}, '2020-01-01T00:00:00Z'))
    monkeypatch.setattr(today, 'loc_query', lambda *a, **k: [10, 4, 6, True])
    monkeypatch.setattr(today, 'commit_counter', lambda *a, **k: 99)
    monkeypatch.setattr(today, 'graph_repos_stars',
                        lambda count_type, *a, **k: {'stars': 42, 'repos': 5}.get(count_type, 7))
    monkeypatch.setattr(today, 'follower_getter', lambda username: 3)
    rendered = []
    monkeypatch.setattr(today, 'svg_overwrite', lambda *args: rendered.append(args))

    today.main(config_path=config)
    capsys.readouterr()  # swallow timing output

    assert today.USER_NAME == 'maxxqcty'
    assert [args[0] for args in rendered] == ['dark_mode.svg', 'light_mode.svg']
    # age, commit, star, repo, contrib, follower, loc — same call shape as before
    assert rendered[0][1] == today.daily_readme(__import__('datetime').date(2004, 9, 13))


def test_template_has_no_personal_archive_logic():
    assert not hasattr(today, 'add_archive')
    source = open('today.py', encoding='utf-8').read()
    assert 'MDQ6VXNlcjU3MzMxMTM0' not in source  # Andrew's hardcoded owner id
    assert 'repository_archive' not in source

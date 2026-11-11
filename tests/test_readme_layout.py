from pathlib import Path

import haiku

README = (Path(__file__).resolve().parents[1] / 'README.md').read_text(encoding='utf-8')
RAW = 'https://raw.githubusercontent.com/maxxqcty/maxxqcty/main/'


def test_no_colored_badges():
    assert 'for-the-badge' not in README


def test_haiku_markers_and_update_still_work():
    assert haiku.MARKER_START in README and haiku.MARKER_END in README
    assert 'x' in haiku.update_readme(README, 'x')


def test_light_dark_pairs_present():
    for name in ('header-banner', 'header-banner-light', 'dark_mode', 'light_mode',
                 'languages_dark', 'languages_light'):
        assert f'{RAW}{name}.svg' in README, name
    assert 'streak-stats.demolab.com?user=maxxqcty&theme=dark' in README
    assert 'streak-stats.demolab.com?user=maxxqcty&theme=light' in README


def test_streak_below_languages():
    assert README.index('languages_light.svg') < README.index('streak-stats.demolab.com')


def test_stack_groups_kept():
    for group in ('Frontend', 'Backend', 'Database &amp; Cloud', 'Mobile', 'DevOps &amp; Tools', 'Design'):
        assert group.upper() in README.upper(), group

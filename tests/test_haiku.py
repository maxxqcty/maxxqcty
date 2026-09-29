import json
from datetime import date, timedelta
from pathlib import Path

import pytest

import haiku

REPO_ROOT = Path(__file__).resolve().parents[1]
FALLBACK_FILE = REPO_ROOT / 'haiku_fallback.txt'
README_FILE = REPO_ROOT / 'README.md'

GOOD = ['autumn twilight falls', 'the old pond waits in silence', 'a frog jumps water']

README = """before

<!-- haiku:start -->
old haiku
<!-- haiku:end -->

after
"""


def test_validate_accepts_three_reasonable_lines():
    assert haiku.validate(GOOD) == GOOD


def test_validate_strips_surrounding_whitespace():
    assert haiku.validate(['  one  ', ' two ', 'three']) == ['one', 'two', 'three']


def test_validate_rejects_two_lines():
    with pytest.raises(ValueError):
        haiku.validate(GOOD[:2])


def test_validate_rejects_four_lines():
    with pytest.raises(ValueError):
        haiku.validate(GOOD + ['a fourth line'])


def test_validate_rejects_blank_line():
    with pytest.raises(ValueError):
        haiku.validate(['first line here', '   ', 'third line here'])


def test_validate_rejects_overlong_line():
    with pytest.raises(ValueError):
        haiku.validate(['x' * (haiku.MAX_LINE + 1), 'seven syllables', 'five here'])


def test_validate_rejects_markup():
    with pytest.raises(ValueError):
        haiku.validate(['<b>bold</b>', 'seven syllables', 'five here'])


def test_render_block_breaks_every_line():
    """Guards the run-on bug: consecutive lines with no <br> collapse into one paragraph."""
    block = haiku.render_block(GOOD, '2026-09-30')
    for line in GOOD:
        assert f'*{line}*' in block
    assert '*autumn twilight falls*<br>' in block
    assert '*the old pond waits in silence*<br>' in block


def test_render_block_centers_itself():
    block = haiku.render_block(GOOD, '2026-09-30')
    assert block.startswith('<div align="center">')
    assert block.endswith('</div>')
    assert not any(line.startswith('>') for line in block.splitlines()), 'no quote bar'


def test_render_block_includes_the_date():
    assert '2026-09-30' in haiku.render_block(GOOD, '2026-09-30')


def test_render_block_puts_the_date_in_small_text():
    block = haiku.render_block(GOOD, '2026-09-30')
    assert '<sub>2026-09-30</sub>' in block
    assert '> <sub>' not in block


def test_render_block_adds_no_stray_markup():
    """After stripping the tags this renderer is allowed to emit, only plain text is left."""
    block = haiku.render_block(GOOD, '2026-09-30')
    for tag in ('<div align="center">', '</div>', '<br>', '<sub>', '</sub>'):
        block = block.replace(tag, '')
    assert '<' not in block
    assert '>' not in block


def test_update_readme_replaces_inner_content_and_keeps_markers():
    block = haiku.render_block(GOOD, '2026-09-30')
    out = haiku.update_readme(README, block)
    assert out.count(haiku.MARKER_START) == 1
    assert out.count(haiku.MARKER_END) == 1
    assert 'old haiku' not in out
    assert '*autumn twilight falls*<br>' in out
    assert out.startswith('before')
    assert out.rstrip().endswith('after')


def test_update_readme_raises_when_markers_are_missing():
    with pytest.raises(ValueError):
        haiku.update_readme('no markers in this file', 'anything')


def test_update_readme_raises_when_end_precedes_start():
    text = '<!-- haiku:end -->\ncontent\n<!-- haiku:start -->'
    with pytest.raises(ValueError):
        haiku.update_readme(text, 'anything')


def test_parse_lines_reads_flat_json():
    assert haiku.parse_lines(json.dumps({'lines': GOOD})) == GOOD


def test_parse_lines_reads_json_embedded_in_response_text():
    body = json.dumps({'steps': [{'content': [{'text': json.dumps({'lines': GOOD})}]}]})
    assert haiku.parse_lines(body) == GOOD


def test_parse_lines_reads_fenced_json():
    body = '```json\n' + json.dumps({'lines': GOOD}) + '\n```'
    assert haiku.parse_lines(body) == GOOD


def test_parse_lines_raises_when_json_has_no_lines():
    with pytest.raises(ValueError):
        haiku.parse_lines('{"something": "else"}')


def test_parse_lines_raises_on_unparseable_body():
    with pytest.raises(ValueError):
        haiku.parse_lines('<<< not json >>>')


def test_every_fallback_entry_is_a_valid_haiku():
    entries = haiku.load_fallback(FALLBACK_FILE)
    assert len(entries) >= 30, 'need at least 30 fallback haikus'
    for entry in entries:
        assert haiku.validate(entry) == entry


def test_fallback_lines_are_deterministic_for_a_date():
    first = haiku.fallback_lines('2026-09-30', FALLBACK_FILE)
    assert first == haiku.fallback_lines('2026-09-30', FALLBACK_FILE)


def test_fallback_lines_rotate_across_dates():
    assert haiku.fallback_lines('2026-09-30', FALLBACK_FILE) != \
        haiku.fallback_lines('2026-10-01', FALLBACK_FILE)


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


def _good_post(calls=None):
    def post(url, **kwargs):
        if calls is not None:
            calls.append((url, kwargs))
        payload = {'steps': [{'content': [{'text': json.dumps({'lines': GOOD})}]}]}
        return FakeResponse(200, json.dumps(payload))
    return post


def test_fetch_lines_sends_the_documented_request():
    calls = []
    assert haiku.fetch_lines('SECRET', post=_good_post(calls)) == GOOD
    url, kwargs = calls[0]
    assert url == haiku.API_URL
    assert kwargs['headers']['x-goog-api-key'] == 'SECRET'
    assert kwargs['json']['model'] == haiku.MODEL
    schema = kwargs['json']['response_format']['schema']
    assert 'lines' in schema['properties']


def test_fetch_lines_retries_once_after_a_server_error():
    attempts = []

    def post(url, **kwargs):
        attempts.append(url)
        return FakeResponse(503, 'busy')

    with pytest.raises(Exception):
        haiku.fetch_lines('SECRET', post=post)
    assert len(attempts) == 2


def test_generate_returns_api_result_without_falling_back():
    lines, used_fallback = haiku.generate('2026-09-30', 'SECRET', post=_good_post())
    assert lines == GOOD
    assert used_fallback is False


def test_generate_falls_back_when_the_api_errors():
    def post(url, **kwargs):
        return FakeResponse(500, 'boom')

    lines, used_fallback = haiku.generate('2026-09-30', 'SECRET', post=post)
    assert used_fallback is True
    assert lines == haiku.fallback_lines('2026-09-30', FALLBACK_FILE)


def test_generate_falls_back_when_the_api_returns_malformed_lines():
    def post(url, **kwargs):
        payload = {'steps': [{'content': [{'text': json.dumps({'lines': ['only one line']})}]}]}
        return FakeResponse(200, json.dumps(payload))

    lines, used_fallback = haiku.generate('2026-09-30', 'SECRET', post=post)
    assert used_fallback is True
    assert lines == haiku.fallback_lines('2026-09-30', FALLBACK_FILE)


def test_generate_never_calls_the_api_without_a_key():
    calls = []

    def post(url, **kwargs):
        calls.append(url)
        return FakeResponse(200, json.dumps({'lines': GOOD}))

    lines, used_fallback = haiku.generate('2026-09-30', None, post=post)
    assert calls == []
    assert used_fallback is True
    assert lines == haiku.fallback_lines('2026-09-30', FALLBACK_FILE)


def test_fallback_cycles_through_every_entry():
    entries = haiku.load_fallback(FALLBACK_FILE)
    start = date(2026, 10, 1)
    seen = {
        tuple(haiku.fallback_lines((start + timedelta(days=i)).isoformat(), FALLBACK_FILE))
        for i in range(len(entries))
    }
    assert len(seen) == len(entries), 'rotation must reach every fallback haiku'


def test_shipped_readme_contains_the_haiku_markers():
    text = README_FILE.read_text(encoding='utf-8')
    assert haiku.MARKER_START in text
    assert haiku.MARKER_END in text


def test_haiku_section_sits_above_the_badges():
    text = README_FILE.read_text(encoding='utf-8')
    assert text.index(haiku.MARKER_START) < text.index('dark_mode.svg')


def test_daily_haiku_heading_is_gone():
    text = README_FILE.read_text(encoding='utf-8')
    assert 'Daily Haiku' not in text

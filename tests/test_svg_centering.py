import re

PANEL_RE = re.compile(r'<text x="390"[^>]*>(.*?)</text>', re.S)
TSpan_Y_RE = re.compile(r'<tspan[^>]*\by="(\d+)"')
RECT_RE = re.compile(r'<rect x="\d+" y="(\d+)" width="36" height="18"')

HEADER_Y = 30
FONT_ASCENT = 12   # body glyph top = baseline - ascent
HEADER_DESCENT = 4  # prompt glyph bottom = baseline + descent
WINDOW_H = 530


def panel_body_ys(filename):
    content = open(filename, encoding='utf-8').read()
    panel = PANEL_RE.search(content)
    assert panel, f'{filename}: panel <text> not found'
    ys = [int(y) for y in TSpan_Y_RE.findall(panel.group(1))]
    assert ys, f'{filename}: no panel tspans'
    return ys


def blocks_bottom(filename):
    content = open(filename, encoding='utf-8').read()
    ys = [int(y) for y in RECT_RE.findall(content)]
    assert len(ys) == 16, f'{filename}: found {len(ys)} color blocks'
    return max(ys) + 18


def test_prompt_line_stays_at_the_top():
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        content = open(filename, encoding='utf-8').read()
        panel = PANEL_RE.search(content)
        first_tspan_y = TSpan_Y_RE.search(panel.group(1)).group(1)
        assert first_tspan_y == str(HEADER_Y), \
            f'{filename}: prompt moved to y={first_tspan_y}'


def test_body_section_is_vertically_centered():
    # equal whitespace between prompt and body top / between blocks and window bottom
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        ys = [y for y in panel_body_ys(filename) if y > HEADER_Y]
        assert ys, f'{filename}: no body rows found'
        body_top = min(ys) - FONT_ASCENT
        top_gap = body_top - (HEADER_Y + HEADER_DESCENT)
        bottom_gap = WINDOW_H - blocks_bottom(filename)
        assert abs(top_gap - bottom_gap) <= 2, \
            f'{filename}: gaps unbalanced, {top_gap}px above vs {bottom_gap}px below'


def test_body_rows_keep_their_relative_spacing():
    # a uniform shift must not scramble the internal layout
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        ys = sorted(y for y in panel_body_ys(filename) if y > HEADER_Y)
        gaps = [b - a for a, b in zip(ys, ys[1:])]
        assert min(gaps) >= 20, f'{filename}: rows too close: {gaps}'
        assert max(gaps) <= 55, f'{filename}: rows too far apart: {gaps}'

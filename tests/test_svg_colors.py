import re

# neofetch's classic ANSI palette: normal row, then bright row
NORMAL = ['#30363d', '#cd3131', '#0dbc79', '#e5e510',
          '#2472c8', '#bc3fbc', '#11a8cd', '#e5e5e5']
BRIGHT = ['#666666', '#f14c4c', '#23d18b', '#f5f543',
          '#3b8eea', '#d670d6', '#29b8db', '#ffffff']
ROW_Y = ('375', '448')
BLOCK_W, BLOCK_H, STEP = 69, 69, 73
PANEL_X = 390

BLOCK_RE = re.compile(
    rf'<rect x="(\d+)" y="(\d+)" width="{BLOCK_W}" height="{BLOCK_H}"'
    r'(?: fill="(#[0-9a-f]{6})")?[^>]*/>'
)


def blocks(filename):
    content = open(filename, encoding='utf-8').read()
    return BLOCK_RE.findall(content)


def test_sixteen_color_blocks_below_the_stats_section():
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        found = blocks(filename)
        assert len(found) == 16, f'{filename}: {len(found)} blocks, expected 16'
        for y in ROW_Y:
            row = sorted((x for x, block_y, _ in found if block_y == y), key=int)
            expected_x = [str(PANEL_X + i * STEP) for i in range(8)]
            assert row == expected_x, f'{filename}: row y={y} x={row}'


def test_block_colors_follow_the_neofetch_palette():
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        found = blocks(filename)
        top = [fill for _, y, fill in found if y == ROW_Y[0]]
        bottom = [fill for _, y, fill in found if y == ROW_Y[1]]
        assert top == NORMAL, f'{filename}: top row {top}'
        assert bottom == BRIGHT, f'{filename}: bottom row {bottom}'


def test_blocks_stay_inside_the_window():
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        for x, y, _ in blocks(filename):
            assert int(x) >= PANEL_X, f'{filename}: block x={x} left of panel'
            assert int(x) + BLOCK_W <= 985, f'{filename}: block x={x} overflows'
            assert int(y) >= 370 and int(y) + BLOCK_H <= 530, \
                f'{filename}: block y={y} out of bounds'


def test_blocks_reach_the_right_edge_with_matching_padding():
    # left margin is 15px (art starts at x15); right margin must match
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        right_edge = max(int(x) + BLOCK_W for x, _, _ in blocks(filename))
        assert right_edge == 970, f'{filename}: right edge at {right_edge}, expected 970'

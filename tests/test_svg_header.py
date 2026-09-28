import re

TRAFFIC_LIGHTS = ['#ff5f57', '#febc2e', '#28c840']


def test_macos_traffic_lights_present_in_both_svgs():
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        content = open(filename, encoding='utf-8').read()
        circles = re.findall(r'<circle [^>]*/>', content)
        assert len(circles) == 3, f'{filename}: expected 3 circles, found {len(circles)}'
        fills = re.findall(r'fill="(#[0-9a-f]{6})"', '\n'.join(circles))
        assert fills == TRAFFIC_LIGHTS, f'{filename}: fills are {fills}'
        for cx, expected in zip(re.findall(r'cx="(\d+)"', '\n'.join(circles)), ('22', '44', '66')):
            assert cx == expected, f'{filename}: cx={cx}, expected {expected}'
        assert all('r="8"' in c for c in circles), f'{filename}: radius changed'


def test_circles_sit_above_the_content_block():
    # circles must be inserted after the background rect, before any text
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        content = open(filename, encoding='utf-8').read()
        rect_pos = content.index('<rect')
        first_circle = content.index('<circle')
        first_text = content.index('<text')
        assert rect_pos < first_circle < first_text, f'{filename}: circles misplaced'

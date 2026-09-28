import re

ART_LINES = open('ascii.txt', encoding='utf-8-sig').read().splitlines()
ART_FONT_SIZE = '12'
ART_TEXT_LENGTH = '370'  # must stay left of the info panel at x=390 (starts x=15)


def art_block(filename):
    content = open(filename, encoding='utf-8').read()
    match = re.search(r'<text x="15"[^>]*>.*?</text>', content, re.S)
    assert match, f'{filename}: no art block found'
    return match.group(0)


def test_art_block_matches_ascii_txt_in_both_svgs():
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        block = art_block(filename)
        rendered = re.findall(r'<tspan[^>]*>(.*?)</tspan>', block, re.S)
        assert len(rendered) == len(ART_LINES), \
            f'{filename}: {len(rendered)} art lines, expected {len(ART_LINES)}'
        assert rendered == ART_LINES, f'{filename}: art differs from ascii.txt'


def test_art_is_scaled_and_pinned_to_the_left_panel():
    for filename in ('dark_mode.svg', 'light_mode.svg'):
        block = art_block(filename)
        assert f'font-size="{ART_FONT_SIZE}"' in block, f'{filename}: art font not scaled'
        tspans = re.findall(r'<tspan [^>]*>', block)
        assert len(tspans) == len(ART_LINES)
        for tag in tspans:
            assert f'textLength="{ART_TEXT_LENGTH}"' in tag, f'{filename}: unpinned line: {tag}'
            assert 'lengthAdjust="spacingAndGlyphs"' in tag
        ys = [int(y) for y in re.findall(r'<tspan[^>]*y="(\d+)"', block)]
        assert ys == sorted(ys) and max(ys) <= 510, f'{filename}: y positions {ys[:3]}...{ys[-1:]}'


def test_art_keeps_its_original_fill_color():
    for filename, expected_fill in (('dark_mode.svg', '#c9d1d9'), ('light_mode.svg', '#24292f')):
        block = art_block(filename)
        assert f'fill="{expected_fill}"' in block, f'{filename}: fill changed: {block[:120]}'

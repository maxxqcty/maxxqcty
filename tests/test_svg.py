from lxml import etree

import today


def parse(svg_body):
    return etree.fromstring(svg_body.encode('utf-8'))


def test_find_and_replace_raises_when_id_missing():
    root = parse('<svg><text id="present">old</text></svg>')
    try:
        today.find_and_replace(root, 'absent', 'new')
    except KeyError as err:
        assert 'absent' in str(err)
    else:
        raise AssertionError('expected KeyError for missing id')


def test_find_and_replace_optional_id_is_silently_skipped():
    root = parse('<svg><text id="present">old</text></svg>')
    assert today.find_and_replace(root, 'absent', 'new', required=False) is None


def test_justify_format_updates_value_on_real_dark_svg():
    tree = etree.parse('dark_mode.svg')
    today.justify_format(tree.getroot(), 'commit_data', 123456)
    element = tree.getroot().find(".//*[@id='commit_data']")
    assert element.text == '123,456'


def test_justify_format_tolerates_missing_dots_id_on_real_dark_svg():
    # contrib_data has no contrib_data_dots partner in the SVG; must not raise
    tree = etree.parse('dark_mode.svg')
    today.justify_format(tree.getroot(), 'contrib_data', 999)
    element = tree.getroot().find(".//*[@id='contrib_data']")
    assert element.text == '999'


def test_svg_overwrite_writes_age_data(tmp_path):
    target = tmp_path / 'dark_mode.svg'
    target.write_bytes(open('dark_mode.svg', 'rb').read())
    today.svg_overwrite(str(target), '21 years, 0 months, 15 days', 10, 20, 30, 40, 50,
                        ['1,000', '500', '500'])
    root = etree.parse(str(target)).getroot()
    age = root.find(".//*[@id='age_data']")
    assert age is not None and age.text == '21 years, 0 months, 15 days'

import today

COMMENT = 'This line is a comment block. Write whatever you want here.\n'
DATA = 'a' * 64 + ' 117 13 86 6\n'


def test_cache_comment_size_detects_seven_line_block():
    lines = [COMMENT] * 7 + [DATA]
    assert today.cache_comment_size(lines) == 7


def test_cache_comment_size_returns_full_length_when_no_data_lines():
    lines = [COMMENT] * 3
    assert today.cache_comment_size(lines) == 3


def test_commit_counter_ignores_comment_block(tmp_path):
    filename = tmp_path / 'cache.txt'
    filename.write_text(''.join([COMMENT] * 5) + DATA + ('b' * 64) + ' 10 4 100 20\n', encoding='utf-8')
    assert today.commit_counter(filename=str(filename)) == 17

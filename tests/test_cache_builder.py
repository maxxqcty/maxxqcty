import hashlib

import today
from tests.test_cache import COMMENT


def sha(name):
    return hashlib.sha256(name.encode('utf-8')).hexdigest()


def test_flush_cache_preserves_loc_for_existing_repos(tmp_path):
    filename = tmp_path / 'cache.txt'
    hash_kept = sha('me/kept')
    filename.write_text(''.join([COMMENT] * 3) + hash_kept + ' 10 5 100 20\n', encoding='utf-8')
    edges = [{'node': {'nameWithOwner': 'me/kept'}}, {'node': {'nameWithOwner': 'me/new'}}]
    today.flush_cache(edges, str(filename))
    lines = open(filename, encoding='utf-8').read().splitlines()
    assert lines[:3] == [COMMENT.rstrip('\n')] * 3  # comment block kept
    assert lines[3] == hash_kept + ' 10 5 100 20'  # LOC preserved for known repo
    assert lines[4] == sha('me/new') + ' 0 0 0 0'  # new repo starts blank


def test_cache_builder_only_rewalks_repos_with_changed_commit_count(tmp_path, monkeypatch):
    filename = tmp_path / 'cache.txt'
    hash_alpha, hash_beta = sha('me/alpha'), sha('me/beta')
    filename.write_text(hash_alpha + ' 10 5 100 20\n' + hash_beta + ' 20 4 50 5\n', encoding='utf-8')
    edges = [
        {'node': {'nameWithOwner': 'me/alpha', 'defaultBranchRef': {'target': {'history': {'totalCount': 10}}}}},
        {'node': {'nameWithOwner': 'me/beta', 'defaultBranchRef': {'target': {'history': {'totalCount': 25}}}}},
    ]
    walked = []
    monkeypatch.setattr(today, 'recursive_loc',
                        lambda owner, repo, *args: (walked.append((owner, repo)) or (999, 111, 3)))
    totals = today.cache_builder(edges, filename=str(filename))
    assert walked == [('me', 'beta')]  # alpha unchanged -> no history walk
    lines = open(filename, encoding='utf-8').read().splitlines()
    assert lines[0] == hash_alpha + ' 10 5 100 20'
    assert lines[1] == hash_beta + ' 25 3 999 111'
    assert totals == [1099, 131, 1099 - 131, True]

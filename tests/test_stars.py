import json

import today


class FakeResponse:
    def __init__(self, payload):
        self.status_code = 200
        self.payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self.payload


def page(edges, total, has_next, cursor=None):
    return FakeResponse({'data': {'user': {'repositories': {
        'totalCount': total,
        'edges': [{'node': {'nameWithOwner': name, 'stargazerCount': stars}}
                  for name, stars in edges],
        'pageInfo': {'endCursor': cursor, 'hasNextPage': has_next},
    }}}})


def test_graph_repos_stars_sums_stars_across_all_pages(monkeypatch):
    pages = iter([page([('me/a', 5), ('me/b', 10)], 3, True, 'cursor-1'),
                  page([('me/c', 7)], 3, False)])
    calls = []
    monkeypatch.setattr(today.requests, 'post',
                        lambda *a, **k: (calls.append(1), next(pages))[1])
    assert today.graph_repos_stars('stars', ['OWNER']) == 22
    assert len(calls) == 2  # followed the cursor


def test_graph_repos_stars_uses_stargazercount_scalar_not_stargazers_connection():
    # GitHub regression (community discussion #202883): the stargazers { totalCount }
    # connection now returns FORBIDDEN for fine-grained PATs; the stargazerCount
    # scalar on Repository requires no extra permission
    source = open('today.py', encoding='utf-8').read()
    assert 'stargazers {' not in source, 'query still uses the forbidden stargazers connection'
    assert "node['node']['stargazerCount']" in source, 'stars_counter must read the scalar field'


def test_graph_repos_stars_repos_count_needs_no_pagination(monkeypatch):
    calls = []
    monkeypatch.setattr(today.requests, 'post',
                        lambda *a, **k: (calls.append(1), page([('me/a', 5)], 41, True, 'cursor-1'))[1])
    assert today.graph_repos_stars('repos', ['OWNER']) == 41
    assert len(calls) == 1  # totalCount is already the full count

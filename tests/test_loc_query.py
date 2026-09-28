import itertools

import today
from tests.test_stars import FakeResponse, page


def test_loc_query_does_not_accumulate_edges_between_calls(monkeypatch):
    received = []
    pages = itertools.cycle([page([('me/a', 1), ('me/b', 2)], 4, True, 'cursor-1'),
                             page([('me/c', 3), ('me/d', 4)], 4, False)])
    monkeypatch.setattr(today.requests, 'post', lambda *a, **k: next(pages))
    monkeypatch.setattr(today, 'cache_builder',
                        lambda edges, *a, **k: (received.append(len(edges)), [0, 0, 0, True])[1])
    today.loc_query(['OWNER'])
    today.loc_query(['OWNER'])
    assert received == [4, 4]  # each call merges its own two pages, no carry-over

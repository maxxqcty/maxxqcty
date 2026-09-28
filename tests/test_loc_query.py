import today
from tests.test_stars import FakeResponse, page


def test_loc_query_does_not_accumulate_edges_between_calls(monkeypatch):
    received = []
    monkeypatch.setattr(today.requests, 'post',
                        lambda *a, **k: page([('me/a', 1), ('me/b', 2)], 2, False))
    monkeypatch.setattr(today, 'cache_builder',
                        lambda edges, *a, **k: (received.append(len(edges)), [0, 0, 0, True])[1])
    today.loc_query(['OWNER'])
    today.loc_query(['OWNER'])
    assert received == [2, 2]  # each call sees only its own page, no carry-over

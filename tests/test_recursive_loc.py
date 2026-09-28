import today
from tests.test_stars import FakeResponse

PAGES = 600  # old recursive implementation used 2 stack frames per page -> RecursionError


def history_page(edges, has_next, cursor):
    return FakeResponse({'data': {'repository': {'defaultBranchRef': {'target': {'history': {
        'edges': edges, 'pageInfo': {'endCursor': cursor, 'hasNextPage': has_next}}}}}}})


def commit_edge(user_id, adds, dels):
    return {'node': {'author': {'user': {'id': user_id}},
                     'additions': adds, 'deletions': dels,
                     'committedDate': '2020-01-01T00:00:00Z'}}


def test_recursive_loc_walks_hundreds_of_pages_without_recursion_error(monkeypatch):
    monkeypatch.setattr(today, 'OWNER_ID', {'id': 'me'}, raising=False)
    calls = []

    def fake_post(*args, **kwargs):
        page_index = len(calls)
        calls.append(1)
        return history_page([commit_edge('me', 10, 1), commit_edge('someone-else', 99, 99)],
                            page_index < PAGES - 1, str(page_index))

    monkeypatch.setattr(today.requests, 'post', fake_post)
    addition_total, deletion_total, my_commits = today.recursive_loc('me', 'repo', [], [])
    assert len(calls) == PAGES
    assert my_commits == PAGES
    assert addition_total == 10 * PAGES
    assert deletion_total == 1 * PAGES

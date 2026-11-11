import os

import pytest

os.environ.setdefault('ACCESS_TOKEN', 'test-token')

import today  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture
def post(monkeypatch):
    """Stubs requests.post; set post.status to control the response, post.calls counts calls."""
    class Stub:
        status = 200
        calls = 0

    stub = Stub()

    def fake_post(*args, **kwargs):
        stub.calls += 1
        return FakeResponse(stub.status, {'data': {}}, 'body')

    monkeypatch.setattr(today.requests, 'post', fake_post)
    monkeypatch.setattr(today.time, 'sleep', lambda *_: None)
    return stub


def test_401_raises_token_error_with_guidance(post):
    post.status = 401
    with pytest.raises(today.TokenError, match='ACCESS_TOKEN'):
        today.simple_request('user_getter', 'query', {})


def test_401_is_not_retried(post):
    post.status = 401
    with pytest.raises(today.TokenError):
        today.simple_request('user_getter', 'query', {})
    assert post.calls == 1


def test_403_still_retries(post):
    post.status = 403
    with pytest.raises(Exception) as excinfo:
        today.simple_request('user_getter', 'query', {})
    assert not isinstance(excinfo.value, today.TokenError)
    assert post.calls == today.MAX_ATTEMPTS


def test_200_returns_response(post):
    response = today.simple_request('user_getter', 'query', {})
    assert response.status_code == 200
    assert response.json() == {'data': {}}

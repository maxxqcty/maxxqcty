import json

import pytest

import today


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self.payload


def script(responses, monkeypatch, calls):
    responses = iter(responses)

    def fake_post(*args, **kwargs):
        calls.append(1)
        return next(responses)

    monkeypatch.setattr(today.requests, 'post', fake_post)
    monkeypatch.setattr(today.time, 'sleep', lambda seconds: None)


def test_simple_request_retries_transient_status_then_succeeds(monkeypatch):
    calls = []
    script([FakeResponse(502, {'message': 'bad gateway'}),
            FakeResponse(502, {'message': 'bad gateway'}),
            FakeResponse(200, {'data': {'ok': True}})], monkeypatch, calls)
    response = today.simple_request('test_query', 'query', {})
    assert response.status_code == 200
    assert len(calls) == 3


def test_simple_request_raises_on_graphql_errors_payload(monkeypatch):
    calls = []
    script([FakeResponse(200, {'errors': [{'message': 'Something went wrong'}]})] * 3, monkeypatch, calls)
    with pytest.raises(Exception) as excinfo:
        today.simple_request('test_query', 'query', {})
    assert 'GraphQL error' in str(excinfo.value)
    assert 'Something went wrong' in str(excinfo.value)


def test_simple_request_does_not_retry_client_error(monkeypatch):
    calls = []
    script([FakeResponse(401, {'message': 'Bad credentials'})], monkeypatch, calls)
    with pytest.raises(Exception) as excinfo:
        today.simple_request('test_query', 'query', {})
    assert 'has failed' in str(excinfo.value)
    assert len(calls) == 1

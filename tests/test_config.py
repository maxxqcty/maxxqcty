import datetime
import json

import pytest

import today


def write_config(tmp_path, payload):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(payload), encoding='utf-8')
    return path


def test_load_config_returns_username_and_birthday(tmp_path):
    path = write_config(tmp_path, {'username': 'maxxqcty', 'birthday': '2004-09-13'})
    config = today.load_config(path)
    assert config['username'] == 'maxxqcty'
    assert config['birthday'] == datetime.date(2004, 9, 13)


def test_load_config_missing_key_raises(tmp_path):
    path = write_config(tmp_path, {'username': 'maxxqcty'})
    with pytest.raises(KeyError):
        today.load_config(path)


def test_load_config_invalid_date_raises(tmp_path):
    path = write_config(tmp_path, {'username': 'maxxqcty', 'birthday': 'not-a-date'})
    with pytest.raises(ValueError):
        today.load_config(path)

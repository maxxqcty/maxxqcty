"""Generate a daily haiku and write it into the profile README.

The haiku is fetched from the Gemini Interactions API. Any failure on that
path (missing key, network error, rate limit, malformed reply) falls back to a
bundled haiku chosen by date, so the daily commit always has something to write.
"""
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests

MARKER_START = '<!-- haiku:start -->'
MARKER_END = '<!-- haiku:end -->'
MAX_LINE = 60
FALLBACK_FILE = 'haiku_fallback.txt'
README_FILE = 'README.md'
API_URL = 'https://generativelanguage.googleapis.com/v1beta/interactions'
MODEL = 'gemini-3.8-flash'
MAX_ATTEMPTS = 4
BACKOFF_BASE = 4
READ_TIMEOUT = 45
# Google returns 503 + "usually temporary" when gemini-flash is under load, and
# 429 when the free tier is throttled; every other 4xx will never succeed.
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

PROMPT = (
    'Write one original English haiku.\n'
    'Rules:\n'
    '- exactly three lines\n'
    '- syllable pattern 5, then 7, then 5\n'
    '- no title, no author, no trailing punctuation on any line\n'
    '- plain words only: no markdown, no HTML, no quotation marks\n'
    '- concrete imagery from nature or everyday life, not a famous published haiku\n'
    'Return only the JSON object.'
)

SCHEMA = {
    'type': 'object',
    'properties': {
        'lines': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['lines'],
}


def validate(lines):
    """Returns the three cleaned lines, or raises ValueError if unusable."""
    if not isinstance(lines, (list, tuple)) or len(lines) != 3:
        count = len(lines) if isinstance(lines, (list, tuple)) else 'not a list'
        raise ValueError(f'haiku must be exactly 3 lines, got {count}')
    cleaned = []
    for line in lines:
        if not isinstance(line, str):
            raise ValueError('haiku lines must be strings')
        text = line.strip()
        if not text:
            raise ValueError('haiku line is blank')
        if len(text) > MAX_LINE:
            raise ValueError(f'haiku line exceeds {MAX_LINE} characters')
        if '<' in text or '>' in text:
            raise ValueError('haiku lines must not contain markup')
        cleaned.append(text)
    return cleaned


def _json_candidates(body):
    """Yields JSON values parsed from the body and from balanced {...} runs in it."""
    if not isinstance(body, str):
        return
    try:
        yield json.loads(body)
    except ValueError:
        pass
    depth, start = 0, None
    for index, char in enumerate(body):
        if char == '{':
            if depth == 0:
                start = index
            depth += 1
        elif char == '}' and depth:
            depth -= 1
            if depth == 0 and start is not None:
                snippet = body[start:index + 1]
                if '"lines"' in snippet:
                    try:
                        yield json.loads(snippet)
                    except ValueError:
                        pass
                start = None


def _find_lines(value):
    """Searches a parsed structure for a `lines` array, including inside strings."""
    if isinstance(value, dict):
        lines = value.get('lines')
        if isinstance(lines, list) and lines:
            return list(lines)
        for item in value.values():
            found = _find_lines(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_lines(item)
            if found is not None:
                return found
    elif isinstance(value, str) and '"lines"' in value:
        try:
            return _find_lines(json.loads(value))
        except ValueError:
            return None
    return None


def parse_lines(body):
    """Extracts the raw `lines` array from an API response body."""
    for candidate in _json_candidates(body):
        found = _find_lines(candidate)
        if found is not None:
            return found
    raise ValueError('response body carried no lines array')


def render_block(lines, day):
    """Renders the centred haiku that lives between the README markers.

    Lines are joined with <br> rather than blank lines: without an explicit
    break, consecutive lines collapse into a single run-on paragraph when
    rendered. The blank line before the date is a paragraph break, so the
    date sits apart from the poem rather than running into it.
    """
    poem = '<br>'.join(f'*{line}*' for line in validate(lines))
    return f'<div align="center">\n\n{poem}\n\n<sub>{day}</sub>\n\n</div>'


def update_readme(text, block):
    """Replaces the content between the haiku markers, keeping the markers."""
    start = text.find(MARKER_START)
    end = text.find(MARKER_END)
    if start == -1 or end == -1:
        raise ValueError('README is missing the haiku markers')
    if end < start:
        raise ValueError('haiku markers are out of order')
    return f'{text[:start + len(MARKER_START)]}\n{block}\n{text[end:]}'


def load_fallback(path=FALLBACK_FILE):
    """Reads the bundled haikus as a list of three-line groups; `#` lines are comments."""
    entries, current = [], []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        text = line.strip()
        if text.startswith('#'):
            continue
        if not text:
            if current:
                entries.append(current)
                current = []
            continue
        current.append(text)
    if current:
        entries.append(current)
    if not entries:
        raise ValueError(f'no fallback haikus found in {path}')
    return entries


def fallback_lines(day, path=FALLBACK_FILE):
    """Picks a bundled haiku deterministically from the date, so a rerun is idempotent."""
    entries = load_fallback(path)
    day_of_year = date.fromisoformat(day).timetuple().tm_yday
    return entries[(day_of_year - 1) % len(entries)]


def fetch_lines(api_key, post=None, attempts=MAX_ATTEMPTS):
    """Asks Gemini for a haiku and returns validated lines; raises on failure.

    Two things this has to get right, because it runs unattended and the
    workflow log is the only place its failure ever gets seen:

    Diagnostics -- HTTP status, response body and validation message are all
    logged and folded into the raised error, so a failure names its boundary
    instead of collapsing into "something went wrong". The key travels in a
    header and is never printed; only its length is.

    Patience -- a 503 from an overloaded model is temporary, so transient
    failures get exponential backoff across ``attempts``; a 400 will never
    become a 200, so client errors stop on the first one instead of burning
    the budget.
    """
    if post is None:
        post = requests.post
    payload = {
        'model': MODEL,
        'input': PROMPT,
        'response_format': {
            'type': 'text',
            'mime_type': 'application/json',
            'schema': SCHEMA,
        },
    }
    headers = {'x-goog-api-key': api_key, 'Content-Type': 'application/json'}
    print(
        f'Gemini: key present ({len(api_key)} chars) -> POST {API_URL} '
        f'model={MODEL} bytes={len(json.dumps(payload))}',
        file=sys.stderr,
    )
    last_problem = 'no attempt completed'
    for attempt in range(1, attempts + 1):
        body = None
        retryable = True
        try:
            response = post(API_URL, json=payload, headers=headers, timeout=READ_TIMEOUT)
        except Exception as error:
            # A timeout or connection error never produced a status: always worth retrying.
            last_problem = repr(error)
            print(f'Gemini: attempt {attempt} failed -> {last_problem}', file=sys.stderr)
        else:
            body = response.text
            print(f'Gemini: attempt {attempt} HTTP {response.status_code} | {body[:400]}',
                  file=sys.stderr)
            if response.status_code >= 400:
                last_problem = f'HTTP {response.status_code} | body: {body[:400]}'
                retryable = response.status_code in RETRYABLE_STATUSES
            else:
                try:
                    return validate(parse_lines(body))
                except Exception as error:
                    # The call worked but the haiku did not; re-asking may do better.
                    last_problem = f'{error!r} | body: {body[:400]}'
                    print(f'Gemini: attempt {attempt} failed -> {last_problem}', file=sys.stderr)
        if not retryable:
            print(f'Gemini: attempt {attempt} is not retryable, stopping', file=sys.stderr)
            break
        if attempt < attempts:
            delay = BACKOFF_BASE * 2 ** (attempt - 1)
            print(f'Gemini: backing off {delay}s before attempt {attempt + 1}', file=sys.stderr)
            time.sleep(delay)
    raise RuntimeError(f'haiku request failed after {attempt} attempt(s): {last_problem}')


def generate(day, api_key, post=None, fallback_path=FALLBACK_FILE):
    """Returns (lines, used_fallback); never raises, so a commit always has content."""
    if api_key:
        try:
            return fetch_lines(api_key, post=post), False
        except Exception as error:
            print(f'Gemini failed, using the bundled haiku: {error}', file=sys.stderr)
    return fallback_lines(day, fallback_path), True


def main():
    day = date.today().isoformat()
    lines, used_fallback = generate(day, os.environ.get('GEMINI_API_KEY'))
    readme = Path(README_FILE)
    readme.write_text(
        update_readme(readme.read_text(encoding='utf-8'), render_block(lines, day)),
        encoding='utf-8',
        newline='\n',
    )
    source = 'bundled fallback' if used_fallback else 'Gemini'
    print(f'{day} haiku from {source}: {lines}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

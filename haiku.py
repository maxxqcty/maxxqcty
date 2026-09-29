"""Write the daily haiku into the profile README.

The haiku comes from a bundled pool of 31 entries, picked deterministically by
date, so the same day always yields the same poem and every run has something
to commit. Nothing here touches the network.
"""
import sys
from datetime import date
from pathlib import Path

MARKER_START = '<!-- haiku:start -->'
MARKER_END = '<!-- haiku:end -->'
MAX_LINE = 60
FALLBACK_FILE = 'haiku_fallback.txt'
README_FILE = 'README.md'


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


def main():
    day = date.today().isoformat()
    lines = fallback_lines(day)
    readme = Path(README_FILE)
    readme.write_text(
        update_readme(readme.read_text(encoding='utf-8'), render_block(lines, day)),
        encoding='utf-8',
        newline='\n',
    )
    print(f'{day} haiku from bundled pool: {lines}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

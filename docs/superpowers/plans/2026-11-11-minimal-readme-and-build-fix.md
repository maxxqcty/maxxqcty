# Minimal README + clear 401 message Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the profile README minimal (streak kept below languages) and make an invalid `ACCESS_TOKEN` fail with one clear message.

**Architecture:** Two independent changes. `today.py` gets a small `TokenError` raised from `simple_request` on HTTP 401; all other request behavior is unchanged. `README.md` is edited by hand; a layout test pins what must not break.

**Tech Stack:** Python 3.12, pytest, requests (stubbed in tests), GitHub-flavored README.

**Spec:** `docs/superpowers/specs/2026-11-11-minimal-readme-and-build-fix-design.md`

## Global Constraints

- Do not edit `svg_overwrite`, SVG templates, or any `*.svg` file.
- Keep `<!-- haiku:start -->` / `<!-- haiku:end -->` and every `raw.githubusercontent.com/maxxqcty/maxxqcty/main/<name>.svg` path the build writes: `dark_mode.svg`, `light_mode.svg`, `languages_dark.svg`, `languages_light.svg`, `header-banner.svg`, `header-banner-light.svg`.
- Streak widget stays, below the languages card, same two `streak-stats.demolab.com` URLs (dark and light) as today.
- Tech stack: same six groups and same technologies as today; flat single-color grey badges (`style=flat-square`, color `555555`), left-aligned, bold-free grey labels.
- Retry behavior of `simple_request` (3 attempts, backoff, statuses 403/429/5xx) must not change.
- Do not commit unless the user asks; commit steps below are for when they do.
- The real build only goes green after the user replaces the `ACCESS_TOKEN` secret (owner action, not part of this plan).

## Review Focus

- A 403 (rate limit) must still retry, not be mistaken for a token error. Pinned in Task 1.
- A 401 on the first call must not be retried (wasted ~3s, same answer). Pinned in Task 1.
- Dark and light `<picture>` pairs must both survive for banner, stats, languages, streak. Pinned in Task 2.
- `haiku.update_readme` must still work on the edited README. Pinned in Task 2.
- No leftover colored `for-the-badge` badges. Pinned in Task 2.

---

### Task 1: Clear message on invalid token

**Files:**
- Create: `tests/test_today.py`
- Modify: `today.py:34-63` (`simple_request`, add `TokenError`)

**Interfaces:**
- Produces: `today.TokenError(Exception)`; `simple_request(func_name, query, variables)` unchanged signature, now raises `TokenError` on a 401 response.
- Test setup: `today` reads `os.environ['ACCESS_TOKEN']` at import, so the test file must `os.environ.setdefault('ACCESS_TOKEN', 'test-token')` before `import today`.

- [ ] **Step 1: Write failing tests** in `tests/test_today.py`, stubbing `today.requests.post` with a fake response (`status_code`, `text`, `json()`) and `today.time.sleep` with a no-op:
  - `test_401_raises_token_error_with_guidance`: 401 response → `pytest.raises(today.TokenError, match='ACCESS_TOKEN')`.
  - `test_401_is_not_retried`: stub counts calls; after the 401, `calls == 1`.
  - `test_403_still_retries`: always-403 stub → raises a plain `Exception` that is not a `TokenError`; `calls == today.MAX_ATTEMPTS`.
  - `test_200_returns_response`: 200 with `json()` → `{'data': {}}` returns the same object.
- [ ] **Step 2: Run** `python -m pytest tests/test_today.py -v`. Expected: FAIL (`TokenError` undefined; 401 test fails).
- [ ] **Step 3: Implement** `class TokenError(Exception)` in `today.py` near `MAX_ATTEMPTS`, and in `simple_request` check `request.status_code == 401` before the retry/fatal branches, raising `TokenError('ACCESS_TOKEN is invalid or expired; regenerate it and update the repository secret')`.
- [ ] **Step 4: Run** `python -m pytest tests -v`. Expected: all PASS (including existing `test_haiku.py`).
- [ ] **Step 5: Commit (only if asked)** `git add tests/test_today.py today.py && git commit -m "fix: clear error when ACCESS_TOKEN is invalid"`

### Task 2: Minimal README

**Files:**
- Modify: `README.md`
- Create: `tests/test_readme_layout.py`

**Interfaces:**
- Consumes: `haiku.update_readme(text, block)` and `haiku.MARKER_START/MARKER_END` (from `haiku.py`).

- [ ] **Step 1: Write failing tests** in `tests/test_readme_layout.py`, reading the real `README.md`:
  - `test_no_colored_badges`: `'for-the-badge'` not in text.
  - `test_haiku_markers_and_update_still_work`: both markers present, and `haiku.update_readme(text, 'x')` returns text containing `'x'`.
  - `test_light_dark_pairs_present`: each of `header-banner`, `dark_mode`/`light_mode`, `languages_dark`/`languages_light` SVG paths appears, plus the streak URL with `theme=dark` and with `theme=light`.
  - `test_streak_below_languages`: index of `languages_light.svg` < index of `streak-stats.demolab.com`.
  - `test_stack_groups_kept`: the six group names appear (Frontend, Backend, Database & Cloud, Mobile, DevOps & Tools, Design & Creative).
- [ ] **Step 2: Run** `python -m pytest tests/test_readme_layout.py -v`. Expected: `no_colored_badges` and `streak_below_languages` FAIL.
- [ ] **Step 3: Edit `README.md`** per the approved preview: put the streak `<picture>` directly under the languages `<picture>` in the right column; delete the commented-out typing-SVG and views/followers blocks; replace the `## 🛠️ Tech Stack` section with plain grey group labels and `https://img.shields.io/badge/<Name>-555555?style=flat-square` badges (URL-encode `C++` as `C%2B%2B`, `Next.js`, `Node.js` as-is, spaces as `_`), left-aligned (no centering `<div>`). Leave the haiku block untouched.
- [ ] **Step 4: Run** `python -m pytest tests -v`. Expected: all PASS.
- [ ] **Step 5: Visual check:** open `README.md` rendered (e.g. the earlier `scratchpad/preview.html`, or GitHub's preview after push) and compare with the approved mockup in light and dark.
- [ ] **Step 6: Commit (only if asked)** `git add README.md tests/test_readme_layout.py && git commit -m "style: minimal README layout"`

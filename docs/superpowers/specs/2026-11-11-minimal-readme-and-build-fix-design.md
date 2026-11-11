# Minimal README layout + build failure fix (short design)

## Intent and why
The profile README is visually heavy (banner, stats cards, streak widget, ~30
colored `for-the-badge` badges) and the daily `README build` workflow has failed
every run since 2026-10-28, leaving the stats SVGs stale. Goal: a quiet,
minimal profile that updates reliably.

## Goals
- Minimal, consistent, left-aligned README; works in light and dark mode.
- Build failure is diagnosable at a glance (clear message, not a stack trace).
- Nothing that currently works is broken.

## Non-goals / anti-goals
- No redesign of the generated SVGs or changes to `svg_overwrite` (script finds
  elements by ID; risk not worth it). That was approach B, not chosen.
- No refactor of `today.py` state handling in this change (separate, earlier
  proposal; not requested here).
- Must not remove the haiku markers or the SVG/image paths the build writes.

## Approaches considered
- **A. Trim and tidy README only** (chosen by user).
- B. A plus redesign of the stats SVG; more work, riskier. Not chosen.

## Design
1. **Root cause of the build failure:** `ACCESS_TOKEN` secret rejected (401 Bad
   credentials); likely 30-day token expiry (set 2026-09-28, last success
   2026-10-27). Fix is owner-only: regenerate token, `gh secret set ACCESS_TOKEN`.
2. **Guard (my call):** in `today.py`, a 401 from the API raises a one-line
   message "ACCESS_TOKEN is invalid or expired; regenerate it and update the
   repo secret". Behavior otherwise identical.
3. **README (my calls):**
   - Keep banner, stats card, languages pie, haiku block and its markers.
   - Keep the streak-stats widget (user request), moved below the languages card.
   - Tech stack: replace colored `for-the-badge` badges with flat, single-color
     (grey) badges, same five groups, with plain bold labels in place of the
     emoji heading; left aligned instead of centered.
   - Remove commented-out dead blocks (typing SVG, views/followers badges).
4. **Verification:** existing `tests/test_haiku.py` still passes; `haiku.py`
   still finds its markers; README renders with all image links resolving.

## Left to the builder
Exact badge grey, spacing, and wording of the 401 message.

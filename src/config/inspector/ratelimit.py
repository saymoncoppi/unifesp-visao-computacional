"""Sliding-window tracker for the free-tier Gemini quota (requests-per-minute).

The free tier of ``gemini-flash-latest`` allows a small number of requests per
minute (RPM) on a *rolling* 60 s window — not a clock that zeroes at the top of
the minute. This module keeps an in-process timestamp log of the Gemini calls
the app actually issues so the UI can show ``used/limit`` and a countdown until
a slot frees, and (best effort) so the composer can block a new analysis while
the quota is exhausted instead of failing with a 429 mid-request.

Design notes / honest limitations:
  * The count is a best-effort proxy. It records the calls this app *owns* (the
    diagnosis call and the multimodal arbiter call). A 429's ``retryDelay`` — the
    only value Google itself vouches for — is folded in via :func:`observe_exception`
    as an authoritative hard reset when a rate-limit error is seen.
  * There is NO API to ask whether a key is free-tier; that is inferred purely
    from behaviour (the RPM limit and any 429s).
  * State is per-process and in-memory (reset on restart). Good enough for a
    single-worker dev/demo server, which is how this app runs.
"""
from __future__ import annotations

import os
import re
import threading
import time
from collections import deque

# Free-tier gemini-flash default is 5 requests/minute. Overridable via env so a
# paid key (or a different model) can raise/relax the guard without code changes.
RPM_LIMIT = int(os.environ.get("GEMINI_RPM_LIMIT", "5"))
_WINDOW = 60.0                      # rolling window length, in seconds.
_DEFAULT_RETRY = 30.0              # hard-reset fallback when a 429 has no retryDelay.

_lock = threading.Lock()
_calls: "deque[float]" = deque()   # monotonic-ish timestamps of issued calls.
_hard_reset_at = 0.0              # epoch until which we are known-blocked (from a 429).
_seen_429 = False                  # whether a rate-limit (429) has ever been observed.

# Matches google.rpc.RetryInfo's retryDelay, e.g. 'retryDelay: "37s"' or
# '"retryDelay":"37.5s"'. Tolerant of quoting/spacing across SDK surfaces.
_RETRY_RE = re.compile(r"retry[_-]?delay['\"\s:]+(\d+(?:\.\d+)?)\s*s", re.IGNORECASE)


def _prune(now: float) -> None:
    """Drop timestamps that have aged out of the rolling window. Caller holds the lock."""
    while _calls and now - _calls[0] >= _WINDOW:
        _calls.popleft()


def record() -> None:
    """Register that a Gemini call is being issued right now.

    Call this immediately BEFORE the network request so an attempt that later
    fails with a 429 still counts toward the rate (Google counts the attempt).
    """
    now = time.time()
    with _lock:
        _prune(now)
        _calls.append(now)


def note_429(retry_after: float | None) -> None:
    """Record an authoritative hard reset from a rate-limit (429) response.

    Args:
        retry_after: Seconds to wait as reported by the API's ``retryDelay``.
            ``None`` falls back to :data:`_DEFAULT_RETRY` (a conservative
            free-tier estimate) so the UI still shows an honest countdown.
    """
    global _hard_reset_at, _seen_429
    delay = _DEFAULT_RETRY if retry_after is None else max(0.0, float(retry_after))
    with _lock:
        _hard_reset_at = max(_hard_reset_at, time.time() + delay)
        _seen_429 = True


def observe_exception(exc: BaseException) -> None:
    """Inspect an exception and, if it is a rate-limit error, fold in its reset.

    Safe to call on ANY exception: non-rate-limit errors are ignored. This lets
    the existing ``except Exception`` fallbacks stay untouched apart from a
    single call.
    """
    text = str(exc) or ""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    is_rate = code == 429 or "RESOURCE_EXHAUSTED" in text or "429" in text
    if not is_rate:
        return
    match = _RETRY_RE.search(text)
    note_429(float(match.group(1)) if match else None)


def snapshot() -> dict:
    """Return the current quota state for the UI.

    Returns:
        A dict with:
          * ``limit``     -- the RPM limit in effect.
          * ``used``      -- calls issued within the trailing 60 s window.
          * ``remaining`` -- ``limit - used`` (0 while a 429 hard reset is active).
          * ``reset_in``  -- seconds until the state improves (the oldest call
                              ages out, or the 429 hard reset elapses); 0 when
                              idle. The client counts this down locally.
          * ``blocked``   -- whether a new analysis should be withheld.
    """
    now = time.time()
    with _lock:
        _prune(now)
        used = len(_calls)
        window_wait = (_WINDOW - (now - _calls[0])) if used else 0.0
        hard = max(0.0, _hard_reset_at - now)
        seen_429 = _seen_429
    reset_in = max(hard, window_wait if used else 0.0)
    remaining = 0 if hard > 0 else max(0, RPM_LIMIT - used)
    return {
        "limit": RPM_LIMIT,
        "used": used,
        "remaining": remaining,
        "reset_in": round(reset_in, 1),
        "blocked": remaining == 0,
        "seen_429": seen_429,
    }

"""THE ONLY place an anthropic client is constructed. Everything else asks make_client().

  make_client("mock", mock=MockAnthropic(...))  real SDK, fake wire, fake key. No network, no real key.
  make_client("live", key_provider=...)         refuses (LiveNotEnabled) unless the go flag file exists AND the key
                                                provider returns a key (studio_key: Keychain, and only with
                                                ALTO_LIVE_ANTHROPIC=1). This is the key switch-over point.

Alto does its own bounded retries (so each attempt is visible to the meter and the fake clock in tests), so the
client is built with max_retries=0.
"""
from __future__ import annotations

import contextlib
import os
from pathlib import Path

from ._sdk import anthropic   # lazy: only the gated live/mock client construction needs the SDK

from . import keys
from .errors import LiveNotEnabled
from .mock_anthropic import BASE_URL, MockAnthropic

TIMEOUT_S = 120.0


@contextlib.contextmanager
def _clean_env():
    """The SDK reads ANTHROPIC_* from the environment when it is built (base URL, auth token, profile, custom headers).
    None of that may decide where Alto's key goes, so it is hidden while the client is constructed, then put back."""
    saved = {k: v for k, v in os.environ.items() if k.startswith("ANTHROPIC_")}
    for k in saved:
        del os.environ[k]
    try:
        yield
    finally:
        os.environ.update(saved)


def go_flag_path() -> Path:
    """The file Luke's go creates (via the Board). Its existence is the only thing it means."""
    return Path(os.environ.get("ALTO_BASS_LIVE_GO", "") or (Path.home() / ".config" / "alto" / "bass" / "LIVE_GO"))


def live_enabled() -> bool:
    return go_flag_path().is_file()


def make_client(mode: str = "mock", *, mock: MockAnthropic | None = None,
                key_provider: keys.KeyProvider | None = None,
                go_check=None) -> "anthropic.Anthropic":
    if mode == "mock":
        mock = mock or MockAnthropic()
        provider = key_provider or keys.MockKeyProvider()
        with _clean_env():
            return anthropic.Anthropic(api_key=provider.get_key(), base_url=BASE_URL, max_retries=0,
                                       timeout=TIMEOUT_S,
                                       http_client=anthropic.DefaultHttpxClient(transport=mock.transport()))
    if mode == "live":
        if not (go_check() if go_check is not None else live_enabled()):     # go_check: the server's own flag (bass_beta/live_go)
            raise LiveNotEnabled("Bass is not switched on for real traffic yet (no go flag).")
        provider = key_provider or keys.KeychainKeyProvider()
        key = provider.get_key()
        with _clean_env():      # base_url is pinned: the key goes to api.anthropic.com and nowhere else
            return anthropic.Anthropic(api_key=key, base_url=BASE_URL, max_retries=0, timeout=TIMEOUT_S)
    raise ValueError(f"unknown client mode {mode!r}")

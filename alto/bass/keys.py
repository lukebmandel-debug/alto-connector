"""Where the Anthropic API key comes from. The key is IT's: it lives in the macOS Keychain (service
alto-anthropic-test) and is read ONLY by studio_key.get_key(), which refuses unless ALTO_LIVE_ANTHROPIC=1. This module is a
thin adapter over it: no second key reader, nothing here reads, prints or stores a real key.

  MockKeyProvider      fake sk-ant-MOCK key for the simulated API
  KeychainKeyProvider  adapter over studio_key.get_key(); NotConfigured when the live gate is off or the Keychain is empty
"""
from __future__ import annotations

from . import studio_key
from .errors import NotConfigured
from .mock_anthropic import MOCK_KEY


class KeyProvider:
    name = "base"

    def get_key(self) -> str:
        raise NotImplementedError

    def describe(self) -> dict:
        """Safe to log: says WHERE the key would come from, never the key."""
        return {"provider": self.name}


class MockKeyProvider(KeyProvider):
    name = "mock"

    def get_key(self) -> str:
        return MOCK_KEY


class KeychainKeyProvider(KeyProvider):
    name = "keychain"

    def get_key(self) -> str:
        try:
            return studio_key.get_key().reveal()
        except studio_key.KeyUnavailable as e:
            raise NotConfigured(str(e), code="bass_paused") from None

    def describe(self) -> dict:
        return {"provider": self.name, "service": studio_key.SERVICE}

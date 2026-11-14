"""Lazy handles for the Anthropic SDK and its HTTP library. Importing alto.bass never needs either installed (public CI and the product
carry neither); the import happens on first attribute use, which only the gated Bass paths and the tests that need the SDK reach."""
import importlib


class _Lazy:
    def __init__(self, name: str):
        self._name = name

    def __getattr__(self, attr: str):
        return getattr(importlib.import_module(self._name), attr)


anthropic = _Lazy("anthropic")
httpx2 = _Lazy("httpx2")

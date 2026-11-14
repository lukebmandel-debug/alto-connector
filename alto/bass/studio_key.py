"""Reader for the Bass test API key, kept in the macOS Keychain.

The key is never read from an env var, file or argument, and this module never
prints, logs or repr()s it. The Keychain read is refused unless BOTH live gates
are open (ALTO_LIVE_ANTHROPIC=1 and the LIVE_GO file), so a test run cannot even
fetch the key.
"""
import getpass
import os
import subprocess

SERVICE = "alto-anthropic-test"


class KeyUnavailable(RuntimeError):
    pass


class Secret(str):
    """A str that hides itself if something prints or logs it by accident."""
    __slots__ = ()

    def __repr__(self):
        return "<Secret>"

    def __format__(self, spec):
        return "<Secret>"

    def reveal(self):
        return str.__str__(self)

    __str__ = __format__ = lambda self, spec="": "<Secret>"


def _account():
    return os.environ.get("USER") or getpass.getuser()


def key_present():
    """True/False without reading the value (no -w, so the secret is not fetched)."""
    r = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-a", _account()],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode == 0


def get_key():
    """Return the key as a Secret; use .reveal() only when building the request header."""
    if os.environ.get("ALTO_LIVE_ANTHROPIC") != "1":
        raise KeyUnavailable("live Anthropic calls are not enabled (ALTO_LIVE_ANTHROPIC != 1)")
    # Second lock, here and not only in the callers: the LIVE_GO file Luke's go creates (alto.bass.client.go_flag_path).
    from .client import live_enabled, go_flag_path
    if not live_enabled():
        raise KeyUnavailable("live Anthropic calls are not enabled (no LIVE_GO file at %s)" % go_flag_path())
    r = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-a", _account(), "-w"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise KeyUnavailable("no key in the Keychain (service %s)" % SERVICE)
    return Secret(r.stdout.strip())

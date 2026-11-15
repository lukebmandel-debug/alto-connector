"""The free-credit promo cutoff (alto/bass/promo.py). SDK-free: runs on public CI. Every LIVE entry point refuses from 18 Nov 2026 23:00Z with
BassError(promo_ended) and makes no request; mock paths keep working; an unreadable or absurd clock fails closed. No network, no key."""
import datetime as dt
import importlib.util
import socket

import pytest

from bass_support import ROOT
from alto.bass import client as C
from alto.bass import local_reserve as LR
from alto.bass import promo
from alto.bass.errors import BassError, POLICIES, InsufficientCredits

U = dt.timezone.utc
T_OK = dt.datetime(2026, 11, 18, 22, 59, tzinfo=U)
T_CUT = dt.datetime(2026, 11, 18, 23, 0, tzinfo=U)
T_END = dt.datetime(2026, 11, 19, 0, 0, tzinfo=U)
T_DEC = dt.datetime(2026, 12, 5, 12, 0, tzinfo=U)
T_NOW = dt.datetime(2026, 11, 14, 12, 0, tzinfo=U)
MSG = "The free Bass credit has ended."


def _boom():
    raise OSError("clock unreadable")


BROKEN = {"raises": _boom, "none": lambda: None, "string": lambda: "2026-11-14", "naive": lambda: dt.datetime(2026, 11, 14, 12, 0),
          "before_nov1": lambda: dt.datetime(2026, 10, 31, 23, 59, tzinfo=U), "epoch": lambda: dt.datetime(1970, 1, 1, tzinfo=U)}
REFUSED = {"23:00": T_CUT, "19 Nov": T_END, "Dec": T_DEC}


@pytest.fixture(autouse=True)
def _guard(monkeypatch, tmp_path):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    monkeypatch.delenv("ALTO_LIVE_ANTHROPIC", raising=False)
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(tmp_path / "no-go-file"))
    connects = []
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: connects.append(a) or (_ for _ in ()).throw(OSError("no network in tests")))
    yield connects
    assert connects == []


def at(t):
    return lambda: t


class StubTransport:
    """Stands in for the wire. Anything that sends must go through .send(); the tests assert it is never called when refused."""
    def __init__(self):
        self.sent = 0

    def send(self, *a, **k):
        self.sent += 1


def test_constants_and_policy():
    assert promo.PROMO_END_UTC == T_END and promo.CUTOFF_UTC == T_CUT and promo.MARGIN == dt.timedelta(hours=1)
    assert POLICIES["promo_ended"].user_message == MSG
    e = BassError(code="promo_ended")
    assert e.code == "promo_ended" and e.user_message == MSG


def test_check_boundaries():
    promo.check(at(T_OK))
    promo.check(at(T_NOW))
    for name, t in REFUSED.items():
        with pytest.raises(BassError) as ei:
            promo.check(at(t))
        assert ei.value.code == "promo_ended" and ei.value.user_message == MSG, name
    for name, clk in BROKEN.items():
        with pytest.raises(BassError) as ei:
            promo.check(clk)
        assert ei.value.code == "promo_ended", name
    assert promo.live_allowed(at(T_OK)) and not promo.live_allowed(at(T_CUT))
    # an offset-aware time is compared in UTC: 23:30+01:00 is 22:30Z (allowed), 00:00+01:00 on the 19th is 23:00Z on the 18th (refused)
    plus1 = dt.timezone(dt.timedelta(hours=1))
    assert promo.live_allowed(at(dt.datetime(2026, 11, 18, 23, 30, tzinfo=plus1)))
    assert not promo.live_allowed(at(dt.datetime(2026, 11, 19, 0, 0, tzinfo=plus1)))


# -- the local reserve: every hold on the fixed (live) file ----------------------------------------------------------------------
@pytest.fixture()
def fixed(monkeypatch, tmp_path):
    f = tmp_path / "Alto-bass-local" / "reserve.json"
    monkeypatch.setattr(LR, "RESERVE_FILE", f)
    return f


def test_reserve_live_allowed_before_cutoff(fixed):
    r = LR.LocalReserve(clock=at(T_OK))
    assert r.is_fixed()
    r.hold("own", "h1", 1000)
    assert r.status()["used_credits"] == 1.0


@pytest.mark.parametrize("name", list(REFUSED))
def test_reserve_live_refuses_at_and_after_cutoff(fixed, name):
    t = REFUSED[name]
    LR.LocalReserve(clock=at(T_OK)).hold("own", "h0", 1000)        # opens the file
    before = fixed.read_text()
    stub = StubTransport()
    r = LR.LocalReserve(clock=at(t))
    with pytest.raises(BassError) as ei:
        r.hold("own", "h1", 1000)
    assert ei.value.code == "promo_ended" and ei.value.user_message == MSG
    assert fixed.read_text() == before and stub.sent == 0


@pytest.mark.parametrize("name", list(BROKEN))
def test_reserve_live_refuses_on_a_broken_clock(fixed, name):
    r = LR.LocalReserve(clock=BROKEN[name])
    with pytest.raises(BassError) as ei:
        r.hold("own", "h1", 1000)
    assert ei.value.code == "promo_ended"
    assert not fixed.exists()                        # refused before the lock and the file


def test_reserve_ledger_sends_nothing_when_refused(fixed):
    """The pattern every spender follows: ReservedLedger.hold first, the wire only after it. Zero requests reach the stub transport."""
    class Inner:
        called = 0

        def hold(self, *a, **k):
            Inner.called += 1
    stub = StubTransport()
    for t in (T_CUT, T_END, T_DEC):
        led = LR.ReservedLedger(Inner(), LR.LocalReserve(clock=at(t)), "own")
        with pytest.raises(BassError) as ei:
            led.hold("u", "h", 1000, "a1")
            stub.send()
        assert ei.value.code == "promo_ended"
    assert Inner.called == 0 and stub.sent == 0
    led = LR.ReservedLedger(Inner(), LR.LocalReserve(clock=at(T_OK)), "own")      # control: allowed -> the hold goes through, the wire is reached
    led.hold("u", "h", 1000, "a1")
    stub.send()
    assert Inner.called == 1 and stub.sent == 1


def test_reserve_mock_hold_ok_after_cutoff(tmp_path):
    for t in (T_CUT, T_END, T_DEC):
        r = LR.LocalReserve(tmp_path / f"reserve.mock-{t.day}-{t.hour}.json", clock=at(t))
        assert not r.is_fixed()
        r.hold("own", "h", 1000)
        assert r.status()["used_credits"] == 1.0


# -- make_client("live") ----------------------------------------------------------------------------------------------------------
class SpyKeys:
    gets = 0

    def get_key(self):
        SpyKeys.gets += 1
        raise AssertionError("the key must not be read")


@pytest.mark.parametrize("clk", [at(T_CUT), at(T_END), at(T_DEC)] + list(BROKEN.values()))
def test_make_client_live_refuses_before_flag_key_and_sdk(clk):
    gos = []
    with pytest.raises(BassError) as ei:
        C.make_client("live", key_provider=SpyKeys(), go_check=lambda: gos.append(1) or True, clock=clk)
    assert ei.value.code == "promo_ended" and ei.value.user_message == MSG
    assert gos == [] and SpyKeys.gets == 0


def test_make_client_live_before_cutoff_reaches_the_go_check():
    with pytest.raises(BassError) as ei:
        C.make_client("live", key_provider=SpyKeys(), go_check=lambda: False, clock=at(T_OK))
    assert ei.value.code == "bass_paused"        # LiveNotEnabled: the promo check passed, the old gate refused


# -- the two tools ----------------------------------------------------------------------------------------------------------------
def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize("t", [T_CUT, T_END, T_DEC, None])
def test_local_server_live_refuses_at_startup(monkeypatch, tmp_path, t, capsys):
    S = _load("bass_local_server")
    monkeypatch.setattr(promo, "_default_clock", BROKEN["raises"] if t is None else at(t))
    studio = []
    monkeypatch.setattr(S.studio_key, "key_present", lambda: studio.append(1) or True)
    page = tmp_path / "p.html"
    page.write_text("<html><body>x</body></html>")
    with pytest.raises(SystemExit) as ei:
        S.main(["--purpose", "own", "--live", "--site", str(page)])
    assert ei.value.code == 2 and MSG in str(ei.value) and "promo_ended" in str(ei.value)
    assert studio == []                               # the Keychain was not even asked


def test_local_server_live_before_cutoff_reaches_the_old_gates(monkeypatch, tmp_path):
    S = _load("bass_local_server")
    monkeypatch.setattr(promo, "_default_clock", at(T_OK))
    page = tmp_path / "p.html"
    page.write_text("<html><body>x</body></html>")
    with pytest.raises(SystemExit) as ei:
        S.main(["--purpose", "own", "--live", "--site", str(page)])
    assert ei.value.code == 2 and "missing" in str(ei.value) and "promo_ended" not in str(ei.value)


@pytest.mark.parametrize("t", [T_CUT, T_END, T_DEC])
def test_local_server_build_proxy_live_refuses(tmp_path, t):
    S = _load("bass_local_server")
    with pytest.raises(BassError) as ei:
        S.build_proxy("own", S.DEFAULT_ROOT, 0, "tok", True, clock=at(t))
    assert ei.value.code == "promo_ended"


def test_local_server_mock_proxy_builds_after_the_cutoff(tmp_path):
    S = _load("bass_local_server")
    for t in (T_OK, T_CUT, T_DEC):
        assert S.build_proxy("own", tmp_path / f"root-{t.day}-{t.hour}", 0, "tok", False, clock=at(t)) is not None


@pytest.mark.parametrize("t", [T_CUT, T_END, T_DEC, None])
def test_live_check_refuses_at_startup(monkeypatch, tmp_path, capsys, t):
    L = _load("bass_live_check")
    monkeypatch.setattr(promo, "_default_clock", BROKEN["raises"] if t is None else at(t))
    made = []
    monkeypatch.setattr(L.C, "make_client", lambda *a, **k: made.append(a))
    flag = tmp_path / "go"
    flag.write_text("x")
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(flag))                  # even with the go flag and the env gate open
    rc = L.main(["--out", str(tmp_path / "out")], env={"ALTO_STORE": "local", "ALTO_LIVE_ANTHROPIC": "1"})
    assert rc == 2 and made == []
    assert MSG in capsys.readouterr().err


def test_live_check_before_cutoff_is_not_a_promo_refusal(monkeypatch, tmp_path, capsys):
    L = _load("bass_live_check")
    monkeypatch.setattr(promo, "_default_clock", at(T_OK))
    rc = L.main(["--out", str(tmp_path / "out")], env={"ALTO_STORE": "local"})      # no go flag: the old gate refuses
    assert rc == 2 and MSG not in capsys.readouterr().err


# -- the UI -----------------------------------------------------------------------------------------------------------------------
def test_ui_knows_the_promo_code():
    from alto.build import bass_ui_js
    js = bass_ui_js.JS
    assert "promo_ended:1" in js and "promo_ended:'" + MSG + "'" in js and "a.code==='promo_ended'" in js


# -- the beta Proxy (the hosted path): every live action refuses before any hold or upstream request ------------------------------------
def _proxy(tmp_path, clock_t, live):
    from alto.bass.beta_config import BetaConfig
    from alto.bass.beta_ledger import LIVE_GO_KEY, confirm_key
    from alto.bass.beta_proxy import Proxy, SecretReader, TokenVerifier
    from alto.bass.beta_store import FakeStore
    from alto.bass.tools import ToolBox
    from alto.store.local import LocalStore

    class V(TokenVerifier):
        def verify(self, t):
            return {"uid": "u1", "email": "t@example.com", "email_verified": True}

    class Sec(SecretReader):
        calls = []

        def read(self, name):
            Sec.calls.append(name)
            raise AssertionError("the secret must not be read")

    store, clock = FakeStore(auto_terms=True), at(clock_t)
    cfg = BetaConfig(testers=10, allowlist=frozenset({"t@example.com"}))
    store.put(confirm_key(cfg.period_id(clock())), {"confirmed": True})
    if live:
        store.put(LIVE_GO_KEY, {"on": True})
    p = Proxy(cfg, store, V(), Sec(), ToolBox(LocalStore(tmp_path / "store")), clock=clock)
    spy = StubTransport()
    p.service.actions.dispatch = lambda *a, **k: spy.send() or {"ok": True}      # anything past the gates would reach the wire here
    return p, spy, Sec


def _post(p, action):
    import json
    st, _, body = p.handle_http("POST", {"Authorization": "Bearer t"}, json.dumps({"action": action, "args": {}}))
    return st, json.loads(body)


@pytest.mark.parametrize("action", ["build", "propose", "edit", "convert", "make_study_plan", "estimate", "chat", "unknown_new_action"])
@pytest.mark.parametrize("t", [T_CUT, T_END, T_DEC, None])
def test_proxy_live_refuses_every_action_after_the_cutoff(tmp_path, t, action):
    p, spy, Sec = _proxy(tmp_path, T_DEC if t is None else t, True)
    if t is None:
        p.clock = BROKEN["raises"]
    st, out = _post(p, action)
    assert st == 200 and out["code"] == "promo_ended" and out["message"] == MSG and out["ok"] is False
    assert spy.sent == 0 and Sec.calls == []


def test_proxy_mock_mode_is_not_touched_by_the_cutoff(tmp_path):
    p, spy, Sec = _proxy(tmp_path, T_DEC, False)
    st, out = _post(p, "balance")
    assert st == 200 and out.get("code") != "promo_ended" and Sec.calls == []

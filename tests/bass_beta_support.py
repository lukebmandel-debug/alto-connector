"""A whole beta stack on the mock: fake clock, transactional fake store, recording alert sink, the real engine/actions.
No network, no key. Imported by tests/test_bass_beta*.py."""
import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alto.bass import engine as E, mock_anthropic as M                         # noqa: E402
from alto.bass.actions import Actions                                          # noqa: E402
from alto.bass.beta_config import BetaConfig                                   # noqa: E402
from alto.bass.beta_guard import (Allowlist, BetaFlags, BetaService, KillSwitch, RecordingSink, Watchdog)  # noqa: E402
from alto.bass.beta_ledger import BetaLedger, confirm_key                                   # noqa: E402
from alto.bass.beta_store import FakeStore                                     # noqa: E402
from alto.bass.client import make_client                                       # noqa: E402
from alto.bass.tools import ToolBox                                            # noqa: E402
from alto.store.local import LocalStore                                        # noqa: E402

CHIPS = {"title": "Contracts", "acts": [{"label": "Formation"}, {"label": "Remedies"}],
         "entities": [{"id": "offer", "name": "Offer"}], "fields": ["Case", "Rule"], "card_estimate": 6}
MATERIALS = [{"name": "Contracts notes.pdf", "kind": "notes",
              "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel."}]
EMAIL = "tester1@example.com"


class FakeClock:
    """A UTC clock tests move by hand. 2026-11-03 15:00 UTC = 10:00 in New York (after the November change)."""

    def __init__(self, start=None):
        self.now = start or dt.datetime(2026, 11, 3, 15, 0, 0, tzinfo=dt.timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds=0, days=0):
        self.now += dt.timedelta(seconds=seconds, days=days)

    def ts(self):
        return self.now.timestamp()


def make_stack(tmp, testers=10, emails=(EMAIL,), clock=None, store=None, confirm=True, **over):
    # the guard tests are written for the PLANNED $90 ceiling (N = 10 -> 900 each); the interim $70 default (finding M4) has its own
    # tests in tests/test_bass_live_fixes.py
    over.setdefault("server_ceiling_credits", 9000)
    cfg = BetaConfig(testers=testers, allowlist=frozenset(emails), **over)
    clock = clock or FakeClock()
    store = store or FakeStore(auto_terms=True)
    if confirm:
        store.put(confirm_key(cfg.period_id(clock())), {"confirmed": True})      # IT's marker for the current credit period
    sink = RecordingSink()
    kill = KillSwitch(store, sink, clock)
    slept = []
    ledger = BetaLedger(store, cfg, clock, sink=sink, kill=kill, sleep=slept.append)
    ledger.on_commit = Watchdog(cfg, kill, clock)
    flags = BetaFlags(kill, sink, store=store, clock=clock, cfg=cfg)
    mock = M.MockAnthropic()
    client = make_client("mock", mock=mock)
    tools = ToolBox(LocalStore(Path(tmp) / "store"))
    engine = E.Engine(client, ledger, tools, flags=flags, sleep=lambda s: None, monotonic=clock.ts)
    engine.cfg.per_action_cap_mc = cfg.per_action_cap_mc
    ids = iter(range(1, 10 ** 6))
    acts = Actions(engine, ledger, ids=lambda: f"act_{next(ids):05d}")
    svc = BetaService(cfg, acts, ledger, store=store, kill=kill, allow=Allowlist(store, cfg, sink), sink=sink, clock=clock)
    return SimpleNamespace(cfg=cfg, clock=clock, store=store, sink=sink, kill=kill, ledger=ledger, flags=flags,
                           mock=mock, engine=engine, acts=acts, svc=svc, tools=tools, tmp=Path(tmp), slept=slept)


def req(request, email=EMAIL, uid=None, xff="203.0.113.7", verified=True):
    return {"uid": uid if uid is not None else "u_" + email.split("@")[0], "email": email, "email_verified": verified,
            "xff": xff, "request": request}


def build_req(**over):
    args = {"chips": CHIPS, "materials": MATERIALS, "consent": True, "accepted": True}
    args.update(over)
    return {"action": "build", "args": args}


def edit_req(text="Add a card about consideration.", timeline_id="t1"):
    return {"action": "edit", "args": {"timeline_id": timeline_id, "text": text}}


def long_text(tokens=15000):
    """A reply whose metered output is close to (but under) the build's max_tokens: a realistic big turn."""
    s = ""
    while M.approx_tokens(s) < tokens:
        s += "contract law " * 200
    return s


def endless(tokens=15000):
    """Every turn calls a tool and talks a lot, forever: the runaway loop G4 and G7 need."""
    return M.Scenario("endless", [M.Step(M.Reply([M.text(long_text(tokens)),
                                                  M.tool_use("create_project", {"name": "Loop"})]))],
                      repeat_last=True)

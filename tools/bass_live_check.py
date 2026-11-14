#!/usr/bin/env python3
"""The LOCAL live check for Bass: run from the Home Desktop, with the Keychain key and NO proxy. PREPARED AND TESTED ONLY AGAINST THE MOCK;
never run live until Luke says "go for the first live call" and the beta guards pass.

    python3 tools/bass_live_check.py --dry-run                                  # the whole script against the mock: how it is tested
    ALTO_STORE=local ALTO_LIVE_ANTHROPIC=1 python3 tools/bass_live_check.py     # LIVE: refuses unless BOTH gates are open (below)

Any ALTO_STORE but local is refused (exit 2); a live run must be given ALTO_STORE=local; a --dry-run uses its own temp store under a
private temp HOME (alto/bass/isolate.py).

Live mode refuses to start (exit 2, nothing constructed, zero requests) unless
    1. ~/.config/alto/bass/LIVE_GO exists (alto.bass.client.go_flag_path), and
    2. ALTO_LIVE_ANTHROPIC=1 is set for this run only.
The key comes from IT's Keychain item through alto.bass.studio_key (which refuses without gate 2). It is never printed or written.

Steps, in order (each recorded; the run STOPS on the first error, 401 or low balance, with no retry):
    1  count_tokens smoke (free): confirms the key authenticates.
    2  one Haiku edit (well under 1 credit).
    3  5 to 10 measured builds from fixed sample notes of different sizes, through the same engine, ledger and meter Bass uses.
    4  summary: median/p90 actual credits, estimate vs actual, a re-fit of the estimate by size, and a suggested price per build.
Money (review finding M3): every hold is taken from the ONE local reserve file (alto/bass/local_reserve.py: $10 per credit period,
shared with tools/bass_local_server.py, kept across runs). A run can never spend more than what is LEFT of that reserve for the period,
whatever --cap-credits says; when the next call cannot fit, the run ends. A live run always uses the fixed file (--reserve-file is refused
for it); a dry run books its mock money into a throw-away file. `--open-period` opens the current credit period in the fixed file (a human
runs it after Luke confirms the credit refreshed) and makes no call.
Output: <out>/measurements.json and measurements.csv (measurements.dry-run.* for a dry run). Metadata only: sizes, tokens, credits,
times, status codes. No notes, no model text.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.bass import client as C                      # noqa: E402
from alto.bass import config as P                      # noqa: E402
from alto.bass import engine as E                      # noqa: E402
from alto.bass import meter                            # noqa: E402
from alto.bass import mock_anthropic as M              # noqa: E402
from alto.bass.actions import Actions                  # noqa: E402
from alto.bass.errors import Flags                     # noqa: E402
from alto.bass.ledger import Ledger, MemoryStore       # noqa: E402
from alto.bass.local_reserve import LocalReserve, ReservedLedger, RESERVE_FILE   # noqa: E402
from alto.bass.tools import ToolBox                    # noqa: E402

MC = P.MC
UID = "live-check"
DEFAULT_OUT = Path.home() / "Desktop" / "Terrarium" / "Alto" / "ORG" / "bass-live-check"
DEFAULT_CAP_CREDITS = 1000                              # $10: the period reserve Luke set aside for this
SIZES = (800, 2500, 6000, 12000, 20000, 1500, 9000, 30000, 4000, 15000)     # characters of notes per build, cycled
CHIPS = {"title": "Live check", "acts": [{"label": "Formation"}, {"label": "Defences"}, {"label": "Remedies"}],
         "entities": [{"id": "offer", "name": "Offer"}, {"id": "consideration", "name": "Consideration"}],
         "fields": ["Case", "Rule"], "card_estimate": 6}
SENTENCES = ("An offer is a manifestation of willingness to enter a bargain. Acceptance must mirror the offer under the common law. "
             "Consideration is a bargained-for exchange of legal value. Promissory estoppel protects reasonable detrimental reliance. "
             "The statute of frauds requires a writing for certain classes of contract. Expectation damages put the plaintiff where "
             "performance would have. Reliance damages restore what was spent. Restitution prevents unjust enrichment. ")


def sample_notes(chars: int, i: int) -> list:
    """Fixed, deterministic notes of about `chars` characters (the same text every run, so runs compare)."""
    body = (SENTENCES * (chars // len(SENTENCES) + 1))[:chars]
    return [{"name": f"Contracts notes {i + 1}.txt", "kind": "notes", "text": body}]


def pct(values: list, q: float) -> float:
    s = sorted(values)
    if not s:
        return 0.0
    k = (len(s) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def fit_line(xs: list, ys: list) -> tuple:
    """Least squares y = a + b x. -> (a, b). Needs 2 distinct x; otherwise (mean y, 0)."""
    n = len(xs)
    if n < 2 or len(set(xs)) < 2:
        return (statistics.mean(ys) if ys else 0.0, 0.0)
    mx, my = statistics.mean(xs), statistics.mean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return my - b * mx, b


def summarize(rows: list) -> dict:
    builds = [r for r in rows if r["step"] == "build" and r["status"] == "ok"]
    if not builds:
        return {"builds_ok": 0, "note": "no successful build: nothing to price"}
    actual = [r["credits"] for r in builds]
    ratios = [r["credits"] / r["estimate_credits"] for r in builds if r.get("estimate_credits")]
    a, b = fit_line([r["materials_chars"] for r in builds], actual)
    p90 = pct(actual, 0.9)
    return {"builds_ok": len(builds), "median_credits": round(statistics.median(actual), 2), "p90_credits": round(p90, 2),
            "max_credits": round(max(actual), 2), "median_actual_over_estimate": round(statistics.median(ratios), 3) if ratios else None,
            "estimate_refit": {"base_credits": round(a, 2), "per_1k_chars_credits": round(b * 1000, 3)},
            "suggested_price_per_build_credits": math.ceil(p90),
            "suggested_price_per_build_dollars": round(math.ceil(p90) / 100, 2),
            "how": "price = the 90th-percentile build cost, rounded up (1 credit = 1 cent of API cost, at cost); estimate_refit is the line "
                   "credits = base + per_1k_chars * (characters / 1000) fitted to these builds"}


class Recorder:
    def __init__(self, engine, monotonic):
        self.rows, self.last, self.mono = [], None, monotonic
        run = engine.run_action

        def spy(*a, **k):
            res = run(*a, **k)
            self.last = res
            return res
        engine.run_action = spy


def row_from(rec: Recorder, step: str, out: dict, t0: float, **extra) -> dict:
    res, u = rec.last, (rec.last.usage if rec.last else {})
    cr = out.get("credits") if isinstance(out.get("credits"), dict) else {}
    row = {"step": step, "status": out.get("status"), "code": out.get("code"), "credits": cr.get("spent", 0) or 0,
           "refunded": cr.get("refunded", 0) or 0, "input_tokens": u.get("input_tokens", 0), "output_tokens": u.get("output_tokens", 0),
           "cache_write_tokens": u.get("cache_creation_input_tokens", 0), "cache_read_tokens": u.get("cache_read_input_tokens", 0),
           "turns": res.turns if res else 0, "tool_calls": len(res.tool_calls) if res else 0,
           "wall_s": round(rec.mono() - t0, 3)}
    row.update(extra)
    return row


def write_out(out_dir: Path, meta: dict, rows: list, summary: dict, dry: bool) -> tuple:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "measurements.dry-run" if dry else "measurements"
    js, cs = out_dir / (stem + ".json"), out_dir / (stem + ".csv")
    js.write_text(json.dumps({"meta": meta, "rows": rows, "summary": summary}, indent=1, sort_keys=True), "utf-8")
    cols = ["step", "status", "code", "materials_chars", "estimate_credits", "credits", "refunded", "input_tokens", "output_tokens",
            "cache_write_tokens", "cache_read_tokens", "turns", "tool_calls", "wall_s"]
    with cs.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return js, cs


def run_check(client, out_dir: Path, *, builds: int, cap_credits: int, dry: bool, mock=None, scenario=None,
              monotonic=time.monotonic, now=lambda: dt.datetime.now(dt.timezone.utc), log=print, reserve: LocalReserve | None = None) -> dict:
    if reserve is None:
        raise ValueError("run_check needs the local reserve")
    if not dry:
        reserve.require_fixed()                               # a live run never books anywhere but the one fixed file
    left_mc = reserve.left_mc()
    cap_credits = min(int(cap_credits), left_mc // MC)        # never more than what is left of the period's reserve
    inner = Ledger(MemoryStore())
    if cap_credits <= 0:
        return finish(out_dir, [], now(), now, dry, 0, inner, "stopped: the local reserve for this credit period is used up or not open", reserve)
    inner.grant_allowance(UID, cap_credits)                   # the run's own hard cap: a hold that cannot fit ends the run
    ledger = ReservedLedger(inner, reserve, "live-check")     # every hold is also taken from the shared reserve, every cost booked into it
    tools = ToolBox(__import__("alto.store.local", fromlist=["LocalStore"]).LocalStore(Path(tempfile.mkdtemp(prefix="bass-live-check-"))))
    engine = E.Engine(client, ledger, tools, flags=Flags(), sleep=lambda s: None, monotonic=monotonic)
    acts = Actions(engine, ledger)
    rec = Recorder(engine, monotonic)
    rows, started = [], now()

    def stop_now(row) -> bool:
        return row["status"] not in ("ok", "off_topic")

    # 1: count_tokens, free: proves the key authenticates
    t0 = monotonic()
    try:
        n = client.messages.count_tokens(model=P.HAIKU, messages=[{"role": "user", "content": "ping"}]).input_tokens
        rows.append({"step": "count_tokens", "status": "ok", "code": None, "credits": 0, "input_tokens": n, "wall_s": round(monotonic() - t0, 3)})
    except Exception as e:                                    # 401 and friends: stop, no retry, no detail beyond the class and status
        rows.append({"step": "count_tokens", "status": "error", "code": type(e).__name__, "http_status": getattr(e, "status_code", None),
                     "credits": 0, "wall_s": round(monotonic() - t0, 3)})
        return finish(out_dir, rows, started, now, dry, cap_credits, ledger, "stopped at count_tokens", reserve)
    # 2: one Haiku edit
    t0 = monotonic()
    out = acts.edit(UID, "check-timeline", "Reply with the single word ready.", reset=True)
    rows.append(row_from(rec, "edit", out, t0))
    if stop_now(rows[-1]):
        return finish(out_dir, rows, started, now, dry, cap_credits, ledger, "stopped at the edit", reserve)
    # 3: the measured builds
    for i in range(builds):
        chars = SIZES[i % len(SIZES)]
        mats = sample_notes(chars, i)
        if mock is not None and scenario is not None:
            mock.use(scenario())                              # dry run: a fresh scripted build every time
        est = acts.estimate(UID, "build", mats)
        t0 = monotonic()
        out = acts.build(UID, CHIPS, mats, consent=True, accepted=True)
        rows.append(row_from(rec, "build", out, t0, materials_chars=chars, estimate_credits=est.get("estimate_credits")))
        log(f"build {i + 1}/{builds}: {rows[-1]['status']} {rows[-1]['credits']} credits (estimate {est.get('estimate_credits')})")
        if stop_now(rows[-1]):
            return finish(out_dir, rows, started, now, dry, cap_credits, ledger, f"stopped at build {i + 1}: {rows[-1]['code']}", reserve)
    return finish(out_dir, rows, started, now, dry, cap_credits, ledger, "completed", reserve)


def finish(out_dir, rows, started, now, dry, cap_credits, ledger, ended, reserve=None) -> dict:
    spent = sum(r.get("credits", 0) or 0 for r in rows)
    meta = {"mode": "dry-run (mock)" if dry else "live", "started": started.isoformat(), "ended": now().isoformat(), "result": ended,
            "cap_credits": cap_credits, "spent_credits": round(spent, 2), "balance_left_credits": round(ledger.balance_mc(UID) / MC, 2),
            "models": {"build": P.SONNET, "edit": P.HAIKU}, "prices_file": "alto/bass/prices.json"}
    if reserve is not None:
        meta["local_reserve"] = reserve.status()              # numbers only: the period, what is used and left, by source
    summary = summarize(rows)
    js, cs = write_out(out_dir, meta, rows, summary, dry)
    return {"meta": meta, "rows": rows, "summary": summary, "json": str(js), "csv": str(cs)}


def main(argv=None, *, env=None, mock=None, monotonic=time.monotonic) -> int:
    env = os.environ if env is None else env
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="run everything against the mock; no key, no flags needed")
    ap.add_argument("--builds", type=int, default=8, help="measured builds, 5 to 10 (default 8)")
    ap.add_argument("--cap-credits", type=int, default=DEFAULT_CAP_CREDITS, help="the run's own hard cap in credits (default 1000 = $10)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--reserve-file", type=Path, default=None, help="DRY RUN ONLY: where the mock money is booked (default: a throw-away file). A live run always uses the fixed reserve file")
    ap.add_argument("--open-period", action="store_true", help="open the current credit period in the fixed reserve file and exit (no call is made). Only after Luke confirms the credit refreshed")
    a = ap.parse_args(argv)
    if a.open_period:
        if a.dry_run or a.reserve_file is not None:
            print("refused: --open-period works on the fixed reserve file only.", file=sys.stderr)
            return 2
        print("opened", LocalReserve().open_period(), "in", RESERVE_FILE)
        return 0
    if a.reserve_file is not None and not a.dry_run:
        print(f"refused: a live run uses the one fixed reserve file ({RESERVE_FILE}); --reserve-file is for --dry-run only.", file=sys.stderr)
        return 2
    if not 5 <= a.builds <= 10:
        print("refused: --builds must be 5 to 10.", file=sys.stderr)
        return 2
    if a.cap_credits <= 0:
        print("refused: --cap-credits must be positive.", file=sys.stderr)
        return 2
    if a.dry_run:
        mock = mock or M.MockAnthropic()
        client = C.make_client("mock", mock=mock)
        brief = json.loads((ROOT / "samples" / "contracts_brief.json").read_text("utf-8"))
        reserve = LocalReserve(a.reserve_file or Path(tempfile.mkdtemp(prefix="bass-live-check-reserve-")) / "reserve.dry-run.json")
        res = run_check(client, a.out, builds=a.builds, cap_credits=a.cap_credits, dry=True, mock=mock, monotonic=monotonic, reserve=reserve,
                        scenario=lambda: M.build("Contracts", brief["brief"], brief["nodes"], brief["connections"]))
    else:
        if not C.live_enabled():
            print("refused: no go flag (" + str(C.go_flag_path()) + "). Live check starts only after Luke says go for the first live call.", file=sys.stderr)
            return 2
        if env.get("ALTO_LIVE_ANTHROPIC") != "1":
            print("refused: ALTO_LIVE_ANTHROPIC=1 is not set for this run.", file=sys.stderr)
            return 2
        client = C.make_client("live")                         # Keychain key through studio_key; base_url pinned; max_retries 0
        res = run_check(client, a.out, builds=a.builds, cap_credits=a.cap_credits, dry=False, monotonic=monotonic, reserve=LocalReserve())
    print(json.dumps(res["meta"], indent=1))
    print(json.dumps(res["summary"], indent=1))
    print("wrote", res["json"], "and", res["csv"])
    return 0 if res["meta"]["result"] == "completed" else 1


if __name__ == "__main__":
    # never the default store; a --dry-run runs on its own temp store under a private temp HOME / XDG_CONFIG_HOME; a live run needs
    # ALTO_STORE=local given explicitly (alto/bass/isolate.py)
    from alto.bass import isolate
    isolate.start("bass_live_check", mock="--dry-run" in sys.argv[1:])
    sys.exit(main())

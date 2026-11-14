"""Bass BETA config: ONE place for the beta's numbers (Luke's decisions of 2026-10-29, ORG/notes-bass-beta.md UPDATE 1-3).
Every number is a config value, overridable; nothing in the guard logic hard-codes one.

Luke's credit is $100 a month that refreshes on the 17th, with no rollover (1 credit = 1 cent), so the totals are PER CREDIT PERIOD:

    server ceiling   7,000 credits ($70) per period     INTERIM (Luke, 11 Nov 2026, review finding M4): the planned ceiling is 9,000
                                                        ($90; the other $10 is the local reserve). It stays at 7,000 until the M1
                                                        (failed calls are booked) and M2 (the reaper books abandoned calls) fixes have
                                                        been TESTED LIVE, so that anything the books still miss lands inside the $100.
                                                        Raise it by changing server_ceiling_credits (PLANNED_SERVER_CEILING_CREDITS).
    per tester       floor(ceiling / N) per period      (at 7,000: N = 10 -> 700; at 9,000: N = 15 -> 600, N = 10 -> 900; N up to 15)
    per tester/day     300 ($3)         all testers/day  1,500 ($15)
    per action         300 ($3)         estimate prompt over 20 credits
    ALERTS (Luke's numbers, decision G1 of 11 Nov 2026; an alert tells the owner, it never stops Bass):
                     400 credits ($4) of spend in any 10 minutes; 80% of the day's 1,500 before 18:00
    TRIP (the kill switch, hand reset) stays where security fix B1 put it: 10-minute spend ABOVE anything the caps allow
                     (spike_trip_mc: $33 at N = 10). The day's own limit refuses everything past 100% and resets at midnight.
    period           starts on the 17th, local midnight in `tz`; a NEW period opens only when
                     Firestore bass_beta/periods/<id>.confirmed is true (IT sets it after Luke confirms the refresh)

Money is milli-credits (config.MC = 1000 per credit) below, the ledger's own integer unit.
"""
from __future__ import annotations

import datetime as dt
import re
import zoneinfo
from dataclasses import dataclass, field, replace
from fractions import Fraction as F
from pathlib import Path

from . import config as C

MC = C.MC
MAX_TESTERS = 15
PLANNED_SERVER_CEILING_CREDITS = 9000                                    # what the ceiling goes back to after M1 and M2 are tested live
INTERIM_SERVER_CEILING_CREDITS = 7000
TERMS_FALLBACK = "0.1"
_TERMS_OK = re.compile(r"^[A-Za-z0-9._-]{1,32}$")                       # the version is part of a document id: no slash, no spaces


def current_terms_version() -> str:
    """The Beta Terms version the proxy requires: the contents of alto/legal/VERSION when that file exists (it ships in the bundle
    with the rest of the alto package), else "0.1". A version that is not a plain token stays as read so `problems()` stops the deploy
    and the gate refuses every uid (fail closed)."""
    try:
        v = (Path(__file__).resolve().parent.parent / "legal" / "VERSION").read_text("utf-8").strip()
        return v or TERMS_FALLBACK
    except OSError:
        return TERMS_FALLBACK


def _norm(email: str) -> str:
    return str(email or "").strip().lower()


@dataclass(frozen=True)
class BetaConfig:
    testers: int = 10                           # N
    allowlist: frozenset = field(default_factory=frozenset)     # verified Google emails; the store doc overrides it
    pool_credits: int = 10000                   # Luke's credit per period; the Console limit is set to it by hand
    server_ceiling_credits: int = INTERIM_SERVER_CEILING_CREDITS     # per period, all testers together. INTERIM $70 (M4): see the docstring
    tester_daily_credits: int = 300
    global_daily_credits: int = 1500
    per_action_cap_credits: int = C.PER_ACTION_CAP_CREDITS
    estimate_prompt_credits: int = C.ESTIMATE_THRESHOLD_CREDITS
    spike_credits: int = 400                    # the floor of the spike TRIP (spike_trip_mc); the trip itself sits above the caps
    spike_alert_credits: int = 400              # ALERT (no trip) at this much spend in any spike_window_s: Luke's $4 in 10 minutes
    spike_window_s: int = 600
    start_day: int = 17                         # the credit refreshes on this day of the month
    tz: str = "America/New_York"                # the period and day boundaries, and the "before 18:00" clock
    trip_fraction: F = F(8, 10)                 # ALERT (no trip): the day's counter over this fraction of the daily limit before trip_before_hour
    trip_before_hour: int = 18
    alert_levels: tuple = (50, 80, 100)         # percent of the daily limit (and of the period ceiling)
    account_per_min: int = 12
    docs_per_min: int = 60                      # Bass Documents library calls (list, rename, move, switches); adds also count in account_per_min
    ip_per_min: int = 30
    inflight_build: int = 1
    inflight_chat: int = 2
    refunds_per_day: int = 5
    reservation_ttl_s: int = 900                # a hold older than this with no settle is a crashed function's
    miss_burst: int = 20                        # allowlist misses from one IP in miss_window_s raise an alert
    miss_window_s: int = 600
    live_check_cap_credits: int = 1000          # the local live check's own hard cap ($10)
    trusted_hops: int = 1                       # X-Forwarded-For entries Alto's own infrastructure appends: 1 on the direct run.app/
                                                # cloudfunctions URL (the last entry is Google's); 2+ behind a Hosting rewrite or a load balancer
    bad_input_accounts: int = 3                 # this many DISTINCT accounts hitting bad_input inside bad_input_window_s trips the switch:
    bad_input_window_s: int = 600               # one tester's bad input never does, a request-format bug of ours would
    # Uploads (PDF / .docx -> text on the proxy, alto/bass/extract.py). Raw bytes are capped before anything is parsed.
    upload_max_file_bytes: int = 5_000_000      # one file
    upload_max_total_bytes: int = 6_000_000     # all files of one request
    upload_max_files: int = 5                   # files with bytes in one request
    max_request_bytes: int = 9_000_000          # the whole JSON body (base64 is 4/3 of the raw bytes); a 10 MB function limit sits above it
    pdf_max_pages: int = 200
    extract_max_chars: int = 300_000            # per file, after extraction; more is refused, not cut (the actions' own 600,000 total still applies)
    extract_min_chars: int = 20                 # fewer non-space characters = "no selectable text" (a scan)
    extract_timeout_s: float = 20.0             # ONE deadline for all the files of a request; the worker is killed at it
    extract_mem_bytes: int = 1_500_000_000      # address-space limit for the worker where the OS enforces it (Linux does)
    docx_max_members: int = 200                 # zip entries (a real .docx has 10-40)
    docx_max_uncompressed_bytes: int = 30_000_000
    docx_max_ratio: int = 100                   # declared uncompressed / compressed over this = a bomb
    docx_xml_max_bytes: int = 8_000_000         # hard read limit for word/document.xml
    docx_max_depth: int = 100
    docx_max_elements: int = 400_000
    terms_version: str = field(default_factory=current_terms_version)   # the Beta Terms acceptance Bass requires (terms_acceptance/<uid>_<version>)
    settle_attempts: int = 4                    # a failed settle is retried with backoff; then the books are not trusted: kill switch
    function_timeout_s: int = 300               # the platform's hard cut on one request (deploy.py --timeout reads this number)
    action_wall_s: int = 240                    # one action's wall-clock bound, BELOW the function timeout (finding M2): it stops itself,
                                                # and books what it started, before the platform cuts it mid-stream
    # Pages allowed to call the proxy (CORS). The shared tester site is alto-timelines (IT, ORG/it/beta-address.md);
    # luke-alto stays for Luke's own testing. Edit here, never in code.
    allowed_origins: tuple = ("https://alto-timelines.web.app", "https://luke-alto.web.app", "https://luke-alto.firebaseapp.com")

    def __post_init__(self):
        if int(self.testers) <= 0 or int(self.server_ceiling_credits) <= 0:
            raise ValueError("beta config: testers and the ceiling must be positive")
        if not 1 <= int(self.start_day) <= 28:
            raise ValueError("beta config: start_day must be 1..28 so every month has it")
        zoneinfo.ZoneInfo(self.tz)
        object.__setattr__(self, "allowlist", frozenset(_norm(e) for e in self.allowlist if _norm(e)))

    # -- derived (credits) --------------------------------------------------------------------------------------
    @property
    def tester_period_credits(self) -> int:
        return self.server_ceiling_credits // self.testers                       # floor

    allowance_credits = tester_period_credits                                    # the name the older tests used

    # -- derived (milli-credits, what the ledger uses) -----------------------------------------------------------
    @property
    def allowance_mc(self) -> int:
        return self.tester_period_credits * MC

    @property
    def ceiling_mc(self) -> int:
        return self.server_ceiling_credits * MC

    @property
    def tester_daily_mc(self) -> int:
        return self.tester_daily_credits * MC

    @property
    def daily_ceiling_mc(self) -> int:
        return self.global_daily_credits * MC

    @property
    def spike_mc(self) -> int:
        return self.spike_credits * MC

    @property
    def spike_trip_mc(self) -> int:
        """The 10-minute spend that trips the kill switch (security finding B1): never below what the caps ALLOW in 10 minutes, so normal use
        (two testers at once, one tester across midnight, everyone at once) can never switch Bass off for everyone. That most is every account's
        day on both sides of one midnight, bounded by two whole global days, plus one turn that lands past its hold. Above it, the books let
        through spend the caps should have refused: something is broken, so stop for everyone."""
        legit = min(int(self.testers) * 2 * self.tester_daily_mc, 2 * self.daily_ceiling_mc) + self.per_action_cap_mc
        return max(self.spike_mc, legit + MC)

    @property
    def per_action_cap_mc(self) -> int:
        return self.per_action_cap_credits * MC

    @property
    def zone(self):
        return zoneinfo.ZoneInfo(self.tz)

    # -- the credit period ---------------------------------------------------------------------------------------
    def period_id(self, now: dt.datetime) -> str:
        """The id (the start date, local) of the credit period `now` falls in: the start_day on or before it."""
        d = now.astimezone(self.zone).date()
        y, m = (d.year, d.month) if d.day >= self.start_day else ((d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12))
        return f"{y:04d}-{m:02d}-{self.start_day:02d}"

    def day_id(self, now: dt.datetime) -> str:
        return now.astimezone(self.zone).strftime("%Y-%m-%d")

    def problems(self) -> list:
        """Things worth stopping a deploy for (the handler refuses to start with any)."""
        out = []
        if self.testers > MAX_TESTERS:
            out.append(f"{self.testers} testers is over the {MAX_TESTERS} the ceiling was planned for")
        if len(self.allowlist) > self.testers:
            out.append(f"{len(self.allowlist)} emails on the list but only {self.testers} testers were budgeted")
        if self.tester_period_credits <= 0:
            out.append("the per-tester allowance rounds to zero")
        if self.tester_period_credits * self.testers > self.server_ceiling_credits:
            out.append("the testers' allowances add up to more than the server ceiling")
        if self.server_ceiling_credits > self.pool_credits:
            out.append("the server ceiling is above the pool")
        if not _TERMS_OK.match(str(self.terms_version)):
            out.append(f"the terms version {self.terms_version!r} is not a plain token (letters, digits, . _ -)")
        if self.max_request_bytes < self.upload_max_total_bytes * 4 // 3 + 200_000:
            out.append("max_request_bytes is too small for the upload cap (base64 is 4/3 of the raw bytes)")
        if self.upload_max_file_bytes > self.upload_max_total_bytes:
            out.append("one file may not be bigger than the whole upload total")
        if self.trusted_hops < 1:
            out.append("trusted_hops must be at least 1")
        if self.global_daily_credits < self.per_action_cap_credits:
            out.append("the daily limit is below one action's cap")
        if self.action_wall_s <= 0 or self.action_wall_s > self.function_timeout_s - 30:
            out.append("action_wall_s must leave at least 30 seconds before function_timeout_s")
        return out

    def with_(self, **kw) -> "BetaConfig":
        return replace(self, **kw)

    def summary(self) -> dict:
        """For the runbook and the alerts: every number, in credits."""
        return {"testers": self.testers, "pool_credits": self.pool_credits,
                "server_ceiling_credits": self.server_ceiling_credits,
                "tester_period_credits": self.tester_period_credits, "tester_daily_credits": self.tester_daily_credits,
                "global_daily_credits": self.global_daily_credits, "per_action_cap_credits": self.per_action_cap_credits,
                "estimate_prompt_credits": self.estimate_prompt_credits, "spike_credits": self.spike_credits,
                "spike_alert_credits": self.spike_alert_credits, "spike_trip_credits": self.spike_trip_mc // MC,
                "action_wall_s": self.action_wall_s, "function_timeout_s": self.function_timeout_s,
                "start_day": self.start_day, "tz": self.tz}

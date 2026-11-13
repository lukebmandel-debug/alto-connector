"""Typed Bass errors, and what each failure does (user message, refund, retry, kill switch).

`classify(exc)` turns whatever the Anthropic SDK raised into a BassError carrying its policy, so the
engine has ONE place that knows what a 429 or a 401 means. Nobody is ever blamed for an Alto-side problem."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Policy:
    code: str
    user_message: str
    retry: bool = False          # worth retrying the same call (bounded)
    refund: bool = True          # the user is never charged for a failed turn
    kill_switch: bool = False    # Alto-side fault: pause Bass for everyone
    pause_bass: bool = False   # Anthropic-side balance empty: pause Bass, alert
    alert: bool = False          # tell Alto's owner


POLICIES = {p.code: p for p in (
    Policy("rate_limited", "Bass is busy right now. Nothing was charged. Please try again in a minute.",
           retry=True),
    Policy("overloaded", "Bass is busy right now. Nothing was charged. Please try again in a minute.",
           retry=True),
    Policy("timeout", "That took too long, so it was stopped. Nothing was charged. Please try again.",
           retry=True),
    Policy("connection", "Bass could not be reached. Nothing was charged. Please try again.",
           retry=True),
    Policy("upstream", "Something went wrong on our side. Nothing was charged. Please try again.",
           retry=True, alert=True),
    Policy("auth", "Bass is down for maintenance. Nothing was charged. We are fixing it.",
           kill_switch=True, alert=True),
    Policy("balance_low", "Bass is down for maintenance. Nothing was charged. We are fixing it.",
           pause_bass=True, alert=True),
    Policy("bad_request", "Bass hit a problem on our side. Nothing was charged. We have been told.",
           alert=True),
    Policy("history_mismatch", "Bass lost its place in this conversation. Nothing was charged. Please try again.",
           alert=True),          # the API's history-editing check on a thinking block: this conversation only, never the kill switch
    Policy("time_limit", "This step ran out of time and was stopped. Your work so far is saved.", refund=False),
    Policy("refused", "Bass could not help with that request. Nothing was charged."),
    Policy("max_tokens", "That reply was cut off because it was too long. Try a smaller step."),
    Policy("busy", "You have a lot going on at once. Give it a moment and try again.", refund=True),
    Policy("bass_paused", "Bass is taking a short break. Nothing was charged. Please try again later.",
           refund=True),
    Policy("bass_off", "Bass is not switched on for this account yet."),
    Policy("needs_plan", "That is in a plan you do not have yet. Nothing was charged."),
    Policy("conversion_failed", "Bass could not turn that file into the new format using only its own cards, so nothing was saved. Nothing was charged."),
    Policy("plan_failed", "Bass could not make a plan using only your timeline and what you told it, so nothing was saved. Nothing was charged."),
    Policy("terms_required", "Please accept the Beta Terms to use Bass. Sign in again to see the box."),
    Policy("research_off", "Conversation sharing is not available right now. Bass works the same without it."),
    Policy("research_version", "Please read the current sharing details and choose again. Nothing was saved."),
    Policy("research_error", "That did not go through, so nothing changed. Please try again."),
    Policy("upload_too_big", "That file is too large for Bass. Try a smaller file, or paste the text."),
    Policy("upload_too_many_pages", "This PDF has too many pages for Bass. Upload a shorter part of it, or paste the text."),
    Policy("upload_encrypted", "This PDF is password-protected. Upload an unlocked copy, or paste the text."),
    Policy("upload_no_text", "This file has no selectable text. Paste the text or upload a text version."),
    Policy("upload_scanned", "This looks like a scanned PDF (pictures of pages), so there is no text for Bass to read. Upload a copy with selectable text, or paste the text."),
    Policy("upload_too_long", "That file has more text than Bass can read at once. Upload a shorter part of it."),
    Policy("upload_unsupported", "Bass can read PDF, Word (.docx) and plain-text files. Paste the text or upload one of those."),
    Policy("upload_unreadable", "Bass could not read that file. Paste the text or upload a text version."),
    Policy("bass_disabled", "Bass is switched off for now. Viewing and the rest of Alto still work."),
    Policy("beta_tester_daily", "You have reached your Bass limit for today. Nothing was charged. Please try again tomorrow."),
    Policy("workspace_limit", "Your Bass beta credits are used up. Thank you for testing Bass!", pause_bass=True, alert=True),
    Policy("beta_credits_used", "Your Bass beta credits are used up. Thank you for testing Bass!"),
    Policy("beta_daily_full", "Today's beta limit has been reached. Nothing was charged. Please try again tomorrow.",
           refund=True),
    Policy("stopped", "Stopped. Your work so far is saved.", refund=False),
    Policy("consent_required", "Please confirm you want Bass to build only from your own materials."),
    Policy("bad_input", "Bass could not read that request. Nothing was charged."),
    Policy("too_large", "Those materials are too large for one step. Try fewer files. Nothing was charged."),
    Policy("no_credits", "You are out of credits. Your work so far is saved."),
    Policy("action_cap", "This step reached its credit limit and was stopped. Your work so far is saved."),
    Policy("daily_cap", "You reached today's credit limit. Your work so far is saved."),
    Policy("monthly_cap", "You reached this month's credit limit. Your work so far is saved."),
)}


class BassError(Exception):
    """Base. `.policy` says what the engine must do."""
    code = "upstream"

    def __init__(self, message: str = "", *, code: str | None = None, detail: dict | None = None):
        self.code = code or type(self).code
        self.policy = POLICIES[self.code]
        self.detail = detail or {}
        super().__init__(message or self.policy.user_message)

    @property
    def user_message(self) -> str:
        return self.policy.user_message


class NotConfigured(BassError):
    """No API key store has been wired (IT names it). Never carries a key."""
    code = "bass_paused"


class LiveNotEnabled(BassError):
    """make_client("live") without Luke's go flag."""
    code = "bass_paused"


class InsufficientCredits(BassError):
    code = "no_credits"


class CapReached(BassError):
    """code is action_cap / daily_cap / monthly_cap."""
    code = "action_cap"


class UpstreamError(BassError):
    """An Anthropic failure that exhausted its retries; code says which."""


def _body_type(exc) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict):
            return str(err.get("type", ""))
    return ""


def _body_message(exc) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict):
            return str(err.get("message", ""))
    return str(getattr(exc, "message", "") or exc)


def _error_code(exc) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict):
            det = err.get("details")
            # the documented 429 carries it in error.details.error_code; also accept it flat in error / at the top
            return str(err.get("error_code") or (det.get("error_code") if isinstance(det, dict) else "") or body.get("error_code") or "")
    return ""


INPUT_PROBLEMS = ("prompt is too long", "too many pages", "pages", "image", "document", "pdf", "too large", "too many tokens",
                  "maximum number of")


def is_history_mismatch(msg: str) -> bool:
    """The history-editing check's 400 (claude-api reference: "Invalid `signature` in `thinking` block. The block is bound to a different
    conversation..."): one conversation's kept history no longer matches a thinking block in it. Not a fault that should stop everyone."""
    m = msg.lower()
    return "thinking" in m and ("bound to a different conversation" in m or "invalid `signature`" in m or "invalid signature" in m)


def _is_input_problem(msg: str) -> bool:
    """A 400 caused by what one tester sent (their notes), not by anything of Alto's: it must never switch Bass off for everyone."""
    m = msg.lower()
    return any(k in m for k in INPUT_PROBLEMS)


def retry_after_seconds(exc) -> float | None:
    resp = getattr(exc, "response", None)
    try:
        v = resp.headers.get("retry-after") if resp is not None else None
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def classify(exc: BaseException) -> UpstreamError:
    """Map an SDK exception to an UpstreamError carrying the right policy. Unknown exceptions are treated as an
    Alto-side upstream fault (refund, alert), never as the user's."""
    import anthropic as A
    import httpx2
    if isinstance(exc, BassError):
        return exc  # type: ignore[return-value]
    btype, status = _body_type(exc), getattr(exc, "status_code", None)
    msg = _body_message(exc)
    detail = {"status": status, "type": btype, "message": msg}
    if isinstance(exc, (A.APITimeoutError, httpx2.TimeoutException)):
        code = "timeout"
    elif isinstance(exc, (A.APIConnectionError, httpx2.TransportError, httpx2.StreamError)):
        code = "connection"      # includes a stream that drops half-way: the SDK lets httpx errors through there
    elif _error_code(exc) == "enforced_spend_limit_reached" or "enforced_spend_limit_reached" in msg:
        code = "workspace_limit"            # the organisation's spend cap arrives as a 429, with no retry-after: never retry it
    elif status == 429 or btype == "rate_limit_error":
        code = "rate_limited"
        detail["retry_after"] = retry_after_seconds(exc)
    elif status == 529 or btype == "overloaded_error":
        code = "overloaded"
    elif status == 401 or btype == "authentication_error":
        code = "auth"
    elif "api usage limits" in msg.lower() and "specified" in msg.lower():
        code = "workspace_limit"            # the Console's limit, workspace or organisation wording: like an empty balance, no retry
    elif status == 402 or btype == "billing_error" or "credit balance is too low" in msg.lower():
        code = "balance_low"
    elif status == 403 or btype == "permission_error":
        code = "auth"
    elif status is not None and status >= 500:
        code = "upstream"
    elif status == 400 and is_history_mismatch(msg):
        code = "history_mismatch"           # checked before the input words: its text also says "block"/"document"-like things
    elif status == 400 and _is_input_problem(msg):
        code = "bad_input"                  # one tester's input (too long, too many pages, a bad image): theirs alone, no trip
    elif status is not None and 400 <= status < 500:
        code = "bad_request"
    elif btype == "api_error":
        code = "upstream"
    else:
        code = "upstream"
    return UpstreamError(code=code, detail=detail)


@dataclass
class Flags:
    """Process-wide switches the engine flips and the host reads. `alerts` is what would be sent to the owner."""
    bass_enabled: bool = True
    reason: str = ""
    alerts: list = field(default_factory=list)

    def trip(self, policy: Policy, detail: dict | None = None) -> None:
        if policy.kill_switch or policy.pause_bass:
            self.bass_enabled = False
            self.reason = policy.code
        if policy.alert:
            self.alerts.append({"code": policy.code, "detail": detail or {}})

    def reset(self) -> None:
        self.bass_enabled, self.reason = True, ""

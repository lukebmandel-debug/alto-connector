"""usage -> credits. Integer milli-credits everywhere (1 credit = 1000), exact fraction math, rounded UP once per
call. Students never see tokens: the only words that leave this module are "about N credits"."""
from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from . import config as P

import json
from dataclasses import dataclass as _dc
from pathlib import Path

PRICES_FILE = Path(__file__).with_name("prices.json")


@_dc(frozen=True)
class Rate:
    inp: Fraction
    out: Fraction
    cache_read: Fraction
    cache_write: Fraction


@_dc(frozen=True)
class ModelPrice:
    model: str
    base: Rate
    long_threshold: int | None = None   # prompts above this many tokens use `long`
    long: Rate | None = None


def _f(x) -> Fraction:
    return Fraction(str(x))


def load_prices(path=PRICES_FILE):
    """prices.json (USD per million tokens) -> ({model: ModelPrice}, credits_per_usd). A null price is refused loudly:
    an unpriced model must never be metered as free. The long-prompt tier gives input/output only; its cache rates
    are DERIVED by scaling the base cache rates by the same input ratio (flagged in the report; confirm at the key step)."""
    raw = json.loads(Path(path).read_text("utf-8"))
    out = {}
    for name, p in raw["models"].items():
        if any(p.get(k) is None for k in ("input", "output", "cache_write", "cache_read")):
            raise ValueError(f"prices.json: {name} has a null price")
        base = Rate(_f(p["input"]), _f(p["output"]), _f(p["cache_read"]), _f(p["cache_write"]))
        lp = p.get("long_prompt")
        long = thr = None
        if lp:
            k = _f(lp["input"]) / base.inp
            long = Rate(_f(lp["input"]), _f(lp["output"]), base.cache_read * k, base.cache_write * k)
            thr = int(lp["over_input_tokens"])
        out[name] = ModelPrice(name, base, thr, long)
    return out, int(raw["credits_per_usd"])


PRICES, CREDITS_PER_USD = load_prices()


def price_for(model: str) -> ModelPrice:
    try:
        return PRICES[model]
    except KeyError:
        raise KeyError(f"no price for model {model!r}: add it to alto/bass/prices.json (ORG/it/studio-key/prices.json)")


def usage_dict(usage) -> dict:
    """An SDK Usage object or a dict -> the four counters (missing/None -> 0)."""
    def g(k):
        v = usage.get(k) if isinstance(usage, dict) else getattr(usage, k, None)
        return int(v or 0)
    return {"input_tokens": g("input_tokens"), "output_tokens": g("output_tokens"),
            "cache_creation_input_tokens": g("cache_creation_input_tokens"),
            "cache_read_input_tokens": g("cache_read_input_tokens")}


def prompt_tokens(u: dict) -> int:
    return u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"]


def rate_for(model: str, prompt_tok: int) -> Rate:
    mp = price_for(model)
    if mp.long is not None and mp.long_threshold is not None and prompt_tok > mp.long_threshold:
        return mp.long          # the long-prompt tier prices the WHOLE request, not just the excess
    return mp.base


def _mc(dollars: Fraction) -> int:
    return math.ceil(dollars * CREDITS_PER_USD * P.MC * P.CREDIT_MARKUP)


def dollars_for_usage(model: str, usage) -> Fraction:
    u = usage_dict(usage)
    r = rate_for(model, prompt_tokens(u))
    per_mtok = (u["input_tokens"] * r.inp + u["output_tokens"] * r.out
                + u["cache_read_input_tokens"] * r.cache_read + u["cache_creation_input_tokens"] * r.cache_write)
    return per_mtok / 1_000_000


def credits_for_usage(model: str, usage) -> int:
    """Milli-credits for one response's usage."""
    return _mc(dollars_for_usage(model, usage))


def estimate_turn(model: str, input_tokens: int, max_output_tokens: int) -> int:
    """Worst case for ONE call: the counted input plus the whole max_tokens budget at the output price."""
    r = rate_for(model, input_tokens)
    return _mc((input_tokens * r.inp + max_output_tokens * r.out) / 1_000_000)


def worst_turn(model: str, input_tokens: int, max_output_tokens: int) -> int:
    """What a HOLD reserves for one call (review finding M6): every input token at the dearer of the plain and the cache-write rate (the
    cached prefix is billed at 1.25x when it is written), plus the whole max_tokens budget at the output price. estimate_turn stays the
    number shown to the student; this one is only ever at or above it."""
    r = rate_for(model, input_tokens)
    return _mc((input_tokens * max(r.inp, r.cache_write) + max_output_tokens * r.out) / 1_000_000)


@dataclass(frozen=True)
class Estimate:
    mc: int
    turns: int
    show_prompt: bool

    @property
    def message(self) -> str:
        return f"This will use {credits_text(self.mc)}."


def estimate_action(model: str, first_input_tokens: int, output_per_turn: int, turns: int = 1,
                    growth_per_turn: int | None = None) -> Estimate:
    """A planned multi-turn action: every turn re-sends the history, so input grows by what each turn added
    (its output plus the tool results; `growth_per_turn` defaults to 2x the output)."""
    grow = 2 * output_per_turn if growth_per_turn is None else growth_per_turn
    total = 0
    for t in range(max(1, turns)):
        total += estimate_turn(model, first_input_tokens + t * grow, output_per_turn)
    return Estimate(total, max(1, turns), total > P.ESTIMATE_THRESHOLD_CREDITS * P.MC)


def credits_text(mc: int) -> str:
    if mc < P.MC:
        return "less than 1 credit"
    n = math.ceil(mc / P.MC)
    return f"about {n} credit" + ("" if n == 1 else "s")

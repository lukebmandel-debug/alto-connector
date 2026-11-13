"""Bass limits and ids. NO PRICES live here: the one price table is prices.json (a copy of ORG/it/studio-key/prices.json,
IT's pool ledger reads the same table; meter.py loads it)."""
from __future__ import annotations

from fractions import Fraction as F

HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"
TEST_MODEL = HAIKU       # every test uses Haiku ids
BUILD_MODEL = SONNET     # builds are priced against Sonnet

# 1 credit = 1 cent of real cost (credits_per_usd is in prices.json). Milli-credits are the integer unit everywhere
# (1 credit = 1000).
MC = 1000
CREDIT_MARKUP = F(1)     # credits charged = real cost x this; 1 = at cost (the memo's v1)

PER_ACTION_CAP_CREDITS = 300
ESTIMATE_THRESHOLD_CREDITS = 20
DAILY_CEILING_CREDITS = 1500
MONTHLY_CEILING_CREDITS = 10000
ACTIONS_PER_MINUTE = 12              # per account
PURCHASE_LIFETIME_DAYS = 365
MAX_RETRIES = 3                      # bounded Alto-side retries for 429/529/timeouts/5xx
RETRY_MAX_WAIT_S = 30.0
CHAT_MAX_TOKENS = 800
BUILD_MAX_TOKENS = 16000
GATE_MAX_TOKENS = 16                 # the gate's one word; the gate ALWAYS runs with thinking off (thinking counts inside max_tokens)
# Thinking (claude-api reference, 2026-11-03): both models think by default and thinking counts inside max_tokens.
#   Haiku 5.5: thinking {type: "disabled"} is accepted at effort low / medium / high.
#   Sonnet 5.5: {type: "disabled"} is a 400; its lowest setting is {type: "between_tools"} (effort high or below, no other field).
THINKING_OFF = {HAIKU: {"type": "disabled"}, SONNET: {"type": "between_tools"}}
THINKING_OFF_EFFORTS = ("low", "medium", "high")
THINKING_MIN_MAX_TOKENS = 4000       # a kind that leaves thinking ON never gets a smaller max_tokens than this
ACTION_WALL_S = None                 # an action's wall-clock bound; None = no bound (the hosted proxy sets it below the function timeout)
TURN_MARGIN_S = 20.0                 # no new turn starts with less than this left of the bound

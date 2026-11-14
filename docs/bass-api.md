# Bass API: the contract between the browser and the action layer

Generated from real runs on the simulated API by `tests/bass_apidoc.py` (do not edit by hand; `tests/test_bass_actions.py` checks this file still matches the code). Mock only: no live call exists yet.

## How it works

The browser never talks to Claude. It sends ONE JSON object `{"action": ..., "args": {...}}` to the Bass endpoint (`Actions.dispatch(uid, request, on_event)` in `alto/bass/actions.py`) and gets ONE JSON object back. The only free text the student can type is the `edit` request, and it goes through the off-topic gate first.

Actions: `balance`, `estimate`, `propose`, `build`, `edit`, `stop`. The user is the signed-in uid on the server side; the browser never sends it.

### Every result has these keys

| key | meaning |
|---|---|
| `ok` | true only for status `ok` |
| `status` | one of the states below; the UI switches on this |
| `code` | machine reason behind a non-ok status (null when ok) |
| `message` | text to show. For `ok` it is the assistant's last words; otherwise a plain sentence that never blames the student |
| `action_id` | id of this action (`stop` takes it); null if no action started |
| `work_saved` | true if anything was written to the student's timeline (stopping never rolls it back) |
| `credits` | `{spent, refunded, balance, label}` in credits (1 credit = 1 cent of real cost); null if no action ran |
| `retryable` | the UI may offer Try again |
| `events` | the progress events of this action, in order (also pushed live to `on_event`) |

build and edit add `timeline_id`; build adds `cards: {done, total}`; propose adds `chips`; edit adds `changed`. Credits are plain numbers (2 decimals); `label` is the words to print ("41 credits"). Students never see tokens.

### States (`status`)

| status | when | UI |
|---|---|---|
| `ok` | done | show `message`; refresh the timeline |
| `estimate` | `build` would cost more than 20 credits and `accepted` was not sent | show `credits_text`, `have`, `short_by`; Continue calls `build` again with `accepted:true` |
| `no_credits` | balance too low (before or part-way) | show `message`; `work_saved` says if anything is kept |
| `busy` | too many actions in a minute | Try again |
| `paused` | Bass is switched off for everyone | show `message` |
| `off_topic` | the edit text was not about the timeline | show `message`; nothing charged |
| `refused` | the model declined | show `message`; nothing charged |
| `capped` | per-action, daily or monthly credit limit | show `message`; work is saved |
| `stopped` | the student pressed stop | work is saved |
| `error` | anything else (see `code`) | show `message`; offer Try again if `retryable` |

### Progress events

`start` `{event, action_id, kind}` first; then `progress` after each step `{event, action_id, step, label, detail, ok, cards_done, cards_total, spent_credits}` where `step` is one of `setup consent chips cards links layout build look work` and `detail` is e.g. "cards 4 of 6" (empty otherwise; `cards_total` comes from the chips' `card_estimate`, null if unknown); last `result` `{event, action_id, status, message}`.

### Codes

| code | message |
|---|---|
| `rate_limited` | Bass is busy right now. Nothing was charged. Please try again in a minute. |
| `overloaded` | Bass is busy right now. Nothing was charged. Please try again in a minute. |
| `timeout` | That took too long, so it was stopped. Nothing was charged. Please try again. |
| `connection` | Bass could not be reached. Nothing was charged. Please try again. |
| `upstream` | Something went wrong on our side. Nothing was charged. Please try again. |
| `auth` | Bass is down for maintenance. Nothing was charged. We are fixing it. |
| `balance_low` | Bass is down for maintenance. Nothing was charged. We are fixing it. |
| `bad_request` | Bass hit a problem on our side. Nothing was charged. We have been told. |
| `history_mismatch` | Bass lost its place in this conversation. Nothing was charged. Please try again. |
| `time_limit` | This step ran out of time and was stopped. Your work so far is saved. |
| `refused` | Bass could not help with that request. Nothing was charged. |
| `max_tokens` | That reply was cut off because it was too long. Try a smaller step. |
| `busy` | You have a lot going on at once. Give it a moment and try again. |
| `bass_paused` | Bass is taking a short break. Nothing was charged. Please try again later. |
| `bass_off` | Bass is not switched on for this account yet. |
| `needs_plan` | That is in a plan you do not have yet. Nothing was charged. |
| `conversion_failed` | Bass could not turn that file into the new format using only its own cards, so nothing was saved. Nothing was charged. |
| `plan_failed` | Bass could not make a plan using only your timeline and what you told it, so nothing was saved. Nothing was charged. |
| `terms_required` | Please accept the Beta Terms to use Bass. Sign in again to see the box. |
| `research_off` | Conversation sharing is not available right now. Bass works the same without it. |
| `research_version` | Please read the current sharing details and choose again. Nothing was saved. |
| `research_error` | That did not go through, so nothing changed. Please try again. |
| `upload_too_big` | That file is too large for Bass. Try a smaller file, or paste the text. |
| `upload_too_many_pages` | This PDF has too many pages for Bass. Upload a shorter part of it, or paste the text. |
| `upload_encrypted` | This PDF is password-protected. Upload an unlocked copy, or paste the text. |
| `upload_no_text` | This file has no selectable text. Paste the text or upload a text version. |
| `upload_scanned` | This looks like a scanned PDF (pictures of pages), so there is no text for Bass to read. Upload a copy with selectable text, or paste the text. |
| `upload_too_long` | That file has more text than Bass can read at once. Upload a shorter part of it. |
| `upload_unsupported` | Bass can read PDF, Word (.docx) and plain-text files. Paste the text or upload one of those. |
| `upload_unreadable` | Bass could not read that file. Paste the text or upload a text version. |
| `bass_disabled` | Bass is switched off for now. Viewing and the rest of Alto still work. |
| `beta_tester_daily` | You have reached your Bass limit for today. Nothing was charged. Please try again tomorrow. |
| `workspace_limit` | Your Bass beta credits are used up. Thank you for testing Bass! |
| `beta_credits_used` | Your Bass beta credits are used up. Thank you for testing Bass! |
| `beta_daily_full` | Today's beta limit has been reached. Nothing was charged. Please try again tomorrow. |
| `stopped` | Stopped. Your work so far is saved. |
| `consent_required` | Please confirm you want Bass to build only from your own materials. |
| `bad_input` | Bass could not read that request. Nothing was charged. |
| `too_large` | Those materials are too large for one step. Try fewer files. Nothing was charged. |
| `no_credits` | You are out of credits. Your work so far is saved. |
| `action_cap` | This step reached its credit limit and was stopped. Your work so far is saved. |
| `daily_cap` | You reached today's credit limit. Your work so far is saved. |
| `monthly_cap` | You reached this month's credit limit. Your work so far is saved. |

## Calls and states, with real responses

### balance

The credits meter and the homepage balance line.

Request:
```json
{
  "action": "balance",
  "args": {}
}
```

Response:
```json
{
  "ok": true,
  "status": "ok",
  "credits": 500.0,
  "label": "500 credits",
  "available": true
}
```

### estimate (small, no prompt)

A quick edit: nothing to ask the student.

Request:
```json
{
  "action": "estimate",
  "args": {
    "kind": "edit",
    "text": "Add a card about promissory estoppel."
  }
}
```

Response:
```json
{
  "ok": true,
  "status": "ok",
  "kind": "edit",
  "credits_text": "less than 1 credit",
  "estimate_credits": 1,
  "show_prompt": false,
  "have": 500.0,
  "have_label": "500 credits",
  "short_by": 0
}
```

### estimate (big, prompt, short of credits)

show_prompt is true above 20 credits; short_by > 0 means the student cannot afford it yet.

Request:
```json
{
  "action": "estimate",
  "args": {
    "kind": "build",
    "materials": [
      {
        "name": "Contracts notes.pdf",
        "kind": "notes",
        "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel. Statute of frauds. Remedies: expectation, reliance, restitution."
      }
    ]
  }
}
```

Response:
```json
{
  "ok": true,
  "status": "ok",
  "kind": "build",
  "credits_text": "about 185 credits",
  "estimate_credits": 185,
  "show_prompt": true,
  "have": 5.0,
  "have_label": "5 credits",
  "short_by": 180
}
```

### propose (chips)

The interview step. Nothing is written; the UI shows the chips as removable pills.

Request:
```json
{
  "action": "propose",
  "args": {
    "materials": [
      {
        "name": "Contracts notes.pdf",
        "kind": "notes",
        "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel. Statute of frauds. Remedies: expectation, reliance, restitution."
      }
    ]
  }
}
```

Response:
```json
{
  "ok": true,
  "status": "ok",
  "code": null,
  "message": "Here is my plan.",
  "action_id": "act_0001",
  "work_saved": false,
  "credits": {
    "spent": 0.04,
    "refunded": 0.0,
    "balance": 499.96,
    "label": "499 credits"
  },
  "retryable": false,
  "events": [
    {
      "event": "start",
      "action_id": "act_0001",
      "kind": "propose"
    },
    {
      "event": "result",
      "action_id": "act_0001",
      "status": "ok",
      "message": "Here is my plan."
    }
  ],
  "chips": {
    "title": "Contracts",
    "acts": [
      {
        "label": "Formation"
      },
      {
        "label": "Defences"
      },
      {
        "label": "Remedies"
      }
    ],
    "entities": [
      {
        "id": "offer",
        "name": "Offer"
      },
      {
        "id": "consideration",
        "name": "Consideration"
      }
    ],
    "fields": [
      "Case",
      "Rule"
    ],
    "card_estimate": 6
  }
}
```

### propose (a question instead)

chips is null: show the message and let the student answer.

Request:
```json
{
  "action": "propose",
  "args": {
    "materials": [
      {
        "name": "scrap.txt",
        "kind": "notes",
        "text": "week 3"
      }
    ]
  }
}
```

Response:
```json
{
  "ok": true,
  "status": "ok",
  "code": null,
  "message": "Which course is this for, and which weeks should it cover?",
  "action_id": "act_0002",
  "work_saved": false,
  "credits": {
    "spent": 0.03,
    "refunded": 0.0,
    "balance": 499.94,
    "label": "499 credits"
  },
  "retryable": false,
  "events": [
    {
      "event": "start",
      "action_id": "act_0002",
      "kind": "propose"
    },
    {
      "event": "result",
      "action_id": "act_0002",
      "status": "ok",
      "message": "Which course is this for, and which weeks should it cover?"
    }
  ],
  "chips": null
}
```

### build (consent missing)

The UI must send consent:true only after the student ticks the closed-system statement.

Request:
```json
{
  "action": "build",
  "args": {
    "chips": {
      "title": "Contracts",
      "acts": [
        {
          "label": "Formation"
        },
        {
          "label": "Defences"
        },
        {
          "label": "Remedies"
        }
      ],
      "entities": [
        {
          "id": "offer",
          "name": "Offer"
        },
        {
          "id": "consideration",
          "name": "Consideration"
        }
      ],
      "fields": [
        "Case",
        "Rule"
      ],
      "card_estimate": 6
    },
    "materials": [
      {
        "name": "Contracts notes.pdf",
        "kind": "notes",
        "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel. Statute of frauds. Remedies: expectation, reliance, restitution."
      }
    ]
  }
}
```

Response:
```json
{
  "ok": false,
  "status": "error",
  "code": "consent_required",
  "message": "Please confirm you want Bass to build only from your own materials.",
  "action_id": null,
  "work_saved": false,
  "credits": null,
  "retryable": false,
  "events": []
}
```

### build (estimate state)

Above 20 credits the first call stops here, without calling the model. Show credits_text, then call again with accepted:true.

Request:
```json
{
  "action": "build",
  "args": {
    "chips": {
      "title": "Contracts",
      "acts": [
        {
          "label": "Formation"
        },
        {
          "label": "Defences"
        },
        {
          "label": "Remedies"
        }
      ],
      "entities": [
        {
          "id": "offer",
          "name": "Offer"
        },
        {
          "id": "consideration",
          "name": "Consideration"
        }
      ],
      "fields": [
        "Case",
        "Rule"
      ],
      "card_estimate": 6
    },
    "materials": [
      {
        "name": "Contracts notes.pdf",
        "kind": "notes",
        "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel. Statute of frauds. Remedies: expectation, reliance, restitution."
      }
    ],
    "consent": true
  }
}
```

Response:
```json
{
  "ok": false,
  "status": "estimate",
  "kind": "build",
  "credits_text": "about 185 credits",
  "estimate_credits": 185,
  "show_prompt": true,
  "have": 499.94,
  "have_label": "499 credits",
  "short_by": 0,
  "message": "This will use about 185 credits.",
  "work_saved": false,
  "credits": {
    "spent": 0.0,
    "refunded": 0.0,
    "balance": 499.94,
    "label": "499 credits"
  },
  "events": [],
  "code": null,
  "retryable": false,
  "action_id": null
}
```

### build (ok, with progress events)

events are also pushed one by one to the on_event callback / SSE stream while the build runs.

Request:
```json
{
  "action": "build",
  "args": {
    "chips": {
      "title": "Contracts",
      "acts": [
        {
          "label": "Formation"
        },
        {
          "label": "Defences"
        },
        {
          "label": "Remedies"
        }
      ],
      "entities": [
        {
          "id": "offer",
          "name": "Offer"
        },
        {
          "id": "consideration",
          "name": "Consideration"
        }
      ],
      "fields": [
        "Case",
        "Rule"
      ],
      "card_estimate": 6
    },
    "materials": [
      {
        "name": "Contracts notes.pdf",
        "kind": "notes",
        "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel. Statute of frauds. Remedies: expectation, reliance, restitution."
      }
    ],
    "consent": true,
    "accepted": true
  }
}
```

Response:
```json
{
  "ok": true,
  "status": "ok",
  "code": null,
  "message": "Your timeline is built.",
  "action_id": "act_0003",
  "work_saved": true,
  "credits": {
    "spent": 7.65,
    "refunded": 0.0,
    "balance": 492.28,
    "label": "492 credits"
  },
  "retryable": false,
  "events": [
    {
      "event": "start",
      "action_id": "act_0003",
      "kind": "build"
    },
    {
      "event": "progress",
      "action_id": "act_0003",
      "step": "setup",
      "label": "Setting up your timeline",
      "detail": "",
      "ok": true,
      "cards_done": 0,
      "cards_total": 6,
      "spent_credits": 3.25
    },
    {
      "event": "progress",
      "action_id": "act_0003",
      "step": "setup",
      "label": "Setting up your timeline",
      "detail": "",
      "ok": true,
      "cards_done": 0,
      "cards_total": 6,
      "spent_credits": 3.87
    },
    {
      "event": "progress",
      "action_id": "act_0003",
      "step": "consent",
      "label": "Checking your materials",
      "detail": "",
      "ok": true,
      "cards_done": 0,
      "cards_total": 6,
      "spent_credits": 4.17
    },
    {
      "event": "progress",
      "action_id": "act_0003",
      "step": "chips",
      "label": "Adding your chips",
      "detail": "",
      "ok": true,
      "cards_done": 0,
      "cards_total": 6,
      "spent_credits": 4.67
    },
    {
      "event": "progress",
      "action_id": "act_0003",
      "step": "cards",
      "label": "Writing cards",
      "detail": "cards 6 of 6",
      "ok": true,
      "cards_done": 6,
      "cards_total": 6,
      "spent_credits": 5.9
    },
    {
      "event": "progress",
      "action_id": "act_0003",
      "step": "links",
      "label": "Linking cards",
      "detail": "",
      "ok": true,
      "cards_done": 6,
      "cards_total": 6,
      "spent_credits": 6.5
    },
    {
      "event": "progress",
      "action_id": "act_0003",
      "step": "build",
      "label": "Building your page",
      "detail": "",
      "ok": true,
      "cards_done": 6,
      "cards_total": 6,
      "spent_credits": 7.06
    },
    {
      "event": "result",
      "action_id": "act_0003",
      "status": "ok",
      "message": "Your timeline is built."
    }
  ],
  "timeline_id": "contracts-i",
  "cards": {
    "done": 6,
    "total": 6
  }
}
```

### edit (ok)

Free text goes through the off-topic gate, then the edit runs on the real tools.

Request:
```json
{
  "action": "edit",
  "args": {
    "timeline_id": "contracts-i",
    "text": "Rename the first card to Offer (revised)."
  }
}
```

Response:
```json
{
  "ok": true,
  "status": "ok",
  "code": null,
  "message": "Done: the card now reads \"Offer (revised)\".",
  "action_id": "act_0004",
  "work_saved": true,
  "credits": {
    "spent": 0.21,
    "refunded": 0.0,
    "balance": 492.07,
    "label": "492 credits"
  },
  "retryable": false,
  "events": [
    {
      "event": "start",
      "action_id": "act_0004",
      "kind": "edit"
    },
    {
      "event": "progress",
      "action_id": "act_0004",
      "step": "cards",
      "label": "Writing cards",
      "detail": "cards 6",
      "ok": true,
      "cards_done": 6,
      "cards_total": null,
      "spent_credits": 0.18
    },
    {
      "event": "result",
      "action_id": "act_0004",
      "status": "ok",
      "message": "Done: the card now reads \"Offer (revised)\"."
    }
  ],
  "timeline_id": "contracts-i",
  "changed": true
}
```

### edit (off topic)

Costs the student nothing.

Request:
```json
{
  "action": "edit",
  "args": {
    "timeline_id": "contracts-i",
    "text": "Write me a poem about cats."
  }
}
```

Response:
```json
{
  "ok": false,
  "status": "off_topic",
  "code": null,
  "message": "I can only help with building and editing your timelines and outlines in Alto. Tell me what you would like to add or change.",
  "action_id": "act_0005",
  "work_saved": false,
  "credits": {
    "spent": 0.0,
    "refunded": 0.0,
    "balance": 492.07,
    "label": "492 credits"
  },
  "retryable": false,
  "events": [
    {
      "event": "start",
      "action_id": "act_0005",
      "kind": "edit"
    },
    {
      "event": "result",
      "action_id": "act_0005",
      "status": "off_topic",
      "message": "I can only help with building and editing your timelines and outlines in Alto. Tell me what you would like to add or change."
    }
  ],
  "timeline_id": "contracts-i",
  "changed": false
}
```

### propose (refused)

The model's safety classifier declined. Nothing is charged.

Request:
```json
{
  "action": "propose",
  "args": {
    "materials": [
      {
        "name": "Contracts notes.pdf",
        "kind": "notes",
        "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel. Statute of frauds. Remedies: expectation, reliance, restitution."
      }
    ]
  }
}
```

Response:
```json
{
  "ok": false,
  "status": "refused",
  "code": "refused",
  "message": "Bass could not help with that request. Nothing was charged.",
  "action_id": "act_0006",
  "work_saved": false,
  "credits": {
    "spent": 0.0,
    "refunded": 0.03,
    "balance": 492.07,
    "label": "492 credits"
  },
  "retryable": false,
  "events": [
    {
      "event": "start",
      "action_id": "act_0006",
      "kind": "propose"
    },
    {
      "event": "result",
      "action_id": "act_0006",
      "status": "refused",
      "message": "Bass could not help with that request. Nothing was charged."
    }
  ],
  "chips": null
}
```

### propose (error, retries exhausted)

Alto or Anthropic side. Nothing is charged; offer Try again.

Request:
```json
{
  "action": "propose",
  "args": {
    "materials": [
      {
        "name": "Contracts notes.pdf",
        "kind": "notes",
        "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel. Statute of frauds. Remedies: expectation, reliance, restitution."
      }
    ]
  }
}
```

Response:
```json
{
  "ok": false,
  "status": "error",
  "code": "overloaded",
  "message": "Bass is busy right now. Nothing was charged. Please try again in a minute.",
  "action_id": "act_0007",
  "work_saved": false,
  "credits": {
    "spent": 0.0,
    "refunded": 0.0,
    "balance": 492.07,
    "label": "492 credits"
  },
  "retryable": true,
  "events": [
    {
      "event": "start",
      "action_id": "act_0007",
      "kind": "propose"
    },
    {
      "event": "result",
      "action_id": "act_0007",
      "status": "error",
      "message": "Bass is busy right now. Nothing was charged. Please try again in a minute."
    }
  ],
  "chips": null
}
```

### build (capped, work saved)

The per-action credit cap stopped it. work_saved is true: what was written stays.

Request:
```json
{
  "action": "build",
  "args": {
    "chips": {
      "title": "Contracts",
      "acts": [
        {
          "label": "Formation"
        },
        {
          "label": "Defences"
        },
        {
          "label": "Remedies"
        }
      ],
      "entities": [
        {
          "id": "offer",
          "name": "Offer"
        },
        {
          "id": "consideration",
          "name": "Consideration"
        }
      ],
      "fields": [
        "Case",
        "Rule"
      ],
      "card_estimate": 6
    },
    "materials": [
      {
        "name": "Contracts notes.pdf",
        "kind": "notes",
        "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel. Statute of frauds. Remedies: expectation, reliance, restitution."
      }
    ],
    "consent": true,
    "accepted": true
  }
}
```

Response:
```json
{
  "ok": false,
  "status": "capped",
  "code": "action_cap",
  "message": "This step reached its credit limit and was stopped. Your work so far is saved.",
  "action_id": "act_0008",
  "work_saved": true,
  "credits": {
    "spent": 0.81,
    "refunded": 0.0,
    "balance": 491.27,
    "label": "491 credits"
  },
  "retryable": false,
  "events": [
    {
      "event": "start",
      "action_id": "act_0008",
      "kind": "build"
    },
    {
      "event": "progress",
      "action_id": "act_0008",
      "step": "setup",
      "label": "Setting up your timeline",
      "detail": "",
      "ok": true,
      "cards_done": 0,
      "cards_total": 6,
      "spent_credits": 0.19
    },
    {
      "event": "progress",
      "action_id": "act_0008",
      "step": "setup",
      "label": "Setting up your timeline",
      "detail": "",
      "ok": true,
      "cards_done": 0,
      "cards_total": 6,
      "spent_credits": 0.81
    },
    {
      "event": "result",
      "action_id": "act_0008",
      "status": "capped",
      "message": "This step reached its credit limit and was stopped. Your work so far is saved."
    }
  ],
  "timeline_id": "contracts-i-2",
  "cards": {
    "done": 0,
    "total": 6
  }
}
```

### build (stopped by the student)

stop(action_id) takes effect at the next step boundary.

Request:
```json
{
  "action": "build",
  "args": {
    "chips": {
      "title": "Contracts",
      "acts": [
        {
          "label": "Formation"
        },
        {
          "label": "Defences"
        },
        {
          "label": "Remedies"
        }
      ],
      "entities": [
        {
          "id": "offer",
          "name": "Offer"
        },
        {
          "id": "consideration",
          "name": "Consideration"
        }
      ],
      "fields": [
        "Case",
        "Rule"
      ],
      "card_estimate": 6
    },
    "materials": [
      {
        "name": "Contracts notes.pdf",
        "kind": "notes",
        "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel. Statute of frauds. Remedies: expectation, reliance, restitution."
      }
    ],
    "consent": true,
    "accepted": true
  }
}
```

Response:
```json
{
  "ok": false,
  "status": "stopped",
  "code": "stopped",
  "message": "Stopped. Your work so far is saved.",
  "action_id": "act_0009",
  "work_saved": true,
  "credits": {
    "spent": 0.19,
    "refunded": 0.0,
    "balance": 491.08,
    "label": "491 credits"
  },
  "retryable": false,
  "events": [
    {
      "event": "start",
      "action_id": "act_0009",
      "kind": "build"
    },
    {
      "event": "progress",
      "action_id": "act_0009",
      "step": "setup",
      "label": "Setting up your timeline",
      "detail": "",
      "ok": true,
      "cards_done": 0,
      "cards_total": 6,
      "spent_credits": 0.19
    },
    {
      "event": "result",
      "action_id": "act_0009",
      "status": "stopped",
      "message": "Stopped. Your work so far is saved."
    }
  ],
  "timeline_id": null,
  "cards": {
    "done": 0,
    "total": 6
  }
}
```

### stop

Returns at once; the build's own result says stopped.

Request:
```json
{
  "action": "stop",
  "args": {
    "action_id": "act_0009"
  }
}
```

Response:
```json
{
  "ok": true,
  "status": "ok",
  "stopping": "act_0009"
}
```

### build (no credits)

Fails before any model call; nothing was written.

Request:
```json
{
  "action": "build",
  "args": {
    "chips": {
      "title": "Contracts",
      "acts": [
        {
          "label": "Formation"
        },
        {
          "label": "Defences"
        },
        {
          "label": "Remedies"
        }
      ],
      "entities": [
        {
          "id": "offer",
          "name": "Offer"
        },
        {
          "id": "consideration",
          "name": "Consideration"
        }
      ],
      "fields": [
        "Case",
        "Rule"
      ],
      "card_estimate": 6
    },
    "materials": [
      {
        "name": "Contracts notes.pdf",
        "kind": "notes",
        "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel. Statute of frauds. Remedies: expectation, reliance, restitution."
      }
    ],
    "consent": true,
    "accepted": true
  }
}
```

Response:
```json
{
  "ok": false,
  "status": "no_credits",
  "code": "no_credits",
  "message": "You are out of credits.",
  "action_id": "act_0001",
  "work_saved": false,
  "credits": {
    "spent": 0.0,
    "refunded": 0.0,
    "balance": 0.0,
    "label": "0 credits"
  },
  "retryable": false,
  "events": [
    {
      "event": "start",
      "action_id": "act_0001",
      "kind": "build"
    },
    {
      "event": "result",
      "action_id": "act_0001",
      "status": "no_credits",
      "message": "You are out of credits."
    }
  ],
  "timeline_id": null,
  "cards": {
    "done": 0,
    "total": 6
  }
}
```

### edit (busy)

Too many actions in a minute for one account.

Request:
```json
{
  "action": "edit",
  "args": {
    "timeline_id": "t",
    "text": "hello again"
  }
}
```

Response:
```json
{
  "ok": false,
  "status": "busy",
  "code": "busy",
  "message": "You have a lot going on at once. Give it a moment and try again.",
  "action_id": "act_0002",
  "work_saved": false,
  "credits": {
    "spent": 0.0,
    "refunded": 0.0,
    "balance": 499.83,
    "label": "499 credits"
  },
  "retryable": true,
  "events": [
    {
      "event": "start",
      "action_id": "act_0002",
      "kind": "edit"
    },
    {
      "event": "result",
      "action_id": "act_0002",
      "status": "busy",
      "message": "You have a lot going on at once. Give it a moment and try again."
    }
  ],
  "timeline_id": "t",
  "changed": false
}
```

### propose (paused)

Bass is switched off for everyone (kill switch / Anthropic balance empty). No model call; nobody is blamed.

Request:
```json
{
  "action": "propose",
  "args": {
    "materials": [
      {
        "name": "Contracts notes.pdf",
        "kind": "notes",
        "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel. Statute of frauds. Remedies: expectation, reliance, restitution."
      }
    ]
  }
}
```

Response:
```json
{
  "ok": false,
  "status": "paused",
  "code": "bass_paused",
  "message": "Bass is taking a short break. Nothing was charged. Please try again later.",
  "action_id": "act_0001",
  "work_saved": false,
  "credits": {
    "spent": 0.0,
    "refunded": 0.0,
    "balance": 500.0,
    "label": "500 credits"
  },
  "retryable": true,
  "events": [
    {
      "event": "start",
      "action_id": "act_0001",
      "kind": "propose"
    },
    {
      "event": "result",
      "action_id": "act_0001",
      "status": "paused",
      "message": "Bass is taking a short break. Nothing was charged. Please try again later."
    }
  ],
  "chips": null
}
```

### bad input

Any malformed request.

Request:
```json
{
  "action": "build",
  "args": {
    "chips": {},
    "materials": []
  }
}
```

Response:
```json
{
  "ok": false,
  "status": "error",
  "code": "bad_input",
  "message": "chips needs at least a title and acts",
  "action_id": null,
  "work_saved": false,
  "credits": null,
  "retryable": false,
  "events": []
}
```

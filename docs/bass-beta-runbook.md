# Bass beta runbook (mock-only until Luke says "go for the first live call")

Nothing here is deployed: Blaze is off. This is what IT does, in order, after Luke turns on Blaze and says go.
Design: `ORG/notes-bass-beta.md` (UPDATE 1-3 and IT's note); guard wording G1-G15: `Alto-commercial-structure.md` section 4.9.
All numbers are config defaults in `alto/bass/beta_config.py`; nothing in the guard logic hard-codes one.

## The numbers (Luke, 2026-10-29: $100 a month of credit, refreshes on the 17th, no rollover; 1 credit = 1 cent)
| What | Rule | Value |
|---|---|---|
| Server ceiling | all testers together, per credit period | **7,000 credits ($70), INTERIM** (Luke, 11 Nov 2026). The planned 9,000 ($90) comes back only after the M1 (failed calls are booked) and M2 (abandoned calls are booked) fixes have been tested live: change `server_ceiling_credits` |
| Per tester | floor(ceiling / N) per period, no top-up | at 7,000: N=10: 700 ($7); at 9,000: N=15: 600 ($6), N=10: 900 ($9) |
| Per tester per day | resets at local midnight | 300 ($3) |
| All testers per day | | 1,500 ($15) |
| Per action | | 300 ($3) |
| Estimate prompt | action estimated over | 20 credits |
| Spike trip | spend in any 10 minutes over what the caps allow (B1): min(N x 2 x daily-per-tester, 2 x all-testers-per-day) + one action | N=10: 3,301 credits |
| Alert (not a trip; Luke's numbers, decision G1 of 11 Nov 2026) | more than 400 credits ($4) of spend in any 10 minutes (`spend_over_alert_10min`, at most once per 10 minutes) | 400 credits |
| Alert (not a trip, B1 and G1) | the day's counter over 80% before 18:00 New York (`daily_over_80_before_18`, once a day); the day's own limit refuses past 100% and resets at midnight | 1,200 credits |
| Alerts | 50 / 80 / 100% of the day's limit and of the period ceiling; every trip; allowlist-miss bursts; `abandoned_calls_booked` (the reaper booked calls that were cut off); `history_mismatch` (one conversation's history was refused: that conversation only) | |
| Failed calls | a call that fails AFTER it was sent (a dropped stream, a timeout, the wall-clock stop) is never retried and is booked at its reserved worst case as Alto's cost; only an error answer or a failed connection is free and retried | |
| Wall clock | one action stops itself at `action_wall_s` (240 s), below the function timeout `function_timeout_s` (300 s), and can be resumed | |
| Limits | 12 calls/min per account, 30/min per IP (last X-Forwarded-For entry, IPv6 by /64); in flight 1 build + 2 chat | |
| Refunds | failed or refused turns only, 5 per account per day | |
| Period | starts on the 17th at local midnight (America/New_York), id = the start date, e.g. 2026-11-17 | |
The other $10 of the $100 is the local live check's reserve (own cap, 1,000 credits).
The hold checks, in ONE transaction, all fail closed: this tester's day, this tester's period, all testers' day, all testers' period.
The server-wide counters set aside each call's TRUE worst case (from max_tokens), not the per-action-capped hold.

## What a tester sees (beta mode, `alto/build/bass_ui.py` BETA = True)
* Testers are unpaid: their credits are the free allowance above. There is no card, purchase, Stripe or "Add credits" anywhere in the path, and no price in dollars.
* The meter reads "Beta credits remaining: N". A used-up share or pool shows "Beta credits used up" with "Your Bass beta credits are used up. Thank you for testing Bass!", and the page sends nothing more until Bass is opened again. The proxy refuses the same calls anyway, with zero upstream requests (estimate included: it makes the free count_tokens call, so only `balance` and `stop` skip the allowance gate, and any action name added later is gated too).
* Non-allowlisted accounts: with the proxy URL built in (`ALTO_BASS_BASE`, IT sets it at deploy), the Bass buttons stay hidden until the proxy's free `balance` call says the signed-in account is on the list (remembered 6 hours per account). Signed-out: hidden. The proxy answers `bass_off` to every action for them regardless. Without the URL (every test, every build today) the UI runs its in-page simulator.

* **Beta Terms gate**: Bass refuses a uid that has not accepted the CURRENT Beta Terms version, with the reason `terms_required` and "Please accept the Beta Terms to use Bass. Sign in again to see the box." (no paywall, no button; zero upstream requests, no hold, no grant). The proxy reads ONE document through the store interface: `terms_acceptance/<uid>_<version>`, written by the page (IT's rule, privacy-inventory sec 5), which must have `uid` = the caller's uid, `version` = the current version and `ageConfirmed` = true (other keys, such as `acceptedAt`, are ignored). A missing, unreadable or malformed record, or a store error, refuses (fail closed). Order: right after the allowlist check, before the kill switch, hold and in-flight checks, for every action except `stop`; `balance` answers `available: false` with the same message. The current version is the contents of `alto/legal/VERSION` when that file exists (it ships in the bundle), else `0.1`; bump the file and everyone is asked again. The proxy's service account only READS this collection (`roles/datastore.user` already covers it).

## Uploads: PDF and .docx become text on the proxy (bench-tl-1 job, 2026-10-30)
* The page sends a PDF / .docx as a material `{name, kind, text: "", file_b64}` (files over `upload_max_file_bytes` are not sent; `.txt/.md/...` are read in the page as before). The proxy turns it into text BEFORE any hold or upstream call, and AFTER the allowlist, terms and allowance checks (so a user who is not on the list, has not accepted the terms or has used up the allowance costs no parsing). `estimate`, `propose` and `build` all do it, so the extracted text is in the estimate honestly.
* PDF: `pypdf==6.21.4` (pure Python, no dependencies; 6.21.1-6.21.4 are all parser security fixes, so the pin is the newest, bumped 2026-10-30), text only. NO native PDF block ever goes to Claude (page images would blow the per-action cap). .docx: stdlib `zipfile` + `xml`, the text of `word/document.xml` (paragraphs, tabs, breaks, table rows as `a | b`), no new dependency.
* **Caps (all `BetaConfig` values)**: file `upload_max_file_bytes` 5,000,000; all files of a request `upload_max_total_bytes` 6,000,000; `upload_max_files` 5; whole JSON body `max_request_bytes` 9,000,000 (base64 is 4/3 of the raw bytes; below a 10 MB function limit); `pdf_max_pages` 200; `extract_max_chars` 300,000 per file (more is REFUSED, not cut; the actions' own 600,000 total still applies); `extract_min_chars` 20 (less is "no selectable text"); `extract_timeout_s` 20 for the whole request; `extract_mem_bytes` 1.5 GB; .docx: `docx_max_members` 200, `docx_max_uncompressed_bytes` 30,000,000, `docx_max_ratio` 100, `docx_xml_max_bytes` 8,000,000 (hard read limit), `docx_max_depth` 100, `docx_max_elements` 400,000.
* **Parse path** (`alto/bass/extract.py` then `alto/bass/extract_worker.py`): base64 shape, raw sizes, file count, file name extension and magic bytes (`%PDF` / `PK`) are checked first; then each file goes, as raw bytes on stdin, to a CHILD PROCESS (`python -I extract_worker.py`, isolated mode, empty environment, working directory `/`, CPU / address-space / file-size limits, killed at the request's one deadline). The worker refuses an encrypted PDF without trying a password, checks the PDF page count before reading any page, checks a .docx's member count from the zip end record before parsing the directory, its declared sizes and ratio, reads `document.xml` with a hard byte limit (never `extractall`), refuses any XML with a DOCTYPE or ENTITY or in UTF-16, and caps elements and depth. Nothing is fetched (no network code in the worker). The file bytes are dropped after extraction and are never held, cached, logged or sent upstream.
* **Failures** fail closed with a friendly message, status `refused`, zero upstream requests, no hold, no stack trace: `upload_too_big`, `upload_too_many_pages`, `upload_encrypted`, `upload_no_text` ("This file has no selectable text. Paste the text or upload a text version."), `upload_too_long`, `upload_unsupported`, `upload_unreadable` (corrupt, zip bomb, timeout, junk, name/bytes mismatch). The metadata log records only the code.
* **Deploy**: `pypdf` is in `deploy/bass-proxy/requirements.txt`; the first Cloud Build must confirm it resolves on Python 3.12. The worker runs `sys.executable`, so the function image needs nothing else. Memory: `--memory 512Mi --concurrency 4` leaves room for one worker per request (a 9 MB body plus one parse); raise memory if the real build shows pressure.
* Known limits: the extraction runs again on `propose`, `estimate` and `build` (no cache, deliberately: the proxy keeps no copy of any upload); scanned PDFs are refused (no OCR); text in images, headers/footers and footnotes of a .docx is not read.

## Switches (all by hand in the Firestore Console, `bass_beta/...`)
* **Confirm a credit period (IT only)**: after Luke confirms in chat that the credit refreshed, set the document `bass_beta_periods/<period id>` to `{confirmed: true}` (boolean true, not a string), where the id is the period's start date (the first is `2026-10-17`, then `2026-11-17`). A new period opens ONLY with this marker. No marker (the default): Bass is off, the friendly "beta credits used" message, zero requests; the Claude (bring-your-own) path keeps working. Do this at the start of every period, the first one included.
* **Add a tester**: edit `bass_beta/bass_testers` `{emails: [...]}` (verified Google emails). This is Bass's OWN list: `bass_beta/allowlist` (who may save to the cloud in the Alto beta) gives no Bass access. Keep the count at or below N (and N at or below 15): a list longer than N admits NOBODY and raises the alert `tester_list_too_long`. No deploy.
* **Disable Bass (the budget cutoff)**: `bass_beta/disabled` present (IT writes `{on: true, reason, costAmount, at}`; any content except `{on: false}`) turns Bass off. If the doc cannot be read, Bass is off too. Remove it (or set `{on: false}`) to turn Bass back on.
* **Kill switch**: `bass_beta/kill` `{on: true, reason, t}`. Trips by itself on: a 10-minute spend past what the caps allow (the books are wrong), an upstream 401/403, "credit balance too low", the Console's "You have reached your specified workspace API usage limits" (HTTP 400), or ANY other unexpected 400: no retry, every trip sends an alert. Reset by hand only, after finding out why: set `{on: false}` or delete the doc. Time never resets it. Viewing, presets and by-hand editing never consult it.
* **Go live**: `bass_beta/live_go` `{on: true}`. Absent or false (the default) means every call is answered by the mock. Only Luke or IT, only after "go".

## Console backstops (they do not depend on our code)
Anthropic spend limits are per CALENDAR month (reset 00:00 UTC on the 1st), not per the 17th, and Bass needs its OWN workspace. A $100 Console limit bounds a calendar month, so one 17th-to-16th period can still see more across two months. The real guards: our $90 period ceiling and the daily caps, and the credit balance itself (auto-reload OFF). Blaze budget alerts are an alarm, not a stop. `--max-instances 5` is a cost ceiling that also locks real users out when reached.

## What the proxy does with errors (IT review, 2026-10-30)
* **Stops Bass for everyone, no retry**: HTTP 401/403; "credit balance too low"; the Console limit (workspace OR organisation wording, "You have reached your specified ... API usage limits"); the organisation spend cap (HTTP 429 with `error.details.error_code: enforced_spend_limit_reached`, also accepted flat); any other 400 that is clearly ours (a schema or parameter error).
* **That tester's problem only, no trip, nothing charged**: a 400 caused by their input (prompt too long, too many pages, an image or document problem) is answered with a plain "could not read that request".
* **A settle that cannot be booked** (the model call was paid for but Firestore would not take the write after 4 tries with backoff): the kill switch trips and an alert `settle_failed` names the uid, the hold and the unbooked credits, because the books missed a paid call. The reaper later books that hold's whole reservation as Alto's cost (never less than what was paid), so the counters do not under-count, but the switch stays on until a human has looked. Reconcile by hand from that alert, then reset the switch.
* **bad_input bursts**: every bad_input raises an alert (`bad_input`, uid only); it trips the switch only if 3 DISTINCT accounts hit it inside 10 minutes (more likely a request-format bug of ours than three bad uploads). One account repeating never trips it.
* **Mock mode**: with `live_go` off, every answer carries `mock: true` and a "Test mode" notice, and whatever the mock builds goes to a throw-away store, never the tester's real account. The page must show the notice.

## Deploy notes
* The function needs `ALTO_BUCKET` (the Alto store writes build artifacts to Cloud Storage): `<alto-bass-bucket>` (IT's private notes hold the real name; it is not written in this repository), a DEDICATED private bucket in us-central1 with uniform bucket-level access and public access prevention enforced (a non-Firebase bucket has no client-SDK path at all; the proxy's service account is the only principal). IT creates it after Blaze: `gcloud storage buckets create gs://<alto-bass-bucket> --project <firebase-project-id> --location us-central1 --uniform-bucket-level-access --public-access-prevention`. deploy.py keeps `--bucket` REQUIRED and prints the one scoped IAM grant (`roles/storage.objectAdmin` on that bucket only); it creates nothing.
* The first Cloud Build must confirm that `anthropic==2.3.0` and the other pins in `deploy/bass-proxy/requirements.txt` resolve on Python 3.12. The first deploy stays with `live_go` OFF (mock answers, labelled), so nothing can reach Anthropic while that is checked.
* `tzdata` is in the requirements because `BetaConfig` uses `ZoneInfo("America/New_York")` at cold start and a slim image may have no zone database.
* `--memory 512Mi --concurrency 4 --max-instances 5`. `--timeout 300s` may cut a long build: compare it with the real build times from the local live check before the beta opens.
* CORS origins are `BetaConfig.allowed_origins` (the shared tester site `alto-timelines.web.app`, plus the luke-alto addresses).
* `trusted_hops` (config, default 1): right on the direct run.app / cloudfunctions URL. Behind a Hosting rewrite or a load balancer set 2 (or the real count), or every caller shares one IP bucket (30 calls a minute).
* The bundle's requirements are `deploy/bass-proxy/requirements.txt` (the tested pins) plus the connector's own `requirements.txt`.

## Known limits (documented, not fixed in the beta)
* Hot documents: every hold and settle writes the day and the period counter docs; Firestore sustains about 1 write a second per document. Fine for 15 testers; shard the counters before opening wider.
* The key is cached per instance after the first read: a rotation needs a redeploy or a cold start (a 401 trips the switch first).
* The per-tester `entries` list in `bass_credits/<uid>` grows with every action (1 MiB document limit): fine for the beta.
* Invalid-token requests are rejected before the IP limiter, so a flood costs invocations only; the budget cutoff covers that.

## Rotate the key
1. Console: Bass beta workspace, create a new API key. 2. `gcloud secrets versions add alto-bass-beta-key --data-file=-` (paste, never a file in the repo, never chat). 3. Redeploy or wait for cold starts (the function holds the key in memory). 4. Console: delete the old key. 5. Flip `live_go` off first if the old key leaked.

## Reaper
Rides on traffic (at most every 5 minutes, any request): releases account holds and counter reservations older than 15 minutes that were never settled (a crashed instance).

## Logs
One metadata line per call: uid, action, status, code, credits spent/refunded, tool calls, output tokens. No conversation text, titles, emails or IPs.

## The local live check (Home Desktop, no proxy)
`tools/bass_live_check.py`. Dry run against the mock: `python3 tools/bass_live_check.py --dry-run` (its own temp store under a private temp HOME; any `ALTO_STORE` but `local` is refused). Live (must be given `ALTO_STORE=local` explicitly): only after Luke's go and the guards passing; it refuses unless `~/.config/alto/bass/LIVE_GO` exists AND `ALTO_LIVE_ANTHROPIC=1` is set for that run. Key from IT's Keychain item. Steps: free count_tokens smoke, one Haiku edit, 5-10 measured builds from fixed notes; stops on the first error, 401 or low balance; own hard cap 1,000 credits ($10). Writes `ORG/bass-live-check/measurements.json` and `.csv` (metadata only) with median/p90 cost, estimate vs actual, a re-fit of the estimate by size and a suggested price per build.

Local reserve file (`~/Library/Application Support/Alto-bass-local/reserve.json`, `alto/bass/local_reserve.py`): deleting it resets the local live budget to a fresh $10 for the period. Accepted by the Board on 11 Nov (Home SECURITY stamp alto-testing-1111-basslive, finding "deleting reserve.json = fresh $10"): the file is the soft brake, and the Anthropic Console spend limit ($10, set once by Luke or IT) is the hard backstop that holds even if the file is deleted or the code were wrong. Do not delete it to get more budget; if it is lost, say so in the Board log.

## Checked by hand at "go" (the mock cannot prove them)
Real Firebase token verification, real Secret Manager access, the Firestore adapter under real contention (use the emulator first), real X-Forwarded-For behind Google's front end, the Console limit, Blaze budget alerts, reCAPTCHA/App Check if used.

## Two-account isolation (IT security matrix P1-P3)
The uid comes ONLY from the verified ID token; anything named uid/email/account in the body is ignored or refused. Every tool call runs under that uid against a per-account store, so another tester's project or timeline ids in a request or in the model's tool calls find nothing; a stop only works for the account that started the action. Covered by the P2 tests in `tests/test_bass_beta_proxy.py`.

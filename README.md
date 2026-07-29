# Alto Connector

mcp-name: io.github.lukebmandel-debug/alto-connector

A Claude connector that interviews you about **your own materials** — a course,
a novel, a research project — and builds you an interactive, filterable
"liquid-glass" **Alto timeline**: glass cards on colored act bands, entity
chips, routed connection lines, detail pages with your own schema, highlights
and notes, mobile layout, and a self-contained offline file you can share.

**The one rule (§0):** Alto is a closed knowledge container. It connects and
organizes what *you* provide — it never invents facts, events, holdings, or
descriptions. Sparse notes make a sparse timeline, on purpose. The connector
enforces this server-side: authoring tools stay locked until your materials
and explicit consent are recorded.

## Install

Download the file for your computer from the
[latest release](../../releases/latest), then in Claude Desktop go to
**Settings → Extensions → Advanced settings → Install Extension…** and choose
it. Restart Claude Desktop and Alto appears under Extensions.

| | |
|---|---|
| macOS, Apple Silicon | `Alto-macos-arm64.mcpb` |
| macOS, Intel | `Alto-macos-x64.mcpb` |
| Windows, 64-bit | `Alto-windows-x64.mcpb` |

**Nothing else to install.** Each bundle carries its own Python, which is why
it is around 50MB. Claude Desktop ships Node but not Python, and stock macOS
still has 3.9 — too old for this server.

Other ways in:

```bash
uvx alto-connector          # any MCP client, from PyPI
bash setup.sh               # from a checkout — the development install
```

Once installed, open a chat and say *"I want to build a timeline in Alto —
interview me."*

## Using it — what a new user actually does

1. Open a chat and say something like *"I want to build a timeline in Alto —
   interview me."*
2. Claude calls `get_interview_guide` and runs a short warm interview:
   - **Flow 1** — name the project container and what it's for.
   - **Flow 2 §A** — *the materials gate*: you hand over your actual materials
     (upload files or paste text into the chat), and explicitly agree that
     Alto builds only from them.
   - **§B–§I** — title, what the axis means, your acts/eras, your entities
     (characters, doctrines, teams…), node schema (e.g. Facts·Issue·Holding·
     Rule for law), relationship vocabulary for the lines, extra filter axes,
     persona, presentation.
3. Claude authors nodes **verbatim from your materials**, wires connections,
   runs a layout preview, builds (a verifier gates every build), and
   publishes.
4. You get your timeline two ways:
   - **Offline file** (always): one self-contained HTML — double-click to
     open, send to a friend, works forever with no server.
   - **Web links** (optional, still free): if Firebase publishing is
     configured, `https://<your-site>.web.app/t/<timeline>/` plus a homepage
     listing all your published timelines, a reports page, and cross-device
     sync of highlights/notes/reports.
5. Come back any time — drafts resume across chats via `get_timeline`.

## Publishing (optional web links + cross-device sync)

Timelines are private by default and the offline file always works. To publish
shareable links — and to get highlights, notes and reports syncing between your
desktop and your phone — you host them on **your own** free Firebase project
(Spark plan, no card).

**You host what you share.** Everyone who authors a timeline publishes to their
own project, so the people you send a link to read it from your site and their
notes live in your Firestore. That means you can revoke a link at any time
(`publish_timeline(timeline_id, visibility="private")` deletes the page from
your site), and it means nobody's data flows through anyone else's project.
Reading a shared timeline needs no install and no Alto account — just the link.

1. [console.firebase.google.com](https://console.firebase.google.com) → create
   a project → Hosting → add a site (e.g. `my-alto`).
2. Enable **Firestore** and **Authentication → Google** in that project, and
   deploy the per-user rules in `firestore.rules` (`firebase deploy --only
   firestore:rules`). Do this *before* publishing: a Firestore left in test
   mode is world-readable and world-writable for 30 days.
3. `npm i -g firebase-tools && firebase login`
4. Open Alto's settings in Claude Desktop (**Settings → Extensions → Alto**)
   and fill in **Firebase Hosting site**, **Firebase project id** and
   **Firebase web config**. From a checkout instead, set `ALTO_FIREBASE_SITE`,
   `ALTO_FIREBASE_PROJECT` and `ALTO_FIREBASE_CONFIG` in the environment.

   The web config comes from Firebase console → Project
   settings → Your apps → SDK setup and configuration. It is spliced into
   `alto-cloud.js` at publish time. Leave it unset and sync is simply off:
   highlights stay in the browser's local storage on each device.
   `ALTO_FIREBASE_BIN` overrides the path to the `firebase` CLI if it is not on
   your `PATH`.

Two things worth knowing before you share a link. Published means **public to
anyone who has the URL** — the address carries a random tail so it cannot be
guessed, but it is not access-controlled. And a reader who signs in to sync
their notes gets an account in *your* Firebase project: the security rules stop
you reading their notes through the app, but you own the project and can see
them in the Firebase console.

## Repo layout

- `engine/` — the three page templates, extracted content-free from the
  reference build. The extraction fixtures they were derived from are not
  published: they contain the author's own writing. `test_roundtrip.py` skips
  without them.
- `alto/build/` — brief model, height estimator, layout resolver (a port of
  the engine's own), block generators, verifier, offline bundler.
- `alto/mcp_server.py` — the 14 MCP tools + interview prompt.
- `alto/build/sanitize.py` — makes user content inert before it reaches a page.
  Load-bearing: the engine renders detail sections straight into `innerHTML`.
- `alto/publish_static.py` — free-tier static publishing via the Firebase CLI.
- `packaging/` — the .mcpb bundles, the download page and the registry entry.
  See `packaging/README.md`.
- `alto/web.py`, `alto/auth/` — a full remote-server variant (streamable HTTP
  + OAuth 2.1), not used by the local install; kept for a future hosted
  deployment.

## Development

```bash
.venv/bin/python -m pytest tests/        # incl. the golden round-trip
python3 -m alto.build samples/contracts_brief.json --bundle   # CLI build
```

## Privacy

See `alto/privacy.html`. Short version: your source documents stay in your
Claude conversation; the connector stores only what it builds, locally in
`~/Documents/Alto` (and, if you publish, on your own Firebase site).

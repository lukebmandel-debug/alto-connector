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

### Without Claude Desktop

Alto is a plain MCP server, so any MCP client can run it — Claude Code, Cline,
Zed, Continue, your own script. No download, no bundle.

Add this to your client's MCP config:

```json
{
  "mcpServers": {
    "alto": {
      "command": "uvx",
      "args": ["--from",
               "git+https://github.com/lukebmandel-debug/alto-connector",
               "alto-connector"]
    }
  }
}
```

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/)
(`curl -LsSf https://astral.sh/uv/install.sh | sh`). `uvx` fetches and runs
Alto in a throwaway environment each time, so there is nothing to install or
update.

Prefer a permanent install? Then `alto-connector` is on your `PATH` and the
config is simply `{"command": "alto-connector"}`:

```bash
pip install git+https://github.com/lukebmandel-debug/alto-connector
alto-connector --help      # check it works; without --help it waits for a
                           # client to speak to it, which looks like a hang
```

Everything works the same way — the interview, the build, the offline file —
because the bundle and this are the same server; the bundle just carries its
own Python so Claude Desktop users need not install one.

Timelines land in `~/Documents/Alto`. Each is a single self-contained HTML
file you open in any browser — no server, no account, no internet. Shareable
web links are optional (see Publishing below); without them, that file is the
finished product.

Then tell your client: *"I want to build a timeline in Alto — interview me."*

### From a checkout

`bash setup.sh` — **macOS and Claude Desktop only**; it registers the
connector by writing `claude_desktop_config.json`. For any other client, use
one of the two methods above pointed at your checkout.

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
   - **Web page** (free, set up for you — see Publishing): a page at
     `https://<your-site>.web.app/pv/<key>/` that only your Google account
     can open, listed on your homepage, with cross-device sync of
     highlights/notes/reports. To show it to someone, create a share link
     from your homepage.
5. Come back any time — drafts resume across chats via `get_timeline`.

## Publishing — your own private site, set up for you

Every timeline is private. It goes on **your own** Alto site — a free Firebase
project (Spark plan, no card) in *your* Google account, never one of ours — at
`https://<your-project>.web.app/pv/<key>/`, which opens only for the Google
account that published it. There is no public option.

**You set nothing up.** The first time you use Alto, Claude calls
`set_up_site`, which runs in the background while the interview goes on:

1. fetches the official Node and Firebase CLI into Alto's own folder
   (checksum-pinned; nothing system-wide, no admin password);
2. opens a Google page — you click **Allow** — so it can act in your account;
3. creates your Firebase project, its web app, Firestore, and Google sign-in;
4. deploys your site and the per-user security rules in `firestore.rules`,
   then checks from outside that anonymous reads of your data are refused;
5. opens your new site — you click **Continue with Google** — so Alto on this
   computer is signed in as you, and moves any drafts into your account.

From then on your projects live in your account (**Keep projects in:
auto**), so every computer you sign in on sees the same ones, and
`publish_timeline` puts a timeline on your site with nothing to upload.

**Sharing is a share link.** To show a timeline to someone, use "Create share
link" in its menu on your homepage. It is a snapshot of that one page at
`/s/<key>/`, readable by anyone with the link without an install or an Alto
account, and you can revoke it from the same place at any time.

**Already have a Firebase project?** Fill in the extension's *Advanced*
settings (site, project id, and optionally the web config) — or, from a
checkout, `ALTO_FIREBASE_SITE`, `ALTO_FIREBASE_PROJECT`, `ALTO_FIREBASE_CONFIG`.
If this computer has no Firebase CLI, `set_up_site` installs Alto's own and
finishes setting up *that* project (Firestore, sign-in, rules) instead of
making a new one. `ALTO_FIREBASE_BIN` points at a CLI of your own.

Two things worth knowing before you share a link. A share link is **readable by
anyone who has it** — the key cannot be guessed, but it is not
access-controlled, so revoke it when it has done its job. And a reader who signs in to sync
their notes gets an account in *your* Firebase project: the security rules stop
you reading their notes through the app, but you own the project and can see
them in the Firebase console.

### Moving existing work across

`set_up_site` copies whatever is in the local folder into your account as its
last step. To do it by hand (for example from another folder):

```bash
alto-connector migrate --from ~/Documents/Alto
```

It copies, never deletes, and skips anything already in your account.

### More than one site, and chats that start on their own

A person can have an Alto site for each Google account they use. Every
timeline tool takes an optional `account` (a site name like `luke-alto`, its
address, or the Google email), and nothing is remembered between calls — one
connector process can serve several chats.

- `get_interview_guide` lists every account this computer is signed in to and
  what is in each, so a chat opened on its own (not from a timeline's
  **Edit timeline** button) finds a timeline the user names. `list_projects`
  with `account="all"` does the same on demand.
- `connect_account(site)` adds a site the user already has, from its address
  alone: Alto reads the site's public web config (`/__/firebase/init.json`),
  and the user clicks Continue with Google on the site's own sign-in page.
  Accounts are kept in `~/.config/alto/accounts.json` (no tokens; each
  sign-in is its own `session-<project>.json`, mode 0600).
- A timeline can be named by its id, its published page address
  (`…/pv/<key>/`) or its title. A `not_found` says where it is: another
  account (`found_in_accounts`), or the homepage with no draft behind it
  (`published_without_draft`).
- `import_timeline(published_key)` restores a draft whose page was published
  from a folder-backed connector: that publish now keeps a compressed copy of
  the draft beside the page (`users/{uid}/alto_snapshots/{key}`).
- Publishing into a connected account writes the page straight into it and
  does not redeploy the site: deploying needs the Firebase CLI logged in as
  that Google account, which this computer may not be. A sign-in whose site
  address Alto does not know is never given a guessed one (a project's default
  site can be somebody else's); the site is learned from the account's own
  published timelines.

## Repo layout

- `engine/` — the three page templates, extracted content-free from the
  reference build. The extraction fixtures they were derived from are not
  published: they contain the author's own writing. `test_roundtrip.py` skips
  without them.
- `alto/build/` — brief model, height estimator, layout resolver (a port of
  the engine's own), block generators, verifier, offline bundler.
- `alto/mcp_server.py` — the 25 MCP tools + interview prompt.
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

# Alto main Mac — inventory (IT, 2026-10-24)

Read-only snapshot of what Alto work uses on Luke's main Mac. `alto-setup.sh` pins these versions.

## Machine
- MacBook, Apple silicon (arm64), 10 cores, 16 GB, macOS 27.0.1.
- **No Homebrew.** Every CLI lives user-local under `~/.local`, no sudo needed. The kit keeps that layout.

## Tools
| Tool | Version | Where |
|---|---|---|
| git | 2.54.0 (Apple) | /usr/bin/git (Command Line Tools / Xcode) |
| uv | 0.12.13 | ~/.local/bin/uv |
| Python | 3.12.14 (uv-managed) | ~/.local/share/uv/python/cpython-3.12.14-macos-aarch64-none |
| system python3 | 3.9.6 | /usr/bin/python3 (not used for Alto) |
| node / npm | 22.23.2 / 10.9.8 | ~/.local/node/bin (nodejs.org tarball) |
| Firebase CLI | 15.30.0 | ~/.local/node/bin/firebase (npm -g) |
| gh | 2.100.0 | ~/.local/bin/gh |
| Claude app | 3.1623.4 | /Applications/Claude.app |
| Claude Code | 2.1.304, 2.1.308 | bundled: ~/Library/Application Support/Claude/claude-code/<ver> (no `claude` on PATH) |
| Xcode | 27.1 (27A9275) | /Applications/Xcode.app; xcode-select points at it |
| iOS simulators | iOS 27.0: iPhone 18 Pro, 18 Pro Max, 17e, Air, 17 | `DEVELOPER_DIR=… xcrun simctl` |
| Google Chrome | installed | browser tests launch chromium with `channel="chrome"` |
| Safari | system | Luke's real browser (WebKit checks) |

## Python environments
| Env | Location | Contents | Note |
|---|---|---|---|
| alto venv | ~/.local/share/alto/venv | mcp 1.30.0, quickjs 1.19.4, pytest 9.1.1 (+ deps) | the working Alto Python; the repo `.venv` has broken symlinks |
| pw12 (tests) | /private/tmp/claude-501/bldg/pw12 | playwright 1.64.0, pytest 9.1.1, pytest-xdist 3.8.0, pillow 13.0.0 | **fragile: /private/tmp gets cleaned.** New permanent home: ~/.local/share/alto/pw12 (built by alto-setup.sh) |
| wkvenv | ~/Desktop/Alto Development/_qa/wkvenv | playwright 1.60.0 | its WebKit build (2287) is gone; last fallback only |

Browser tests run as `PYTHONPATH=<repo>:<alto venv site-packages>:_qa/kit <pw12 python> -m pytest …`.
`chromefix.py` (now in `_qa/kit`) is a pytest plugin (`-p chromefix`) that makes every chromium launch use Chrome.

## Playwright browsers (~/Library/Caches/ms-playwright, 302 MB)
- webkit-2370 (WebKit 27.2, matches Playwright 1.64), ffmpeg-1013.
- No Playwright Chromium (Chrome is used instead). **No Firefox** installed yet; the kit adds it on a new Mac.

## Folders
| Path | Size | What |
|---|---|---|
| ~/Desktop/Alto Development/Alto Connector | — | the repo (branch `public-main` → GitHub `lukebmandel-debug/alto-connector` `main`); remote is SSH but this Mac has no SSH key, so fetch/push go over HTTPS with `gh auth git-credential` |
| ~/Desktop/Alto Development/wt-* | ~190 worktrees | one per task branch; made per task with `git worktree add`, not needed on a worker |
| ~/Desktop/Alto Development/_qa | 5.8 GB | kit (slot.sh, busy.sh, py, pwpy, lukeenv*/publicenv* env scripts, publish/release scripts, logs), backups, screens, osm, sandboxes, hosting-deletions archive, team notes, wkvenv |
| ~/Desktop/Alto Development/_cold-storage | 36 MB | archived material |
| ~/Desktop/Terrarium/Alto | 7.8 MB | CEO notes, CEO-handoff.md, post-reset-queue.md, `public/alto-cloud.js` (public web config the env scripts read) |
| ~/.claude/projects/<Terrarium-Alto project>/memory | 428 KB | Claude memory (MEMORY.md + ~60 notes) |
| ~/.claude/CLAUDE.md, settings.json | small | global instructions and settings |
| ~/Library/Application Support/Claude/side-session-notes | 373 MB | per-session notes and screenshots |
| ~/.cache/alto | 1.3 GB | city, cmap, osm, street, wikidata caches (rebuildable; tests stub the network) |
| ~/.config/alto | small | accounts.json, site.json, **session-terrarium-alto.json, mapillary-token (secrets)** |
| ~/.config/configstore/firebase-tools.json | small | **Firebase CLI login (secret)** |
| ~/.config/gh/hosts.yml | small | **gh token (secret)** |
| ~/.local/share/alto | small | venv, firebase-config.json, extension backup |
| ~/Documents/Alto, ~/Documents/Alto Home | — | local stores used by the public/luke-alto deploy envs |
| ~/Library/Application Support/Claude/Claude Extensions/local.mcpb.luke-mandel.alto | — | installed Alto extension, v1.9.139; its settings hold the encrypted firebase_config |

## Kit scripts that matter on a worker
- `slot.sh` (fair FIFO test slots, `slot.max` = 2), `busy.sh`, `py` (clean-env Python with WebKit), `pwpy` (new: picks the Playwright venv), `chromefix.py`.
- Release & Ops only (not for a worker): `lukeenv*.sh`, `publicenv*.sh`, `publish_rel.sh`, `live_release*.py`, `publish_all*.py`, `deploy_public*.py`.

## Changes IT made on this Mac (2026-10-24)
- Added `_qa/kit/pwpy`. `_qa/kit/py` now uses pwpy's pick (permanent pw12, then /private/tmp pw12, then wkvenv); old copy kept as `py.bak-wkvenv`.
- Nothing installed. `alto-setup.sh --check` lists what it would add here: the permanent pw12 venv, Firefox, kit/chromefix.py, a ~/.zprofile PATH line, and a fast-forward of public-main.

# Secrets and sign-ins for a second Alto Mac

No secret is in this kit, in git, or in any note. Each item below gets **recreated by signing in on the new Mac**
(safest) or **AirDropped** (only where a sign-in can't recreate it). Rule: only Release & Ops and IT hold deploy
credentials, so a **worker Mac needs only gh** (plus the Claude app). Everything else is optional.

| # | Item | Where on the main Mac | Worker needs it? | Safest way |
|---|---|---|---|---|
| 1 | Claude app account | Claude.app | **Yes** | Sign in on the new Mac. |
| 2 | GitHub CLI token | ~/.config/gh/hosts.yml | **Yes** (to push; cloning the public repo needs no sign-in) | `gh auth login` → GitHub.com → HTTPS → "Login with a web browser". Then `gh auth setup-git`. Don't copy hosts.yml. |
| 3 | Firebase CLI login | ~/.config/configstore/firebase-tools.json | No (deploys only) | If ever needed: `firebase login` on that Mac. Never copy the file: it holds a refresh token. |
| 4 | Alto cloud session (luke-alto) | ~/.config/alto/session-terrarium-alto.json | No (tests never use the cloud) | If needed, sign in through Alto (`sign_in` tool / Google consent) on that Mac. |
| 5 | Google sign-ins (Drive / Docs connectors, Alto Google consent) | claude.ai connectors, browser | Only for live work | Sign in on that Mac when a task asks. Luke gives Google's consents himself. |
| 6 | Mapillary token | ~/.config/alto/mapillary-token | No | Recreate from the Mapillary dashboard, or AirDrop the file into ~/.config/alto/ and `chmod 600` it. |
| 7 | Env scripts lukeenv.sh / publicenv.sh (+ numbered copies) | _qa/kit | No (Release & Ops only) | They hold **no secret values**: they read the public web config from ~/Desktop/Terrarium/Alto/public/alto-cloud.js and use the Firebase login (#3). They stay on the release Mac. |
| 8 | Alto extension settings (encrypted firebase_config) | Claude Extensions settings | No | If the extension is installed there: install the .mcpb, then re-enter its settings in the Claude app. The encrypted blob is tied to that Mac, so copying it doesn't work. |
| 9 | GitHub recovery codes | main Mac only | **Never** | Keep them in a password manager, not in a file. Never sync or AirDrop them. |
| 10 | SSH key (optional) | none (this Mac has none) | Optional | Not needed: git goes over HTTPS through gh. |

## Rules for the move
- Prefer re-login over copying. A copied token is a second live credential that nothing tracks.
- If you AirDrop a file, AirDrop it Mac→Mac directly (not through iCloud, Mail or Messages), put it in place, `chmod 600` it,
  and delete the copy from ~/Downloads.
- None of the sync options in SYNC.md may include `~/.config`, `~/.local`, recovery codes or any `*env*.sh`.

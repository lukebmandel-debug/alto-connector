# Keeping the two Macs in step: options (nothing is turned on yet)

What needs sharing, all non-secret:
- Claude memory: `~/.claude/projects/<Terrarium-Alto project>/memory` (428 KB)
- Side-session notes: `~/Library/Application Support/Claude/side-session-notes` (373 MB, mostly screenshots)
- CEO notes: `~/Desktop/Terrarium/Alto` (7.8 MB; CEO-handoff.md, post-reset-queue.md)
- `_qa` records: team notes, docs, kit scripts (not the 5.8 GB of screens/backups/osm, and never `*env*.sh`)

The code itself already syncs through GitHub. Caches (`~/.cache/alto`) and venvs are rebuilt per Mac, never synced.

## Option A — private GitHub repo for notes (recommended)
A private repo `alto-notes` holding memory, CEO notes, `_qa/team`, `_qa/docs` and the kit scripts. Each Mac keeps
its own checkout, and the folders that Claude expects become symlinks into it. A scheduled `git pull --rebase && git push`
every few minutes, plus at session end, keeps them in step.
- Pros: full history (an overwritten note can be recovered), conflicts show up instead of silently winning, works over
  any network, a `.gitignore` plus a pre-commit secret scan keeps secrets out, and it's the same tool the sessions already use.
- Cons: not instant (minutes); two Macs editing the same note at once makes a merge conflict someone has to resolve;
  side-session-notes screenshots (373 MB) are too big for git, so only their `.md` files go in.
- Risks: a secret committed by mistake goes to GitHub (mitigation: a deny-list .gitignore for `~/.config`, `*env*.sh`,
  `*token*`, `*recovery*`, plus a pre-commit grep); the repo must stay **private**.

## Option B — iCloud Drive with symlinks
Move the four folders into `~/Library/Mobile Documents/com~apple~CloudDocs/Alto-shared/` and leave symlinks at the old paths.
- Pros: no tooling, near-instant, handles the screenshots too, nothing to schedule.
- Cons: no history (a bad write syncs everywhere), "Optimize Mac Storage" can evict files so a session finds a placeholder
  instead of a note, conflicts become "file 2.md" duplicates (this is already what `slot 2.queue` looks like).
- Risks: **live lock and queue files must never be in iCloud** (slot.queue, slot.lockdir: sync lag would let two
  Macs think they hold the same slot), so `_qa/kit` stays local; Claude may not follow a symlinked memory folder in
  every version; a secret dropped into a synced folder leaves the Mac.

## Option C — one-way rsync over SSH (main Mac stays the source of truth)
After Remote Login is on, the main Mac pushes the notes to the worker (`rsync -a --delete …`) before starting a session
there, and pulls the worker's new side-session notes back when it finishes.
- Pros: simplest mental model, no cloud, no third party, nothing new on GitHub, and the worker can't overwrite memory.
- Cons: the worker's memory edits are lost unless they're pulled back; only works while both Macs are awake and on the same network.
- Risks: `--delete` in the wrong direction wipes notes (mitigation: the script always backs up to `_qa/backups` first,
  and runs only from the main Mac).

## IT recommendation
**A for memory + CEO notes + `_qa` docs, with C for side-session-note screenshots.** Avoid B for anything a lock or
queue lives in. Luke picks; IT sets it up only after that, since it moves his data.

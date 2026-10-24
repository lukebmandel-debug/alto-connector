You are setting up this Mac as Luke's second Alto worker machine, at parity with his main Mac. Work in small steps, say what you're about to do before each one, and be as efficient with usage as you can while still finishing the job.

Hard rules:
- Never type, ask for, read out, or store a password, token, or secret. Every sign-in is Luke's: give him the exact command or click path, then wait for him to say "done".
- Never deploy, publish, delete, or push anything. Don't change system or security settings yourself; Luke does those.
- Run tests only through the kit's slot.sh, with the 20-minute cap and `-k "not sound and not fleet"` (alto-setup.sh --smoke already does this). Never play sound.

Steps:
1. Repo. The code lives at `~/Desktop/Alto Development/Alto Connector` (public GitHub repo lukebmandel-debug/alto-connector).
   - If that folder is missing: `mkdir -p ~/Desktop/"Alto Development" && git clone https://github.com/lukebmandel-debug/alto-connector.git ~/Desktop/"Alto Development/Alto Connector"`, then `git -C ~/Desktop/"Alto Development/Alto Connector" checkout -B public-main origin/main`.
   - If it exists: run `git status`. If there are uncommitted changes, stop and show Luke the list before going on. Otherwise fetch from `https://github.com/lukebmandel-debug/alto-connector.git` (main and it-setup-kit).
2. Kit. Check out the setup branch in its own worktree and copy the kit into place, so the main checkout stays on public-main:
   `cd ~/Desktop/"Alto Development/Alto Connector" && git fetch https://github.com/lukebmandel-debug/alto-connector.git it-setup-kit:it-setup-kit && git worktree add ../wt-it-setup-kit it-setup-kit` (if the worktree exists already, `git -C ../wt-it-setup-kit pull --ff-only https://github.com/lukebmandel-debug/alto-connector.git it-setup-kit`), then
   `mkdir -p ../_qa/setup && cp -R ../wt-it-setup-kit/docs/machine-setup/. ../_qa/setup/`.
3. Dry run: `bash ~/Desktop/"Alto Development"/_qa/setup/alto-setup.sh --check`. Show Luke the WOULD and NEED lines in plain words, then go on unless he says stop.
4. Real run: `bash ~/Desktop/"Alto Development"/_qa/setup/alto-setup.sh` (run it in the background if it may take more than ~2 minutes; downloads take a while the first time). Re-run it after each fix until it ends with `Needs Luke/attention: 0`. For each NEED line:
   - Xcode missing or old: ask Luke to install or update it from the App Store, open it once and accept the licence.
   - xcode-select: give Luke `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer` to run himself.
   - Claude app or Google Chrome missing: ask Luke to install them (claude.ai/download, google.com/chrome).
   - GitHub: ask Luke to run `~/.local/bin/gh auth login --web --git-protocol https`, then `~/.local/bin/gh auth setup-git`.
   - Anything else: explain it in one line and ask Luke.
5. Remote Login (SSH), so the CEO on the main Mac can start Claude Code sessions here. Ask Luke to do these:
   - System Settings > General > Sharing > Remote Login: turn it on, and under "Allow access for" choose only his account.
   - Battery (or Energy) > Options: turn on "Prevent automatic sleeping when the display is off", and keep the laptop plugged in.
   Then check it yourself with `nc -z -G 2 localhost 22`, and tell Luke the address to save: `$(whoami)@$(scutil --get LocalHostName).local`.
   On the MAIN Mac, he adds that address in the Claude app (Code tab, environment picker, add an SSH connection) and approves the first connection.
6. Smoke test: `bash ~/Desktop/"Alto Development"/_qa/setup/alto-setup.sh --smoke`. It must say it passed in WebKit and Chrome.
7. Notes sync. Luke picked option A + C in `_qa/setup/SYNC.md`.
   - If gh isn't signed in yet, ask Luke to sign in (step 4). Then clone the PRIVATE notes repo: `~/.local/bin/gh repo clone alto-notes ~/Desktop/"Alto Development/alto-notes"`.
   - Run `bash ~/Desktop/"Alto Development/alto-notes/bin/notes-sync.sh" --check` and show Luke what would be copied. This laptop's notes are older, and a file is only replaced by a newer copy, so nothing newer gets lost. Notes that exist only here get added.
   - Run it for real once Luke says go. If the secret scan refuses a file, show Luke the file name only, never the matching text.
   - Tell Luke to run `notes-sync.sh` at the end of work sessions on either Mac. Screenshots come from the main Mac with `bin/notes-push-screens.sh`, which needs the SSH key step in LUKE-STEPS.md step 7, done on the main Mac.
8. Parity report. Finish with a short report Luke can paste to the CEO, covering:
   - each tool and its version versus the pins in `_qa/setup/INVENTORY.md`, with anything not matching marked;
   - the repo's branch and commit compared with GitHub main;
   - where the venvs and Playwright browsers are;
   - Xcode and the simulators;
   - which sign-ins are done and which are skipped on purpose (a worker doesn't need Firebase, the Alto cloud session, or the lukeenv/publicenv scripts);
   - the SSH address and whether it's reachable;
   - the smoke result;
   - the notes-sync result;
   - anything still open.
   Also write the report to `~/Desktop/Alto Development/_qa/setup/PARITY-REPORT.md`, and include the notes-sync result.

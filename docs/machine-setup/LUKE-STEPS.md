# Get the other laptop up to speed — your steps

About 20 minutes of your time; the script does the rest. Do them on the **other laptop** unless it says otherwise.

1. **Update macOS and Xcode.** Install the macOS updates in System Settings > General > Software Update. Then update
   Xcode in the App Store, open it once, accept the licence, and let it add the iOS platform.
2. **Install and sign in to the Claude app and Google Chrome** if they're missing (claude.ai/download, google.com/chrome).
3. **Copy the kit over:** AirDrop the folder `~/Desktop/Alto Development/_qa/setup` from this Mac to the other one,
   and put it at the same path (`~/Desktop/Alto Development/_qa/setup`). It holds no secrets.
4. **Run one command** on the other laptop:
   ```bash
   bash ~/Desktop/"Alto Development"/_qa/setup/alto-setup.sh
   ```
   It installs the tools, clones the repo, builds the test environments and browsers, and runs a short browser test.
   It will ask you to sign in to GitHub (needed to push work): run `~/.local/bin/gh auth login --web --git-protocol https`,
   then `~/.local/bin/gh auth setup-git`, and run the command again. Repeat until it ends with `Needs Luke/attention: 0`
   (each `NEED` line names the one thing to do; Remote Login is step 5).
5. **Turn on Remote Login:** System Settings > General > Sharing > Remote Login → On, "Allow access for: Only these
   users" → your account. Note the address it shows (e.g. `you@Your-Old-MacBook.local`). Keep the laptop
   plugged in, and set Battery > Options > "Prevent automatic sleeping when the display is off" to on.
6. **Save it in the Claude app (on this Mac):** in the Code tab, open the environment/location picker → Add SSH connection,
   paste the address from step 5, and approve the first connection (it asks you to trust the host key and enter your
   password on the other laptop once). Then tell the CEO it's saved, and they can start sessions there.
7. **Notes sync (you picked A + C).** On the other laptop, the setup session clones the private `alto-notes` repo and runs
   its first sync. On this Mac, once step 6 works, run these two commands so the screenshot copy can log in without a password:
   ```bash
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
   ```
   ```bash
   ssh-copy-id you@Your-Old-MacBook.local
   ```
   (Use the address from step 5. The second command asks for that laptop's password once.)

Not needed on a worker: the Firebase login, lukeenv/publicenv scripts, the Alto cloud sign-in, and the recovery codes
(see SECRETS.md). Deploys stay on this Mac.

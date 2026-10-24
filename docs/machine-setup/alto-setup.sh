#!/bin/bash
# Alto worker-Mac bootstrap (IT). Brings any Apple-silicon Mac to parity with Luke's main Alto Mac.
# Idempotent: every step checks first and only acts on what is missing or out of date.
#
#   bash alto-setup.sh            # install / update everything, then run the smoke test
#   bash alto-setup.sh --check    # dry run: report what it WOULD change, change nothing
#   bash alto-setup.sh --smoke    # only the smoke test (one fast pytest file, WebKit + Chrome)
#   bash alto-setup.sh --only venvs,browsers [--check]   # just those steps (preflight tools repo venvs browsers xcode logins remote_login smoke)
#
# Same layout as the main Mac: tools live user-local (no sudo, no Homebrew needed):
#   ~/.local/bin/{uv,gh,claude}  ~/.local/node (node + firebase CLI)  ~/.local/share/alto/{venv,pw12}
#   ~/Desktop/Alto Development/{Alto Connector,_qa/kit,_qa/setup}
# No secrets here. Sign-ins (gh, firebase, Google, Claude) are Luke's: see SECRETS.md / LUKE-STEPS.md.
set -uo pipefail

MODE=apply; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE=check ;;
    --smoke) MODE=smoke ;;
    --apply) ;;
    --only) ONLY="${2:-}"; shift ;;
    -h|--help) sed -n 2,13p "$0"; exit 0 ;;
    *) echo "usage: alto-setup.sh [--check|--smoke] [--only step,step]"; exit 2 ;;
  esac; shift
done

# Pinned to what the main Mac runs (2026-10-24, see INVENTORY.md).
PY_VER=3.12.14
NODE_VER=22.23.2
FIREBASE_VER=15.30.0
GH_VER=2.100.0
PW_VER=1.64.0
PW_PKGS="playwright==$PW_VER pytest==9.1.1 pytest-xdist==3.8.0 pillow==13.0.0"
ALTO_PKGS="mcp==1.30.0 quickjs==1.19.4 pytest==9.1.1"
REPO_SLUG=lukebmandel-debug/alto-connector

DEV="${ALTO_DEV:-$HOME/Desktop/Alto Development}"
REPO="$DEV/Alto Connector"
KIT="$DEV/_qa/kit"
SETUP="$(cd "$(dirname "$0")" && pwd)"
LOCAL="$HOME/.local"
ALTO_VENV="$LOCAL/share/alto/venv"
PW_VENV="$LOCAL/share/alto/pw12"
export PATH="$LOCAL/bin:$LOCAL/node/bin:$PATH"
XDEV=/Applications/Xcode.app/Contents/Developer

CHANGES=0; PROBLEMS=0
ok()   { printf '  ok    %s\n' "$*"; }
todo() { printf '  %s  %s\n' "$([ $MODE = check ] && echo WOULD || echo DO...)" "$*"; CHANGES=$((CHANGES+1)); }
bad()  { printf '  NEED  %s\n' "$*"; PROBLEMS=$((PROBLEMS+1)); }
run()  { [ $MODE = check ] && return 0; "$@"; }   # every changing command goes through run
step() { printf '\n== %s\n' "$*"; }

preflight() {
  step "Machine"
  [ "$(uname -s)" = Darwin ] || { echo "macOS only"; exit 1; }
  [ "$(uname -m)" = arm64 ] && ok "Apple silicon, macOS $(sw_vers -productVersion)" \
    || bad "not arm64: pinned downloads below are aarch64-only"
  command -v git >/dev/null && ok "git $(git --version | awk '{print $3}')" \
    || bad "git missing: run  xcode-select --install  (Luke, needs a click)"
  command -v curl >/dev/null || { bad "curl missing"; exit 1; }
}

tools() {
  step "Tools (user-local)"
  run mkdir -p "$LOCAL/bin"
  if command -v uv >/dev/null; then ok "uv $(uv --version | awk '{print $2}')"
  else todo "install uv (astral.sh installer into ~/.local/bin)"
       run sh -c 'curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh'; fi

  if command -v uv >/dev/null && uv python find "$PY_VER" >/dev/null 2>&1; then ok "python $PY_VER (uv-managed)"
  else todo "install python $PY_VER via uv"; run uv python install "$PY_VER"; fi

  if [ "$(node --version 2>/dev/null)" = "v$NODE_VER" ]; then ok "node $NODE_VER"
  else todo "install node $NODE_VER into ~/.local/node (now: $(node --version 2>/dev/null || echo none))"
       if [ $MODE != check ]; then
         t=$(mktemp -d); curl -fsSL "https://nodejs.org/dist/v$NODE_VER/node-v$NODE_VER-darwin-arm64.tar.gz" | tar -xz -C "$t" \
           && rm -rf "$LOCAL/node" && mv "$t/node-v$NODE_VER-darwin-arm64" "$LOCAL/node"; rm -rf "$t"; fi; fi

  if [ "$(firebase --version 2>/dev/null)" = "$FIREBASE_VER" ]; then ok "firebase CLI $FIREBASE_VER"
  else todo "npm install -g firebase-tools@$FIREBASE_VER (now: $(firebase --version 2>/dev/null || echo none))"
       run npm install -g --silent "firebase-tools@$FIREBASE_VER"; fi

  if gh --version 2>/dev/null | grep -q " $GH_VER "; then ok "gh $GH_VER"
  else todo "install gh $GH_VER into ~/.local/bin (now: $(gh --version 2>/dev/null | head -1 | awk '{print $3}' || true))"
       if [ $MODE != check ]; then
         t=$(mktemp -d); curl -fsSL -o "$t/gh.zip" "https://github.com/cli/cli/releases/download/v$GH_VER/gh_${GH_VER}_macOS_arm64.zip" \
           && unzip -q "$t/gh.zip" -d "$t" && cp "$t"/gh_*/bin/gh "$LOCAL/bin/gh"; rm -rf "$t"; fi; fi

  local bundled; bundled=$(ls -d "$HOME/Library/Application Support/Claude/claude-code/"*/ 2>/dev/null | tail -1)
  if command -v claude >/dev/null; then ok "Claude Code CLI $(claude --version 2>/dev/null | head -1)"
  elif [ -n "$bundled" ]; then ok "Claude Code $(basename "$bundled") (bundled with the Claude app)"
  else todo "install Claude Code CLI (claude.ai/install.sh; needed for SSH sessions from the Claude app)"
       run sh -c 'curl -fsSL https://claude.ai/install.sh | bash'; fi

  [ -d /Applications/Claude.app ] && ok "Claude app $(defaults read /Applications/Claude.app/Contents/Info CFBundleShortVersionString 2>/dev/null)" \
    || bad "Claude app missing: Luke installs it from claude.ai/download and signs in"
  [ -d "/Applications/Google Chrome.app" ] && ok "Google Chrome (tests launch chromium with channel=chrome)" \
    || bad "Google Chrome missing: Luke installs it from google.com/chrome (browser tests need it)"

  # PATH for new shells (Claude sessions over SSH read ~/.zshrc / ~/.zprofile)
  local line='export PATH="$HOME/.local/bin:$HOME/.local/node/bin:$PATH"'
  if grep -qsF "$line" "$HOME/.zprofile"; then ok "~/.zprofile PATH line"
  else todo "add ~/.local/bin + ~/.local/node/bin to ~/.zprofile"; run sh -c "echo '$line' >> \"\$HOME/.zprofile\""; fi
}

repo() {
  step "Repo + kit"
  run mkdir -p "$DEV/_qa"
  if [ -d "$REPO/.git" ]; then
    ok "repo at $REPO ($(git -C "$REPO" rev-parse --abbrev-ref HEAD) $(git -C "$REPO" rev-parse --short HEAD))"
    local dirty; dirty=$(git -C "$REPO" status --porcelain --untracked-files=no | wc -l | tr -d ' ')
    if [ "$dirty" != 0 ]; then bad "repo has $dirty uncommitted changes: left alone, update it by hand"
    else
      local GH='credential.helper=!gh auth git-credential' remote
      remote=$(git -C "$REPO" -c credential.helper= -c "$GH" ls-remote "https://github.com/$REPO_SLUG.git" refs/heads/main 2>/dev/null | cut -c1-7)
      if [ -z "$remote" ]; then bad "cannot reach GitHub main (gh auth login done?)"
      elif [ "$(git -C "$REPO" rev-parse --short=7 HEAD)" = "$remote" ]; then ok "repo matches GitHub main ($remote)"
      else todo "fast-forward $(git -C "$REPO" rev-parse --abbrev-ref HEAD) to GitHub main $remote (https via gh)"
         run git -C "$REPO" -c credential.helper= -c 'credential.helper=!gh auth git-credential' \
           pull -q --ff-only "https://github.com/$REPO_SLUG.git" main || bad "fast-forward failed: local commits on this branch?"
      fi
    fi
  else
    # the repo is public: cloning needs no sign-in (pushing does: gh auth login)
    todo "clone $REPO_SLUG into $REPO (branch public-main tracking main)"
    run git clone -q -b main "https://github.com/$REPO_SLUG.git" "$REPO" && run git -C "$REPO" checkout -q -B public-main
  fi
  # Worktrees are made per task by the sessions (git worktree add ../wt-<task> -b <branch>), so none are pre-made here.

  run mkdir -p "$KIT"
  local f
  for f in slot.sh busy.sh pwpy py chromefix.py; do
    if [ -e "$KIT/$f" ]; then ok "kit/$f present"
    else todo "copy kit/$f from setup/kit"; run cp -p "$SETUP/kit/$f" "$KIT/$f"; fi
  done
  [ -e "$KIT/slot.max" ] && ok "kit/slot.max = $(cat "$KIT/slot.max")" || { todo "kit/slot.max = 2"; run sh -c "echo 2 > \"$KIT/slot.max\""; }
}

venvs() {
  step "Python venvs (permanent, not /private/tmp)"
  if [ -x "$ALTO_VENV/bin/python" ] && "$ALTO_VENV/bin/python" -c "import mcp, quickjs, pytest" 2>/dev/null; then
    ok "alto venv $ALTO_VENV"
  else todo "build alto venv $ALTO_VENV ($ALTO_PKGS)"
       run uv venv -q --python "$PY_VER" "$ALTO_VENV" && run uv pip install -q --python "$ALTO_VENV/bin/python" $ALTO_PKGS; fi

  if [ -x "$PW_VENV/bin/python" ] && "$PW_VENV/bin/python" -c "import playwright, pytest, xdist, PIL" 2>/dev/null \
     && [ "$("$PW_VENV/bin/python" -c 'import importlib.metadata as m; print(m.version("playwright"))')" = "$PW_VER" ]; then
    ok "test venv $PW_VENV (Playwright $PW_VER)"
  else todo "build test venv $PW_VENV ($PW_PKGS)"
       [ -x /private/tmp/claude-501/bldg/pw12/bin/python ] && ok "(meanwhile kit/pwpy falls back to /private/tmp/claude-501/bldg/pw12)"
       run uv venv -q --python "$PY_VER" "$PW_VENV" && run uv pip install -q --python "$PW_VENV/bin/python" $PW_PKGS; fi
}

browsers() {
  step "Playwright browsers (~/Library/Caches/ms-playwright)"
  local b dirs pyx="$PW_VENV/bin/python"
  [ -x "$pyx" ] || pyx=$("$KIT/pwpy" --which 2>/dev/null) || pyx=""
  for b in webkit firefox; do
    dirs=$(ls -d "$HOME/Library/Caches/ms-playwright/$b"-* 2>/dev/null | xargs -n1 basename 2>/dev/null | tr '\n' ' ')
    if [ -n "$pyx" ] && "$pyx" -m playwright install --dry-run "$b" 2>/dev/null \
         | awk '/Install location/{print $3}' | { n=0; while read -r d; do n=1; [ -d "$d" ] || exit 1; done; [ $n = 1 ]; }; then
      ok "$b for $("$pyx" -c 'import importlib.metadata as m; print("Playwright", m.version("playwright"))') ($dirs)"
    else todo "playwright install $b (have: ${dirs:-none})"; run "$PW_VENV/bin/python" -m playwright install "$b"; fi
  done
}

xcode() {
  step "Xcode + iOS simulators"
  if [ -d "$XDEV" ]; then
    ok "$(DEVELOPER_DIR=$XDEV xcodebuild -version 2>/dev/null | tr '\n' ' ')"
    [ "$(xcode-select -p 2>/dev/null)" = "$XDEV" ] && ok "xcode-select -> Xcode" \
      || bad "xcode-select points at $(xcode-select -p 2>/dev/null): Luke runs  sudo xcode-select -s $XDEV  (or tools use DEVELOPER_DIR)"
    local n; n=$(DEVELOPER_DIR=$XDEV xcrun simctl list devices available 2>/dev/null | grep -c "iPhone")
    if [ "$n" -gt 0 ]; then ok "$n iPhone simulators ($(DEVELOPER_DIR=$XDEV xcrun simctl list runtimes 2>/dev/null | grep -o 'iOS [0-9.]*' | tr '\n' ' '))"
    else todo "download the iOS simulator platform (xcodebuild -downloadPlatform iOS, several GB)"
         run env DEVELOPER_DIR=$XDEV xcodebuild -downloadPlatform iOS; fi
  else bad "Xcode missing: Luke installs it from the App Store, opens it once to accept the licence, then reruns this"; fi
}

logins() {
  step "Sign-ins (Luke's; this only looks)"
  gh auth status >/dev/null 2>&1 && ok "gh signed in" || bad "gh: run  gh auth login  (GitHub.com, HTTPS, browser)"
  [ -s "$HOME/.config/configstore/firebase-tools.json" ] && grep -q '"user"' "$HOME/.config/configstore/firebase-tools.json" \
    && ok "firebase CLI signed in" || echo "  info  firebase: not signed in (only Release & Ops needs it; worker Macs skip)"
  [ -s "$HOME/.config/alto/session-terrarium-alto.json" ] && ok "Alto cloud session present" \
    || echo "  info  Alto cloud session absent (fine for a worker: tests never use the cloud)"
}

remote_login() {
  step "Remote Login (SSH) so the CEO can start sessions here"
  if nc -z -G 2 localhost 22 >/dev/null 2>&1; then ok "SSH is on: connect as $(whoami)@$(scutil --get LocalHostName 2>/dev/null).local"
  else bad "SSH is off: System Settings > General > Sharing > Remote Login (see LUKE-STEPS.md)"; fi
}

smoke() {
  step "Smoke test (slot.sh, 20-minute cap, WebKit + Chrome)"
  local py; py=$("$KIT/pwpy" --which 2>/dev/null) || { bad "no Playwright venv for the smoke test"; return; }
  [ -f "$REPO/tests/test_hover_lines.py" ] || { bad "repo missing tests/test_hover_lines.py"; return; }
  local name="setup-smoke-$$" site="$ALTO_VENV/lib/python3.12/site-packages" log rc
  log=$(mktemp)
  "$KIT/slot.sh" acquire "$name" && {
    ( cd "$REPO" && env -i HOME="$HOME" PATH="$PATH" PYTHONPATH="$REPO:$site:$KIT" \
        perl -e 'alarm shift; exec @ARGV' 1200 "$py" -m pytest -q -p no:cacheprovider tests/test_hover_lines.py \
        -k "not sound and not fleet" -rs ) >"$log" 2>&1; rc=$?
    "$KIT/slot.sh" release "$name"; }
  tail -4 "$log" | sed 's/^/        /'
  if [ "${rc:-1}" = 0 ] && ! grep -qE "SKIPPED.*(no webkit|no chromium)" "$log"; then ok "smoke test passed in WebKit and Chrome ($py)"
  else bad "smoke test failed or skipped a browser (log: $log)"; fi
}

echo "Alto setup — mode: $MODE — $(date '+%Y-%m-%d %H:%M')"
if [ -n "$ONLY" ]; then for f in ${ONLY//,/ }; do "$f"; done
elif [ $MODE = smoke ]; then smoke
else
  preflight; tools; repo; venvs; browsers; xcode; logins; remote_login
  if [ $MODE = apply ]; then smoke; else echo; echo "(--check: smoke test not run; use --smoke)"; fi
fi
echo
if [ $MODE = check ]; then echo "Would change: $CHANGES   Needs Luke/attention: $PROBLEMS   (nothing was changed)"
else echo "Steps acted on: $CHANGES   Needs Luke/attention: $PROBLEMS"; fi
[ $PROBLEMS = 0 ]

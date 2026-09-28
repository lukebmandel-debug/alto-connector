"""set_up_site: give a new user their own Alto site with nothing to do by hand.

What a person used to do from the README — create a Firebase project, add a
site, turn on Firestore and Google sign-in, deploy the security rules, install
Node and the Firebase CLI, log it in, paste three settings — Alto now does
itself, in the user's own Google account:

  tools     Node (official build, pinned SHA-256) + firebase-tools (pinned),
            into Alto's own folder. Nothing global, nothing that needs admin.
  login     `firebase login` under a pseudo-terminal, so the CLI runs its
            browser flow: the user clicks Allow once and it finishes by
            itself. Its credentials live in Alto's folder, never in a
            developer's own ~/.config/configstore.
  project   `projects:create <slug>-alto-<rand>`. Its DEFAULT hosting site is
            <project>.web.app, which Firebase authorizes for Google sign-in
            automatically — no authorized-domains step.
  app       a web app "Alto" and its public SDK config.
  firestore the (default) database.
  auth      Google sign-in, through `deploy --only auth` (Firebase's own
            provisioning API — no console toggle).
  deploy    the site shell (/, /connect/, /pv/, /s/) and firestore.rules,
            BEFORE anyone signs in — so /connect/ exists when sign_in needs it.
  verify    the live site answers, and Firestore refuses anonymous reads of
            users/ and a listing of shares/ (the same probes that check
            luke-alto): rules that are not live fail the setup.
  sign_in   the connector signs in as the user on their new /connect/ page.
  migrate   drafts kept in the local folder are copied into the account.

Each step is idempotent and its result is saved to site.json as it lands, so
an interrupted setup resumes where it stopped. The work runs on a background
thread: the tool returns at once with where it has got to, and the model
calls it again later — the interview goes on in the meantime.

Every external effect goes through `self.run` (the CLI), `self.http` (plain
GETs) or `self.opener` (the browser), so the whole machine is testable with
fakes (tests/test_set_up_site.py).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

from . import site as site_rec

NODE_VERSION = "22.23.2"
NODE_SHA256 = {
    "darwin-arm64": "61130f394c1630d211dd50aecc4353d379480f36d3ac913cd85dbba1aed585c6",
    "darwin-x64": "58e99022c2ff89395576cc7fd4d98cea24bb68081475d5f88b801ee8729fb026",
    "win-x64": "1177b4137ba5adaa56354ae40f1080c7450e8ae09cecb47da459d1c52ac99f97",
}
FIREBASE_TOOLS = "15.31.0"
FIRESTORE_LOCATION = "nam5"

# States the tool reports. WAITING_* need the person (a browser click);
# everything else is Alto working or done.
WORKING = "working"
WAITING_GOOGLE = "waiting_for_google"      # CLI consent screen
WAITING_SIGN_IN = "waiting_for_sign_in"    # Continue with Google on /connect/
NEEDS_BROWSER = "needs_browser_step"       # a Google terms page, etc.
NEEDS_CODE = "needs_code"                  # Windows: paste the CLI's code
READY = site_rec.READY
FAILED = "error"


class StepError(RuntimeError):
    def __init__(self, msg: str, status: str = FAILED, url: str = ""):
        super().__init__(msg)
        self.status, self.url = status, url


# ── where Alto keeps its own tools ──────────────────────────────────────────

def tools_dir() -> Path:
    override = os.environ.get("ALTO_TOOLS_DIR")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Alto" / "tools"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Alto" / "tools"
    return Path.home() / ".local" / "share" / "alto" / "tools"


def node_platform() -> str:
    m = platform.machine().lower()
    if sys.platform == "darwin":
        return "darwin-arm64" if m in ("arm64", "aarch64") else "darwin-x64"
    if os.name == "nt":
        return "win-x64"
    raise StepError("Alto can set up a site automatically on macOS and "
                    "Windows; on this system use the manual steps in the README")


def managed_node() -> Path | None:
    """Alto's own node, if it has installed one (also used by the JS gate)."""
    d = tools_dir() / "node"
    p = d / ("node.exe" if os.name == "nt" else "bin/node")
    return p if p.exists() else None


def wrapper_path() -> Path:
    return tools_dir() / ("firebase.cmd" if os.name == "nt" else "firebase")


# ── the provisioner ─────────────────────────────────────────────────────────

def _http_get(url: str, timeout: float = 20) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "Alto"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, OSError):
        return 0


def _api(method: str, url: str, body, token: str, timeout: float = 60):
    """One Google API call with a bearer token: (status, parsed JSON)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
        "User-Agent": "Alto"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}


def _download(url: str, timeout: float = 300) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Alto"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _json_out(out: str):
    """The CLI prints spinner lines before its --json document."""
    i = out.find("{")
    if i < 0:
        raise ValueError("no JSON in output")
    return json.loads(out[i:])


class Provisioner:
    def __init__(self, run=None, http=None, opener=None, download=None,
                 login=None, session_factory=None, deploy=None, migrate=None,
                 sleep=time.sleep, api=None):
        self.run = run or self._run_cli
        self.http = http or _http_get
        self.opener = opener or webbrowser.open
        self.download = download or _download
        self.api = api or _api
        self.login_starter = login or self._start_login_pty
        self.session_factory = session_factory
        self.deploy = deploy
        self.migrate = migrate
        self.sleep = sleep
        self.state = site_rec.load()
        if self.state.get("status") in (WORKING, WAITING_GOOGLE, WAITING_SIGN_IN):
            # Left mid-run by an earlier process: nothing is waiting on that
            # link any more. set_up_site resumes from the last finished step.
            self.state.update(status="paused", url="", message=(
                "Setting up the site was interrupted; call set_up_site to "
                "carry on from where it stopped."))
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._login_proc = None
        self._session = None

    # ── public face ─────────────────────────────────────────────────────────
    def status(self) -> dict:
        s = self.state
        out = {"status": s.get("status") or "not_started",
               "step": s.get("step", "")}
        for k in ("url", "message", "site_url", "project", "email", "migrated"):
            if s.get(k):
                out[k] = s[k]
        return out

    def kick(self, code: str = "", adopt: tuple[str, str] | None = None) -> None:
        """Start (or resume) the background run unless one is going. `adopt`
        (site, project) finishes setting up a project the user named in the
        settings instead of creating one."""
        if code:
            self.state["auth_code"] = code
        if adopt and not self.state.get("project"):
            self.state.update(site=adopt[0], project=adopt[1], adopted=True)
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            if self.state.get("status") == READY and site_rec.ready(self.state):
                return
            self._thread = threading.Thread(target=self._drive, daemon=True)
            self._thread.start()

    def wait(self, seconds: float) -> dict:
        """Return as soon as the person is needed, the run ends, or `seconds`
        pass — whichever is first."""
        end = time.time() + seconds
        while time.time() < end:
            if self.state.get("status") in (WAITING_GOOGLE, WAITING_SIGN_IN,
                                            NEEDS_BROWSER, NEEDS_CODE, READY,
                                            FAILED):
                break
            if not (self._thread and self._thread.is_alive()):
                break
            time.sleep(0.2)
        return self.status()

    # ── the run ─────────────────────────────────────────────────────────────
    STEPS = ("tools", "login", "project", "app", "apis", "firestore", "auth",
             "deploy", "verify", "sign_in", "migrate")

    def _set(self, **kw) -> None:
        self.state.update(kw)
        site_rec.save({k: v for k, v in self.state.items() if k != "auth_code"})

    def _drive(self) -> None:
        try:
            for step in self.STEPS:
                if step in self.state.get("done", []):
                    continue
                self._set(status=WORKING, step=step, url="", message="")
                getattr(self, "_" + step)()
                self._set(done=self.state.get("done", []) + [step])
            site_rec.apply(self.state)
            self._set(status=READY, step="", url="", site_url=self._site_url(),
                      message=("Your private Alto site is ready at "
                               f"{self._site_url()} — timelines publish there, "
                               "and only your Google account can open them."))
        except StepError as e:
            self._set(status=e.status, url=e.url, message=str(e))
        except Exception as e:                    # noqa: BLE001 — reported, resumable
            self._set(status=FAILED, message=f"{type(e).__name__}: {e}")

    def _site_url(self) -> str:
        return f"https://{self.state.get('site', '')}.web.app"

    # ── CLI plumbing ────────────────────────────────────────────────────────
    def _run_cli(self, args: list[str], timeout: float = 300):
        fb = self.state.get("firebase_bin") or str(wrapper_path())
        # From Alto's own folder: a failing CLI call writes firebase-debug.log
        # into its working directory, which must not be the user's.
        work = tools_dir()
        work.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([fb, *args], capture_output=True, text=True,
                           timeout=timeout, stdin=subprocess.DEVNULL, cwd=work)
        return r.returncode, r.stdout, r.stderr

    def _cli_json(self, args: list[str], timeout: float = 300):
        rc, out, err = self.run([*args, "--json", "--non-interactive"], timeout)
        try:
            doc = _json_out(out)
        except ValueError:
            doc = {"status": "error", "error": (err or out)[-600:]}
        if rc != 0 or doc.get("status") != "success":
            return None, str(doc.get("error") or err or out)[-800:]
        return doc.get("result"), ""

    # ── steps ───────────────────────────────────────────────────────────────
    def _tools(self) -> None:
        if self.state.get("firebase_bin") and Path(self.state["firebase_bin"]).exists():
            return
        plat = node_platform()
        root = tools_dir()
        root.mkdir(parents=True, exist_ok=True)
        node_dir = root / "node"
        if managed_node() is None:
            ext = "zip" if plat.startswith("win") else "tar.gz"
            name = f"node-v{NODE_VERSION}-{plat}"
            data = self.download(f"https://nodejs.org/dist/v{NODE_VERSION}/{name}.{ext}")
            if hashlib.sha256(data).hexdigest() != NODE_SHA256[plat]:
                raise StepError("the Node download did not match its published "
                                "checksum, so it was not used; try again")
            tmp = root / "node.partial"
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir()
            if ext == "zip":
                zipfile.ZipFile(io.BytesIO(data)).extractall(tmp)
            else:
                with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
                    t.extractall(tmp, filter="data")
            shutil.rmtree(node_dir, ignore_errors=True)
            (tmp / name).rename(node_dir)
            shutil.rmtree(tmp, ignore_errors=True)
        node = managed_node()
        npm = (node_dir / "node_modules" / "npm" / "bin" / "npm-cli.js"
               if os.name == "nt" else
               node_dir / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js")
        fb_dir = root / "firebase-tools"
        fb_js = fb_dir / "node_modules" / "firebase-tools" / "lib" / "bin" / "firebase.js"
        if not fb_js.exists():
            r = subprocess.run(
                [str(node), str(npm), "install", "--prefix", str(fb_dir),
                 f"firebase-tools@{FIREBASE_TOOLS}", "--no-audit", "--no-fund",
                 "--omit=dev", "--loglevel=error"],
                capture_output=True, text=True, timeout=900,
                env={**os.environ, "PATH": f"{node.parent}{os.pathsep}{os.environ.get('PATH', '')}"})
            if r.returncode != 0 or not fb_js.exists():
                raise StepError("installing the Firebase CLI failed: "
                                + (r.stderr or r.stdout)[-600:])
        cfg = root / "config"
        cfg.mkdir(exist_ok=True)
        w = wrapper_path()
        if os.name == "nt":
            w.write_text(f'@echo off\r\nset "XDG_CONFIG_HOME={cfg}"\r\n'
                         f'"{node}" "{fb_js}" %*\r\n', encoding="utf-8")
        else:
            w.write_text("#!/bin/sh\n"
                         "# Alto's own Firebase CLI: its login is kept in Alto's folder.\n"
                         f"export XDG_CONFIG_HOME='{cfg}'\n"
                         f"export PATH='{node.parent}':\"$PATH\"\n"
                         f"exec '{node}' '{fb_js}' \"$@\"\n", encoding="utf-8")
            w.chmod(0o755)
        self._set(firebase_bin=str(w))

    def _logged_in_email(self) -> str:
        res, _ = self._cli_json(["login:list"], 60)
        for acct in res or []:
            email = ((acct or {}).get("user") or {}).get("email")
            if email:
                return email
        return ""

    def _login(self) -> None:
        email = self._logged_in_email()
        if email:
            self._set(email=email)
            return
        if self.state.get("auth_code"):
            # Without a terminal the CLI runs its copy-a-code flow; the code
            # completes the login it started in _code_url.
            rc, out, err = self.run(["login", self.state.pop("auth_code")], 120)
            email = self._logged_in_email()
            if not email:
                raise StepError("that code did not sign the Firebase CLI in; "
                                "open the link again for a fresh one",
                                NEEDS_CODE, self.state.get("url", ""))
            self._set(email=email)
            return
        url, done = self.login_starter()
        if url is None:                     # no pseudo-terminal (Windows)
            raise StepError(
                "Sign in to Google at this link, then paste the code it shows "
                "back into the chat.", NEEDS_CODE, self._code_url())
        try:
            self.opener(url)
        except Exception:                   # noqa: BLE001 — the URL is shown anyway
            pass
        self._set(status=WAITING_GOOGLE, url=url, message=(
            "A Google page is open in your browser: click Allow so Alto can "
            "create your own free Firebase project (only yours; nothing is "
            "billed). This continues by itself afterwards."))
        deadline = time.time() + 900
        while time.time() < deadline and not done():
            self.sleep(1)
        email = self._logged_in_email()
        if not email:
            said = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", bytes(
                getattr(self, "_login_tail", b"")).decode("utf-8", "replace"))
            said = " ".join(l.strip() for l in said.splitlines()
                            if "rror" in l)[-300:]
            raise StepError(
                "Google sign-in for the Firebase CLI did not finish"
                + (f" ({said})" if said else "") + ". If a page from an "
                "earlier attempt was used, close it; call set_up_site again "
                "for a fresh one")
        self._set(email=email, status=WORKING, url="", message="")

    def _code_url(self) -> str:
        rc, out, err = self.run(["login"], 20)
        m = re.search(r"https://\S+", out or "")
        return m.group(0) if m else "https://auth.firebase.tools/login"

    def _start_login_pty(self):
        """Run `firebase login` under a pseudo-terminal (its browser flow only
        runs interactively), answer its opt-in questions "no", and hand back
        the Google URL and a `done()` probe. None on systems without pty."""
        try:
            import pty
            import select
        except ImportError:
            return None, None
        fb = self.state.get("firebase_bin") or str(wrapper_path())
        # The CLI would `open` the page itself as well, and the person would
        # get two identical Google tabs; Alto opens it once, and reports it in
        # case nothing could be opened. So the CLI finds a stub `open` that
        # does nothing. (Taking `open` off PATH instead crashes the CLI:
        # "spawn open ENOENT".)
        stub = tools_dir() / "noopen"
        stub.mkdir(parents=True, exist_ok=True)
        (stub / "open").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (stub / "open").chmod(0o755)
        env = {**os.environ, "TERM": "dumb",
               "PATH": f"{stub}{os.pathsep}{os.environ.get('PATH', '')}"}
        pid, fd = pty.fork()
        if pid == 0:                                     # child
            try:
                os.chdir(tools_dir())
                os.execve(fb, [fb, "login"], env)
            finally:
                os._exit(127)
        buf, url, answered = b"", None, 0
        end = time.time() + 60
        while time.time() < end and url is None:
            r, _, _ = select.select([fd], [], [], 0.5)
            if not r:
                continue
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            asks = buf.count(b"(Y/n)") + buf.count(b"(y/N)")
            if asks > answered:
                time.sleep(0.2)
                os.write(fd, b"n\r")
                answered = asks
            m = re.search(rb"https://accounts\.google\.com/\S+", buf)
            if m:
                url = m.group(0).decode()
        if url is None:
            raise StepError("the Firebase CLI did not start its Google sign-in")

        tail = bytearray(buf[-2000:])

        def reader():
            while True:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                tail.extend(chunk)
                del tail[:-2000]
        self._login_tail = tail
        threading.Thread(target=reader, daemon=True).start()
        self._login_proc = pid
        # A login still waiting when Claude quits must not outlive it (it
        # holds localhost:9005, and the next setup would start another).
        import atexit
        import signal
        atexit.register(lambda: _kill(pid, signal.SIGTERM))

        def done() -> bool:
            try:
                p, _ = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                return True
            return p != 0
        return url, done

    def _slug(self) -> str:
        who = (self.state.get("email") or "my").split("@")[0].lower()
        who = re.sub(r"[^a-z0-9]+", "-", who).strip("-") or "my"
        if not who[0].isalpha():
            who = "a-" + who
        return who[:14].strip("-")

    def _project(self) -> None:
        if self.state.get("project"):
            pid = self.state["project"]
            res, _ = self._cli_json(["projects:list"], 120)
            if any((p or {}).get("projectId") == pid for p in res or []):
                return
            # The Cloud project exists but Firebase was never added to it.
            res, err = self._cli_json(["projects:addfirebase", pid], 300)
            if res is None and "already" not in err.lower():
                raise StepError(f"adding Firebase to {pid} failed: {err}")
            return
        last = ""
        for _ in range(5):
            pid = f"{self._slug()}-alto-{secrets.token_hex(2)}"
            res, err = self._cli_json(
                ["projects:create", pid, "--display-name", "Alto"], 600)
            if res is not None:
                self._set(project=pid, site=pid)
                return
            last = err
            low = err.lower()
            if "terms of service" in low or "tos" in low.split():
                raise StepError(
                    "Google needs you to accept the Firebase terms once. The "
                    "page is open; accept them, then say done.",
                    NEEDS_BROWSER, "https://console.firebase.google.com/")
            if "quota" in low or "exceeded" in low:
                raise StepError("this Google account has reached its limit on "
                                "new Cloud projects: " + err)
            if "already" not in low and "exists" not in low:
                break
        raise StepError(f"creating your Firebase project failed: {last}")

    def _app(self) -> None:
        pid = self.state["project"]
        apps, err = self._cli_json(["apps:list", "WEB", "--project", pid], 120)
        if apps is None:
            raise StepError(f"listing the project's apps failed: {err}")
        app = next((a for a in apps if a.get("displayName") == "Alto"), None)
        if app is None:
            app, err = self._cli_json(["apps:create", "WEB", "Alto",
                                       "--project", pid], 300)
            if app is None:
                raise StepError(f"creating the web app failed: {err}")
        res, err = self._cli_json(["apps:sdkconfig", "WEB", app["appId"],
                                   "--project", pid], 120)
        cfg = (res or {}).get("sdkConfig") or {}
        if not cfg.get("apiKey"):
            raise StepError(f"reading the web app's config failed: {err}")
        keep = ("apiKey", "authDomain", "projectId", "storageBucket",
                "messagingSenderId", "appId", "measurementId")
        self._set(app_id=app["appId"],
                  config={k: cfg[k] for k in keep if cfg.get(k)})

    # A new project has these switched off, and the CLI turns on only some of
    # them itself (firestore:databases:create does not: 403 "Cloud Firestore
    # API has not been used in project … before or it is disabled").
    APIS = ("firestore.googleapis.com", "firebaserules.googleapis.com",
            "identitytoolkit.googleapis.com", "firebasehosting.googleapis.com")

    def _token(self) -> str:
        """The CLI's own access token, refreshed by a cheap authenticated
        call first. Read from the CLI's config store: Alto's (a managed CLI)
        or the user's."""
        self._cli_json(["projects:list"], 120)          # refreshes if stale
        fb = self.state.get("firebase_bin") or ""
        cfg = (tools_dir() / "config" if fb == str(wrapper_path()) else
               Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"))
        try:
            d = json.loads((cfg / "configstore" / "firebase-tools.json")
                           .read_text(encoding="utf-8"))
            return (d.get("tokens") or {}).get("access_token", "")
        except (OSError, ValueError):
            return ""

    def _apis(self) -> None:
        pid = self.state["project"]
        token = self._token()
        if not token:
            raise StepError("could not read the Firebase CLI's sign-in to "
                            "switch on your project's services")
        base = "https://serviceusage.googleapis.com/v1"
        code, op = self.api("POST", f"{base}/projects/{pid}/services:batchEnable",
                            {"serviceIds": list(self.APIS)}, token)
        if code != 200:
            raise StepError(f"switching on your project's services failed "
                            f"(HTTP {code}): {str(op)[:400]}")
        for _ in range(60):
            if (op or {}).get("done"):
                if op.get("error"):
                    raise StepError("switching on your project's services "
                                    f"failed: {op['error']}")
                break
            self.sleep(3)
            code, op = self.api("GET", f"{base}/{op['name']}", None, token)
        else:
            raise StepError("switching on your project's services timed out; "
                            "call set_up_site again")

    def _firestore(self) -> None:
        pid = self.state["project"]
        dbs, err = self._cli_json(["firestore:databases:list", "--project", pid], 120)
        if dbs is not None and any(str(d.get("name", "")).endswith("/(default)")
                                   for d in dbs):
            return
        for attempt in range(6):
            res, err = self._cli_json(["firestore:databases:create", "(default)",
                                       "--location", FIRESTORE_LOCATION,
                                       "--project", pid], 600)
            if res is not None or "already exists" in err.lower():
                return
            # A just-enabled API takes a minute or two to be usable.
            if "has not been used" not in err and "disabled" not in err:
                break
            self.sleep(20)
        raise StepError(f"creating Firestore failed: {err}")

    def _auth(self) -> None:
        pid = self.state["project"]
        work = tools_dir() / "deploy-auth"
        work.mkdir(parents=True, exist_ok=True)
        (work / "firebase.json").write_text(json.dumps({"auth": {"providers": {
            # No authorizedRedirectUris: the provisioning API adds the
            # project's own firebaseapp.com handler itself, and naming it again
            # is refused ("OAuth 2 redirect URLs have duplicate").
            "googleSignIn": {
                "oAuthBrandDisplayName": "Alto",
                "supportEmail": self.state.get("email", "")}}}}))
        rc, out, err = self.run(["deploy", "--only", "auth", "--project", pid,
                                 "--non-interactive", "--config",
                                 str(work / "firebase.json")], 600)
        if rc != 0:
            raise StepError("turning on Google sign-in failed: "
                            + (err or out)[-600:])

    def _deploy(self) -> None:
        pid = self.state["project"]
        sites, err = self._cli_json(["hosting:sites:list", "--project", pid], 120)
        names = [s.get("name", "").rsplit("/", 1)[-1]
                 for s in (sites or {}).get("sites", [])]
        if self.state["site"] not in names:
            res, err = self._cli_json(["hosting:sites:create", self.state["site"],
                                       "--project", pid], 300)
            if res is None and "already" not in err.lower():
                raise StepError(f"creating your site failed: {err}")
        site_rec.apply(self.state, partial=True)
        (self.deploy or _deploy_shell)()

    def _verify(self) -> None:
        pid, url = self.state["project"], self._site_url()
        docs = (f"https://firestore.googleapis.com/v1/projects/{pid}"
                "/databases/(default)/documents")
        checks = {f"{url}/connect/": 200, f"{docs}/users": 403,
                  f"{docs}/shares": 403}
        bad = []
        for _ in range(12):                     # CDN / rules propagation
            bad = [f"{u} → {got} (expected {want})"
                   for u, want in checks.items()
                   if (got := self.http(u)) != want]
            if not bad:
                self._set(verified_at=time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                    time.gmtime()))
                return
            self.sleep(10)
        raise StepError("your site is up but did not pass its safety check: "
                        + "; ".join(bad))

    def _sign_in(self) -> None:
        from .session import Session, set_session
        s = self._session or (self.session_factory or Session)(self.state["config"])
        self._session = s
        if s.signed_in:
            set_session(s)
            return
        p = s.start(self._site_url())
        self._set(status=WAITING_SIGN_IN, url=p["url"], message=(
            "Last step: on your new Alto site, click Continue with Google. "
            "That connects Alto on this computer to your own account."))
        deadline = time.time() + 900
        while time.time() < deadline and not s.signed_in:
            if p.get("error"):
                raise StepError("sign-in did not complete: " + p["error"])
            self.sleep(1)
        if not s.signed_in:
            raise StepError("sign-in was not finished; call set_up_site again")
        set_session(s)
        self._set(status=WORKING, url="", message="")

    def _migrate(self) -> None:
        n = (self.migrate or _migrate_local)(self._session)
        self._set(migrated=n)


def _kill(pid: int, sig: int) -> None:
    try:
        os.kill(pid, sig)
    except OSError:
        pass


# ── defaults wired to the rest of Alto ──────────────────────────────────────

def _deploy_shell() -> None:
    """The site before any timeline: homepage, /connect/, /pv/, /s/ + rules."""
    from ..mcp_server import get_store, uid
    from ..publish_static import deploy_site, regenerate_site
    deploy_site(regenerate_site(get_store(), uid()))


def _migrate_local(session) -> dict:
    """Copy what the local folder holds into the new account, then switch the
    connector to it. Copies, never deletes; skips anything already there."""
    from .. import mcp_server as srv
    from ..migrate import _uids, copy
    from ..store.cloud import CloudStore
    from ..store.local import LocalStore
    root = Path(srv.store_dir())
    local = LocalStore(root)
    cloud = CloudStore(session, local)
    total = {"projects": 0, "timelines": 0, "nodes": 0, "skipped": 0}
    if root.is_dir():
        for u in _uids(root):
            if u == session.uid:
                continue
            n = copy(local, u, cloud, session.uid, local, log=lambda *_: None)
            for k in total:
                total[k] += n[k]
    srv.set_store(None)                 # the next call sees the cloud store
    return total


_PROVISIONER: Provisioner | None = None


def get_provisioner() -> Provisioner:
    global _PROVISIONER
    if _PROVISIONER is None:
        _PROVISIONER = Provisioner()
    return _PROVISIONER


def set_provisioner(p: Provisioner | None) -> None:
    global _PROVISIONER
    _PROVISIONER = p

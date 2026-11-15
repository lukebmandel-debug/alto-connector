"""Hosted Bass: what Luke needs, after a build, to SEE the timeline on luke-alto (alto/bass/hosted.py is the gate in front of this).

luke-alto's homepage lists users/{uid}/pagemeta and opens users/{uid}/pages/{key} in its private shell (/pv/{key}/). A draft in alto_timelines
alone is not enough: it is the same step as publish_timeline 'private-web' that puts the page and its list entry there. Bass's belt never
offers publish_timeline (NEVER_OFFERED), and that stays. This subclass does the one private-web step server-side, for the ONE pinned uid, right
after a successful build_timeline: same primitives as mcp_server._publish_to_account (private_page, engine_stamp, put_page), and nothing else:
no share, no public link, no deploy of any site. Rebuilding the same timeline reuses its private_key, so the page is updated in place."""
from __future__ import annotations

import json
import shutil

from .tools import ToolBox, ToolOutcome


class HostedToolBox(ToolBox):
    def __init__(self, store, pinned_uid: str, **kw):
        super().__init__(store, **kw)
        self.pinned = pinned_uid

    def execute(self, uid: str, name: str, tool_input) -> ToolOutcome:
        out = super().execute(uid, name, tool_input)
        if name != "build_timeline" or out.is_error or uid != self.pinned:
            return out
        try:
            res = json.loads(out.content)
        except ValueError:
            return out
        if not isinstance(res, dict) or res.get("error"):
            return out
        tid = tool_input.get("timeline_id", "")
        try:
            res["on_homepage"] = self._publish_private(uid, tid)
        except Exception as e:                                    # noqa: BLE001 - the build stands; say what is missing
            res["on_homepage"] = False
            res["homepage_error"] = f"{type(e).__name__}: {e}"[:300]
        finally:
            self._drop_artifacts(uid, tid)
        res.pop("offline_path", None)                              # a path on the function's scratch disk means nothing to Luke
        if res["on_homepage"]:
            res["note"] = "The timeline is on your homepage now: open it from the list there. It is private to your account."
            res["next"] = "tell the user it is on their homepage"
        else:
            res.pop("homepage_error", None)                        # no internals in what the user is told
            res["note"] = "The timeline was built, but it could not be added to your homepage."
            res["next"] = ("tell the user plainly that it was built but could not be added to their homepage; "
                           "do not say it is on the homepage; they can ask for the build again")
        return ToolOutcome(json.dumps(res, default=str, ensure_ascii=False), False, out.wrote, out.name, out.final)

    def _publish_private(self, uid: str, tid: str) -> bool:
        from .. import mcp_server as srv
        from ..build.engine_stamp import stamp as engine_stamp
        from ..build.private_shell import MAX_PAGE_BYTES, stored_bytes
        from ..build.single_file import private_page
        from ..cloud.meta import meta_of, title_of
        st = self.store
        tok = srv.current_uid.set(uid)
        try:
            doc = st.get_timeline(uid, tid)
            raw = st.get_artifact(uid, tid, "timeline.html")
            if not doc or not raw:
                raise RuntimeError("the built page is missing")
            b, _, _ = srv.load_brief({"brief": doc["brief"]})
            names = {p["project_id"]: p["name"] for p in st.list_projects(uid)}
            page = engine_stamp(private_page(b, raw, names.get(doc.get("project_id", ""), "")))
            if stored_bytes(page) > MAX_PAGE_BYTES:
                raise RuntimeError("the page is over the size a private page can be")
            key = doc.get("private_key") or srv._private_key()
            st.put_page(uid, key, page, title_of(page), {**meta_of(page), "added": srv._added_epoch(doc)})
            doc.update({"private_key": key, "status": "published", "visibility": "private-web",
                        "urls": {"note": "Private to this account: only the owner's Google sign-in opens it, from the homepage."}})
            st.put_timeline(uid, tid, doc)
            return True
        finally:
            srv.current_uid.reset(tok)

    def _drop_artifacts(self, uid: str, tid: str) -> None:
        try:
            shutil.rmtree(self.store.local._p(uid, "timelines", tid, "artifacts", mkdir=False), ignore_errors=True)
        except Exception:                                          # noqa: BLE001 - scratch only
            pass

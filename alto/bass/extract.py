"""Upload text extraction for the Bass proxy (bench-tl-1 job, CEO-approved 2026-10-30).

The Bass page sends a PDF / .docx as a material {name, kind, text: "", file_b64}. Here, BEFORE anything is held or sent upstream, the file
becomes text: .txt/.md/etc. need nothing (the page already read them); PDF -> pypdf text only (never a native PDF block to Claude: page
images would blow the per-action cap); .docx -> stdlib zipfile + xml, document.xml text only. The upload is untrusted, so:

  checked BEFORE parsing   base64 shape, raw size per file and in total, file count, magic bytes vs the file name, a PDF's page count
  .docx guard              member count (from the end record), declared + compressed ratio, a hard byte limit when reading document.xml,
                           no DOCTYPE / ENTITY, element and depth caps, never extractall
  where it runs            a child process (extract_worker.py) with a deadline for the whole request, CPU / memory / file-size limits; a
                           timeout kills it and is a failure
  after                    extracted-text cap (too long = refused, not silently cut), no selectable text = refused

Every failure is a code in POLICIES (upload_*), fails closed, and costs nothing: the caller has not held or called anything. Nothing here
logs content, names or sizes. All numbers are BetaConfig values.
"""
from __future__ import annotations

import base64
import binascii
import json
import subprocess
import sys
import time
from pathlib import Path

from .beta_config import BetaConfig

WORKER = Path(__file__).with_name("extract_worker.py")
_REASON = {"pages": "upload_too_many_pages", "encrypted": "upload_encrypted", "unreadable": "upload_unreadable",
           "too_long": "upload_too_long", "no_text": "upload_no_text", "bomb": "upload_unreadable"}
KINDS = {".pdf": ("pdf", b"%PDF"), ".docx": ("docx", b"PK\x03\x04")}


class UploadRefused(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def limits(cfg: BetaConfig) -> dict:
    return {"pdf_max_pages": cfg.pdf_max_pages, "max_chars": cfg.extract_max_chars, "min_chars": cfg.extract_min_chars,
            "docx_max_members": cfg.docx_max_members, "docx_max_uncompressed": cfg.docx_max_uncompressed_bytes,
            "docx_max_ratio": cfg.docx_max_ratio, "docx_xml_max_bytes": cfg.docx_xml_max_bytes,
            "docx_max_depth": cfg.docx_max_depth, "docx_max_elements": cfg.docx_max_elements,
            "cpu_s": max(2, int(cfg.extract_timeout_s) + 1), "mem_bytes": cfg.extract_mem_bytes}


def subprocess_runner(kind: str, data: bytes, lim: dict, timeout: float, cmd=None) -> dict:
    """Runs the worker on `data`; any trouble (timeout, crash, junk output, output too big) is a refusal."""
    cmd = list(cmd) if cmd else [sys.executable, "-I", str(WORKER), kind, json.dumps(lim)]
    try:
        done = subprocess.run(cmd, input=data, capture_output=True, timeout=max(0.1, timeout), check=False,
                              env={"PYTHONIOENCODING": "utf-8"}, cwd="/")
    except subprocess.TimeoutExpired:                                     # run() has already killed the child
        return {"ok": False, "code": "unreadable"}
    except Exception:
        return {"ok": False, "code": "unreadable"}
    if len(done.stdout) > lim["max_chars"] * 4 + 4096:
        return {"ok": False, "code": "unreadable"}
    try:
        res = json.loads(done.stdout.decode("utf-8"))
        return res if isinstance(res, dict) else {"ok": False, "code": "unreadable"}
    except Exception:
        return {"ok": False, "code": "unreadable"}


class Extractor:
    def __init__(self, cfg: BetaConfig, runner=None, clock=time.monotonic, worker_cmd=None):
        self.cfg, self.clock = cfg, clock                                 # worker_cmd: tests point the real subprocess path at a stand-in
        self.runner = runner or (lambda kind, data, lim, t: subprocess_runner(kind, data, lim, t, worker_cmd))

    def prepare(self, materials) -> None:
        """Turns every uploaded file in `materials` (a list the caller owns) into text, IN PLACE: the file bytes are dropped, `text` is the
        extraction. Raises UploadRefused(code). Materials with no file are left alone, except a file the page flagged `needs_extraction`
        that arrived without its bytes (too big for the page, or an old page): refused, since there would be nothing to build from."""
        if not isinstance(materials, list):
            return
        cfg = self.cfg
        files = [m for m in materials if isinstance(m, dict) and m.get("file_b64") is not None]
        if len(files) > cfg.upload_max_files:
            raise UploadRefused("upload_too_big")
        for m in materials:
            if isinstance(m, dict) and m.get("file_b64") is None and m.get("needs_extraction") and not str(m.get("text") or "").strip():
                raise UploadRefused("upload_unreadable")
        if not files:
            return
        decoded, total = [], 0
        for m in files:                                                   # every size check first, before any parsing
            b64, name = m.get("file_b64"), m.get("name")
            if not isinstance(b64, str) or not isinstance(name, str):
                raise UploadRefused("upload_unreadable")
            if len(b64) > (cfg.upload_max_file_bytes * 4) // 3 + 8:
                raise UploadRefused("upload_too_big")
            try:
                raw = base64.b64decode(b64, validate=True)
            except (binascii.Error, ValueError):
                raise UploadRefused("upload_unreadable")
            total += len(raw)
            if len(raw) > cfg.upload_max_file_bytes or total > cfg.upload_max_total_bytes:
                raise UploadRefused("upload_too_big")
            ext = Path(name.lower()).suffix
            kind = KINDS.get(ext)
            if kind is None:
                raise UploadRefused("upload_unsupported")
            if not raw.startswith(kind[1]):                               # the name says one thing, the bytes another
                raise UploadRefused("upload_unreadable")
            decoded.append((m, kind[0], raw))
        deadline = self.clock() + cfg.extract_timeout_s                   # one deadline for the whole request
        lim = limits(cfg)
        for m, kind, raw in decoded:
            left = deadline - self.clock()
            if left <= 0:
                raise UploadRefused("upload_unreadable")
            res = self.runner(kind, raw, lim, left)
            if self.clock() > deadline:                                   # the deadline also covers the file that just ran
                raise UploadRefused("upload_unreadable")
            if not isinstance(res, dict) or res.get("ok") is not True or not isinstance(res.get("text"), str):
                code = _REASON.get(res.get("code") if isinstance(res, dict) else None, "upload_unreadable")
                raise UploadRefused("upload_scanned" if code == "upload_no_text" and kind == "pdf" else code)
            if len(res["text"]) > cfg.extract_max_chars:                  # the worker already checked; a stub or a bug must not slip past
                raise UploadRefused("upload_too_long")
            m["text"] = res["text"]
            m["needs_extraction"] = False
            m.pop("file_b64", None)

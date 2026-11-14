"""PDF / .docx text extraction, run as a CHILD PROCESS of the Bass proxy:  python -I extract_worker.py '<limits json>' < raw-file-bytes

Why a child: the upload is untrusted. A process can be killed on a deadline and given CPU / memory / file-size limits; a thread cannot.
-I (isolated mode) keeps the script's folder and the environment's PYTHONPATH off sys.path. This file imports only the standard library
and, for PDFs, pypdf (pure Python). It opens no sockets and fetches nothing: pypdf does not fetch, and the .docx XML is refused when it
carries a DOCTYPE or an ENTITY (no entity expansion, no external DTD).

stdout is ONE json line: {"ok": true, "text": "..."} or {"ok": false, "code": "<reason>"}.  stderr is never used. The file's content and
name never reach a log. Reasons: pages, encrypted, unreadable, too_long, no_text, bomb.
"""
from __future__ import annotations

import io
import json
import re
import struct
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class Refuse(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _clean(text: str) -> str:
    text = _CTRL.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+\n", "\n", text)).strip()


def _finish(text: str, lim: dict) -> str:
    text = _clean(text)
    if len(text) > lim["max_chars"]:
        raise Refuse("too_long")
    if len(re.sub(r"\s+", "", text)) < lim["min_chars"]:
        raise Refuse("no_text")
    return text


# -- PDF -----------------------------------------------------------------------------------------------------------------
def pdf_text(data: bytes, lim: dict) -> str:
    from pypdf import PdfReader                                           # imported here so the module imports without it
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:                                           # never tried with an empty password: refused outright
            raise Refuse("encrypted")
        n = len(reader.pages)
        if n > lim["pdf_max_pages"]:                                      # the page cap is checked before any page is read
            raise Refuse("pages")
        out, total = [], 0
        for page in reader.pages:
            t = page.extract_text() or ""
            total += len(t)
            if total > lim["max_chars"] * 2:                              # stop early; _finish decides on the cleaned text
                raise Refuse("too_long")
            out.append(t)
    except Refuse:
        raise
    except Exception:
        raise Refuse("unreadable")
    return _finish("\n\n".join(out), lim)


# -- .docx ---------------------------------------------------------------------------------------------------------------
def _eocd_count(data: bytes) -> int:
    i = data.rfind(b"PK\x05\x06", max(0, len(data) - 65557))
    if i < 0 or i + 22 > len(data):
        raise Refuse("unreadable")
    return struct.unpack("<H", data[i + 10:i + 12])[0]


def _read_limited(zf: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int) -> bytes:
    buf, got = [], 0
    with zf.open(info) as f:                                              # never extractall; the declared size is not trusted
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            got += len(chunk)
            if got > limit:
                raise Refuse("bomb")
            buf.append(chunk)
    return b"".join(buf)


def docx_text(data: bytes, lim: dict) -> str:
    try:
        if _eocd_count(data) > lim["docx_max_members"]:                   # entry count from the end record, before the directory is parsed
            raise Refuse("bomb")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > lim["docx_max_members"]:
                raise Refuse("bomb")
            declared = sum(i.file_size for i in infos)
            comp = max(1, sum(i.compress_size for i in infos))
            if declared > lim["docx_max_uncompressed"] or declared / comp > lim["docx_max_ratio"]:
                raise Refuse("bomb")
            info = next((i for i in infos if i.filename == "word/document.xml"), None)
            if info is None or info.file_size > lim["docx_xml_max_bytes"]:
                raise Refuse("unreadable" if info is None else "bomb")
            xml = _read_limited(zf, info, lim["docx_xml_max_bytes"])
        return _finish(_walk(xml, lim), lim)
    except Refuse:
        raise
    except Exception:
        raise Refuse("unreadable")


def _walk(xml: bytes, lim: dict) -> str:
    head = xml[:200]
    if xml[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in head:           # UTF-16 would hide a DOCTYPE from the scan below
        raise Refuse("unreadable")
    m = re.search(rb'encoding\s*=\s*["\']([^"\']+)', head)
    if m and m.group(1).lower() not in (b"utf-8", b"utf8"):
        raise Refuse("unreadable")
    try:
        s = xml.decode("utf-8")
    except UnicodeDecodeError:
        raise Refuse("unreadable")
    if "<!DOCTYPE" in s or "<!ENTITY" in s or "<!doctype" in s.lower():   # no DTD, no entities: nothing to expand
        raise Refuse("bomb")
    lines, paras, cells, rows = [], [], [], []
    depth = elements = total = 0
    for ev, el in ET.iterparse(io.BytesIO(xml), events=("start", "end")):
        tag = el.tag[len(W):] if el.tag.startswith(W) else ""
        if ev == "start":
            depth += 1
            elements += 1
            if depth > lim["docx_max_depth"] or elements > lim["docx_max_elements"]:
                raise Refuse("bomb")
            if tag == "p":
                paras.append([])
            elif tag == "tc":
                cells.append([])
            elif tag == "tr":
                rows.append([])
            elif tag == "tab" and paras:
                paras[-1].append("\t")
            elif tag in ("br", "cr") and paras:
                paras[-1].append("\n")
            continue
        depth -= 1
        if tag == "t":
            if paras and el.text:
                paras[-1].append(el.text)
                total += len(el.text)
                if total > lim["max_chars"] * 2:
                    raise Refuse("too_long")
        elif tag == "p" and paras:
            text = "".join(paras.pop())
            (cells[-1].append(text) if cells else lines.append(text))
        elif tag == "tc" and cells:
            cell = " ".join(t for t in cells.pop() if t.strip())
            if rows:
                rows[-1].append(cell)
        elif tag == "tr" and rows:
            row = rows.pop()
            if any(c.strip() for c in row):
                (cells[-1].append(" | ".join(row)) if cells else lines.append(" | ".join(row)))
        el.clear()
    return "\n".join(lines)


def main(argv: list, stdin) -> dict:
    try:
        kind, lim = argv[1], json.loads(argv[2])
        data = stdin.read()
        return {"ok": True, "text": (pdf_text if kind == "pdf" else docx_text)(data, lim)}
    except Refuse as r:
        return {"ok": False, "code": r.code}
    except BaseException:                                                 # MemoryError included: a refusal, never a trace
        return {"ok": False, "code": "unreadable"}


def apply_limits(lim: dict) -> dict:
    """Sets the child's CPU, file-size and address-space limits and returns the EFFECTIVE soft values read back (None = the OS refused that
    one: macOS ignores RLIMIT_AS, for example). The deadline in the parent still holds either way; `selfcheck` lets a test see the truth."""
    out = {}
    try:
        import resource
    except Exception:
        return {"cpu_s": None, "fsize": None, "as": None}
    for name, which, value in (("cpu_s", resource.RLIMIT_CPU, int(lim["cpu_s"])), ("fsize", resource.RLIMIT_FSIZE, 0),
                               ("as", resource.RLIMIT_AS, int(lim["mem_bytes"]))):
        try:
            resource.setrlimit(which, (value, value + 1 if name == "cpu_s" else value))
            out[name] = resource.getrlimit(which)[0]
        except Exception:
            out[name] = None
    return out


if __name__ == "__main__":
    try:
        applied = apply_limits(json.loads(sys.argv[2]))
    except Exception:
        applied = {}
    if len(sys.argv) > 1 and sys.argv[1] == "selfcheck":                   # what limits did this child really get? (tests; no file is read)
        res = {"ok": True, "limits": applied}
    else:
        res = main(sys.argv, sys.stdin.buffer)
    sys.stdout.write(json.dumps(res))
    sys.stdout.flush()

"""A static file server that answers byte-range requests: Safari/WebKit will not play a <video> from a server that cannot (Firebase Hosting can)."""
import functools
import http.server
import re
import socketserver
import threading


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng or "")
        if not m or not path.endswith(".mp4"):
            return super().send_head()
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404)
            return None
        size = f.seek(0, 2)
        a, b = m.group(1), m.group(2)
        start, end = (size - int(b), size - 1) if not a else (int(a), int(b) if b else size - 1)
        end = min(end, size - 1)
        if start > end:
            f.close()
            self.send_error(416)
            return None
        f.seek(start)
        self._left = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(self._left))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        return f

    def copyfile(self, src, dst):
        left = getattr(self, "_left", None)
        if left is None:
            return super().copyfile(src, dst)
        self._left = None
        try:
            while left > 0:
                chunk = src.read(min(65536, left))
                if not chunk:
                    break
                dst.write(chunk)
                left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes") if not self.path.endswith(".mp4") else None
        super().end_headers()


def serve(directory):
    """(server, base url): a threaded range-capable server on a free port."""
    h = functools.partial(RangeHandler, directory=str(directory))
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), h)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"

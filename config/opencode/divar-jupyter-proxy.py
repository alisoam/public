#!/usr/bin/env python3
"""Self-contained wrapper for jupyter-mcp-server.

Runs an in-process auth-fixing proxy (converts ?token= query auth to an
Authorization header, which the upstream JupyterHub requires, and tunnels
kernel WebSockets), then starts the MCP server pointing at it.

Stdio is passed straight through, so an MCP client (opencode) can launch
this script as the local MCP command.
"""
import os
import ssl
import sys
import signal
import socket
import threading
import subprocess
import urllib.parse
import http.server
import urllib.request
import urllib.error

UPSTREAM = os.environ.get("DIVAR_JUPYTER_URL", "").rstrip("/")
TOKEN = os.environ.get("DIVAR_JUPYTER_TOKEN", "")
MCP_COMMAND = ["uvx", "jupyter-mcp-server@latest", "start"]
HOP = {"host", "content-length", "connection", "transfer-encoding", "accept-encoding", "authorization"}

_u = urllib.parse.urlsplit(UPSTREAM)
U_SCHEME, U_HOST, U_PORT = _u.scheme, _u.hostname, _u.port or (443 if _u.scheme == "https" else 80)
U_PREFIX = _u.path.rstrip("/")
SSL_CTX = ssl.create_default_context()


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def split_token(path):
    parsed = urllib.parse.urlsplit(path)
    params = urllib.parse.parse_qs(parsed.query)
    token = params.pop("token", [None])[0] or TOKEN
    query = urllib.parse.urlencode(params, doseq=True)
    return parsed.path + ("?" + query if query else ""), token


class Proxy(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _forward(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        path, token = split_token(self.path)
        log(f">>> {self.command} {self.path}")

        if self.headers.get("Upgrade", "").lower() == "websocket":
            return self._tunnel_ws(path, token)

        req = urllib.request.Request(UPSTREAM + path, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() not in HOP:
                req.add_header(k, v)
        if token:
            req.add_header("Authorization", f"token {token}")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                log(f"<<< {r.status} {path} ({len(data)}b): {data[:200]!r}")
                self.send_response(r.status)
                for k, v in r.getheaders():
                    if k.lower() not in HOP | {"content-encoding"}:
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            log(f"<<< {e.code} {path}: {data[:200]!r}")
            self.send_response(e.code)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            log(f"<<< ERROR {self.command} {path}: {e!r}")
            self.send_response(502)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def _tunnel_ws(self, path, token):
        raw = socket.create_connection((U_HOST, U_PORT), timeout=30)
        if U_SCHEME == "https":
            raw = SSL_CTX.wrap_socket(raw, server_hostname=U_HOST)
        ws_hop = HOP - {"connection"}
        lines = [f"{self.command} {U_PREFIX}{path} HTTP/1.1", f"Host: {U_HOST}"]
        for k, v in self.headers.items():
            if k.lower() not in ws_hop | {"host"}:
                lines.append(f"{k}: {v}")
        if token:
            lines.append(f"Authorization: token {token}")
        raw.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = raw.recv(4096)
            if not chunk:
                break
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        status = head.split(b"\r\n")[0].decode(errors="replace")
        log(f"<<< WS {path}: {status}")
        if b" 101 " not in head.split(b"\r\n")[0] + b" ":
            self.connection.sendall(head + b"\r\n\r\n" + rest)
            self.close_connection = True
            raw.close()
            return
        self.connection.sendall(head + b"\r\n\r\n")
        if rest:
            self.connection.sendall(rest)

        def pump(a, b):
            try:
                while True:
                    data = a.recv(65536)
                    if not data:
                        break
                    b.sendall(data)
            except OSError:
                pass
            finally:
                try:
                    b.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        t = threading.Thread(target=pump, args=(raw, self.connection), daemon=True)
        t.start()
        pump(self.connection, raw)
        self.close_connection = True

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _forward

    def log_message(self, *a):
        pass


def _pdeathsig():
    import ctypes
    ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGTERM)


def run_inprocess():
    sys.argv = ["jupyter-mcp-server", "start"]
    from jupyter_mcp_server.cli.cli import serve
    serve()


def main():
    if not UPSTREAM:
        log("error: DIVAR_JUPYTER_URL is not set")
        raise SystemExit(1)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log(f"proxy on 127.0.0.1:{port} -> {UPSTREAM}")

    os.environ["JUPYTER_URL"] = f"http://127.0.0.1:{port}"
    os.environ["JUPYTER_TOKEN"] = TOKEN

    try:
        import jupyter_mcp_server  # noqa: F401
    except ImportError:
        pass
    else:
        log("starting jupyter-mcp-server in-process")
        run_inprocess()
        raise SystemExit(0)

    log("jupyter_mcp_server not importable, falling back to uvx subprocess")
    proc = subprocess.Popen(MCP_COMMAND, env=os.environ, preexec_fn=_pdeathsig)

    def on_signal(signum, frame):
        proc.terminate()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    raise SystemExit(proc.wait())


if __name__ == "__main__":
    main()

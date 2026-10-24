#!/usr/bin/env python3
"""sbox.py — run a command in a bubblewrap sandbox with an allowlisted network.

Design:
  - bwrap --unshare-all: the sandbox has NO network stack (no direct TCP/UDP,
    no DNS). The only egress is a Unix socket passed into /run/proxy.sock.
  - The proxy runs on the HOST: this same file re-executes itself as a small
    asyncio SOCKS5 + HTTP-CONNECT server listening on that Unix socket. There
    is no third-party proxy dependency (replaces 3proxy and its AF_UNIX
    sendto()/EISCONN bug, patched builds and the relay self-test workaround).
  - Inside the sandbox a loopback bridge (socat) makes the proxy available at
    127.0.0.1:1080; the listener auto-detects SOCKS5 (first byte 0x05) vs HTTP
    proxy traffic, so http_proxy=http://127.0.0.1:1080 works for tools that
    do not understand socks5h:// (npm, apt, ...).
    all_proxy=socks5h://127.0.0.1:1080 is set as well; http(s)_proxy too.
  - ssh ignores proxy env vars, so proxied mode additionally injects a
    generated /etc/ssh/ssh_config (read-only bind) whose ProxyCommand runs
    socat's HTTP-CONNECT client through the bridge: ssh/scp/sftp and
    git-over-ssh ride the same allowlist-checked proxy. ~/.ssh/config still
    wins per-option (ssh reads the user config first).
  - Fail-closed: apps that ignore the proxy vars simply get no network.

Security model of the proxy (default-deny):
  - A destination is checked against the allowlist BEFORE anything else; in
    particular hostnames of DENIED destinations are never resolved — there is
    no DNS side channel (no <data>.evil.com exfiltration through lookups).
  - Allowed hostnames are resolved on the host; answers in private, loopback,
    link-local, CGNAT, multicast or reserved ranges are rejected, so an
    allowed name cannot be used to reach host/LAN services (SSRF guard,
    incl. 169.254.169.254). Explicit -a IP/CIDR entries deliberately bypass
    that guard (explicit intent) — use them with care.
  - Suffix match is on dot boundaries: -a example.com allows example.com and
    sub.example.com, but not notexample.com. Entries may carry a port
    (example.com:443); IPs and CIDRs are also accepted. Catch-all entries
    (bare '*', 0.0.0.0/0, ::/0) and CIDRs with host bits set (203.0.113.7/24)
    are rejected loudly instead of being widened or allowed silently.
  - Optional upstream chaining (--upstream, or $SBOX_UPSTREAM / $https_proxy):
    schemes http, https (TLS to the proxy), socks5 and socks5h; userinfo in
    the URL is passed on (Basic auth / RFC 1929). Destinations are still
    resolved and checked host-side before anything is sent upstream. Set
    $SBOX_UPSTREAM_INSECURE (or --upstream-insecure) to skip TLS verification
    of an https:// upstream (e.g. corporate MITM CA).
  - A startup self-test talks to the real socket and verifies that a
    non-allowed destination is refused on both protocols before the sandbox
    starts, so the fail-closed guarantee is checked, not assumed.

  - --net skips all of the above: bwrap then shares the host network
    namespace (--unshare-all --share-net), /etc/resolv.conf is mounted, and
    no proxy is started (direct egress; the allowlist is NOT enforced, and
    host loopback services and abstract Unix sockets — D-Bus, X11, ... —
    become reachable; only use it for trusted work).
  - Lifecycle: one component dies -> everything dies (supervisor loop,
    --die-with-parent on bwrap, PR_SET_PDEATHSIG on the proxy; a SIGKILLed
    launcher therefore still takes the proxy with it).

Dependencies: bwrap, socat and python3 >= 3.8 (stdlib only). --net mode needs
bwrap only.

Known limits (design trade-offs, not bugs):
  - -b/--ro-bind paths are only refused when they cover a protected path
    (system dirs, $HOME, /run/user/<uid>); anything else you bind — the
    launcher's /tmp/sbox.* work dir, which holds proxy.json and any upstream
    credentials, included — is handed over as requested.
  - No seccomp filter and no resource limits (CPU/memory/PID/fds) inside
    the sandbox; bwrap's namespace isolation is the only boundary.
  - Ports are unrestricted unless an entry carries :port, and there is no
    domain-fronting protection (an allowed CDN host may serve many origins).
  - With --upstream, the destination reaches the upstream as a literal IP:
    it sees CONNECT 1.2.3.4:443, never the hostname. Hostname-based policy
    or logging on that proxy cannot work, and some proxies reject IP
    CONNECT targets.
  - --home exposes the real $HOME: ~/.bashrc, ~/.local/bin and any agent
    sockets in it run with your full identity.
  - --ssh-agent forwards $SSH_AUTH_SOCK (one read-only socket file): any
    code in the sandbox can sign with every key loaded in the agent, i.e.
    authenticate as you wherever the network policy allows.
  - The proxy has no connection caps, idle timeouts or header-count limits,
    tunnels have no TCP half-close, and only the first resolved address is
    tried when chaining through an upstream.

Installed to ~/.local/bin via config/sync.py (Directory("bin", ..., "~/.local/bin")).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import ctypes
import ipaddress
import json
import os
import re
import shutil
import signal
import socket
import ssl
import stat
import struct
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.parse

PROG = "sbox.py"
PR_SET_PDEATHSIG = 1
CONNECT_TIMEOUT = 15.0  # seconds; TCP + upstream handshakes

# Networks that an allowlisted *name* must never resolve into (SSRF guard).
# Private/loopback/link-local/multicast/reserved are covered by the
# ipaddress predicates; CGNAT is not is_private on older Pythons, so it is
# listed explicitly. Explicit -a IP/CIDR entries bypass this guard on purpose.
EXTRA_BAD_NETS = (ipaddress.ip_network("100.64.0.0/10"),)

# Paths that user binds (-b/-r) and the automatic cwd bind must never cover
# (they would shadow the tmpfs /tmp — exposing the host's /tmp and $WORK —
# hide /run/proxy.sock, or hand the sandbox a writable system directory).
SYSTEM_DIRS = {
    "/", "/bin", "/boot", "/dev", "/etc", "/lib", "/lib64", "/proc", "/run",
    "/sbin", "/sys", "/tmp", "/usr", "/var",
}

UPSTREAM_SCHEMES = ("http", "https", "socks5", "socks5h")


def covers(a: str, b: str) -> bool:
    """True if path a is equal to or an ancestor of path b (realpaths)."""
    a = a.rstrip("/")
    return b == a or b.startswith(a + "/")


def err(msg: str) -> None:
    print(f"{PROG}: {msg}", file=sys.stderr, flush=True)


def die(msg: str) -> None:
    err(msg)
    sys.exit(1)


# --------------------------------------------------------------- allowlist ---

NAME_RE = re.compile(
    r"^[a-z0-9_](?:[a-z0-9_-]*[a-z0-9_])?(?:\.[a-z0-9_](?:[a-z0-9_-]*[a-z0-9_])?)*$"
)


def parse_allow_entry(raw: str) -> dict:
    """Parse one allow entry into {"kind": "name"|"net", "value", "port"}.

    Accepts: example.com, *.example.com (same thing), example.com:443,
    203.0.113.7, 203.0.113.0/24, [2001:db8::]/32, [2001:db8::]:443.
    Rejects anything else loudly (this is a fail-closed tool).
    """
    e = raw.split("#", 1)[0].strip().lower()
    while e.startswith("*."):
        e = e[2:]
    e = e.strip(".")
    if not e:
        raise ValueError("empty entry")
    if set(e) <= {"*", "."}:
        raise ValueError("wildcard-only entry would allow everything; use --net for unrestricted egress")

    port = None
    host = e
    if e.startswith("["):
        m = re.fullmatch(r"\[([0-9a-f:.]+)\](?:/(\d{1,3}))?(?::(\d+))?", e)
        if not m or ":" not in m.group(1):  # a bracketed host must be IPv6
            raise ValueError(f"malformed IPv6 entry: {raw!r}")
        host = m.group(1) + ("/" + m.group(2) if m.group(2) else "")
        if m.group(3):
            port = int(m.group(3))
    elif e.count(":") == 1:
        host, _, p = e.rpartition(":")
        if not p.isdigit():
            raise ValueError(f"bad port in allow entry {raw!r} (expected host:port)")
        port = int(p)
    if port is not None and not 1 <= port <= 65535:
        raise ValueError(f"bad port in allow entry {raw!r} (expected 1-65535)")

    if "*" in host:
        raise ValueError(f"wildcards are only supported as a leading '*.' in {raw!r}")

    try:
        # strict: never silently widen "203.0.113.7/24" to the whole /24.
        net = ipaddress.ip_network(host)
    except ValueError:
        # Anything that *looks* like an address must be a valid one — never
        # silently reclassify e.g. "300.1.2.3" or "example.com:443" as a name.
        if re.fullmatch(r"[0-9.]+", host) or ":" in host:
            try:
                widened = ipaddress.ip_network(host, strict=False)
            except ValueError:
                widened = None
            if widened is not None:
                raise ValueError(
                    f"{raw!r}: host bits set — refusing to widen to {widened}; "
                    f"write {widened.network_address}/{widened.prefixlen} instead"
                )
            raise ValueError(f"invalid IP/CIDR entry: {raw!r}")
        if not NAME_RE.fullmatch(host):
            raise ValueError(f"not a valid hostname, IP or CIDR: {raw!r}")
        return {"kind": "name", "value": host, "port": port}
    if net.prefixlen < (8 if net.version == 4 else 16):
        # /0 is an explicit catch-all, but 0.0.0.0/1 + 128.0.0.0/1 (or ::/1)
        # amount to the same thing while silently bypassing the private-range
        # guard for literal-IP destinations. Refuse effectively-global nets.
        raise ValueError(
            f"{raw!r} is an effectively catch-all network (/{net.prefixlen}); "
            f"add narrower entries or use --net for unrestricted egress"
        )
    return {"kind": "net", "value": str(net), "port": port}


def load_allows(opt_allows: list[str], opt_files: list[str]) -> list[dict]:
    entries: list[dict] = []
    for path in opt_files:
        if not os.path.isfile(path):
            die(f"cannot read allow file: {path}")
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    entries.append(parse_allow_entry(line))
                except ValueError as e:
                    die(f"{path}:{lineno}: {e}")
    for raw in opt_allows:
        try:
            entries.append(parse_allow_entry(raw))
        except ValueError as e:
            die(f"--allow: {e}")
    return entries


def destination_allowed(allows: list[dict], host: str, port: int) -> tuple[bool, str]:
    """Allowlist check for a destination. Performs NO DNS and NO connection.

    Literal IPs match only -a IP/CIDR entries; names match name entries by
    exact or dot-boundary suffix comparison. Port-scoped entries additionally
    require the destination port to match.
    """
    h = host.rstrip(".").lower()
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        ip = None
    if ip is not None:
        for a in allows:
            if a["kind"] == "net" and a["port"] in (None, port) and ip in ipaddress.ip_network(a["value"]):
                return True, f"matches allowed network {a['value']}"
        return False, "IP destination not in any allowed network"
    for a in allows:
        if a["kind"] == "name" and a["port"] in (None, port):
            v = a["value"]
            if h == v or h.endswith("." + v):
                return True, f"matches allowed name {v}"
    return False, "hostname not on the allowlist"


def bad_ip(addr: ipaddress._BaseAddress) -> bool:
    if addr.version == 6:
        # Address forms that embed an IPv4 address: judge the embedded IPv4,
        # not the covering prefix.
        #   - NAT64 (RFC 6052, 64:ff9b::/96): ipaddress marks the whole
        #     prefix reserved, but on DNS64 networks legitimate public
        #     IPv4-only hosts come back this way.
        #   - 6to4 (RFC 3056, 2002::/16): the v6 form looks global, but
        #     relays decapsulate to the embedded IPv4 (bits 16..47), which
        #     may be loopback/LAN — SSRF via e.g. a 2002:7f00:1:: answer.
        #   - Teredo (RFC 4380, 2001:0::/32): deprecated — refuse the whole
        #     prefix instead of decoding it (layout: prefix, server IPv4,
        #     flags, obfuscated port, obfuscated client IPv4), and do not
        #     rely on is_private covering 2001::/23 on every Python version.
        try:
            if addr in ipaddress.ip_network("64:ff9b::/96"):
                embedded = addr.ipv4_mapped or ipaddress.IPv4Address(int(addr) & 0xFFFFFFFF)
                return bad_ip(embedded)
            if addr in ipaddress.ip_network("2002::/16"):
                return bad_ip(ipaddress.IPv4Address((int(addr) >> 80) & 0xFFFFFFFF))
            if addr in ipaddress.ip_network("2001:0::/32"):
                return True
        except ipaddress.AddressValueError:
            pass
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
        or any(addr in n for n in EXTRA_BAD_NETS)
    )


# ------------------------------------------------------------------- proxy ---

class DestinationError(Exception):
    """Denial/connection failure; .rep is the SOCKS5 reply code."""

    def __init__(self, rep: int, why: str):
        super().__init__(why)
        self.rep = rep
        self.why = why


def _parse_ip(host: str):
    try:
        return ipaddress.ip_address(host.rstrip("."))
    except ValueError:
        return None


async def resolve_filtered(host: str, port: int) -> list:
    """Resolve host on the host side and drop blocked (private etc.) answers."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as e:
        raise DestinationError(4, f"DNS failure for {host}: {e}")
    good, blocked = [], []
    for info in infos:
        sockaddr = info[4]
        ip = ipaddress.ip_address(sockaddr[0])
        if bad_ip(ip):
            blocked.append(str(ip))
        else:
            good.append(info)
    if blocked and not good:
        raise DestinationError(
            2, f"{host} resolves only to blocked (private/loopback/link-local) addresses: {', '.join(blocked)}"
        )
    if not good:
        raise DestinationError(4, f"no usable addresses for {host}")
    return good


async def _pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
    try:
        while True:
            buf = await src.read(65536)
            if not buf:
                break
            dst.write(buf)
            await dst.drain()
    except Exception:
        pass  # OSError and anything else: the tunnel is done either way
    finally:
        try:
            dst.close()
        except Exception:
            pass


async def _tunnel(cr, cw, sr, sw) -> None:
    """Bidirectional copy; tear down as soon as one direction ends."""
    t1 = asyncio.create_task(_pipe(cr, sw))
    t2 = asyncio.create_task(_pipe(sr, cw))
    _, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for w in (cw, sw):
        try:
            w.close()
        except Exception:
            pass


def parse_hostport(target: str, default_port: int) -> tuple[str, int]:
    if target.startswith("["):
        host, _, rest = target[1:].partition("]")
        if not host or rest and not rest.startswith(":"):
            raise ValueError(target)
        port = int(rest[1:]) if rest else default_port
        return host, port
    host, _, p = target.rpartition(":")
    if not host:
        return target, default_port
    if not p.isdigit() or not 1 <= int(p) <= 65535:
        raise ValueError(target)
    return host, int(p)


class Proxy:
    """SOCKS5 + HTTP-CONNECT proxy with an allowlist, on a Unix socket."""

    def __init__(self, cfg: dict):
        self.allows = cfg.get("allows", [])
        self.upstream = cfg.get("upstream")
        self.verbose = bool(cfg.get("verbose"))

    def log(self, msg: str) -> None:
        if self.verbose:
            print(f"sbox-proxy: {msg}", file=sys.stderr, flush=True)

    # -- destination handling -------------------------------------------------

    async def connect_destination(self, host: str, port: int):
        """Allowlist -> resolve (SSRF-guarded) -> connect (or chain upstream).

        Returns (reader, writer) of the established tunnel; raises
        DestinationError otherwise. Never resolves denied names.
        """
        if not 1 <= port <= 65535:
            raise DestinationError(1, f"invalid port {port}")
        h = host.rstrip(".").lower()
        ip = _parse_ip(h)
        if ip is None and (
            not NAME_RE.fullmatch(h)
            # getaddrinfo raises bare UnicodeError (a ValueError) for labels
            # over 63 chars — reject here for a clean client error instead.
            or len(h) > 253
            or any(len(label) > 63 for label in h.split("."))
        ):
            # Never hand sandbox-controlled bytes to the resolver: embedded
            # NULs, backslash escapes etc. are rejected before getaddrinfo.
            raise DestinationError(4, f"invalid hostname {host!r}")
        allowed, why = destination_allowed(self.allows, h, port)
        if not allowed:
            # !r: hostnames come from the sandbox and may contain control
            # bytes — never let them reach the terminal raw.
            self.log(f"deny  {h!r}:{port} — {why}")
            raise DestinationError(2, why)

        if self.upstream:
            if ip is None:
                infos = await resolve_filtered(h, port)
                ip = ipaddress.ip_address(infos[0][4][0])
            u = self.upstream
            self.log(f"allow {h!r}:{port} — via {u['scheme']} upstream {u['host']}:{u['port']} to {ip}")
            return await self._open_upstream(str(ip), port)
        if ip is not None:
            # Literal IP allowed explicitly: private ranges are intentional.
            self.log(f"allow {h!r}:{port} — direct (allowed literal IP)")
            try:
                return await asyncio.wait_for(asyncio.open_connection(str(ip), port), CONNECT_TIMEOUT)
            except (OSError, asyncio.TimeoutError) as e:
                raise DestinationError(5, f"connect to {ip}:{port} failed: {e}")
        infos = await resolve_filtered(h, port)
        self.log(f"allow {h!r}:{port} — resolved " + ", ".join(str(i[4][0]) for i in infos))
        last: Exception | None = None
        for info in infos:
            sockaddr = info[4]
            try:
                return await asyncio.wait_for(asyncio.open_connection(sockaddr[0], sockaddr[1]), CONNECT_TIMEOUT)
            except (OSError, asyncio.TimeoutError) as e:
                last = e
        raise DestinationError(5, f"connect to {h}:{port} failed: {last}")

    async def _open_upstream(self, dest_ip: str, dest_port: int):
        u = self.upstream

        async def handshake():
            ssl_ctx = None
            if u["scheme"] == "https":
                ssl_ctx = ssl.create_default_context()
                if not u["tls_verify"]:
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE
            reader, writer = await asyncio.open_connection(u["host"], u["port"], ssl=ssl_ctx)
            if u["scheme"] in ("http", "https"):
                req = f"CONNECT {dest_ip}:{dest_port} HTTP/1.1\r\nHost: {dest_ip}:{dest_port}\r\n"
                if u["user"] is not None:
                    token = base64.b64encode(f"{u['user']}:{u['pass'] or ''}".encode()).decode()
                    req += f"Proxy-Authorization: Basic {token}\r\n"
                req += "\r\n"
                writer.write(req.encode("latin-1"))
                status = await reader.readline()
                parts = status.split(None, 2)
                if len(parts) < 2 or not parts[1].startswith(b"2"):
                    raise OSError(f"upstream CONNECT failed: {status.decode('latin-1', 'replace').strip()}")
                while True:
                    line = await reader.readline()
                    if line in (b"\r\n", b"\n", b""):
                        break
            else:  # socks5
                writer.write(b"\x05\x01\x02" if u["user"] is not None else b"\x05\x01\x00")
                resp = await reader.readexactly(2)
                if resp[0] != 5:
                    raise OSError("upstream is not SOCKS5")
                if resp[1] == 0x02:
                    user = (u["user"] or "").encode()
                    pw = (u["pass"] or "").encode()
                    if len(user) > 255 or len(pw) > 255:
                        raise OSError("upstream credentials too long")
                    writer.write(b"\x01" + bytes([len(user)]) + user + bytes([len(pw)]) + pw)
                    auth = await reader.readexactly(2)
                    if auth[1] != 0:
                        raise OSError("upstream username/password auth failed")
                elif resp[1] != 0x00:
                    raise OSError("upstream refused our auth methods")
                addr = ipaddress.ip_address(dest_ip)
                if addr.version == 4:
                    writer.write(b"\x05\x01\x00\x01" + socket.inet_aton(dest_ip))
                else:
                    writer.write(b"\x05\x01\x00\x04" + socket.inet_pton(socket.AF_INET6, dest_ip))
                writer.write(struct.pack(">H", dest_port))
                rep = await reader.readexactly(4)
                if rep[1] != 0:
                    raise OSError(f"upstream CONNECT failed with reply code {rep[1]}")
                if rep[3] == 1:
                    await reader.readexactly(4 + 2)
                elif rep[3] == 3:
                    n = (await reader.readexactly(1))[0]
                    await reader.readexactly(n + 2)
                elif rep[3] == 4:
                    await reader.readexactly(16 + 2)
            return reader, writer

        try:
            return await asyncio.wait_for(handshake(), CONNECT_TIMEOUT)
        except DestinationError:
            raise
        except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError) as e:
            raise DestinationError(1, f"upstream {u['scheme']}://{u['host']}:{u['port']} failed: {e}")

    # -- SOCKS5 ----------------------------------------------------------------

    @staticmethod
    async def _socks_reply(writer: asyncio.StreamWriter, rep: int) -> None:
        writer.write(b"\x05" + bytes([rep]) + b"\x00\x01\x00\x00\x00\x00\x00\x00")
        await writer.drain()

    async def _socks5(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nmethods = (await reader.readexactly(1))[0]
        methods = await reader.readexactly(nmethods)
        if 0 not in methods:  # only NO-AUTH (the socket is 0600, mode 0)
            writer.write(b"\x05\xff")
            await writer.drain()
            return
        writer.write(b"\x05\x00")
        await writer.drain()
        try:
            ver, cmd, _rsv, atyp = await reader.readexactly(4)
            if ver != 5:
                return
            if atyp == 1:
                host = socket.inet_ntop(socket.AF_INET, await reader.readexactly(4))
            elif atyp == 3:
                length = (await reader.readexactly(1))[0]
                host = (await reader.readexactly(length)).decode("ascii")
            elif atyp == 4:
                host = socket.inet_ntop(socket.AF_INET6, await reader.readexactly(16))
            else:
                return await self._socks_reply(writer, 8)  # address type unsupported
            port = struct.unpack(">H", await reader.readexactly(2))[0]
        except (asyncio.IncompleteReadError, UnicodeDecodeError):
            return
        if cmd != 1:  # only CONNECT
            return await self._socks_reply(writer, 7)
        try:
            sr, sw = await self.connect_destination(host, port)
        except DestinationError as e:
            return await self._socks_reply(writer, e.rep)
        except (OSError, asyncio.TimeoutError):
            return await self._socks_reply(writer, 1)
        await self._socks_reply(writer, 0)
        await _tunnel(reader, writer, sr, sw)

    # -- HTTP (CONNECT + absolute-form) -----------------------------------------

    @staticmethod
    async def _http_error(writer: asyncio.StreamWriter, code: int, text: str, reason: str = "") -> None:
        phrase = {400: "Bad Request", 403: "Forbidden", 502: "Bad Gateway"}.get(code, "Error")
        body = text.encode("utf-8", "replace")
        hdr = f"HTTP/1.1 {code} {phrase}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n"
        if reason:
            # Reasons can embed attacker-controlled hostnames: keep the header
            # single-line and printable.
            safe = "".join(c if "\x20" <= c <= "\x7e" else " " for c in reason)[:200]
            hdr += "X-Sbox-Error: " + safe + "\r\n"
        writer.write(hdr.encode("latin-1") + b"\r\n" + body)
        await writer.drain()

    async def _http_connect(self, reader, writer, target: str) -> None:
        try:
            host, port = parse_hostport(target, 80)
        except ValueError:
            return await self._http_error(writer, 400, "bad CONNECT target\n")
        while True:  # drain request headers up to the blank line
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
        try:
            sr, sw = await self.connect_destination(host, port)
        except DestinationError as e:
            code = 403 if e.rep == 2 else 502
            return await self._http_error(writer, code, f"{code}: {e.why}\n", e.why)
        writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        await writer.drain()
        await _tunnel(reader, writer, sr, sw)

    async def _http_absolute(self, reader, writer, method: str, url: str) -> None:
        try:
            parts = urllib.parse.urlsplit(url)
            host = parts.hostname or ""
            port = parts.port if parts.port is not None else 80  # :0 is NOT 80
            if parts.scheme.lower() != "http" or not host:
                raise ValueError(url)
        except ValueError:  # urlsplit/bad port/unsupported scheme -> 400
            return await self._http_error(
                writer, 400, "only http:// absolute URLs are proxied; https:// must use CONNECT\n"
            )
        headers: list[tuple[str, str]] = []
        try:
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b"\n", b""):
                    break
                name, _, value = line.decode("latin-1").partition(":")
                if name:
                    headers.append((name, value.strip()))
        except UnicodeDecodeError:
            return await self._http_error(writer, 400, "malformed headers\n")
        if not any(n.lower() == "host" for n, _ in headers):
            # Synthesize Host from host[:port]: never copy the netloc, which
            # may carry userinfo (http://user@host/) that must not reach the
            # origin server. IPv6 literals need their brackets back.
            if ":" in host:
                headers.append(("Host", f"[{host}]:{port}"))
            elif port != 80:
                headers.append(("Host", f"{host}:{port}"))
            else:
                headers.append(("Host", host))
        drop = {"proxy-connection", "proxy-authorization", "connection", "keep-alive"}
        head = "".join(f"{n}: {v}\r\n" for n, v in headers if n.lower() not in drop)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        try:
            sr, sw = await self.connect_destination(host, port)
        except DestinationError as e:
            code = 403 if e.rep == 2 else 502
            return await self._http_error(writer, code, f"{code}: {e.why}\n", e.why)
        sw.write(f"{method} {path} HTTP/1.1\r\n{head}Connection: close\r\n\r\n".encode("latin-1"))
        await sw.drain()
        await _tunnel(reader, writer, sr, sw)

    async def _http(self, reader, writer, first: bytes) -> None:
        line = first + await reader.readline()
        parts = line.decode("latin-1", "replace").split()
        if len(parts) < 3 or not parts[2].upper().startswith("HTTP/"):
            return await self._http_error(writer, 400, "bad request line\n")
        method, target = parts[0].upper(), parts[1]
        if method == "CONNECT":
            return await self._http_connect(reader, writer, target)
        if method in ("GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"):
            return await self._http_absolute(reader, writer, method, target)
        return await self._http_error(writer, 400, f"method {method} not supported\n")

    # -- dispatch ----------------------------------------------------------------

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            try:
                first = await reader.readexactly(1)
            except (asyncio.IncompleteReadError, OSError):
                return  # client closed immediately (readiness probe) — fine
            if first == b"\x05":  # SOCKS5 greeting always starts with 0x05
                await self._socks5(reader, writer)
            else:
                await self._http(reader, writer, first)
        except Exception:
            if self.verbose:
                traceback.print_exc(file=sys.stderr)
        finally:
            try:
                writer.close()
            except Exception:
                pass


def proxy_main(sock_path: str, cfg_path: str, expected_ppid: int) -> int:
    # Die with the launcher even if it is SIGKILLed.
    try:
        ctypes.CDLL(None, use_errno=True).prctl(PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0)
    except Exception:
        pass
    if os.getppid() != expected_ppid:  # launcher died between fork and prctl
        return 1
    with open(cfg_path, "r", encoding="utf-8") as fh:
        proxy = Proxy(json.load(fh))

    async def serve() -> None:
        server = await asyncio.start_unix_server(proxy.handle, path=sock_path)
        os.chmod(sock_path, 0o600)
        async with server:
            await server.serve_forever()

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
    return 0


# ------------------------------------------------------------------ client ---

def redact_userinfo(url: str) -> str:
    """url with any userinfo (user[:pass]@) removed, so it is safe to print
    (die() output ends up in the terminal and scrollback)."""
    return re.sub(r"//[^/?#]*@", "//", url, count=1)


def parse_upstream(raw: str, insecure: bool) -> dict | None:
    if not raw:
        return None
    url = raw if "://" in raw else "http://" + raw
    # Error messages echo the redacted URL only: --upstream URLs may carry
    # credentials in the userinfo.
    safe = redact_userinfo(url)
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        die(f"cannot parse --upstream URL: {safe}")
    scheme = (parts.scheme or "http").lower()
    if scheme not in UPSTREAM_SCHEMES:
        die(f"unsupported --upstream scheme {scheme!r} (supported: {', '.join(UPSTREAM_SCHEMES)}): {safe}")
    host = parts.hostname
    if not host:
        die(f"cannot parse --upstream URL: {safe}")
    default = 443 if scheme == "https" else 1080 if scheme.startswith("socks5") else 80
    try:
        port = parts.port  # raises ValueError for non-numeric/out-of-range
    except ValueError:
        die(f"bad port in --upstream URL: {safe}")
    if port is None:
        port = default
    elif not 1 <= port <= 65535:  # urlsplit allows :0; that is not a port
        die(f"bad port in --upstream URL: {safe}")
    return {
        # socks5h behaves like socks5 here: resolution stays on our side so
        # the allowlist and the private-IP guard keep applying.
        "scheme": "socks5" if scheme == "socks5h" else scheme,
        "host": host,
        "port": port,
        "user": urllib.parse.unquote(parts.username) if parts.username is not None else None,
        "pass": urllib.parse.unquote(parts.password) if parts.password is not None else None,
        "tls_verify": not insecure,
    }


def self_test(sock_path: str, allows: list[dict]) -> None:
    """Fail-closed gate on the real socket, before the sandbox starts: a
    non-allowed destination must be refused on both SOCKS5 and HTTP CONNECT
    (denied names are never resolved, so this needs no network)."""
    name = f"sbox-selftest-{os.urandom(4).hex()}.invalid"
    if destination_allowed(allows, name, 80)[0]:
        err("note: allowlist covers the self-test destination; skipping enforcement check")
        return
    try:
        # SOCKS5: expect REP=2 (not allowed)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect(sock_path)
            s.sendall(b"\x05\x01\x00")
            if s.recv(2) != b"\x05\x00":
                die("self-test: bad SOCKS5 greeting on the proxy socket")
            host = name.encode()
            s.sendall(b"\x05\x01\x00\x03" + bytes([len(host)]) + host + struct.pack(">H", 80))
            rep = s.recv(64)
            if len(rep) < 2 or rep[1] != 0x02:
                die(f"self-test: SOCKS5 denial not enforced (reply={rep[:2].hex() if rep else 'eof'}) — failing closed")
        # HTTP CONNECT: expect 403
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect(sock_path)
            s.sendall(f"CONNECT {name}:80 HTTP/1.1\r\nHost: {name}\r\n\r\n".encode())
            status = s.recv(128)
            if not status.startswith(b"HTTP/1.1 403"):
                first = status.split(b"\r\n")[0][:40] if status else b"<eof>"
                die(f"self-test: HTTP denial not enforced ({first!r}) — failing closed")
    except OSError as e:  # wedged proxy, timeouts: fail closed with a clean message
        die(f"self-test: cannot talk to the proxy ({e!r}) — failing closed")


# ------------------------------------------------------------------ sandbox ---

INNER_PROXY = """\
socat TCP-LISTEN:1080,bind=127.0.0.1,fork,reuseaddr UNIX-CONNECT:/run/proxy.sock &
i=0
until socat -u /dev/null TCP:127.0.0.1:1080 >/dev/null 2>&1; do
    i=$((i+1)); [ "$i" -ge 50 ] && { echo "sbox.py: warning: in-sandbox proxy bridge not ready after 2.5s" >&2; break; }
    sleep 0.05
done
exec "$@"
"""
INNER_DIRECT = 'exec "$@"'

# Installed read-only at /etc/ssh/ssh_config inside the sandbox (proxied mode
# only). socat is guaranteed to exist in there — the bridge itself runs on it.
# The proxy resolves and allowlist-checks %h host-side, exactly like the
# env-var path for curl etc. Note ssh reads ~/.ssh/config first and the first
# obtained value wins, so a user config (e.g. --home) overrides per-option.
SSH_CLIENT_CONFIG = """\
# Generated by sbox.py: ssh has no native proxy support, so every host is
# routed through the sandbox's HTTP-CONNECT proxy (destination allowlist is
# enforced host-side). Disable per-invocation with -o ProxyCommand=none.
Host *
\tProxyCommand socat - PROXY:127.0.0.1:%h:%p,proxyport=1080
"""


def protected_paths(home: str) -> set[str]:
    """Paths a user-supplied bind (or the cwd bind) must never cover."""
    return set(SYSTEM_DIRS) | {os.path.realpath(home), "/run/user", f"/run/user/{os.getuid()}"}


def check_bind_paths(opts, home: str) -> list[tuple[str, str]]:
    """Validate -b/--ro-bind before anything is started; return the resolved
    (flag, realpath) pairs that build_bwrap mounts — validation and mount
    must use the same path, so symlink swaps and relative paths can't make
    bwrap mount something that was never checked.

    Whatever these paths really point at is handed to the sandbox, so refuse
    anything that covers a protected path (an ancestor of — or equal to —
    $HOME, a system dir, or the user runtime dir with its agent/pipewire/
    D-Bus sockets). Children are fine (e.g. -b ~/proj). -b $HOME itself is
    only acceptable together with --home (which binds it anyway); anything
    that merely covers $HOME, like /home, is still refused.
    """
    real_home = os.path.realpath(home)
    protected = sorted(protected_paths(home))
    binds: list[tuple[str, str]] = []
    for flag, paths in (("--bind", opts.bind), ("--ro-bind", opts.ro_bind)):
        for p in paths:
            rp = os.path.realpath(p)
            exempt = flag == "--bind" and opts.home and rp == real_home
            hits = [] if exempt else [q for q in protected if covers(rp, q)]
            if hits:
                die(f"{flag} {p} covers protected path(s): {', '.join(hits)}"
                    + ("; use --home to bind $HOME itself"
                       if flag == "--bind" and rp == real_home else ""))
            binds.append((flag, rp))
    return binds


def agent_socket_path() -> str:
    """Resolve $SSH_AUTH_SOCK for --ssh-agent. Fails loudly: an explicit
    flag must never silently forward nothing (or bind a non-socket)."""
    raw = (os.environ.get("SSH_AUTH_SOCK") or "").strip()
    if not raw:
        die("--ssh-agent: SSH_AUTH_SOCK is not set — no agent to forward")
    path = os.path.realpath(raw)  # agents are often reached via a symlink
    try:
        st = os.stat(path)
    except OSError as e:
        die(f"--ssh-agent: agent socket {raw!r} is not usable: {e}")
    if not stat.S_ISSOCK(st.st_mode):
        die(f"--ssh-agent: SSH_AUTH_SOCK {raw!r} is not a Unix socket")
    return path


def build_bwrap(opts, sand: str, sock: str, home: str, user_binds: list[tuple[str, str]],
                agent: str | None, ssh_cfg: str | None) -> tuple[list[str], str]:
    import pwd  # POSIX only; we require Linux anyway (bwrap)

    uid = os.getuid()
    user = os.environ.get("USER") or pwd.getpwuid(uid).pw_name
    bw = [
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--setenv", "HOME", home,
        "--setenv", "USER", user,
        "--setenv", "TERM", os.environ.get("TERM") or "xterm-256color",
        "--setenv", "PATH", os.environ.get("PATH") or "/usr/local/bin:/usr/bin:/bin",
        "--setenv", "LANG", os.environ.get("LANG") or "C.UTF-8",
        "--proc", "/proc",
        "--dev", "/dev",
        "--bind", sand, "/tmp",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind-try", "/lib", "/lib",
        "--ro-bind-try", "/lib64", "/lib64",
        "--ro-bind-try", "/bin", "/bin",
        "--ro-bind-try", "/sbin", "/sbin",
        # CA stores: Debian/Ubuntu (/etc/ssl), Fedora/RHEL (/etc/pki, where
        # /etc/ssl/certs is often a dangling symlink without this), misc.
        "--ro-bind-try", "/etc/ssl", "/etc/ssl",
        "--ro-bind-try", "/etc/pki", "/etc/pki",
        "--ro-bind-try", "/etc/ca-certificates", "/etc/ca-certificates",
        "--ro-bind-try", "/etc/hosts", "/etc/hosts",
        "--ro-bind-try", "/etc/localtime", "/etc/localtime",
        "--ro-bind-try", "/etc/passwd", "/etc/passwd",
        "--ro-bind-try", "/etc/group", "/etc/group",
        # Debian/Ubuntu: many /usr/bin entries (awk, editor, java, vi, at
        # times python3) are symlinks into /etc/alternatives, which dangle
        # without this; ld.so.cache matters if libs live outside the default
        # loader paths.
        "--ro-bind-try", "/etc/alternatives", "/etc/alternatives",
        "--ro-bind-try", "/etc/ld.so.cache", "/etc/ld.so.cache",
        "--perms", "0755", "--tmpfs", "/run",
    ]

    if not opts.net:
        bw += [
            "--setenv", "all_proxy", "socks5h://127.0.0.1:1080",
            "--setenv", "ALL_PROXY", "socks5h://127.0.0.1:1080",
            "--setenv", "http_proxy", "http://127.0.0.1:1080",
            "--setenv", "https_proxy", "http://127.0.0.1:1080",
            "--setenv", "HTTP_PROXY", "http://127.0.0.1:1080",
            "--setenv", "HTTPS_PROXY", "http://127.0.0.1:1080",
            "--setenv", "no_proxy", "localhost,127.0.0.1,::1",
            "--setenv", "NO_PROXY", "localhost,127.0.0.1,::1",
            "--ro-bind", sock, "/run/proxy.sock",
        ]
        if ssh_cfg:
            # Nothing else mounts /etc/ssh; bwrap creates the dest path.
            bw += ["--ro-bind", ssh_cfg, "/etc/ssh/ssh_config"]
        inner = INNER_PROXY
    else:
        # --share-net keeps the host network namespace (only valid together
        # with --unshare-all); resolv.conf makes DNS work. NOTE: this also
        # exposes host loopback services and abstract Unix sockets.
        bw += ["--share-net", "--ro-bind-try", "/etc/resolv.conf", "/etc/resolv.conf"]
        inner = INNER_DIRECT

    if opts.home:
        bw += ["--bind", home, home]
    else:
        bw += ["--perms", "0700", "--tmpfs", home]

    if opts.gui:
        # X11 allows any client to log keys / capture the screen; Wayland is
        # the preferred path. Keep the sockets themselves read-only.
        xdg = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}"
        bw += ["--setenv", "XDG_RUNTIME_DIR", xdg, "--perms", "0700", "--dir", xdg]
        wl = os.environ.get("WAYLAND_DISPLAY")
        if wl:
            path = wl if wl.startswith("/") else os.path.join(xdg, wl)
            bw += ["--setenv", "WAYLAND_DISPLAY", wl, "--ro-bind-try", path, path]
        if os.environ.get("DISPLAY"):
            bw += ["--setenv", "DISPLAY", os.environ["DISPLAY"],
                   "--ro-bind-try", "/tmp/.X11-unix", "/tmp/.X11-unix"]
            for xauth in (os.environ.get("XAUTHORITY"), os.path.join(home, ".Xauthority")):
                if xauth and os.path.exists(xauth):
                    bw += ["--setenv", "XAUTHORITY", xauth, "--ro-bind-try", xauth, xauth]
                    break

    if agent:
        # One socket file, read-only — connect() works through a ro-bind
        # (same trick as /run/proxy.sock). Fixed path inside, because the
        # host path is usually under /run/user/<uid>, which stays hidden.
        bw += [
            "--ro-bind", agent, "/run/ssh-agent.sock",
            "--setenv", "SSH_AUTH_SOCK", "/run/ssh-agent.sock",
        ]

    # Current directory: bind it (rw unless --ro-cwd) unless it covers a
    # protected path (system dir, $HOME or an ancestor of it — a recursive
    # bind of e.g. /home would cover the tmpfs $HOME and expose the real
    # ~/.ssh etc.) or sits under a tmpfs $HOME. A cwd at or below an
    # explicitly bound path still exists inside the sandbox, so chdir works.
    # Children of /dev, /proc, /sys and /run (incl. XDG_RUNTIME_DIR) are not
    # auto-mounted either: `cd` alone should never hand over runtime state —
    # use an explicit -b for the rare legitimate case (e.g. -b /dev/dri).
    real_home = os.path.realpath(home)
    protected = sorted(protected_paths(home))
    runtime_roots = ("/dev", "/proc", "/sys", "/run")
    project = os.path.realpath(os.getcwd())
    bind = True
    if project == real_home or project.startswith(real_home + "/"):
        if not opts.home:
            err("note: cwd is inside $HOME and $HOME is a tmpfs — using /tmp instead (--home to bind)")
            bind = False
    else:
        hits = [q for q in protected if covers(project, q)]
        hits += [q for q in runtime_roots if covers(q, project)]
        if hits:
            err(f"note: cwd {project} overlaps protected path(s) {', '.join(sorted(set(hits)))} — not mounting it")
            bind = False

    # Emit the cwd bind BEFORE the user binds: a later bind shadows earlier
    # mounts at or below its target, so the automatic (rw by default) cwd
    # mount must come first for explicit -r/-b flags to win — `-r "$PWD"`
    # would otherwise silently end up read-write.
    if bind:
        bw += ["--ro-bind" if opts.ro_cwd else "--bind", project, project]

    for flag, rp in user_binds:
        bw += [flag, rp, rp]  # mount exactly the validated (resolved) path

    # bwrap applies --chdir after all mounts, wherever it sits in argv.
    user_bound = {rp for _, rp in user_binds}
    if bind or any(covers(b, project) for b in user_bound):
        bw += ["--chdir", project]
    else:
        bw += ["--chdir", "/tmp"]

    return bw, inner


def wait_for_socket(sock_path: str, proc: subprocess.Popen, timeout: float = 5.0) -> None:
    """Wait until the proxy is actually accepting connections. The socket
    file appears at bind() time, before listen(), so existence alone is not
    enough — poll with a real connect() to avoid an ECONNREFUSED race."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(sock_path):
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                probe.connect(sock_path)
                return
            except OSError:
                pass  # bound but not listening yet
            finally:
                probe.close()
        if proc.poll() is not None:
            die("the proxy died at startup (see errors above)")
        time.sleep(0.02)
    die("the proxy did not come up")


def rm_tree_writable(path: str) -> None:
    # The sandbox may have created 0555 directories; make them removable.
    # lstat everywhere: /tmp inside the sandbox is attacker-controlled, and
    # a symlink like x -> ~/.ssh/config must never be chmod'ed through.
    for dirpath, dirnames, filenames in os.walk(path):
        for name in dirnames + filenames:
            p = os.path.join(dirpath, name)
            try:
                st = os.lstat(p)
                if not stat.S_ISLNK(st.st_mode):
                    os.chmod(p, st.st_mode | 0o700)
            except OSError:
                pass
    shutil.rmtree(path, ignore_errors=True)


def run_sandbox(opts, command: list[str], allows: list[dict], upstream: dict | None) -> int:
    # During startup there is nothing to forward signals to yet; die so the
    # finally below removes $WORK (proxy.json may hold upstream credentials).
    # Replaced by the forwarding handler once the sandbox is up. Installed
    # before $WORK exists so every startup signal is caught by these handlers.
    def early_signal(signum, _frame):
        raise SystemExit(128 + signum)

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, early_signal)

    work: str | None = None
    procs: list[subprocess.Popen] = []
    sandbox: subprocess.Popen | None = None
    proxy: subprocess.Popen | None = None
    try:
        # mkdtemp inside the try: early_signal raises SystemExit, and a
        # signal landing anywhere between mkdtemp() and the setup below must
        # still unwind through the finally instead of leaking $WORK on the
        # host (os.mkdir(sand) etc. are such windows).
        work = tempfile.mkdtemp(prefix="sbox.", dir="/tmp")
        sand = os.path.join(work, "tmp")
        sock = os.path.join(work, "net.sock")
        cfg_path = os.path.join(work, "proxy.json")
        os.mkdir(sand)
        os.chmod(work, 0o700)
        # Validate user binds (resolved paths) before starting anything.
        user_binds = check_bind_paths(opts, os.environ["HOME"])
        agent = agent_socket_path() if opts.ssh_agent else None
        ssh_cfg = None

        if not opts.net:
            # Created 0600 from the start — it may carry upstream credentials.
            fd = os.open(cfg_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"allows": allows, "upstream": upstream, "verbose": opts.verbose}, fh)
            proxy = subprocess.Popen(
                [sys.executable, os.path.abspath(__file__), "--_proxy", sock, cfg_path, str(os.getpid())],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,  # logs go to stderr
                start_new_session=True,  # keep terminal Ctrl-C out of the proxy's way
            )
            procs.append(proxy)
            wait_for_socket(sock, proxy)
            # The proxy has read its config by now (it accepted a connection);
            # drop the file so a SIGKILLed launcher cannot leave credentials
            # behind in /tmp.
            try:
                os.unlink(cfg_path)
            except OSError:
                pass
            self_test(sock, allows)
            # No secrets here (the proxy does the allowlist checks), so this
            # one is world-readable and merely deleted with $WORK at exit.
            ssh_cfg = os.path.join(work, "ssh_config")
            with open(ssh_cfg, "w", encoding="utf-8") as fh:
                fh.write(SSH_CLIENT_CONFIG)

        bw, inner = build_bwrap(opts, sand, sock, os.environ["HOME"], user_binds, agent, ssh_cfg)
        sandbox = subprocess.Popen(["bwrap"] + bw + ["--", "/bin/sh", "-c", inner, "sbox-sh"] + command)
        procs.append(sandbox)

        seen_signals: set[int] = set()

        def forward(signum, _frame):
            # The first signal is relayed as-is; a sandboxed command that
            # traps or ignores it would otherwise hang the launcher forever
            # (repeated Ctrl-C did nothing useful), so the same signal
            # arriving twice escalates to SIGKILL. --die-with-parent already
            # covers a SIGKILL of the launcher itself.
            escalate = signum in seen_signals
            seen_signals.add(signum)
            if sandbox is None or sandbox.poll() is not None:
                return
            try:
                if escalate:
                    sandbox.kill()
                else:
                    sandbox.send_signal(signum)
            except ProcessLookupError:
                pass

        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, forward)

        # Supervisor: if the proxy dies, tear the sandbox down (and vice versa).
        while sandbox.poll() is None:
            if proxy is not None and proxy.poll() is not None:
                err("the network proxy exited unexpectedly — shutting the sandbox down")
                sandbox.terminate()
                try:
                    sandbox.wait(5)
                except subprocess.TimeoutExpired:
                    sandbox.kill()
                    sandbox.wait()
                return 1
            time.sleep(0.1)
        rc = sandbox.returncode
        if rc is None:
            rc = 1
        elif rc < 0:  # killed by a signal: report the conventional 128+signum
            rc = 128 - rc
        return rc
    finally:
        # A second Ctrl-C while cleaning up must not abort the cleanup
        # (a skipped rm_tree_writable would leave proxy.json behind).
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(3)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        if work:
            rm_tree_writable(work)


# ---------------------------------------------------------------------- cli ---

OPTS_WITH_VALUE = {
    "-a", "--allow", "-A", "--allow-file", "-b", "--bind", "-r", "--ro-bind",
    "--upstream", "--_proxy",
}


def split_argv(argv: list[str]) -> tuple[list[str], list[str]]:
    """Split argv at the first positional: everything after it belongs to the
    sandboxed command (so `sbox.py -- cmd -v` works), like the shell version."""
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--":
            return argv[:i], argv[i + 1:]
        if tok.startswith("-") and tok != "-":
            # "--allow x" consumes two tokens; "--allow=x" (or a flag) one.
            i += 2 if "=" not in tok and tok in OPTS_WITH_VALUE else 1
            continue
        return argv[:i], argv[i:]
    return argv, []


def parse_cli(argv: list[str]):
    pre, command = split_argv(argv)
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Run COMMAND in a bubblewrap sandbox with an allowlisted network.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,  # split_argv only knows full option names
        epilog="""\
By default the sandbox has no network except a SOCKS5 *and* HTTP-CONNECT
proxy (auto-detected) at 127.0.0.1:1080 — http_proxy/https_proxy/all_proxy
are pre-set. https:// always goes through CONNECT; plain http:// URLs are
forwarded (absolute-form). Destinations not on the allowlist are denied
BEFORE any DNS lookup happens. Hostnames are resolved host-side; answers in
private, loopback, link-local or CGNAT ranges are rejected, so allowed names
cannot reach host/LAN services (explicit -a IP/CIDR entries bypass that
guard; effectively catch-all networks such as 0.0.0.0/1 are refused).
--net drops the proxy and shares the host network namespace instead.

Notes:
  - --net also exposes host loopback services and abstract Unix sockets
    (D-Bus, X11, ...) to the sandbox; only use it for trusted work.
  - --gui passes through Wayland (preferred) and X11. X11 lets any client
    log keystrokes and capture the screen.
  - --ssh-agent forwards $SSH_AUTH_SOCK to /run/ssh-agent.sock (read-only,
    $SSH_AUTH_SOCK preset). Combined with the injected ssh config, ssh can
    then authenticate with your keys through the allowlisted proxy.
  - Proxied mode installs /etc/ssh/ssh_config with a ProxyCommand (socat
    HTTP-CONNECT through 127.0.0.1:1080): ssh/scp/sftp/git-over-ssh ride the
    allowlist without extra flags. ~/.ssh/config is read first and wins
    per-option; `ssh -o ProxyCommand=none` opts out (and usually fails,
    fail-closed). --net installs nothing (direct egress, no allowlist).
  - The cwd is mounted read-write by default: sandboxed code can plant
    .git/hooks, Makefiles etc. that run on the host later. Use --ro-cwd
    for untrusted code.
  - Explicit -b/-r binds overlay the automatic cwd mount when they cover
    it: -r "$PWD" from inside the directory gives a read-only cwd, and
    likewise -b over --ro-cwd gives read-write (the explicit flag wins).
  - The sandbox runs in a new session (TIOCSTI protection): Ctrl-C reaches
    sbox.py, which then tears the whole sandbox down.

Examples:
  sbox.py -a pypi.org -a files.pythonhosted.org -- pip install requests
  sbox.py -a github.com -- git clone https://github.com/torvalds/linux
  sbox.py -a example.com -v -- curl -sI https://example.com
  sbox.py --ssh-agent -a github.com -- git clone git@github.com:me/repo.git
""",
    )
    parser.add_argument("-a", "--allow", action="append", default=[], metavar="HOST",
                        help="Allow HOST or any subdomain (suffix match on a dot boundary); "
                             "IP/CIDR entries match literal IP destinations; optional :port. Repeatable.")
    parser.add_argument("-A", "--allow-file", action="append", default=[], metavar="FILE",
                        help="File with allow entries (one per line, '#' comments). Repeatable.")
    parser.add_argument("-b", "--bind", action="append", default=[], metavar="PATH",
                        help="Bind PATH read-write at the same location. Repeatable.")
    parser.add_argument("-r", "--ro-bind", action="append", default=[], metavar="PATH",
                        help="Bind PATH read-only at the same location. Repeatable.")
    parser.add_argument("--ro-cwd", action="store_true", help="Mount the current directory read-only (default: rw).")
    parser.add_argument("--home", action="store_true", help="Bind the real $HOME (default: private tmpfs home).")
    parser.add_argument("--gui", action="store_true", help="Pass through Wayland/X11 sockets (X11: see notes).")
    parser.add_argument("--ssh-agent", action="store_true",
                        help="Forward the host SSH agent socket ($SSH_AUTH_SOCK) into the sandbox, read-only, "
                             "at /run/ssh-agent.sock. Anything in the sandbox can then sign with every key "
                             "loaded in the agent.")
    parser.add_argument("--upstream", metavar="URL",
                        help="Egress through an upstream proxy: http://, https://, socks5://, socks5h:// "
                             "(userinfo supported). Default: $SBOX_UPSTREAM, else $https_proxy/$HTTPS_PROXY. "
                             "Pass an empty string to force direct egress.")
    parser.add_argument("--upstream-insecure", action="store_true",
                        help="Do not verify the upstream's TLS certificate (https:// upstreams).")
    parser.add_argument("--net", action="store_true",
                        help="Share the host network namespace: direct egress, DNS via the host resolver, "
                             "no proxy/allowlist (-a/-A/--upstream are ignored).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Log allow/deny decisions to stderr.")
    parser.add_argument("--shell", action="store_true", help="Run an interactive shell ($SHELL if available).")
    parser.add_argument("--_proxy", nargs=3, metavar=("SOCK", "CFG", "PPID"), help=argparse.SUPPRESS)
    opts = parser.parse_args(pre)
    return parser, opts, command


def main(argv: list[str]) -> int:
    if argv[:1] == ["--_proxy"]:
        if len(argv) != 4:
            die("internal error: --_proxy needs SOCK CFG PPID")
        return proxy_main(argv[1], argv[2], int(argv[3]))
    parser, opts, command = parse_cli(argv)
    if opts._proxy:
        return proxy_main(*opts._proxy)

    if not shutil.which("bwrap"):
        die("missing dependency: bwrap (needed on the host)")
    if not opts.net and not shutil.which("socat"):
        die("missing dependency: socat (needed on the host for the in-sandbox bridge)")
    if "HOME" not in os.environ:
        die("HOME is not set")

    if opts.shell and command:
        parser.error("--shell takes no command")
    if opts.shell:
        shell = os.environ.get("SHELL") or "/bin/bash"
        home = os.environ["HOME"]
        usable = shell.startswith(("/usr/", "/bin/")) or (opts.home and shell.startswith(home + "/"))
        if not usable or not os.path.isfile(shell):
            shell = "/bin/bash" if os.path.isfile("/bin/bash") else "/bin/sh"
            err(f"note: $SHELL is not available inside the sandbox — falling back to {shell}")
        command = [shell]
    if not command:
        parser.error("no command given (or use --shell)")

    if opts.net and (opts.allow or opts.allow_file or opts.upstream is not None):
        err("warning: --net shares the host network directly; -a/-A/--upstream are ignored")

    try:
        allows = load_allows(opts.allow, opts.allow_file)
        if not opts.net and not allows:
            err("warning: no --allow entries — ALL outbound connections will be denied")

        if opts.upstream is None:
            raw = os.environ.get("SBOX_UPSTREAM") or os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or ""
        else:
            raw = opts.upstream
        upstream = parse_upstream(raw, opts.upstream_insecure or bool(os.environ.get("SBOX_UPSTREAM_INSECURE")))

        return run_sandbox(opts, command, allows, upstream)
    except KeyboardInterrupt:
        # Covers the pre-sandbox window (allow-file reads can block, e.g.
        # -A on a FIFO) plus the few instructions at run_sandbox entry
        # before it installs early_signal/forward — from then on SIGINT is
        # handled there and never surfaces as KeyboardInterrupt.
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

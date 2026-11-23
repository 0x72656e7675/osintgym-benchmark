from __future__ import annotations

import asyncio
import base64
import json
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from urllib.parse import parse_qsl, unquote, urlsplit

import httpx
import uvicorn

from .world.web import Request, Response, Web

# Path form of the gateway, for clients that reach it over ordinary HTTPS, where no proxy can be addressed:
# /gateway/{attempt}/{host}/{path}?{query} stands for http://{host}/{path}?{query} requested by that attempt.
PATH_PREFIX = "/gateway/"


@dataclass
class Entry:
    attempt: str | None
    at: float
    method: str
    url: str
    status: int
    in_world: bool
    event: dict | None = None


class RequestLog:
    def __init__(self, sink: Callable[[Entry], None] | None = None) -> None:
        self._lock = threading.Lock()
        self.entries: list[Entry] = []
        self.sink = sink

    def add(self, entry: Entry) -> None:
        with self._lock:
            self.entries.append(entry)
            if self.sink is not None:
                self.sink(entry)

    def restore(self, entries: list[Entry]) -> None:
        with self._lock:
            self.entries.extend(entries)

    def forget(self, attempt: str) -> None:
        with self._lock:
            self.entries = [e for e in self.entries if e.attempt != attempt]

    def for_attempt(self, attempt: str) -> list[Entry]:
        with self._lock:
            return [e for e in self.entries if e.attempt == attempt]

    def dump(self) -> list[dict]:
        with self._lock:
            return [asdict(e) for e in self.entries]


def _attempt(headers: dict[str, str]) -> str | None:
    credentials = headers.get("proxy-authorization", "")
    if credentials.lower().startswith("basic "):
        try:
            user = base64.b64decode(credentials[6:].strip()).decode().split(":", 1)[0]
        except (ValueError, UnicodeDecodeError):
            user = ""
        if user:
            return user
    return headers.get("x-osintgym-attempt") or None


async def _lifespan(receive, send, on_shutdown: Callable | None = None) -> None:
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            if on_shutdown is not None:
                await on_shutdown()
            await send({"type": "lifespan.shutdown.complete"})
            return


async def _body(receive, limit: int) -> bytes:
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if len(body) > limit or not message.get("more_body"):
            return body


async def _send(send, response: Response) -> None:
    # no-transform keeps CDNs in front of a hosted gateway from rewriting pages (e-mail obfuscation, injected
    # scripts) or images (stripped metadata): what an agent reads must be what the world served.
    await send({"type": "http.response.start", "status": response.status, "headers": [
        (b"content-type", response.content_type.encode()),
        (b"content-length", str(len(response.body)).encode()),
        (b"cache-control", b"no-store, no-transform"),
    ]})
    await send({"type": "http.response.body", "body": response.body})


class Gateway:
    """The only network an agent sees: world hosts answer, every other name fails to resolve. Requests are
    attributed to an attempt through proxy credentials, a header or the path form, and logged with any action they
    perform. With admit set, only the attempts it accepts are served."""

    def __init__(self, web: Web, log: RequestLog | None = None, max_body: int = 1_000_000,
                 admit: Callable[[str | None], bool] | None = None):
        self.web = web
        self.log = log or RequestLog()
        self.max_body = max_body
        self.admit = admit
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="world")

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "lifespan":
            await _lifespan(receive, send)
            return
        if scope["type"] != "http":
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        method = scope["method"].upper()
        path = scope["path"]
        query_string = scope.get("query_string", b"").decode("latin-1")
        host = headers.get("host", "")
        if path.startswith(("http://", "https://")):
            parts = urlsplit(path)
            host, path = parts.netloc, unquote(parts.path) or "/"
            query_string = parts.query or query_string
        host = host.split(":", 1)[0].lower()
        attempt = _attempt(headers)
        if not self.web.is_world_host(host):
            if path == "/healthz":
                await _send(send, Response(200, b"ok\n", "text/plain"))
                return
            if path.startswith(PATH_PREFIX):
                attempt, _, rest = path[len(PATH_PREFIX):].partition("/")
                host, _, rest = rest.partition("/")
                attempt, host, path = attempt or None, host.split(":", 1)[0].lower(), "/" + rest
        if self.admit is not None and not self.admit(attempt):
            await _send(send, Response(403, b"Unknown or closed attempt", "text/plain"))
            return
        url = f"http://{host}{path}" + (f"?{query_string}" if query_string else "")
        if method == "CONNECT":
            self.log.add(Entry(attempt, time.time(), method, url, 405, False))
            await _send(send, Response(405, b"CONNECT is not supported", "text/plain"))
            return
        body = await _body(receive, self.max_body)
        form: dict[str, str] = {}
        content_type = headers.get("content-type", "")
        if method == "POST":
            if "application/json" in content_type:
                try:
                    data = json.loads(body or b"{}")
                    form = {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
                except ValueError:
                    form = {}
            else:
                form = dict(parse_qsl(body.decode("utf-8", "replace"), keep_blank_values=True))
        query = dict(parse_qsl(query_string, keep_blank_values=True))
        trimmed = path[:-1] if len(path) > 1 and path.endswith("/") else path
        request = Request(method, host, unquote(trimmed), query, form, attempt)
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(self._executor, self.web.handle, request)
        if response is None:
            self.log.add(Entry(attempt, time.time(), method, url, 502, False))
            await _send(send, Response(502, f"Could not resolve host: {host}".encode(), "text/plain"))
            return
        self.log.add(Entry(attempt, time.time(), method, url, response.status, True, response.event))
        await _send(send, response)


class Relay:
    """A local HTTP proxy for harnesses that expect one, in front of a gateway reached only through its path form,
    such as the hidden split behind HTTPS: a request for http://{host}/{path} whose proxy user name is the attempt
    goes to {gateway}/{attempt}/{host}/{path}. Pages and images pass through unchanged."""

    def __init__(self, gateway: str, max_body: int = 1_000_000):
        self.gateway = gateway.rstrip("/")
        self.max_body = max_body
        self._client: httpx.AsyncClient | None = None

    async def _close(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "lifespan":
            await _lifespan(receive, send, self._close)
            return
        if scope["type"] != "http":
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        method = scope["method"].upper()
        if method == "CONNECT":
            await _send(send, Response(405, b"CONNECT is not supported", "text/plain"))
            return
        attempt = _attempt(headers)
        if not attempt:
            await _send(send, Response(407, b"The proxy user name must be the attempt", "text/plain"))
            return
        target = (scope.get("raw_path") or scope["path"].encode()).decode("latin-1")
        host = headers.get("host", "")
        if target.startswith(("http://", "https://")):
            parts = urlsplit(target)
            host, target = parts.netloc, parts.path or "/"
        host = host.rsplit("@", 1)[-1].split(":", 1)[0].lower()
        query = scope.get("query_string", b"").decode("latin-1")
        url = f"{self.gateway}/{attempt}/{host}{target}" + (f"?{query}" if query else "")
        body = await _body(receive, self.max_body)
        forward = {k: v for k, v in headers.items() if k in ("content-type", "user-agent", "accept")}
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        try:
            upstream = await self._client.request(method, url, content=body or None, headers=forward)
            response = Response(upstream.status_code, upstream.content,
                                upstream.headers.get("content-type", "application/octet-stream"))
        except httpx.HTTPError as exc:
            response = Response(502, f"Gateway unreachable: {type(exc).__name__}".encode(), "text/plain")
        await _send(send, response)


class Server:
    """Runs an ASGI app on a background thread; port 0 picks a free port."""

    def __init__(self, app, host: str = "127.0.0.1", port: int = 0):
        self.config = uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False, lifespan="on")
        self.server = uvicorn.Server(self.config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.port = port

    def __enter__(self) -> Server:
        self.thread.start()
        while not self.server.started:
            if not self.thread.is_alive():
                raise RuntimeError("world server failed to start")
            time.sleep(0.02)
        self.port = self.server.servers[0].sockets[0].getsockname()[1]
        return self

    def __exit__(self, *exc) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)

    @property
    def url(self) -> str:
        return f"http://{self.config.host}:{self.port}"

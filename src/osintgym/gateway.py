from __future__ import annotations

import asyncio
import base64
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from urllib.parse import parse_qsl, unquote, urlsplit

import uvicorn

from .world.web import Request, Response, Web


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
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.entries: list[Entry] = []

    def add(self, entry: Entry) -> None:
        with self._lock:
            self.entries.append(entry)

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


class Gateway:
    """The only network an agent sees: world hosts answer, every other name fails to resolve. Requests are
    attributed to an attempt through proxy credentials or a header, and logged with any action they perform."""

    def __init__(self, web: Web, log: RequestLog | None = None, max_body: int = 1_000_000):
        self.web = web
        self.log = log or RequestLog()
        self.max_body = max_body
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="world")

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
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
        url = f"http://{host}{path}" + (f"?{query_string}" if query_string else "")
        if method == "CONNECT":
            self.log.add(Entry(attempt, time.time(), method, url, 405, False))
            await self._send(send, Response(405, b"CONNECT is not supported", "text/plain"))
            return
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if len(body) > self.max_body or not message.get("more_body"):
                break
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
            await self._send(send, Response(502, f"Could not resolve host: {host}".encode(), "text/plain"))
            return
        self.log.add(Entry(attempt, time.time(), method, url, response.status, True, response.event))
        await self._send(send, response)

    async def _send(self, send, response: Response) -> None:
        await send({"type": "http.response.start", "status": response.status, "headers": [
            (b"content-type", response.content_type.encode()),
            (b"content-length", str(len(response.body)).encode()),
            (b"cache-control", b"no-store"),
        ]})
        await send({"type": "http.response.body", "body": response.body})


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

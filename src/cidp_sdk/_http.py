"""The one place the SDK talks HTTP: the base path, the bearer token, request ids, errors and pagination."""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import IO, Any, TypeVar

import httpx
from pydantic import BaseModel

from cidp_sdk import __version__
from cidp_sdk.errors import BY_STATUS, OUTCOME_UNKNOWN, CIDPError, OutcomeUnknown, TooManyRequests, TransportError

API = "/api/data/v1"
T = TypeVar("T", bound=BaseModel)
log = logging.getLogger("cidp_sdk")

# Every token value the SDK has held, so a log line can be cleaned of one whatever put it there (design A5).
_SECRETS: set[str] = set()
_BEARER = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+")


def remember(secret: str | None) -> None:
    """A token (or client secret) the redactor must take out of log records."""
    if secret and len(secret) >= 8:
        _SECRETS.add(secret)


def redact(text: str) -> str:
    for s in _SECRETS:
        if s in text:
            text = text.replace(s, "***")
    return _BEARER.sub(r"\1 ***", text)


class _Redact(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        clean = redact(message)
        if clean != message:
            record.msg, record.args = clean, ()
        return True


for _name in ("cidp_sdk", "httpx", "httpcore"):
    logging.getLogger(_name).addFilter(_Redact())


class TokenSource:
    """Where the bearer token comes from: a fixed token, client credentials or a browser login (``auth``)."""

    def token(self) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def refresh(self) -> bool:
        """Get a new token after the service refused the current one; False when there is no other to get."""
        return False

    def close(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class _Bearer(httpx.Auth):
    def __init__(self, tokens: TokenSource):
        self.tokens = tokens

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self.tokens.token()}"
        response = yield request
        if response.status_code == 401 and self.tokens.refresh():
            request.headers["Authorization"] = f"Bearer {self.tokens.token()}"
            yield request


def _error(method: str, path: str, r: httpx.Response, request_id: str) -> CIDPError:
    rid = r.headers.get("x-request-id") or request_id
    code, message, details = "error", "", None
    try:
        body = r.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and isinstance(body.get("code"), str):
        code, message, details = body["code"], str(body.get("message") or ""), body.get("details")
    # The service's message is written for people; a message that quotes a token is replaced, never shown.
    if not message or redact(message) != message:
        message = f"{method} {API}{path}: HTTP {r.status_code}"
    # outcome_unknown goes by its code, whatever the status (504 today): it is never a plain 5xx to try again.
    cls = OutcomeUnknown if code in OUTCOME_UNKNOWN else BY_STATUS.get(r.status_code, CIDPError)
    kw: dict[str, Any] = {"code": code, "status": r.status_code, "request_id": rid,
                          "details": details if isinstance(details, dict) else None}  # fmt: skip
    if cls is OutcomeUnknown:
        cause = kw["details"].get("cause") if kw["details"] else None
        kw["cause"] = cause if isinstance(cause, str) else None
    if cls is TooManyRequests:
        try:
            kw["retry_after"] = float(r.headers["retry-after"])
        except (KeyError, ValueError):
            kw["retry_after"] = None
    return cls(message, **kw)


class FileBody:
    """A file sent as a request body in chunks, never read whole into memory. Its length is sent as Content-Length
    (no chunked encoding), and each send starts from the file's start again (a send after a refreshed token)."""

    CHUNK = 1024 * 1024

    def __init__(self, file: IO[bytes]):
        self.file = file
        self.start = file.tell()
        file.seek(0, 2)
        self.length = file.tell() - self.start
        file.seek(self.start)

    def __iter__(self) -> Iterator[bytes]:
        self.file.seek(self.start)
        while chunk := self.file.read(self.CHUNK):
            yield chunk


def raw_body(data: bytes | IO[bytes]) -> tuple[bytes | FileBody, dict[str, str]]:
    """A raw request body and its headers: bytes as they are, a binary file streamed (``FileBody``)."""
    headers = {"Content-Type": "application/octet-stream"}
    if isinstance(data, bytes | bytearray | memoryview):
        return bytes(data), headers
    body = FileBody(data)
    return body, {**headers, "Content-Length": str(body.length)}


class Http:
    """A synchronous client of ``<host>/api/data/v1``. ``transport`` replaces the network (tests, a proxy)."""

    def __init__(self, host: str, tokens: TokenSource | None, *, transport: httpx.BaseTransport | None = None,
                 timeout: float = 60.0, verify: Any = True):  # fmt: skip
        self.host = host.rstrip("/")
        self.tokens = tokens
        self._client = httpx.Client(
            base_url=self.host + API,
            transport=transport,
            timeout=timeout,
            verify=verify,
            auth=_Bearer(tokens) if tokens else None,
            headers={"User-Agent": f"cidp-sdk/{__version__}"},
            follow_redirects=False,
        )

    def __repr__(self) -> str:
        return f"Http(host={self.host!r})"

    def use(self, tokens: TokenSource) -> None:
        """Sign the calls from now on with ``tokens`` (the client reads ``/config`` before it knows how to sign in)."""
        self.tokens = tokens
        self._client.auth = _Bearer(tokens)

    def close(self) -> None:
        self._client.close()
        if self.tokens:
            self.tokens.close()

    def call(self, method: str, path: str, *, params: Mapping[str, Any] | None = None, json: Any = None,
             content: bytes | Iterable[bytes] | None = None, headers: Mapping[str, str] | None = None,
             authenticated: bool = True) -> httpx.Response:  # fmt: skip
        """One request; an answer of 400 or more raises the error class for its status. ``content``: a raw body."""
        rid = uuid.uuid4().hex
        query = {k: v for k, v in (params or {}).items() if v is not None}
        extra: dict[str, Any] = {} if authenticated else {"auth": None}
        log.debug("%s %s%s request_id=%s", method, API, path, rid)
        try:
            r = self._client.request(method, path, params=query, json=json, content=content,
                                     headers={"X-Request-Id": rid, **(headers or {})}, **extra)  # fmt: skip
        except httpx.HTTPError as e:
            raise TransportError(f"{method} {API}{path}: the service did not answer ({type(e).__name__})",
                                 code="transport", request_id=rid) from None  # fmt: skip
        if r.status_code >= 400:
            raise _error(method, path, r, rid)
        return r

    def events(self, path: str, *, params: Mapping[str, Any] | None = None,
               timeout: httpx.Timeout | None = None) -> Iterator[tuple[str, str, str | None]]:  # fmt: skip
        """A server-sent stream as ``(event, data, id)``, and ``("ping", "", None)`` for each comment line (the
        service's heartbeat: it had nothing new). An answer of 400 or more raises as ``call`` does."""
        rid = uuid.uuid4().hex
        query = {k: v for k, v in (params or {}).items() if v is not None}
        headers = {"X-Request-Id": rid, "Accept": "text/event-stream", "Cache-Control": "no-cache"}
        log.debug("GET %s%s (stream) request_id=%s", API, path, rid)
        try:
            with self._client.stream("GET", path, params=query, headers=headers,
                                     timeout=timeout or httpx.USE_CLIENT_DEFAULT) as r:  # fmt: skip
                if r.status_code >= 400:
                    r.read()
                    raise _error("GET", path, r, rid)
                event, data, ident = "message", "", None
                for line in r.iter_lines():
                    if line == "":
                        if data:
                            yield event, data, ident
                        event, data, ident = "message", "", None
                    elif line.startswith(":"):
                        yield "ping", "", None
                    else:
                        field, _, value = line.partition(":")
                        value = value.removeprefix(" ")
                        if field == "event":
                            event = value
                        elif field == "data":
                            data = f"{data}\n{value}" if data else value
                        elif field == "id":
                            ident = value
        except httpx.HTTPError as e:
            raise TransportError(f"GET {API}{path}: the stream broke off ({type(e).__name__})",
                                 code="transport", request_id=rid) from None  # fmt: skip

    def get(self, path: str, model: type[T], /, **params: Any) -> T:
        return model.model_validate(self.call("GET", path, params=params).json())

    def send(self, method: str, path: str, model: type[T] | None, body: Any = None, *,
             headers: Mapping[str, str] | None = None, **params: Any) -> Any:  # fmt: skip
        r = self.call(method, path, json=body, params=params, headers=headers)
        return model.model_validate(r.json()) if model is not None else None

    def items(self, path: str, model: type[T], /, **params: Any) -> list[T]:
        """A listing answered in one page (``items`` without ``next_cursor``)."""
        return [model.model_validate(x) for x in self.call("GET", path, params=params).json()["items"]]

    def pages(self, path: str, item: Callable[[Any], T], /, *, limit: int | None = None, **params: Any) -> Iterator[T]:
        """Every item of a listing, following ``next_cursor`` page by page (``limit`` is the page size)."""
        cursor: str | None = None
        while True:
            body = self.call("GET", path, params={**params, "limit": limit, "cursor": cursor}).json()
            for x in body["items"]:
                yield item(x)
            cursor = body.get("next_cursor")
            if not cursor:
                return

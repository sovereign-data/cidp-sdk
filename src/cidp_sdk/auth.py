"""Tokens (design A5): a fixed token, client credentials, or a browser login with code and PKCE over loopback.

The service's ``/v1/config`` names the issuer and the public client; the issuer's discovery document names the
endpoints. A browser login keeps its refresh token in the OS keyring under ``cidp-sdk``, keyed by host and
profile, and never in a file; without a keyring backend it keeps it in memory and warns. Access tokens stay in
memory. No token reaches a log, a ``repr`` or an error.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import secrets
import threading
import time
import warnings
import webbrowser
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from cidp_sdk._http import TokenSource, remember
from cidp_sdk.errors import ConfigError, Unauthenticated

KEYRING_SERVICE = "cidp-sdk"
SKEW = 30.0  # seconds before expiry a token counts as expired
# The data service's own platform account: never a caller's identity (AGENTS.md, design A5).
SERVICE_ACCOUNT = "portal-data-svc"


class StaticToken(TokenSource):
    """A token given as is (``CIDP_TOKEN``, CI). It is not refreshed: a 401 is ``Unauthenticated``."""

    def __init__(self, token: str):
        remember(token)
        self._token = token

    def token(self) -> str:
        return self._token


class _Endpoints:
    """The issuer's endpoints from its discovery document, read once."""

    def __init__(self, issuer: str, http: httpx.Client):
        self.issuer = issuer.rstrip("/")
        self._http = http
        self._doc: dict[str, Any] | None = None

    def _get(self, key: str) -> str:
        if self._doc is None:
            url = f"{self.issuer}/.well-known/openid-configuration"
            try:
                r = self._http.get(url)
                r.raise_for_status()
                self._doc = r.json()
            except (httpx.HTTPError, ValueError) as e:
                raise ConfigError(f"The issuer's discovery document could not be read ({type(e).__name__})",
                                  code="issuer_unreachable") from None  # fmt: skip
        value = (self._doc or {}).get(key)
        if not isinstance(value, str):
            raise ConfigError(f"The issuer names no {key}", code="issuer_invalid")
        return value

    @property
    def token(self) -> str:
        return self._get("token_endpoint")

    @property
    def authorize(self) -> str:
        return self._get("authorization_endpoint")


class _Grant(TokenSource):
    """A token from the issuer's token endpoint, kept until shortly before it expires."""

    def __init__(self, endpoints: _Endpoints, http: httpx.Client, clock: Callable[[], float]):
        self._endpoints = endpoints
        self._http = http
        self._clock = clock
        self._access: str | None = None
        self._expires = 0.0

    def _valid(self) -> bool:
        return self._access is not None and self._clock() < self._expires

    def _post(self, form: dict[str, str]) -> dict[str, Any]:
        try:
            r = self._http.post(self._endpoints.token, data=form, headers={"Accept": "application/json"})
        except httpx.HTTPError as e:
            raise Unauthenticated(f"The token endpoint did not answer ({type(e).__name__})",
                                  code="token_endpoint") from None  # fmt: skip
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code >= 400 or not isinstance(body.get("access_token"), str):
            # The issuer's error code only ("invalid_grant"); its description may quote what was sent.
            error = body.get("error") if isinstance(body.get("error"), str) else f"HTTP {r.status_code}"
            raise Unauthenticated(f"The issuer refused the sign-in ({error})", code="token_refused", status=r.status_code)
        remember(body["access_token"])
        remember(body.get("refresh_token"))
        self._access = body["access_token"]
        self._expires = self._clock() + float(body.get("expires_in") or 300) - SKEW
        return body

    def close(self) -> None:
        self._access = None


class ClientCredentials(_Grant):
    """A service's own identity: the client credentials of a project service principal (``job_principals``)."""

    def __init__(self, endpoints: _Endpoints, client_id: str, client_secret: str, http: httpx.Client,
                 clock: Callable[[], float] = time.monotonic):  # fmt: skip
        if client_id == SERVICE_ACCOUNT:
            raise ConfigError(f"{SERVICE_ACCOUNT} is the data service's platform account and never signs in through "
                              "the SDK: use a project service principal", code="service_account")  # fmt: skip
        super().__init__(endpoints, http, clock)
        remember(client_secret)
        self._client_id = client_id
        self._secret = client_secret

    def __repr__(self) -> str:
        return f"ClientCredentials(client_id={self._client_id!r})"

    def token(self) -> str:
        if not self._valid():
            self._post({"grant_type": "client_credentials", "client_id": self._client_id,
                        "client_secret": self._secret})  # fmt: skip
        assert self._access is not None
        return self._access

    def refresh(self) -> bool:
        self._access = None
        self.token()
        return True


class TokenStore:
    """The refresh token of a browser login: the OS keyring, or memory (with a warning) when there is none."""

    def __init__(self, key: str):
        self.key = key
        self._memory: str | None = None
        self._keyring: Any = None
        try:
            import keyring
            from keyring.backends import fail

            if not isinstance(keyring.get_keyring(), fail.Keyring):
                self._keyring = keyring
        except Exception:  # any backend failure means memory
            self._keyring = None
        if self._keyring is None:
            warnings.warn("No OS keyring: the sign-in is kept for this process only", RuntimeWarning, stacklevel=3)

    def __repr__(self) -> str:
        return f"TokenStore(key={self.key!r})"

    def get(self) -> str | None:
        if self._keyring is not None:
            try:
                value = self._keyring.get_password(KEYRING_SERVICE, self.key)
                remember(value)
                return value
            except Exception:
                return self._memory
        return self._memory

    def set(self, value: str | None) -> None:
        self._memory = value
        if self._keyring is None:
            return
        try:
            if value:
                self._keyring.set_password(KEYRING_SERVICE, self.key, value)
            else:
                self._keyring.delete_password(KEYRING_SERVICE, self.key)
        except Exception:  # noqa: S110 kept in memory; the next process signs in again
            pass


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class _Callback(http.server.BaseHTTPRequestHandler):
    result: dict[str, str]

    def do_GET(self) -> None:  # noqa: N802 - the stdlib's name
        url = urlparse(self.path)
        if url.path != "/callback":
            self.send_error(404)
            return
        self.server.result = {k: v[0] for k, v in parse_qs(url.query).items()}  # type: ignore[attr-defined]
        body = b"<!doctype html><title>Signed in</title><p>Signed in. You can close this window.</p>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # the query holds the code: never logged
        pass


class BrowserLogin(_Grant):
    """A person's sign-in: authorization code with PKCE, the redirect to ``http://127.0.0.1:<random port>/callback``."""

    def __init__(self, endpoints: _Endpoints, client_id: str, store: TokenStore, http: httpx.Client, *,
                 opener: Callable[[str], Any] = webbrowser.open, timeout: float = 300.0,
                 clock: Callable[[], float] = time.monotonic):  # fmt: skip
        super().__init__(endpoints, http, clock)
        self._client_id = client_id
        self.store = store
        self._opener = opener
        self._timeout = timeout
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return f"BrowserLogin(client_id={self._client_id!r}, store={self.store!r})"

    def token(self) -> str:
        with self._lock:
            if not self._valid() and not self._refresh_grant():
                self.login()
            assert self._access is not None
            return self._access

    def refresh(self) -> bool:
        with self._lock:
            self._access = None
            return self._refresh_grant()

    def _refresh_grant(self) -> bool:
        rt = self.store.get()
        if not rt:
            return False
        try:
            body = self._post({"grant_type": "refresh_token", "refresh_token": rt, "client_id": self._client_id})
        except Unauthenticated:
            self.store.set(None)  # expired or revoked: the next call signs in again
            return False
        self.store.set(body.get("refresh_token") or rt)
        return True

    def login(self) -> None:
        """Open the browser and wait for the redirect; raises ``Unauthenticated`` when it does not come."""
        verifier, challenge = _pkce()
        state = secrets.token_urlsafe(24)
        server = http.server.HTTPServer(("127.0.0.1", 0), _Callback)
        server.timeout = 0.5
        server.result = {}  # type: ignore[attr-defined]
        redirect = f"http://127.0.0.1:{server.server_address[1]}/callback"
        url = self._endpoints.authorize + "?" + urlencode({
            "response_type": "code", "client_id": self._client_id, "redirect_uri": redirect, "scope": "openid",
            "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
        })  # fmt: skip
        try:
            self._opener(url)
            deadline = time.monotonic() + self._timeout
            while not server.result and time.monotonic() < deadline:  # type: ignore[attr-defined]
                server.handle_request()
            result: dict[str, str] = server.result  # type: ignore[attr-defined]
        finally:
            server.server_close()
        if not result:
            raise Unauthenticated("The browser sign-in did not complete in time", code="login_timeout")
        if result.get("state") != state:
            raise Unauthenticated("The sign-in answer does not belong to this login (state)", code="login_state")
        if "code" not in result:
            raise Unauthenticated(f"The sign-in was refused ({result.get('error', 'no code')})", code="login_refused")
        body = self._post({"grant_type": "authorization_code", "code": result["code"], "redirect_uri": redirect,
                           "client_id": self._client_id, "code_verifier": verifier})  # fmt: skip
        self.store.set(body.get("refresh_token"))

    def logout(self) -> None:
        self.store.set(None)
        self._access = None

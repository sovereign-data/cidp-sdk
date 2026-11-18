"""AC-4 (OpenSpec change data-api-sdk): the SDK resolves a profile and never keeps a secret in a file.

Arguments win over the environment and the environment over the profile; a profile holding a token and a file others
may read are refused with a pointer to the environment variables; a browser login keeps its refresh token in the
keyring (an in-memory one here) and nowhere else; tokens are redacted from logs and never in a ``repr``. The issuer
and the service are a fake transport; the browser is a thread that follows the redirect to the loopback callback.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from cidp_sdk import CIDPClient, ConfigError, Unauthenticated
from cidp_sdk.config import resolve

HOST = "https://portal.example.org"
ISSUER = "https://sso.example.org/realms/portal"
ACCESS = "eyJ.access-token-one.sig"
ACCESS2 = "eyJ.access-token-two.sig"
REFRESH = "refresh-token-secret-value"

PROFILES = f"""
default_connection_name = "dev"

[dev]
host = "{HOST}"
workspace = "sales"

[ci]
host = "https://ci.example.org"
auth = "token_env"
token_env = "CI_TOKEN"

[robot]
host = "{HOST}"
auth = "client_credentials"
client_id = "svc-project-etl"
"""


def write(home: Path, text: str, mode: int = 0o600) -> dict[str, str]:
    path = home / ".cidp" / "connections.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)
    return {"CIDP_CONFIG_FILE": str(path)}


class Issuer:
    """The service's /v1/config, the issuer's discovery document and token endpoint, and v1 behind the token."""

    def __init__(self):
        self.grants: list[str] = []
        self.authorization: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        if url.path == "/api/data/v1/config":
            assert "authorization" not in request.headers  # read before any sign-in
            return httpx.Response(200, json={
                "api_version": "1", "service_version": "0.2.0", "issuer": ISSUER, "client_id": "portal-data-cli",
                "audience": "portal-data", "polaris_uri": None, "polaris_realm": "portal", "object_store_uri": None,
                "object_store_path_style": True, "capabilities": ["workspaces"],
            })  # fmt: skip
        if url.path == "/realms/portal/.well-known/openid-configuration":
            return httpx.Response(200, json={
                "issuer": ISSUER, "authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth",
                "token_endpoint": f"{ISSUER}/protocol/openid-connect/token",
            })  # fmt: skip
        if url.path == "/realms/portal/protocol/openid-connect/token":
            form = parse_qs(request.content.decode())
            grant = form["grant_type"][0]
            self.grants.append(grant)
            assert form["client_id"] == ["portal-data-cli"]
            if grant == "authorization_code":
                assert form["code"] == ["the-code"] and len(form["code_verifier"][0]) >= 43
                return httpx.Response(200, json={"access_token": ACCESS, "refresh_token": REFRESH, "expires_in": 300})
            if grant == "refresh_token":
                if form["refresh_token"] != [REFRESH]:
                    return httpx.Response(400, json={"error": "invalid_grant", "error_description": "echo " + REFRESH})
                return httpx.Response(200, json={"access_token": ACCESS2, "refresh_token": REFRESH, "expires_in": 300})
        if url.path == "/api/data/v1/workspaces":
            self.authorization.append(request.headers["authorization"])
            return httpx.Response(200, json={"items": [], "next_cursor": None})
        return httpx.Response(404, json={"code": "not_found", "message": "Not found", "details": {}})


def browser(opened: list[str]):
    """A browser that signs in at once: the issuer redirects to the loopback callback with a code and the state."""

    def open_(url: str) -> bool:
        opened.append(url)
        q = parse_qs(urlparse(url).query)
        assert q["code_challenge_method"] == ["S256"] and q["redirect_uri"][0].startswith("http://127.0.0.1:")
        callback = f"{q['redirect_uri'][0]}?code=the-code&state={q['state'][0]}"
        # urllib, not httpx: the browser is not the SDK, and httpx would log the code it carries
        threading.Thread(target=urllib.request.urlopen, args=(callback,), daemon=True).start()
        return True

    return open_


def no_browser(_url: str) -> bool:
    raise AssertionError("a cached sign-in must not open the browser")


def test_ac4_the_sdk_resolves_a_profile_and_never_keeps_a_secret_in_a_file(tmp_path, memory_keyring, caplog):
    env = write(tmp_path, PROFILES)

    # resolution order: the default profile, then the environment over it, then arguments over both
    c = resolve(env=env)
    assert (c.profile, c.host, c.workspace, c.auth) == ("dev", HOST, "sales", "browser")
    c = resolve(env={**env, "CIDP_HOST": "https://env.example.org", "CIDP_WORKSPACE": "hr"})
    assert (c.host, c.workspace) == ("https://env.example.org", "hr")
    c = resolve(host="https://arg.example.org/", env={**env, "CIDP_HOST": "https://env.example.org"})
    assert c.host == "https://arg.example.org"
    c = resolve(env={**env, "CIDP_TOKEN": ACCESS})
    assert c.auth == "token" and c.token == ACCESS and ACCESS not in repr(c)
    assert resolve(token="arg-token-value", env={**env, "CIDP_TOKEN": ACCESS}).token == "arg-token-value"
    # a profile names where its token comes from, never the token
    with pytest.raises(ConfigError) as e:
        resolve(profile="ci", env=env)
    assert e.value.code == "no_token" and "CI_TOKEN" in e.value.message
    c = resolve(env={**env, "CIDP_PROFILE": "ci", "CI_TOKEN": ACCESS})
    assert (c.profile, c.host, c.auth) == ("ci", "https://ci.example.org", "token")
    with pytest.raises(ConfigError) as e:
        resolve(profile="robot", env=env)
    assert e.value.code == "no_client_secret"
    c = resolve(profile="robot", env={**env, "CIDP_CLIENT_SECRET": "client-secret-value"})
    assert c.auth == "client_credentials" and "client-secret-value" not in repr(c)
    with pytest.raises(ConfigError) as e:
        resolve(profile="missing", env=env)
    assert e.value.code == "profile_missing"
    with pytest.raises(ConfigError) as e:
        resolve(env={"CIDP_CONFIG_FILE": str(tmp_path / "none.toml")})
    assert e.value.code == "no_host"

    # a secret in the file is refused, with the way to give it instead; the value is not repeated
    for key in ("token", "client_secret", "password"):
        leaky = write(tmp_path, f'[default]\nhost = "{HOST}"\n{key} = "leaked-value-1234"\n')
        with pytest.raises(ConfigError) as e:
            resolve(env=leaky)
        assert e.value.code == "secret_in_profile", key
        assert "CIDP_TOKEN" in e.value.message and "leaked-value-1234" not in e.value.message
    # a file others may read is refused before it is read
    with pytest.raises(ConfigError) as e:
        resolve(env=write(tmp_path, PROFILES, mode=0o644))
    assert e.value.code == "config_file_mode" and "chmod 600" in e.value.message
    env = write(tmp_path, PROFILES)
    before = (tmp_path / ".cidp" / "connections.toml").read_text()

    # a browser login: code with PKCE over loopback; the refresh token goes to the keyring only
    caplog.set_level(logging.DEBUG)
    issuer, opened = Issuer(), []
    transport = httpx.MockTransport(issuer)
    with CIDPClient(env=env, transport=transport, opener=browser(opened)) as client:
        assert list(client.workspaces.list()) == []
        assert client.config.client_id == "portal-data-cli" and len(opened) == 1
        assert issuer.grants == ["authorization_code"] and issuer.authorization == [f"Bearer {ACCESS}"]
        assert memory_keyring.values == {("cidp-sdk", f"{HOST}|dev"): REFRESH}
        for shown in (repr(client), repr(client.tokens), repr(client.connection), repr(client._http)):
            assert ACCESS not in shown and REFRESH not in shown
        logging.getLogger("cidp_sdk").warning("Authorization: Bearer %s refresh=%s", ACCESS, REFRESH)
        logging.getLogger("httpx").info("sent %s", ACCESS)
    assert (tmp_path / ".cidp" / "connections.toml").read_text() == before
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert all(ACCESS not in p.read_text() and REFRESH not in p.read_text() for p in files)

    # the next process signs in from the keyring with the refresh grant; no browser
    with CIDPClient(env=env, transport=transport, opener=no_browser) as client:
        list(client.workspaces.list())
        assert issuer.grants[-1] == "refresh_token" and issuer.authorization[-1] == f"Bearer {ACCESS2}"
        client.logout()
    assert memory_keyring.values == {}

    # a refresh token the issuer refuses is forgotten; its echo of what was sent never reaches the error
    memory_keyring.values[("cidp-sdk", f"{HOST}|dev")] = "stale-refresh-token"
    timeouts = []

    def gives_up(url: str) -> bool:
        timeouts.append(url)
        return True

    client = CIDPClient(env=env, transport=transport, opener=gives_up)
    client.tokens._timeout = 0.2  # type: ignore[attr-defined]
    with pytest.raises(Unauthenticated) as e:
        list(client.workspaces.list())
    assert e.value.code == "login_timeout" and timeouts and memory_keyring.values == {}
    client.close()

    text = caplog.text + json.dumps([r.getMessage() for r in caplog.records])
    assert ACCESS not in text and ACCESS2 not in text and REFRESH not in text
    # the SDK writes "Bearer ***"; the data service's own redactor, when imported in the same process, gets there first
    assert re.search(r"Bearer (\*\*\*|<redacted>)", text) and "the-code" not in text

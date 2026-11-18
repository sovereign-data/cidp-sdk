"""Where the SDK connects and how it signs in (design A5): arguments, then the environment, then a profile.

Profiles live in ``~/.cidp/connections.toml`` (``CIDP_CONFIG_FILE``), as Snowflake keeps its connections::

    default_connection_name = "prod"

    [prod]
    host = "https://portal.example.org"
    auth = "browser"            # or "client_credentials", "token_env"
    workspace = "sales"

A profile never holds a secret: a ``token``, ``secret`` or ``password`` key is refused, as is a file that others may
read. Tokens come from ``CIDP_TOKEN``, client secrets from ``CIDP_CLIENT_SECRET``, refresh tokens from the OS
keyring.
"""

from __future__ import annotations

import os
import stat
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from cidp_sdk.errors import ConfigError

Auth = Literal["token", "client_credentials", "browser"]
AUTHS = ("browser", "client_credentials", "token_env")
SECRET_WORDS = ("token", "secret", "password")
FILE = Path("~/.cidp/connections.toml")


@dataclass(frozen=True)
class Connection:
    """What a client connects with. ``token`` and ``client_secret`` come from arguments or the environment only."""

    host: str
    auth: Auth
    profile: str | None = None
    workspace: str | None = None
    polaris_uri: str | None = None
    client_id: str | None = None
    token: str | None = field(default=None, repr=False)
    client_secret: str | None = field(default=None, repr=False)


def config_file(env: Mapping[str, str]) -> Path:
    return Path(env.get("CIDP_CONFIG_FILE") or FILE).expanduser()


def load_profiles(path: Path) -> dict[str, Any]:
    """The file's tables; refused when group or others may read or write it (``chmod 600``)."""
    if not path.exists():
        return {}
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ConfigError(f"{path} may be read by others: run `chmod 600 {path}`", code="config_file_mode")
    try:
        return tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path} is not valid TOML: {e}", code="config_file_invalid") from None


def _profile(data: dict[str, Any], name: str, path: Path, explicit: bool) -> dict[str, Any]:
    section = data.get(name)
    if section is None:
        if explicit:
            raise ConfigError(f"No profile [{name}] in {path}", code="profile_missing")
        return {}
    if not isinstance(section, dict):
        raise ConfigError(f"[{name}] in {path} is not a table", code="config_file_invalid")
    leaked = sorted(k for k in section if any(w in k.lower() for w in SECRET_WORDS) and k != "token_env")
    if leaked:
        raise ConfigError(
            f"Profile [{name}] in {path} holds {', '.join(leaked)}: secrets do not go in this file. Remove it; set "
            'CIDP_TOKEN or CIDP_CLIENT_SECRET in the environment, or sign in with auth = "browser"',
            code="secret_in_profile",
        )
    unknown = sorted(set(section) - {"host", "auth", "workspace", "polaris_uri", "client_id", "token_env"})
    if unknown:
        keys = ", ".join(unknown)
        raise ConfigError(f"Profile [{name}] in {path} has unknown keys: {keys}", code="config_file_invalid")
    if section.get("auth", "browser") not in AUTHS:
        raise ConfigError(f"Profile [{name}]: auth is one of {', '.join(AUTHS)}", code="config_file_invalid")
    return section


def resolve(*, profile: str | None = None, host: str | None = None, token: str | None = None,
            client_id: str | None = None, client_secret: str | None = None, workspace: str | None = None,
            env: Mapping[str, str] | None = None) -> Connection:  # fmt: skip
    """The connection: each value from the arguments, else the environment, else the profile."""
    env = os.environ if env is None else env
    path = config_file(env)
    explicit = profile or env.get("CIDP_PROFILE")
    data = load_profiles(path) if (path.exists() or explicit) else {}
    if explicit and not path.exists():
        raise ConfigError(f"Profile {explicit!r} asked for, but {path} does not exist", code="profile_missing")
    name = explicit or str(data.get("default_connection_name") or "default")
    section = _profile(data, name, path, bool(explicit) or "default_connection_name" in data)
    used = name if section else None

    host = host or env.get("CIDP_HOST") or section.get("host")
    if not host:
        raise ConfigError("No host: pass host=, set CIDP_HOST, or add a profile to " + str(path), code="no_host")
    if not host.startswith(("https://", "http://")):
        raise ConfigError(f"host must be an http(s) URL, not {host!r}", code="invalid_host")
    client_id = client_id or env.get("CIDP_CLIENT_ID") or section.get("client_id")
    client_secret = client_secret or env.get("CIDP_CLIENT_SECRET")
    kind = section.get("auth")
    # The environment wins over the profile: a token there is used whatever the profile's auth says.
    token = token or env.get(section.get("token_env") or "CIDP_TOKEN") or None

    auth: Auth
    if token:
        auth = "token"
    elif kind == "client_credentials" or (kind is None and client_id and client_secret):
        if not (client_id and client_secret):
            raise ConfigError("client_credentials needs a client id and CIDP_CLIENT_SECRET", code="no_client_secret")
        auth = "client_credentials"
    elif kind == "token_env":
        raise ConfigError(f"Profile [{name}] reads its token from {section.get('token_env') or 'CIDP_TOKEN'}, "
                          "which is not set", code="no_token")  # fmt: skip
    else:
        auth = "browser"
    return Connection(
        host=host.rstrip("/"),
        auth=auth,
        profile=used,
        workspace=workspace or env.get("CIDP_WORKSPACE") or section.get("workspace"),
        polaris_uri=section.get("polaris_uri"),
        client_id=client_id,
        token=token,
        client_secret=client_secret if auth == "client_credentials" else None,
    )

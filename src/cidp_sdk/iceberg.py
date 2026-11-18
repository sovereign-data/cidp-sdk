"""Iceberg tables from Polaris, as the caller (design A6): a pyiceberg ``RestCatalog`` on the caller's token.

``polaris_uri`` is normally the data service's vending gate (data-vending-gate), which forwards to Polaris as the
caller. Polaris vends short-lived, table-scoped storage keys (``X-Iceberg-Access-Delegation: vended-credentials``);
the gate withholds them for a table with a mask, a row filter or a personal column (``portal.vending`` is then
``withheld`` in the table's properties: read it through SQL). The SDK never holds a warehouse key. The object store's
public address from ``/v1/config`` wins over the one Polaris vends (the address Polaris uses inside the deployment), as
dbx-migrator does. The token comes from the client's token source on every request, so a refreshed sign-in reaches
the catalog without a new one. Needs the ``iceberg`` extra.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cidp_sdk import _models as m
from cidp_sdk._http import TokenSource
from cidp_sdk.errors import ConfigError

if TYPE_CHECKING:
    from pyiceberg.catalog.rest import RestCatalog

AUTH_NAME = "cidp-sdk"
# The storage keys whose value from the configuration must win over a vended one.
STORAGE = ("s3.endpoint", "s3.force-virtual-addressing")


def iceberg_properties(config: m.ConfigInfo, warehouse: str, *, polaris_uri: str | None = None) -> dict[str, str]:
    """The RestCatalog properties for ``warehouse`` (a catalog name), without the token."""
    base = polaris_uri or config.polaris_uri
    if not base:
        raise ConfigError("The deployment publishes no Polaris address: set polaris_uri in the profile",
                          code="no_polaris")  # fmt: skip
    props = {
        "type": "rest",
        "uri": base.rstrip("/") + "/api/catalog",
        "warehouse": warehouse,
        "header.X-Iceberg-Access-Delegation": "vended-credentials",
    }
    if config.polaris_realm:
        props["header.Polaris-Realm"] = config.polaris_realm
    if config.object_store_uri:
        props["s3.endpoint"] = config.object_store_uri
        props["s3.force-virtual-addressing"] = "false" if config.object_store_path_style else "true"
    return props


def _auth_manager() -> type:
    from pyiceberg.catalog.rest.auth import AuthManager

    class _TokenAuth(AuthManager):
        def __init__(self, tokens: TokenSource):
            self._tokens = tokens

        def __repr__(self) -> str:
            return "_TokenAuth()"

        def auth_header(self) -> str | None:
            return f"Bearer {self._tokens.token()}"

    return _TokenAuth


def catalog(config: m.ConfigInfo, warehouse: str, tokens: TokenSource, *, polaris_uri: str | None = None,
            name: str | None = None) -> RestCatalog:  # fmt: skip
    """A ``RestCatalog`` on ``warehouse`` that signs every request with the token source's current token."""
    try:
        from pyiceberg.catalog.rest import RestCatalog
        from pyiceberg.catalog.rest.auth import AuthManagerFactory
    except ImportError:
        raise ConfigError("Iceberg needs the extra: pip install 'cidp-sdk[iceberg]'", code="no_iceberg") from None

    props = iceberg_properties(config, warehouse, polaris_uri=polaris_uri)
    pinned = {k: props[k] for k in STORAGE if k in props}

    class _Catalog(RestCatalog):
        def _load_file_io(self, properties: Any = None, location: str | None = None) -> Any:
            return super()._load_file_io({**(properties or {}), **pinned}, location)

    AuthManagerFactory.register(AUTH_NAME, _auth_manager())
    auth = {"type": AUTH_NAME, AUTH_NAME: {"tokens": tokens}}
    return _Catalog(name or warehouse, **props, auth=auth)  # type: ignore[arg-type]

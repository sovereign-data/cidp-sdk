"""``CIDPClient``: one connection to a data service's public API v1 (design A4, A5)."""

from __future__ import annotations

import time
import webbrowser
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

import httpx

from cidp_sdk import _models as m
from cidp_sdk import auth, config, iceberg, services
from cidp_sdk._http import Http, TokenSource
from cidp_sdk.errors import ConfigError
from cidp_sdk.objects import WorkspaceRef

if TYPE_CHECKING:
    from pyiceberg.catalog.rest import RestCatalog


class CIDPClient:
    """Connect as in Snowflake's Python API: arguments, then ``CIDP_*`` environment variables, then a profile.

    ``transport`` replaces the network for both the service and the issuer (tests, a proxy). The deployment's
    ``/v1/config`` is read once, without a token; it names the issuer, the public client and Polaris.
    """

    def __init__(self, profile: str | None = None, *, host: str | None = None, token: str | None = None,
                 client_id: str | None = None, client_secret: str | None = None, workspace: str | None = None,
                 env: Mapping[str, str] | None = None, transport: httpx.BaseTransport | None = None,
                 timeout: float = 60.0, verify: Any = True, opener: Callable[[str], Any] = webbrowser.open,
                 clock: Callable[[], float] = time.monotonic):  # fmt: skip
        self.connection = config.resolve(profile=profile, host=host, token=token, client_id=client_id,
                                         client_secret=client_secret, workspace=workspace, env=env)  # fmt: skip
        self._http = Http(self.connection.host, None, transport=transport, timeout=timeout, verify=verify)
        self._idp = httpx.Client(transport=transport, timeout=timeout, verify=verify, follow_redirects=False)
        try:
            self.config: m.ConfigInfo = services.Config(self._http).get()
            self.tokens: TokenSource = self._tokens(opener, clock)
        except BaseException:
            self.close()
            raise
        self._http.use(self.tokens)

        h = self._http
        # catalog
        self.workspaces = services.Workspaces(h)
        self.catalogs = services.Catalogs(h)
        self.storage_locations = services.StorageLocations(h)
        self.schemas = services.Schemas(h)
        self.tables = services.Tables(h)
        self.views = services.Views(h)
        self.volumes = services.Volumes(h)
        self.search = services.Search(h)
        # sql
        self.statements = services.Statements(h)
        self.query_engines = services.QueryEngines(h)
        self.query_history = services.QueryHistory(h)
        self.saved_queries = services.SavedQueries(h)
        # governance
        self.permissions = services.Permissions(h)
        self.contracts = services.Contracts(h)
        self.quality = services.Quality(h)
        self.lineage = services.Lineage(h)
        self.glossary = services.Glossary(h)
        # projects, jobs, ingest
        self.projects = services.Projects(h)
        self.jobs = services.Jobs(h)
        self.uploads = services.Uploads(h)
        # the caller, secrets, notifications, operations
        self.me = services.Me(h)
        self.secret_scopes = services.SecretScopes(h)
        self.notifications = services.Notifications(h)
        self.system = services.System(h)
        self.audit = services.Audit(h)
        self.templates = services.Templates(h)
        self.admin = services.Admin(h)

    @property
    def versions(self) -> dict[str, str]:
        """Each service of the deployment's API and its version (``x-service-versions``), as ``/v1/config`` says."""
        return dict(self.config.service_versions or {})

    def _tokens(self, opener: Callable[[str], Any], clock: Callable[[], float]) -> TokenSource:
        c = self.connection
        if c.auth == "token":
            assert c.token is not None
            return auth.StaticToken(c.token)
        endpoints = auth._Endpoints(self.config.issuer, self._idp)
        if c.auth == "client_credentials":
            assert c.client_id is not None and c.client_secret is not None
            return auth.ClientCredentials(endpoints, c.client_id, c.client_secret, self._idp, clock)
        client_id = c.client_id or self.config.client_id
        if not client_id:
            raise ConfigError("The deployment names no public client for a browser sign-in", code="no_client_id")
        store = auth.TokenStore(f"{c.host}|{c.profile or 'default'}")
        return auth.BrowserLogin(endpoints, client_id, store, self._idp, opener=opener, clock=clock)

    def __repr__(self) -> str:
        return f"CIDPClient(host={self.connection.host!r}, auth={self.connection.auth!r})"

    def __enter__(self) -> CIDPClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()
        self._idp.close()

    def workspace(self, slug: str | None = None) -> WorkspaceRef:
        """A workspace handle; without a slug, the connection's ``workspace``."""
        slug = slug or self.connection.workspace
        if not slug:
            raise ConfigError("No workspace: pass one, set CIDP_WORKSPACE or add it to the profile",
                              code="no_workspace")  # fmt: skip
        return WorkspaceRef(self, slug)

    def logout(self) -> None:
        """Forget a browser sign-in (its refresh token in the keyring)."""
        if isinstance(self.tokens, auth.BrowserLogin):
            self.tokens.logout()

    def iceberg(self, workspace: str | None = None, catalog: str | None = None) -> RestCatalog:
        """A pyiceberg catalog on Polaris for one of the workspace's catalogs (None: its home), as the caller."""
        ws = self.workspace(workspace)
        name = catalog or ws.home_catalog
        return iceberg.catalog(self.config, name, self.tokens, polaris_uri=self.connection.polaris_uri)

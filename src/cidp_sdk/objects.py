"""The object tree (design A4), as Snowflake's ``Root``: ``client.workspace("sales").catalog().schema("raw")``.

Handles are lazy: building one calls nothing; ``fetch()`` reads it, iterating a collection lists it. ``catalog()``
without a name is the workspace's home catalog.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from cidp_sdk import _models as m
from cidp_sdk.session import Result, Session

if TYPE_CHECKING:
    from pyiceberg.catalog.rest import RestCatalog

    from cidp_sdk.client import CIDPClient


class WorkspaceRef:
    def __init__(self, client: CIDPClient, slug: str):
        self._client = client
        self.slug = slug
        self._home: str | None = None

    def __repr__(self) -> str:
        return f"WorkspaceRef({self.slug!r})"

    def fetch(self) -> m.WorkspaceInfo:
        info = self._client.workspaces.get(self.slug)
        self._home = info.home_catalog
        return info

    def drop(self) -> None:
        self._client.workspaces.delete(self.slug)

    @property
    def home_catalog(self) -> str:
        if self._home is None:
            self.fetch()
        assert self._home is not None
        return self._home

    def catalogs(self) -> Iterator[m.WorkspaceCatalogInfo]:
        return self._client.workspaces.catalogs(self.slug)

    def catalog(self, name: str | None = None) -> CatalogRef:
        return CatalogRef(self, name)

    def projects(self) -> Iterator[m.ProjectInfo]:
        return self._client.projects.list(self.slug)

    def project(self, slug: str) -> ProjectRef:
        return ProjectRef(self, slug)

    def session(self, *, engine: str = "sqe", catalog: str | None = None, schema: str | None = None,
                query_tag: str | None = None) -> Session:  # fmt: skip
        return Session(self._client.statements, self.slug, engine=engine, catalog=catalog, schema=schema,
                       query_tag=query_tag)  # fmt: skip

    def sql(self, sql: str, *, wait_timeout: int = 10, row_limit: int | None = None) -> Result:
        """One statement in a default session (``session().sql``)."""
        return self.session().sql(sql, wait_timeout=wait_timeout, row_limit=row_limit)

    def iceberg(self, catalog: str | None = None) -> RestCatalog:
        return self._client.iceberg(self.slug, catalog)


class CatalogRef:
    def __init__(self, workspace: WorkspaceRef, name: str | None):
        self.workspace = workspace
        self._name = name

    def __repr__(self) -> str:
        return f"CatalogRef({self._name or '<home>'!r})"

    @property
    def name(self) -> str:
        return self._name or self.workspace.home_catalog

    def fetch(self) -> m.CatalogInfo:
        return self.workspace._client.catalogs.get(self.name)

    @property
    def schemas(self) -> SchemaCollection:
        return SchemaCollection(self)

    def schema(self, name: str) -> SchemaRef:
        return SchemaRef(self, name)

    def permissions(self) -> PermissionsRef:
        return PermissionsRef(self.workspace, "catalog", self.name)


class SchemaCollection:
    def __init__(self, catalog: CatalogRef):
        self.catalog = catalog

    def __iter__(self) -> Iterator[m.SchemaInfo]:
        ws = self.catalog.workspace
        return ws._client.schemas.list(ws.slug, self.catalog.name)

    def create(self, name: str) -> SchemaRef:
        ws = self.catalog.workspace
        ws._client.schemas.create(ws.slug, self.catalog.name, name)
        return SchemaRef(self.catalog, name)


class SchemaRef:
    def __init__(self, catalog: CatalogRef, name: str):
        self.catalog = catalog
        self.name = name

    def __repr__(self) -> str:
        return f"SchemaRef({self.name!r})"

    @property
    def _ws(self) -> WorkspaceRef:
        return self.catalog.workspace

    @property
    def full_name(self) -> str:
        return f"{self.catalog.name}.{self.name}"

    def fetch(self) -> m.SchemaInfo:
        return self._ws._client.schemas.get(self._ws.slug, self.catalog.name, self.name)

    def create(self) -> SchemaRef:
        return self.catalog.schemas.create(self.name)

    def drop(self, *, confirm: str | None = None) -> None:
        """A schema that holds tables is dropped only with ``confirm`` equal to its name."""
        self._ws._client.schemas.delete(self._ws.slug, self.catalog.name, self.name, confirm=confirm)

    def tables(self) -> Iterator[m.TableSummary]:
        return self._ws._client.tables.list(self._ws.slug, self.catalog.name, self.name)

    def table(self, name: str) -> TableRef:
        return TableRef(self, name)

    def views(self) -> Iterator[m.TableSummary]:
        return self._ws._client.views.list(self._ws.slug, self.catalog.name, self.name)

    def view(self, name: str) -> ViewRef:
        return ViewRef(self, name)

    def permissions(self) -> PermissionsRef:
        return PermissionsRef(self._ws, "schema", self.full_name)


class TableRef:
    def __init__(self, schema: SchemaRef, name: str):
        self.schema = schema
        self.name = name

    def __repr__(self) -> str:
        return f"TableRef({self.full_name!r})"

    @property
    def full_name(self) -> str:
        return f"{self.schema.full_name}.{self.name}"

    def _args(self) -> tuple[str, str, str, str]:
        s = self.schema
        return s._ws.slug, s.catalog.name, s.name, self.name

    def fetch(self) -> m.TableInfo:
        return self.schema._ws._client.tables.get(*self._args())

    def history(self) -> Iterator[m.SnapshotInfo]:
        return self.schema._ws._client.tables.history(*self._args())

    def permissions(self) -> PermissionsRef:
        return PermissionsRef(self.schema._ws, "table", self.full_name)


class ViewRef(TableRef):
    def __repr__(self) -> str:
        return f"ViewRef({self.full_name!r})"

    def fetch(self) -> m.ViewInfo:  # type: ignore[override]
        return self.schema._ws._client.views.get(*self._args())


class PermissionsRef:
    def __init__(self, workspace: WorkspaceRef, securable_type: str, full_name: str):
        self.workspace = workspace
        self.securable_type = securable_type
        self.full_name = full_name

    def fetch(self) -> m.PermissionsInfo:
        return self.workspace._client.permissions.get(self.workspace.slug, self.securable_type, self.full_name)

    def grant(self, principal: str, *privileges: str) -> m.PermissionsInfo:
        return self.update([{"principal": principal, "add": list(privileges)}])

    def revoke(self, principal: str, *privileges: str) -> m.PermissionsInfo:
        return self.update([{"principal": principal, "remove": list(privileges)}])

    def update(self, changes: list[dict[str, object]]) -> m.PermissionsInfo:
        return self.workspace._client.permissions.update(self.workspace.slug, self.securable_type, self.full_name,
                                                         changes)  # fmt: skip


class ProjectRef:
    def __init__(self, workspace: WorkspaceRef, slug: str):
        self.workspace = workspace
        self.slug = slug

    def __repr__(self) -> str:
        return f"ProjectRef({self.slug!r})"

    def jobs(self) -> Iterator[m.JobInfo]:
        return self.workspace._client.jobs.list(self.workspace.slug, self.slug)

    def job(self, name: str) -> JobRef:
        return JobRef(self, name)

    def run(self, run_id: str) -> m.ProjectRunInfo:
        return self.workspace._client.projects.run(self.workspace.slug, self.slug, run_id)

    def wait(self, run_id: str, *, timeout: float | None = None, interval: float = 10.0) -> m.ProjectRunInfo:
        """Wait until the project run ends (``Projects.wait_run``); ``WaitTimeout`` after ``timeout`` seconds."""
        return self.workspace._client.projects.wait_run(self.workspace.slug, self.slug, run_id, timeout=timeout,
                                                         interval=interval)  # fmt: skip


class JobRef:
    def __init__(self, project: ProjectRef, name: str):
        self.project = project
        self.name = name

    def __repr__(self) -> str:
        return f"JobRef({self.name!r})"

    def _args(self) -> tuple[str, str, str]:
        return self.project.workspace.slug, self.project.slug, self.name

    @property
    def _jobs(self):  # noqa: ANN202
        return self.project.workspace._client.jobs

    def fetch(self) -> m.JobInfo:
        return self._jobs.get(*self._args())

    def run_now(self, **job_parameters: str) -> m.JobRunInfo:
        return self._jobs.run_now(*self._args(), job_parameters=job_parameters or None)

    def runs(self) -> Iterator[m.JobRunInfo]:
        return self._jobs.runs(*self._args())

    def run(self, run_id: str) -> m.JobRunInfo:
        return self._jobs.run(*self._args(), run_id)

    def wait(self, run_id: str, *, timeout: float | None = None, interval: float = 10.0) -> m.JobRunInfo:
        """Wait until the run ends (``Jobs.wait_run``); ``WaitTimeout`` after ``timeout`` seconds."""
        return self._jobs.wait_run(*self._args(), run_id, timeout=timeout, interval=interval)

    def cancel_run(self, run_id: str) -> m.JobRunInfo:
        return self._jobs.cancel_run(*self._args(), run_id)

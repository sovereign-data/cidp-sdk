"""The object tree (design A4), as Snowflake's ``Root``: ``client.workspace("sales").catalog().schema("raw")``.

Handles are lazy: building one calls nothing; ``fetch()`` reads it, iterating a collection lists it. ``catalog()``
without a name is the workspace's home catalog.

Governance (``catalog.governance()``, the tag helpers on ``CatalogRef``, masks and row filters on ``TableRef``) calls
``internal`` operations: each warns once with ``InternalWarning`` and may change without notice.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any

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

    def governance(self) -> GovernanceRef:
        """The catalog's governance: batches of changes with a dry run, governed tags (internal operations)."""
        return GovernanceRef(self)

    # Governed tags of the catalog (``tag_*`` changes), each applied on its own; GovernanceRef has the same.
    def define_tag(self, name: str, description: str | None = None) -> m.PreviewOut:
        return self.governance().define_tag(name, description)

    def drop_tag(self, name: str) -> m.PreviewOut:
        return self.governance().drop_tag(name)

    def tag_mask(self, name: str, mask_type: str, *, except_groups: Sequence[str] | None = None) -> m.PreviewOut:
        return self.governance().tag_mask(name, mask_type, except_groups=except_groups)

    def tag_unmask(self, name: str) -> m.PreviewOut:
        return self.governance().tag_unmask(name)

    def tag_row_filter(self, name: str, expression: str, *, groups: Sequence[str] | None = None,
                       except_groups: Sequence[str] | None = None) -> m.PreviewOut:  # fmt: skip
        return self.governance().tag_row_filter(name, expression, groups=groups, except_groups=except_groups)

    def tag_clear_row_filter(self, name: str) -> m.PreviewOut:
        return self.governance().tag_clear_row_filter(name)


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

    # Masks and row filters (internal operations): each applied on its own, all or nothing.
    def _apply(self, op: str, **fields: Any) -> m.PreviewOut:
        change = {"op": op, "schema": self.schema.name, "table": self.name, **fields}
        return self.schema.catalog.governance().apply({k: v for k, v in change.items() if v is not None})

    def governance(self) -> m.PermissionsOut:
        """The table's owner, grants, masks, row filter and the tags on its columns (``Governance.get``)."""
        s = self.schema
        return s._ws._client.governance.get(s._ws.slug, s.catalog.name, schema=s.name, table=self.name)

    def mask(self, column: str, mask_type: str, *, except_groups: Sequence[str] | None = None,
             expression: str | None = None) -> m.PreviewOut:  # fmt: skip
        """Mask ``column`` for everyone but ``except_groups``; ``mask_type`` is one of ``services.MASK_TYPES``."""
        return self._apply("mask", column=column, mask_type=mask_type, expression=expression,
                           except_groups=_list(except_groups))  # fmt: skip

    def unmask(self, column: str) -> m.PreviewOut:
        return self._apply("unmask", column=column)

    def row_filter(self, expression: str, *, groups: Sequence[str] | None = None,
                   except_groups: Sequence[str] | None = None) -> m.PreviewOut:  # fmt: skip
        """Rows matching ``expression`` only, for ``groups`` (none: everyone) but not ``except_groups``. A table has
        one row filter per person: a filter that could meet another is 409 ``row_filter_conflict``."""
        return self._apply("row_filter", expression=expression, groups=_list(groups),
                           except_groups=_list(except_groups))  # fmt: skip

    def clear_row_filter(self) -> m.PreviewOut:
        return self._apply("clear_row_filter")


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


def _list(groups: Sequence[str] | None) -> list[str] | None:
    return None if groups is None else list(groups)


Change = m.GovernanceChange | Mapping[str, Any]


class GovernanceRef:
    """A catalog's governance (``CatalogRef.governance()``): ``apply`` and ``preview`` take changes as
    ``Governance.apply`` does, ``{"op": "grant", "schema": ..., "group": ..., "privilege": ...}`` or a
    ``GovernanceChange``. Internal operations: each warns once with ``InternalWarning``."""

    def __init__(self, catalog: CatalogRef):
        self.catalog = catalog

    def __repr__(self) -> str:
        return f"GovernanceRef({self.catalog.name!r})"

    def _args(self) -> tuple[str, str]:
        return self.catalog.workspace.slug, self.catalog.name

    @property
    def _service(self):  # noqa: ANN202
        return self.catalog.workspace._client.governance

    def fetch(self, *, schema: str | None = None, table: str | None = None) -> m.PermissionsOut:
        """The catalog's (or a schema's, or a table's) owner, grants, masks and row filter."""
        return self._service.get(*self._args(), schema=schema, table=table)

    def tags(self) -> m.TagsOut:
        return self._service.tags(*self._args())

    def apply(self, *changes: Change) -> m.PreviewOut:
        """Apply the changes all or nothing."""
        return self._service.apply(*self._args(), list(changes))

    def preview(self, *changes: Change) -> m.PreviewOut:
        """What ``apply`` would change; writes nothing."""
        return self._service.preview(*self._args(), list(changes))

    def _tag(self, op: str, name: str, **fields: Any) -> m.PreviewOut:
        return self.apply({"op": op, "tag": name, **{k: v for k, v in fields.items() if v is not None}})

    def define_tag(self, name: str, description: str | None = None) -> m.PreviewOut:
        """A governed tag of the catalog; a column carries it in its table's ``sqe.column-tags`` property."""
        return self._tag("tag_define", name, description=description)

    def drop_tag(self, name: str) -> m.PreviewOut:
        return self._tag("tag_drop", name)

    def tag_mask(self, name: str, mask_type: str, *, except_groups: Sequence[str] | None = None) -> m.PreviewOut:
        """Mask every column with the tag (409 when tag policies are off in the deployment: ``tags().policies``)."""
        return self._tag("tag_mask", name, mask_type=mask_type, except_groups=_list(except_groups))

    def tag_unmask(self, name: str) -> m.PreviewOut:
        return self._tag("tag_unmask", name)

    def tag_row_filter(self, name: str, expression: str, *, groups: Sequence[str] | None = None,
                       except_groups: Sequence[str] | None = None) -> m.PreviewOut:  # fmt: skip
        """Filter the rows of every table with a column of the tag (409 ``row_filter_conflict`` when it could meet
        another filter, ``row_filter_unchecked`` when that cannot be checked)."""
        return self._tag("tag_row_filter", name, expression=expression, groups=_list(groups),
                         except_groups=_list(except_groups))  # fmt: skip

    def tag_clear_row_filter(self, name: str) -> m.PreviewOut:
        return self._tag("tag_clear_row_filter", name)


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

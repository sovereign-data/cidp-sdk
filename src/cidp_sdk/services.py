"""One class per area of the v1 contract: each method is one operation, marked with its operationId (design A4).

``@op`` ties a method to its row in ``_operations`` (generated from ``openapi-v1.json``): an unknown id fails at
import, and a ``preview`` operation warns once with ``PreviewWarning`` (data-api-consistency AC-9), an ``internal`` one
(``INTERNAL_OPERATIONS``: governance's masks, row filters and tags) with ``InternalWarning``. The SDK tests call
every method and check the request against that row; the operations no method covers are in ``NOT_IN_SDK``.

Listings with ``next_cursor`` are iterators that follow it (``limit`` is the page size, not a cap on the items); a
listing answered in one page is a list.
"""

from __future__ import annotations

import functools
import json
import warnings
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import IO, Any, TypeVar
from urllib.parse import quote

import pyarrow as pa
from pydantic import BaseModel

from cidp_sdk import _models as m
from cidp_sdk._events import wait_until
from cidp_sdk._http import API, Http, raw_body
from cidp_sdk._operations import INTERNAL_OPERATIONS, OPERATIONS
from cidp_sdk.errors import InternalWarning, PreviewWarning

ARROW = "application/vnd.apache.arrow.stream"
F = TypeVar("F", bound=Callable[..., Any])

# A run's ended states; a state the SDK does not know counts as not ended (the API's advice).
PROJECT_RUN_ENDED = frozenset({"succeeded", "failed", "cancelled", "expired"})
JOB_RUN_ENDED = frozenset({"succeeded", "failed", "cancelled", "skipped", "expired"})
WAIT_INTERVAL = 10.0  # seconds between reads of a run, whatever the change stream does

# Public operations the SDK leaves out on purpose, with the reason (the SDK tests hold this list to the contract).
NOT_IN_SDK: dict[str, str] = {
    "audit_ingest": "a deployment's audit shipper posts it with its own key, not a person",
    "spark_audit_ingest": "the Spark gateway posts it with its own key, not a person",
    "lineage_events_ingest": "engines post OpenLineage events with a producer key, not a person",
    "quality_runs_run_all": "a server-sent stream for the quality page; Quality.run() runs a table's checks",
}

_warned: set[str] = set()


def op(operation_id: str) -> Callable[[F], F]:
    """Mark a method as the operation ``operation_id``; a preview or internal one warns on its first use in the
    process."""
    _, _, level, _ = OPERATIONS.get(operation_id) or INTERNAL_OPERATIONS[operation_id]

    def wrap(fn: F) -> F:
        @functools.wraps(fn)
        def call(*args: Any, **kwargs: Any) -> Any:
            if level in ("preview", "internal") and operation_id not in _warned:
                _warned.add(operation_id)
                if level == "preview":
                    warnings.warn(f"{operation_id} is a preview operation of the data API: it may change in a minor "
                                  "release (see the CHANGELOG)", PreviewWarning, stacklevel=2)  # fmt: skip
                else:
                    warnings.warn(f"{operation_id} is an internal operation of the data API: it may change in any "
                                  "release, without notice", InternalWarning, stacklevel=2)  # fmt: skip
            return fn(*args, **kwargs)

        call.operation = operation_id  # type: ignore[attr-defined]
        return call  # type: ignore[return-value]

    return wrap


def _p(*parts: str) -> str:
    """A path from segments, each quoted on its own (a ``/`` in a name stays in its segment)."""
    return "".join("/" + quote(str(p), safe="") for p in parts)


def _body(model: type[BaseModel], given: BaseModel | Mapping[str, Any] | None = None, /, **fields: Any) -> dict[str, Any]:
    """A request body checked against its model: a model, a mapping, or keyword fields (None ones left out)."""
    data = given if given is not None else {k: v for k, v in fields.items() if v is not None}
    obj = data if isinstance(data, model) else model.model_validate(dict(data))  # type: ignore[arg-type]
    return obj.model_dump(by_alias=True, exclude_none=True, mode="json")


def _key(idempotency_key: str | None) -> dict[str, str] | None:
    return {"Idempotency-Key": idempotency_key} if idempotency_key else None


def _csv(value: str | Sequence[str] | None) -> str | None:
    return value if value is None or isinstance(value, str) else ",".join(value)


class _Service:
    def __init__(self, http: Http):
        self._http = http

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


# ── catalog ───────────────────────────────────────────────────────────────────────────────────────────────────────


class Config(_Service):
    @op("config_get")
    def get(self) -> m.ConfigInfo:
        """The deployment's public settings; no token needed."""
        return m.ConfigInfo.model_validate(self._http.call("GET", "/config", authenticated=False).json())


class Workspaces(_Service):
    @op("workspaces_list")
    def list(self, *, external_id: str | None = None, limit: int | None = None) -> Iterator[m.WorkspaceInfo]:
        return self._http.pages("/workspaces", m.WorkspaceInfo.model_validate, limit=limit, external_id=external_id)

    @op("workspaces_get")
    def get(self, slug: str) -> m.WorkspaceInfo:
        return self._http.get(_p("workspaces", slug), m.WorkspaceInfo)

    @op("workspaces_create")
    def create(self, slug: str, display_name: str, *, viewer_groups: Sequence[str] = (),
               admin_group: str | None = None, external_id: str | None = None,
               idempotency_key: str | None = None) -> m.WorkspaceInfo:  # fmt: skip
        body = m.WorkspaceCreate(slug=slug, display_name=display_name, viewer_groups=list(viewer_groups),
                                 admin_group=admin_group, external_id=external_id)  # fmt: skip
        return self._http.send("POST", "/workspaces", m.WorkspaceInfo, body.model_dump(by_alias=True, exclude_none=True),
                               headers=_key(idempotency_key))  # fmt: skip

    @op("workspaces_update")
    def update(self, slug: str, *, default_catalog: str | None = None) -> m.WorkspaceInfo:
        return self._http.send("PATCH", _p("workspaces", slug), m.WorkspaceInfo,
                               _body(m.WorkspaceUpdate, default_catalog=default_catalog))  # fmt: skip

    @op("workspaces_delete")
    def delete(self, slug: str) -> None:
        self._http.call("DELETE", _p("workspaces", slug))

    @op("workspaces_catalogs_list")
    def catalogs(self, slug: str, *, limit: int | None = None) -> Iterator[m.WorkspaceCatalogInfo]:
        return self._http.pages(_p("workspaces", slug, "catalogs"), m.WorkspaceCatalogInfo.model_validate, limit=limit)

    @op("workspaces_catalogs_create")
    def create_catalog(self, slug: str, name: str, *, comment: str | None = None, storage_location: str | None = None,
                       owner_group: str | None = None,
                       idempotency_key: str | None = None) -> m.WorkspaceCatalogInfo:  # fmt: skip
        """A catalog in the workspace: isolated and bound read-write there, owned by its admin group by default."""
        body = _body(m.WorkspaceCatalogCreate, name=name, comment=comment, storage_location=storage_location,
                     owner_group=owner_group)  # fmt: skip
        return self._http.send("POST", _p("workspaces", slug, "catalogs"), m.WorkspaceCatalogInfo, body,
                               headers=_key(idempotency_key))  # fmt: skip

    @op("workspaces_summary")
    def summary(self, slug: str) -> m.WorkspaceSummaryOut:
        """Counts of what the caller can see in the workspace (bounded; ``truncated`` says when it stopped)."""
        return self._http.get(_p("workspaces", slug, "summary"), m.WorkspaceSummaryOut)

    @op("workspaces_storage")
    def storage(self, slug: str) -> m.WorkspaceStorageOut:
        return self._http.get(_p("workspaces", slug, "storage"), m.WorkspaceStorageOut)


class Catalogs(_Service):
    @op("catalogs_list")
    def list(self, *, limit: int | None = None) -> Iterator[m.CatalogInfo]:
        return self._http.pages("/catalogs", m.CatalogInfo.model_validate, limit=limit)

    @op("catalogs_get")
    def get(self, name: str) -> m.CatalogInfo:
        return self._http.get(_p("catalogs", name), m.CatalogInfo)

    @op("catalogs_create")
    def create(self, name: str, owner_group: str, *, isolation: str = "open", bindings: dict[str, str] | None = None,
               comment: str | None = None, storage_location: str | None = None,
               idempotency_key: str | None = None) -> m.CatalogInfo:  # fmt: skip
        """A catalog outside a workspace, as in a Unity metastore. ``bindings``: workspace slug to ``read_write`` or
        ``read_only`` (isolated catalogs)."""
        body = {"name": name, "owner_group": owner_group, "isolation": isolation, "comment": comment,
                "storage_location": storage_location,
                "bindings": [{"workspace": w, "binding": b} for w, b in (bindings or {}).items()]}  # fmt: skip
        return self._http.send("POST", "/catalogs", m.CatalogInfo, {k: v for k, v in body.items() if v is not None},
                               headers=_key(idempotency_key))  # fmt: skip

    @op("catalogs_delete")
    def delete(self, name: str) -> None:
        """Drop a catalog that holds nothing but an empty ``default`` schema."""
        self._http.call("DELETE", _p("catalogs", name))

    @op("catalogs_update")
    def update(self, name: str, *, isolation: str | None = None, comment: str | None = None) -> m.CatalogInfo:
        body = {k: v for k, v in {"isolation": isolation, "comment": comment}.items() if v is not None}
        return self._http.send("PATCH", _p("catalogs", name), m.CatalogInfo, body)

    @op("catalogs_bindings_list")
    def bindings(self, name: str, *, limit: int | None = None) -> Iterator[m.CatalogBindingInfo]:
        return self._http.pages(_p("catalogs", name, "bindings"), m.CatalogBindingInfo.model_validate, limit=limit)

    @op("catalogs_bindings_put")
    def bind(self, name: str, workspace: str, binding: str = "read_write") -> m.CatalogBindingInfo:
        return self._http.send("PUT", _p("catalogs", name, "bindings", workspace), m.CatalogBindingInfo,
                               {"binding": binding})  # fmt: skip

    @op("catalogs_bindings_delete")
    def unbind(self, name: str, workspace: str) -> None:
        self._http.call("DELETE", _p("catalogs", name, "bindings", workspace))


class StorageLocations(_Service):
    @op("storage_locations_list")
    def list(self, *, limit: int | None = None) -> Iterator[m.StorageLocationInfo]:
        return self._http.pages("/storage-locations", m.StorageLocationInfo.model_validate, limit=limit)

    @op("storage_locations_create")
    def create(self, name: str, url: str, *, comment: str | None = None,
               idempotency_key: str | None = None) -> m.StorageLocationInfo:  # fmt: skip
        return self._http.send("POST", "/storage-locations", m.StorageLocationInfo,
                               _body(m.StorageLocationIn, name=name, url=url, comment=comment),
                               headers=_key(idempotency_key))  # fmt: skip

    @op("storage_locations_update")
    def update(self, name: str, *, comment: str | None = None) -> m.StorageLocationInfo:
        return self._http.send("PATCH", _p("storage-locations", name), m.StorageLocationInfo,
                               _body(m.StorageLocationPatch, comment=comment))  # fmt: skip

    @op("storage_locations_delete")
    def delete(self, name: str) -> None:
        self._http.call("DELETE", _p("storage-locations", name))


class Schemas(_Service):
    @op("schemas_list")
    def list(self, slug: str, catalog: str, *, limit: int | None = None) -> Iterator[m.SchemaInfo]:
        return self._http.pages(_p("workspaces", slug, "catalogs", catalog, "schemas"), m.SchemaInfo.model_validate,
                                limit=limit)  # fmt: skip

    @op("schemas_get")
    def get(self, slug: str, catalog: str, schema: str) -> m.SchemaInfo:
        return self._http.get(_p("workspaces", slug, "catalogs", catalog, "schemas", schema), m.SchemaInfo)

    @op("schemas_create")
    def create(self, slug: str, catalog: str, schema: str, *, location_name: str | None = None,
               idempotency_key: str | None = None) -> m.SchemaInfo:  # fmt: skip
        return self._http.send("POST", _p("workspaces", slug, "catalogs", catalog, "schemas"), m.SchemaInfo,
                               _body(m.SchemaCreate, name=schema, location_name=location_name),
                               headers=_key(idempotency_key))  # fmt: skip

    @op("schemas_delete")
    def delete(self, slug: str, catalog: str, schema: str, *, confirm: str | None = None) -> None:
        """Drop a schema; one that holds tables needs ``confirm`` set to its name again."""
        self._http.call("DELETE", _p("workspaces", slug, "catalogs", catalog, "schemas", schema),
                        params={"confirm": confirm})  # fmt: skip


def _table(slug: str, catalog: str, schema: str, table: str, *rest: str) -> str:
    return _p("workspaces", slug, "catalogs", catalog, "schemas", schema, "tables", table, *rest)


class Tables(_Service):
    @op("tables_list")
    def list(self, slug: str, catalog: str, schema: str, *, limit: int | None = None) -> Iterator[m.TableSummary]:
        path = _p("workspaces", slug, "catalogs", catalog, "schemas", schema, "tables")
        return self._http.pages(path, m.TableSummary.model_validate, limit=limit)

    @op("tables_get")
    def get(self, slug: str, catalog: str, schema: str, table: str, *,
            expand: str | Sequence[str] | None = None) -> m.TableInfo:  # fmt: skip
        """``expand``: ``contract``, ``profile``."""
        return self._http.get(_table(slug, catalog, schema, table), m.TableInfo, expand=_csv(expand))

    @op("tables_history")
    def history(self, slug: str, catalog: str, schema: str, table: str, *,
                limit: int | None = None) -> Iterator[m.SnapshotInfo]:  # fmt: skip
        return self._http.pages(_table(slug, catalog, schema, table, "history"), m.SnapshotInfo.model_validate,
                                limit=limit)  # fmt: skip

    @op("tables_sample")
    def sample(self, slug: str, catalog: str, schema: str, table: str, *, limit: int | None = None,
               column: str | None = None, value: str | None = None, lo: float | None = None, hi: float | None = None,
               hi_inclusive: bool | None = None, empty: bool | None = None) -> m.SampleInfo:  # fmt: skip
        """A bounded sample, optionally where ``column`` equals ``value``, lies in ``[lo, hi)`` or is empty."""
        return self._http.get(_table(slug, catalog, schema, table, "sample"), m.SampleInfo, limit=limit,
                              column=column, value=value, lo=lo, hi=hi, hi_inclusive=hi_inclusive,
                              empty=empty)  # fmt: skip

    @op("tables_profile_get")
    def profile(self, slug: str, catalog: str, schema: str, table: str) -> m.ProfileOut:
        return self._http.get(_table(slug, catalog, schema, table, "profile"), m.ProfileOut)

    @op("tables_profile_put")
    def refresh_profile(self, slug: str, catalog: str, schema: str, table: str) -> m.ProfileOut:
        """Profile the table again as the caller."""
        return self._http.send("PUT", _table(slug, catalog, schema, table, "profile"), m.ProfileOut)

    @op("tables_classification_put")
    def classify(self, slug: str, catalog: str, schema: str, table: str, *, level: str | None = None,
                 columns: Mapping[str, str] | None = None) -> m.TableInfo:  # fmt: skip
        """The table's classification (``level``) and its columns' (column name to level)."""
        body = _body(m.ClassificationUpdate, table=level, columns=dict(columns) if columns is not None else None)
        return self._http.send("PUT", _table(slug, catalog, schema, table, "classification"), m.TableInfo, body)


class Views(_Service):
    @op("views_list")
    def list(self, slug: str, catalog: str, schema: str, *, limit: int | None = None) -> Iterator[m.TableSummary]:
        path = _p("workspaces", slug, "catalogs", catalog, "schemas", schema, "views")
        return self._http.pages(path, m.TableSummary.model_validate, limit=limit)

    @op("views_get")
    def get(self, slug: str, catalog: str, schema: str, view: str) -> m.ViewInfo:
        return self._http.get(_p("workspaces", slug, "catalogs", catalog, "schemas", schema, "views", view),
                              m.ViewInfo)  # fmt: skip


class Volumes(_Service):
    def _path(self, slug: str, catalog: str, schema: str, *rest: str) -> str:
        return _p("workspaces", slug, "catalogs", catalog, "schemas", schema, "volumes", *rest)

    @op("volumes_list")
    def list(self, slug: str, catalog: str, schema: str) -> list[m.VolumeInfo]:
        return self._http.items(self._path(slug, catalog, schema), m.VolumeInfo)

    @op("volumes_create")
    def create(self, slug: str, catalog: str, schema: str, name: str, *, comment: str | None = None,
               owner_group: str | None = None) -> m.VolumeInfo:  # fmt: skip
        return self._http.send("POST", self._path(slug, catalog, schema), m.VolumeInfo,
                               _body(m.VolumeCreate, name=name, comment=comment, owner_group=owner_group))  # fmt: skip

    @op("volumes_get")
    def get(self, slug: str, catalog: str, schema: str, volume: str) -> m.VolumeInfo:
        return self._http.get(self._path(slug, catalog, schema, volume), m.VolumeInfo)

    @op("volumes_delete")
    def delete(self, slug: str, catalog: str, schema: str, volume: str, *, confirm: str) -> None:
        """Drop a volume and its files; ``confirm`` is the volume's name again."""
        self._http.call("DELETE", self._path(slug, catalog, schema, volume), params={"confirm": confirm})

    @op("volumes_files_list")
    def files(self, slug: str, catalog: str, schema: str, volume: str, *, path: str | None = None) -> list[m.VolumeFile]:
        """The files and folders in ``path`` (empty: the volume's root)."""
        return self._http.items(self._path(slug, catalog, schema, volume, "files"), m.VolumeFile, path=path)

    @op("volumes_files_upload")
    def upload(self, slug: str, catalog: str, schema: str, volume: str, path: str, data: bytes | IO[bytes], *,
               overwrite: bool = False) -> m.VolumeFile:  # fmt: skip
        """Store ``data`` (bytes, or a binary file sent in chunks) at ``path``; it is scanned before it is kept."""
        content, headers = raw_body(data)
        r = self._http.call("PUT", self._path(slug, catalog, schema, volume, "files"), content=content,
                            params={"path": path, "overwrite": overwrite}, headers=headers)  # fmt: skip
        return m.VolumeFile.model_validate(r.json())

    @op("volumes_files_download")
    def download(self, slug: str, catalog: str, schema: str, volume: str, path: str) -> bytes:
        return self._http.call("GET", self._path(slug, catalog, schema, volume, "files", "content"),
                               params={"path": path}).content  # fmt: skip

    @op("volumes_files_delete")
    def delete_file(self, slug: str, catalog: str, schema: str, volume: str, path: str) -> None:
        self._http.call("DELETE", self._path(slug, catalog, schema, volume, "files"), params={"path": path})

    @op("volumes_permissions_get")
    def permissions(self, slug: str, catalog: str, schema: str, volume: str) -> m.VolumePermissions:
        return self._http.get(self._path(slug, catalog, schema, volume, "permissions"), m.VolumePermissions)

    @op("volumes_permissions_update")
    def update_permissions(self, slug: str, catalog: str, schema: str, volume: str, *,
                           grants: Sequence[Mapping[str, Any] | m.VolumeGrant] | None = None,
                           owner_group: str | None = None) -> m.VolumePermissions:  # fmt: skip
        body = _body(m.VolumePermissionsUpdate, grants=list(grants) if grants is not None else None,
                     owner_group=owner_group)  # fmt: skip
        return self._http.send("PUT", self._path(slug, catalog, schema, volume, "permissions"), m.VolumePermissions,
                               body)  # fmt: skip

    @op("volumes_permissions_explain")
    def explain(self, slug: str, catalog: str, schema: str, volume: str, *,
                need: str | None = None) -> m.VolumeExplanation:  # fmt: skip
        """Why the caller has (or lacks) ``need`` (default ``READ VOLUME``) on the volume."""
        return self._http.get(self._path(slug, catalog, schema, volume, "permissions", "explain"),
                              m.VolumeExplanation, need=need)  # fmt: skip


class Search(_Service):
    @op("search_query")
    def query(self, q: str, *, kinds: str | Sequence[str] | None = None,
              workspace: str | None = None) -> m.SearchResults:  # fmt: skip
        """Tables, columns, terms, projects and files the caller may see. ``kinds`` narrows it."""
        return self._http.get("/search", m.SearchResults, q=q, kinds=_csv(kinds), workspace=workspace)


# ── sql ───────────────────────────────────────────────────────────────────────────────────────────────────────────


class Statements(_Service):
    @op("statements_submit")
    def submit(self, slug: str, sql: str, *, engine: str = "sqe", catalog: str | None = None,
               schema: str | None = None, wait_timeout: int = 10, on_wait_timeout: str = "CONTINUE",
               row_limit: int | None = None, query_tag: str | None = None,
               idempotency_key: str | None = None) -> m.StatementInfo:  # fmt: skip
        body = m.StatementSubmit.model_validate({
            "sql": sql, "engine": engine, "catalog": catalog, "schema": schema, "wait_timeout": wait_timeout,
            "on_wait_timeout": on_wait_timeout, "row_limit": row_limit, "query_tag": query_tag,
        })  # fmt: skip
        return self._http.send("POST", _p("workspaces", slug, "statements"), m.StatementInfo,
                               body.model_dump(by_alias=True, exclude_none=True),
                               headers=_key(idempotency_key))  # fmt: skip

    @op("statements_get")
    def get(self, slug: str, statement_id: str, *, wait_timeout: int | None = None) -> m.StatementInfo:
        return self._http.get(_p("workspaces", slug, "statements", statement_id), m.StatementInfo,
                              wait_timeout=wait_timeout)  # fmt: skip

    @op("statements_cancel")
    def cancel(self, slug: str, statement_id: str) -> m.StatementInfo:
        return self._http.send("POST", _p("workspaces", slug, "statements", statement_id, "cancel"), m.StatementInfo)

    @op("statements_result")
    def result(self, slug: str, statement_id: str, *, cursor: str | None = None) -> m.ResultPage:
        return self._http.get(_p("workspaces", slug, "statements", statement_id, "result"), m.ResultPage,
                              cursor=cursor)  # fmt: skip

    @op("statements_result")
    def result_arrow(self, slug: str, statement_id: str, *, cursor: str | None = None) -> tuple[pa.Table, str | None]:
        """One page as an Arrow table, and the next page's cursor."""
        r = self._http.call("GET", _p("workspaces", slug, "statements", statement_id, "result"),
                            params={"cursor": cursor}, headers={"Accept": ARROW})  # fmt: skip
        with pa.ipc.open_stream(r.content) as reader:
            table = reader.read_all()
        return table, r.headers.get("x-next-cursor") or None

    @op("statements_execute")
    def execute(self, slug: str, sql: str, *, engine: str = "sqe", catalog: str | None = None,
                schema: str | None = None, row_limit: int | None = None) -> m.StatementRows:  # fmt: skip
        """Run one statement and answer its rows directly (capped; nothing is stored, as the query page)."""
        body = _body(m.StatementExecute, sql=sql, engine=engine, catalog=catalog, schema=schema, row_limit=row_limit)
        return self._http.send("POST", _p("workspaces", slug, "statements", "execute"), m.StatementRows, body)

    @op("statements_export")
    def export(self, slug: str, sql: str, *, format: str = "csv", engine: str = "sqe", catalog: str | None = None,
               schema: str | None = None, row_limit: int | None = None) -> bytes:  # fmt: skip
        """A statement's rows as a ``csv`` or ``parquet`` file (capped by the deployment's export limit)."""
        body = _body(m.StatementExecute, sql=sql, engine=engine, catalog=catalog, schema=schema, row_limit=row_limit)
        return self._http.call("POST", _p("workspaces", slug, "statements", "export"), json=body,
                               params={"format": format}).content  # fmt: skip

    @op("statements_explain")
    def explain(self, slug: str, sql: str, *, engine: str = "sqe", catalog: str | None = None,
                schema: str | None = None) -> m.ExplainOut:  # fmt: skip
        body = _body(m.StatementExplain, sql=sql, engine=engine, catalog=catalog, schema=schema)
        return self._http.send("POST", _p("workspaces", slug, "statements", "explain"), m.ExplainOut, body)

    @op("statements_transpile")
    def transpile(self, slug: str, sql: str, *, dialect: str = "databricks", engine: str | None = None,
                  schema: str | None = None) -> m.TranspileOut:  # fmt: skip
        """SQL of another dialect (Databricks by default) in the engine's."""
        body = _body(m.StatementTranspile, sql=sql, dialect=dialect, engine=engine, schema=schema)
        return self._http.send("POST", _p("workspaces", slug, "statements", "transpile"), m.TranspileOut, body)


class QueryEngines(_Service):
    @op("query_engines_list")
    def list(self) -> m.QueryEngines:
        """The engines a statement may name, the default and the row limits."""
        return self._http.get("/query-engines", m.QueryEngines)


class QueryHistory(_Service):
    @op("query_history_list")
    def list(self, slug: str, *, catalog: str | None = None, limit: int | None = None) -> Iterator[m.HistoryEntry]:
        """The caller's own statements in the workspace."""
        return self._http.pages(_p("workspaces", slug, "query-history"), m.HistoryEntry.model_validate, limit=limit,
                                catalog=catalog)  # fmt: skip

    @op("query_history_clear")
    def clear(self, slug: str) -> None:
        self._http.call("DELETE", _p("workspaces", slug, "query-history"))

    @op("query_history_delete")
    def delete(self, slug: str, history_id: str) -> None:
        self._http.call("DELETE", _p("workspaces", slug, "query-history", history_id))


class SavedQueries(_Service):
    @op("saved_queries_list")
    def list(self, slug: str, *, limit: int | None = None) -> Iterator[m.SavedQueryOut]:
        return self._http.pages(_p("workspaces", slug, "saved-queries"), m.SavedQueryOut.model_validate, limit=limit)

    @op("saved_queries_create")
    def create(self, slug: str, name: str, sql: str, *, description: str | None = None, shared: bool | None = None,
               folder: str | None = None) -> m.SavedQueryOut:  # fmt: skip
        body = _body(m.SavedQueryIn, name=name, sql=sql, description=description, shared=shared, folder=folder)
        return self._http.send("POST", _p("workspaces", slug, "saved-queries"), m.SavedQueryOut, body)

    @op("saved_queries_get")
    def get(self, slug: str, saved_query_id: str) -> m.SavedQueryOut:
        return self._http.get(_p("workspaces", slug, "saved-queries", saved_query_id), m.SavedQueryOut)

    @op("saved_queries_update")
    def update(self, slug: str, saved_query_id: str, *, etag: str | None = None, name: str | None = None,
               description: str | None = None, sql: str | None = None, shared: bool | None = None,
               folder: str | None = None) -> m.SavedQueryOut:  # fmt: skip
        """Change the fields given. ``etag``: the version edited (``If-Match``); without one the current version is
        read first, so a change made in between is overwritten. A stale ``etag`` raises ``PreconditionFailed``."""
        path = _p("workspaces", slug, "saved-queries", saved_query_id)
        if etag is None:
            etag = self._http.call("GET", path).headers.get("etag")
        body = _body(m.SavedQueryUpdate, name=name, description=description, sql=sql, shared=shared, folder=folder)
        return self._http.send("PATCH", path, m.SavedQueryOut, body, headers={"If-Match": etag} if etag else None)

    @op("saved_queries_delete")
    def delete(self, slug: str, saved_query_id: str) -> None:
        self._http.call("DELETE", _p("workspaces", slug, "saved-queries", saved_query_id))


# ── governance ────────────────────────────────────────────────────────────────────────────────────────────────────


class Permissions(_Service):
    @op("permissions_get")
    def get(self, slug: str, securable_type: str, full_name: str) -> m.PermissionsInfo:
        return self._http.get(_p("workspaces", slug, "permissions", securable_type, full_name), m.PermissionsInfo)

    @op("permissions_update")
    def update(self, slug: str, securable_type: str, full_name: str,
               changes: Sequence[Mapping[str, Any] | m.PermissionsChangeItem]) -> m.PermissionsInfo:  # fmt: skip
        """``changes``: ``{"principal": group, "add": [...], "remove": [...]}`` per group."""
        items = [c if isinstance(c, m.PermissionsChangeItem) else m.PermissionsChangeItem.model_validate(c)
                 for c in changes]  # fmt: skip
        body = {"changes": [c.model_dump(exclude_none=True) for c in items]}
        return self._http.send("PATCH", _p("workspaces", slug, "permissions", securable_type, full_name),
                               m.PermissionsInfo, body)  # fmt: skip


# Column masks the service knows (ai-portal-data masks.MASK_TYPES, governance 1.12). Not checked here: the service
# answers 422 for another, and may add types.
MASK_TYPES = ("MASK", "MASK_SHOW_LAST_4", "MASK_SHOW_FIRST_4", "MASK_HASH", "MASK_NULL", "MASK_DATE_SHOW_YEAR")


def _changes(changes: Sequence[m.GovernanceChange | Mapping[str, Any]]) -> dict[str, Any]:
    """The body of a batch: each change a model or a mapping (``schema``, not ``namespace``), None fields left out."""
    items = [c if isinstance(c, m.GovernanceChange) else m.GovernanceChange.model_validate(dict(c)) for c in changes]
    return {"changes": [c.model_dump(by_alias=True, exclude_none=True, mode="json") for c in items]}


class Governance(_Service):
    """Grants, owners, column masks, row filters and governed tags of a workspace's catalog, in batches with a dry run.

    ``internal`` operations (the data UI's own, until VPFDATA-713 settles their public shape): each warns once with
    ``InternalWarning`` and may change without notice. The public grants are ``Permissions``. A change names its
    securable with ``schema`` and ``table`` (neither: the catalog; ``tag_*`` changes name neither); the answers name the
    schema ``namespace``.
    """

    def _path(self, workspace: str, catalog: str, *rest: str) -> str:
        return _p("workspaces", workspace, "catalogs", catalog, "governance", *rest)

    @op("governance_get")
    def get(self, workspace: str, catalog: str, *, schema: str | None = None,
            table: str | None = None) -> m.PermissionsOut:  # fmt: skip
        """The catalog, a schema or a table: owner, grants (and the inherited ones), masks, the row filter, the tags on
        its columns, and what the caller may do."""
        return self._http.get(self._path(workspace, catalog), m.PermissionsOut, schema=schema, table=table)

    @op("governance_tags_list")
    def tags(self, workspace: str, catalog: str) -> m.TagsOut:
        """The catalog's governed tags with their mask and row filter; ``policies`` says whether tag masks and row
        filters reach Ranger in this deployment, ``can_manage`` whether the caller may change them."""
        return self._http.get(self._path(workspace, catalog, "tags"), m.TagsOut)

    @op("governance_changes_apply")
    def apply(self, workspace: str, catalog: str,
              changes: Sequence[m.GovernanceChange | Mapping[str, Any]]) -> m.PreviewOut:  # fmt: skip
        """Apply the changes (1 to 50) all or nothing, as the caller; the answer is what changed. 409 ``Conflict``
        (``row_filter_conflict``, ``mask_conflict``, ...: ``details`` names them), 422 ``InvalidParameter``."""
        return self._http.send("POST", self._path(workspace, catalog, "changes"), m.PreviewOut, _changes(changes))

    @op("governance_changes_preview")
    def preview(self, workspace: str, catalog: str,
                changes: Sequence[m.GovernanceChange | Mapping[str, Any]]) -> m.PreviewOut:  # fmt: skip
        """What ``apply`` would change (the Ranger diff, masks and tag policies, grants that would do nothing and the
        grants that would make them work); writes nothing."""
        return self._http.send("POST", self._path(workspace, catalog, "changes", "preview"), m.PreviewOut,
                               _changes(changes))  # fmt: skip


class Contracts(_Service):
    @op("contracts_list")
    def list(self, slug: str, catalog: str) -> list[m.ContractListItem]:
        return self._http.items(_p("workspaces", slug, "catalogs", catalog, "contracts"), m.ContractListItem)

    @op("contracts_get")
    def get(self, slug: str, catalog: str, schema: str, table: str) -> m.ContractOut:
        return self._http.get(_table(slug, catalog, schema, table, "contract"), m.ContractOut)

    @op("contracts_put")
    def put(self, slug: str, catalog: str, schema: str, table: str, *, yaml: str | None = None,
            from_schema: bool | None = None, version: int | None = None) -> m.ContractOut:  # fmt: skip
        """The table's contract from ODCS ``yaml``, or drafted ``from_schema``; ``version`` is the one edited."""
        body = _body(m.ContractPut, yaml=yaml, from_schema=from_schema, version=version)
        return self._http.send("PUT", _table(slug, catalog, schema, table, "contract"), m.ContractOut, body)

    @op("contracts_delete")
    def delete(self, slug: str, catalog: str, schema: str, table: str) -> None:
        self._http.call("DELETE", _table(slug, catalog, schema, table, "contract"))

    @op("contracts_drift")
    def drift(self, slug: str, catalog: str, schema: str, table: str) -> m.DriftOut:
        return self._http.get(_table(slug, catalog, schema, table, "contract", "drift"), m.DriftOut)

    @op("contracts_export")
    def export(self, slug: str, catalog: str, schema: str, table: str, format: str) -> str:
        """The contract as ``odcs`` YAML or as JSON Schema (``json-schema``)."""
        return self._http.call("GET", _table(slug, catalog, schema, table, "contract", "export"),
                               params={"format": format}).text  # fmt: skip

    @op("contracts_suggestions")
    def suggestions(self, slug: str, catalog: str, schema: str, table: str) -> m.SuggestionsOut:
        return self._http.get(_table(slug, catalog, schema, table, "contract", "suggestions"), m.SuggestionsOut)

    @op("contracts_suggestions_apply")
    def apply_suggestions(self, slug: str, catalog: str, schema: str, table: str, ids: Sequence[str],
                          version: int) -> m.ContractOut:  # fmt: skip
        return self._http.send("POST", _table(slug, catalog, schema, table, "contract", "suggestions", "apply"),
                               m.ContractOut, _body(m.SuggestionsApply, ids=list(ids), version=version))  # fmt: skip


class Quality(_Service):
    @op("quality_inbox_get")
    def inbox(self, slug: str, catalog: str) -> m.InboxOut:
        """The catalog's failing checks the caller owns, with what they hold up downstream."""
        return self._http.get(_p("workspaces", slug, "catalogs", catalog, "quality-inbox"), m.InboxOut)

    @op("quality_runs_get")
    def get_run(self, slug: str, catalog: str, run_id: str) -> m.RunOut:
        return self._http.get(_p("workspaces", slug, "catalogs", catalog, "quality-runs", run_id), m.RunOut)

    @op("quality_runs_list")
    def runs(self, slug: str, catalog: str, schema: str, table: str) -> list[m.RunSummaryOut]:
        return self._http.items(_table(slug, catalog, schema, table, "quality-runs"), m.RunSummaryOut)

    @op("quality_runs_create")
    def run(self, slug: str, catalog: str, schema: str, table: str, *, check: str | None = None,
            idempotency_key: str | None = None) -> m.RunOut:  # fmt: skip
        """Run the table's contract checks now (or one ``check``), as the caller."""
        return self._http.send("POST", _table(slug, catalog, schema, table, "quality-runs"), m.RunOut,
                               _body(m.QualityRunCreate, check=check), headers=_key(idempotency_key))  # fmt: skip


class Lineage(_Service):
    @op("lineage_get")
    def get(self, slug: str, catalog: str, schema: str, table: str, *, direction: str | None = None,
            depth: int | None = None, column: str | None = None) -> m.LineageGraphOut:  # fmt: skip
        """The graph around the table: ``up``, ``down`` or ``both`` (default), ``depth`` steps (default 2)."""
        return self._http.get(_table(slug, catalog, schema, table, "lineage"), m.LineageGraphOut,
                              direction=direction, depth=depth, column=column)  # fmt: skip

    @op("lineage_impact")
    def impact(self, slug: str, catalog: str, schema: str, table: str, *, column: str | None = None) -> m.ImpactOut:
        return self._http.get(_table(slug, catalog, schema, table, "lineage", "impact"), m.ImpactOut, column=column)

    @op("lineage_upstream_problems")
    def upstream_problems(self, slug: str, catalog: str, schema: str, table: str) -> m.UpstreamProblemsOut:
        return self._http.get(_table(slug, catalog, schema, table, "lineage", "upstream-problems"),
                              m.UpstreamProblemsOut)  # fmt: skip

    @op("lineage_classification_suggestions")
    def classification_suggestions(self, slug: str, catalog: str, schema: str,
                                   table: str) -> list[m.ClassificationSuggestionOut]:  # fmt: skip
        """Classifications the table's upstream suggests for its columns."""
        return self._http.items(_table(slug, catalog, schema, table, "classification-suggestions"),
                                m.ClassificationSuggestionOut)  # fmt: skip

    @op("lineage_producers_list")
    def producers(self) -> list[m.ProducerOut]:
        return self._http.items("/lineage/producers", m.ProducerOut)

    @op("lineage_producers_create")
    def create_producer(self, name: str, kind: str) -> m.ProducerCreatedOut:
        """A producer key for an engine's OpenLineage events; the key is shown only in this answer."""
        return self._http.send("POST", "/lineage/producers", m.ProducerCreatedOut,
                               _body(m.ProducerCreate, name=name, kind=kind))  # fmt: skip

    @op("lineage_producers_revoke")
    def revoke_producer(self, producer_id: str) -> m.ProducerOut:
        return self._http.send("POST", _p("lineage", "producers", producer_id, "revoke"), m.ProducerOut)

    @op("lineage_status_get")
    def status(self) -> m.LineageStatusOut:
        return self._http.get("/lineage/status", m.LineageStatusOut)


class Glossary(_Service):
    @op("glossary_terms_list")
    def terms(self, slug: str, *, q: str | None = None, status: str | None = None) -> list[m.TermOut]:
        return self._http.items(_p("workspaces", slug, "glossary", "terms"), m.TermOut, q=q, status=status)

    @op("glossary_terms_create")
    def create_term(self, slug: str, term: m.GlossaryTermCreate | Mapping[str, Any]) -> m.TermOut:
        return self._http.send("POST", _p("workspaces", slug, "glossary", "terms"), m.TermOut,
                               _body(m.GlossaryTermCreate, term))  # fmt: skip

    @op("glossary_terms_get")
    def get_term(self, slug: str, term_id: str) -> m.TermOut:
        return self._http.get(_p("workspaces", slug, "glossary", "terms", term_id), m.TermOut)

    @op("glossary_terms_update")
    def update_term(self, slug: str, term_id: str, term: m.GlossaryTermUpdate | Mapping[str, Any]) -> m.TermOut:
        """Replace the term; ``version`` in ``term`` is the one edited."""
        return self._http.send("PUT", _p("workspaces", slug, "glossary", "terms", term_id), m.TermOut,
                               _body(m.GlossaryTermUpdate, term))  # fmt: skip

    @op("glossary_terms_delete")
    def delete_term(self, slug: str, term_id: str) -> None:
        self._http.call("DELETE", _p("workspaces", slug, "glossary", "terms", term_id))

    @op("glossary_terms_history")
    def history(self, slug: str, term_id: str) -> list[m.TermVersionOut]:
        return self._http.items(_p("workspaces", slug, "glossary", "terms", term_id, "history"), m.TermVersionOut)

    @op("glossary_terms_status_update")
    def set_status(self, slug: str, term_id: str, status: str, version: int) -> m.TermOut:
        """``draft``, ``accepted`` or ``retired``."""
        return self._http.send("PUT", _p("workspaces", slug, "glossary", "terms", term_id, "status"), m.TermOut,
                               _body(m.GlossaryTermStatus, status=status, version=version))  # fmt: skip

    @op("glossary_search")
    def search(self, slug: str, q: str) -> m.SearchOut:
        return self._http.get(_p("workspaces", slug, "glossary", "search"), m.SearchOut, q=q)

    @op("glossary_export")
    def export(self, slug: str, format: str = "yaml") -> str:
        """The glossary as ``yaml`` or ``csv``."""
        return self._http.call("GET", _p("workspaces", slug, "glossary", "export"), params={"format": format}).text

    @op("glossary_import")
    def import_terms(self, slug: str, format: str, content: str) -> m.ImportOut:
        return self._http.send("POST", _p("workspaces", slug, "glossary", "import"), m.ImportOut,
                               _body(m.GlossaryImport, format=format, content=content))  # fmt: skip

    @op("glossary_table_terms")
    def table_terms(self, slug: str, catalog: str, schema: str, table: str) -> list[m.TableTermOut]:
        """The terms linked to the table's columns."""
        return self._http.items(_table(slug, catalog, schema, table, "glossary-terms"), m.TableTermOut)


# ── projects and jobs ─────────────────────────────────────────────────────────────────────────────────────────────


class Projects(_Service):
    def _path(self, slug: str, project: str, *rest: str) -> str:
        return _p("workspaces", slug, "projects", project, *rest)

    @op("projects_list")
    def list(self, slug: str, *, limit: int | None = None) -> Iterator[m.ProjectInfo]:
        return self._http.pages(_p("workspaces", slug, "projects"), m.ProjectInfo.model_validate, limit=limit)

    @op("projects_create")
    def create(self, slug: str, project: str, *, name: str | None = None, description: str | None = None,
               owner_group: str | None = None, git_url: str | None = None, branch: str | None = None,
               template: str | None = None, idempotency_key: str | None = None) -> m.ProjectCreated:  # fmt: skip
        """A project: empty, from a ``template``, or a clone of ``git_url`` at ``branch`` (default ``main``)."""
        body = _body(m.ProjectCreate, slug=project, name=name, description=description, owner_group=owner_group,
                     git_url=git_url, branch=branch, template=template)  # fmt: skip
        return self._http.send("POST", _p("workspaces", slug, "projects"), m.ProjectCreated, body,
                               headers=_key(idempotency_key))  # fmt: skip

    @op("projects_get")
    def get(self, slug: str, project: str) -> m.ProjectDetail:
        return self._http.get(self._path(slug, project), m.ProjectDetail)

    @op("projects_delete")
    def delete(self, slug: str, project: str, *, confirm: str) -> None:
        """Delete the project; ``confirm`` is its slug again."""
        self._http.call("DELETE", self._path(slug, project), params={"confirm": confirm})

    @op("personal_project_put")
    def personal(self, slug: str) -> m.ProjectDetail:
        """The caller's personal project in the workspace, made on first use."""
        return self._http.send("PUT", _p("workspaces", slug, "personal-project"), m.ProjectDetail)

    @op("projects_files_list")
    def files(self, slug: str, project: str, branch: str) -> list[m.ProjectTreeEntry]:
        """Every file of the branch, with its sha."""
        return self._http.items(self._path(slug, project, "files"), m.ProjectTreeEntry, branch=branch)

    @op("projects_files_create")
    def create_file(self, slug: str, project: str, branch: str, path: str, starter: str) -> m.ProjectFileOut:
        """A new file from one of the starters (a notebook, a SQL file, a job)."""
        return self._http.send("POST", self._path(slug, project, "files"), m.ProjectFileOut,
                               _body(m.ProjectFileCreate, branch=branch, path=path, starter=starter))  # fmt: skip

    @op("projects_file_get")
    def read_file(self, slug: str, project: str, branch: str, path: str) -> m.ProjectFileOut:
        return self._http.get(self._path(slug, project, "file"), m.ProjectFileOut, branch=branch, path=path)

    @op("projects_file_put")
    def save_file(self, slug: str, project: str, branch: str, path: str, content: str, *,
                  base_sha: str | None = None) -> m.ProjectFileOut:  # fmt: skip
        """Save a file on the branch (not committed); ``base_sha``: the version edited, refused when it moved."""
        body = _body(m.ProjectFileSave, branch=branch, path=path, content=content, base_sha=base_sha)
        return self._http.send("PUT", self._path(slug, project, "file"), m.ProjectFileOut, body)

    @op("projects_file_delete")
    def delete_file(self, slug: str, project: str, branch: str, path: str, *, base_sha: str | None = None) -> None:
        self._http.call("DELETE", self._path(slug, project, "file"),
                        params={"branch": branch, "path": path, "base_sha": base_sha})  # fmt: skip

    @op("projects_history_list")
    def history(self, slug: str, project: str, branch: str) -> list[m.ProjectCommit]:
        return self._http.items(self._path(slug, project, "history"), m.ProjectCommit, branch=branch)

    @op("projects_diff_get")
    def diff(self, slug: str, project: str, branch: str) -> list[m.ProjectDiffOut]:
        """What is saved on the branch and not yet committed."""
        return self._http.items(self._path(slug, project, "diff"), m.ProjectDiffOut, branch=branch)

    @op("projects_branches_create")
    def create_branch(self, slug: str, project: str, name: str, *, source: str | None = None) -> m.ProjectBranchOut:
        return self._http.send("POST", self._path(slug, project, "branches"), m.ProjectBranchOut,
                               _body(m.ProjectBranchCreate, name=name, source=source))  # fmt: skip

    @op("projects_remote_branches_list")
    def remote_branches(self, slug: str, project: str) -> list[m.RemoteBranch]:
        return self._http.items(self._path(slug, project, "remote-branches"), m.RemoteBranch)

    @op("projects_pull")
    def pull(self, slug: str, project: str, branch: str) -> m.ProjectPullOut:
        return self._http.send("POST", self._path(slug, project, "pull"), m.ProjectPullOut,
                               _body(m.ProjectBranchName, branch=branch))  # fmt: skip

    @op("projects_commit")
    def commit(self, slug: str, project: str, branch: str, message: str) -> m.ProjectCommitOut:
        """Commit and push what is saved on the branch; ``jobs`` says what the commit deployed."""
        return self._http.send("POST", self._path(slug, project, "commit"), m.ProjectCommitOut,
                               _body(m.ProjectCommitCreate, branch=branch, message=message))  # fmt: skip

    @op("projects_permissions_get")
    def permissions(self, slug: str, project: str) -> m.ProjectPermissionsOut:
        return self._http.get(self._path(slug, project, "permissions"), m.ProjectPermissionsOut)

    @op("projects_permissions_update")
    def update_permissions(self, slug: str, project: str, *,
                           grants: Sequence[Mapping[str, Any] | m.ProjectGrantIn] | None = None,
                           owner_group: str | None = None) -> m.ProjectPermissionsOut:  # fmt: skip
        body = _body(m.ProjectPermissionsSet, grants=list(grants) if grants is not None else None,
                     owner_group=owner_group)  # fmt: skip
        return self._http.send("PUT", self._path(slug, project, "permissions"), m.ProjectPermissionsOut, body)

    @op("projects_permissions_explain")
    def explain(self, slug: str, project: str, *, need: str | None = None) -> m.ProjectExplainOut:
        """Why the caller has (or lacks) ``need`` (default ``CAN VIEW``) on the project."""
        return self._http.get(self._path(slug, project, "permissions", "explain"), m.ProjectExplainOut, need=need)

    @op("projects_actions_list")
    def actions(self, slug: str, project: str, branch: str, path: str) -> list[m.ProjectActionOut]:
        """What can run on a file (dbt build, a Python script, ...)."""
        return self._http.items(self._path(slug, project, "actions"), m.ProjectActionOut, branch=branch, path=path)

    @op("projects_actions_run")
    def run_action(self, slug: str, project: str, action: str, branch: str, path: str, *,
                   selection: str | None = None, namespace: str | None = None,
                   params: Mapping[str, Any] | None = None,
                   catalog: str | None = None) -> m.ProjectActionResult:  # fmt: skip
        body = _body(m.ProjectActionRun, branch=branch, path=path, selection=selection, namespace=namespace,
                     params=dict(params) if params is not None else None, catalog=catalog)  # fmt: skip
        return self._http.send("POST", self._path(slug, project, "actions", action), m.ProjectActionResult, body)

    @op("projects_runs_list")
    def runs(self, slug: str, project: str, *, branch: str | None = None,
             limit: int | None = None) -> Iterator[m.ProjectRunInfo]:  # fmt: skip
        return self._http.pages(self._path(slug, project, "runs"), m.ProjectRunInfo.model_validate, limit=limit,
                                branch=branch)  # fmt: skip

    @op("projects_runs_get")
    def run(self, slug: str, project: str, run_id: str) -> m.ProjectRunInfo:
        return self._http.get(self._path(slug, project, "runs", run_id), m.ProjectRunInfo)

    def wait_run(self, slug: str, project: str, run_id: str, *, timeout: float | None = None,
                 interval: float = WAIT_INTERVAL) -> m.ProjectRunInfo:  # fmt: skip
        """Wait until the run ends and return it, whatever its result. Reads the run on each change the caller's
        event stream (``/me/events``) reports for it, and every ``interval`` seconds. ``WaitTimeout`` after
        ``timeout`` seconds (None: no limit); the run goes on."""
        return wait_until(self._http, f"{API}/workspaces/{slug}/projects/{project}/runs/{run_id}",
                          lambda: self.run(slug, project, run_id), lambda r: r.status in PROJECT_RUN_ENDED,
                          what=f"Run {run_id}", timeout=timeout, interval=interval)  # fmt: skip

    @op("projects_runs_logs")
    def logs(self, slug: str, project: str, run_id: str, *, after: int = 0,
             follow: bool = True) -> Iterator[dict[str, Any]]:  # fmt: skip
        """The run's log lines after line ``after``: ``{"event": "line", "seq", "stream", "line"}`` each, then
        ``{"event": "end", "status", "error"}`` once the run has ended. ``follow``: new lines as the run writes them,
        until it ends; otherwise stop at the service's first heartbeat (it had nothing new for a while)."""
        path = self._path(slug, project, "runs", run_id, "logs")
        for event, data, ident in self._http.events(path, params={"after": after}):
            if event == "ping":
                if not follow:
                    return
                continue
            try:
                body = json.loads(data)
            except ValueError:
                continue
            if not isinstance(body, dict):
                continue
            if event == "line":
                yield {"event": "line", "seq": int(ident) if ident and ident.isdigit() else None,
                       "stream": body.get("stream"), "line": body.get("line")}  # fmt: skip
            elif event == "end":
                yield {"event": "end", "status": body.get("status"), "error": body.get("error")}
                return

    @op("projects_runs_cancel")
    def cancel_run(self, slug: str, project: str, run_id: str) -> m.ProjectRunInfo:
        return self._http.send("POST", self._path(slug, project, "runs", run_id, "cancel"), m.ProjectRunInfo)

    @op("projects_runs_artifact_get")
    def artifact(self, slug: str, project: str, run_id: str, artifact: str) -> m.ProjectRunArtifact:
        """One artifact of a run (dbt's ``run_results``, ``manifest``, ...)."""
        return self._http.get(self._path(slug, project, "runs", run_id, "artifacts", artifact), m.ProjectRunArtifact)


class Jobs(_Service):
    def _path(self, slug: str, project: str, *rest: str) -> str:
        return _p("workspaces", slug, "projects", project, *rest)

    @op("jobs_list")
    def list(self, slug: str, project: str, *, undeployed: bool | None = None,
             limit: int | None = None) -> Iterator[m.JobInfo]:  # fmt: skip
        return self._http.pages(self._path(slug, project, "jobs"), m.JobInfo.model_validate, limit=limit,
                                undeployed=undeployed)  # fmt: skip

    @op("jobs_get")
    def get(self, slug: str, project: str, name: str, *, expand: str | Sequence[str] | None = None,
            days: int | None = None) -> m.JobInfo:  # fmt: skip
        """``expand``: ``task_graph``, ``stats`` (over ``days``), ``definition``."""
        return self._http.get(self._path(slug, project, "jobs", name), m.JobInfo, expand=_csv(expand), days=days)

    @op("jobs_update")
    def update(self, slug: str, project: str, name: str, *, enabled: bool) -> m.JobInfo:
        """Pause (``enabled=False``) or resume the job's schedule and triggers."""
        return self._http.send("PATCH", self._path(slug, project, "jobs", name), m.JobInfo,
                               _body(m.JobUpdate, enabled=enabled))  # fmt: skip

    @op("jobs_permissions_get")
    def permissions(self, slug: str, project: str, name: str) -> m.JobPermissionsOut:
        return self._http.get(self._path(slug, project, "jobs", name, "permissions"), m.JobPermissionsOut)

    @op("jobs_permissions_update")
    def update_permissions(self, slug: str, project: str, name: str,
                           grants: Sequence[Mapping[str, Any] | m.JobGrantIn]) -> m.JobPermissionsOut:  # fmt: skip
        return self._http.send("PUT", self._path(slug, project, "jobs", name, "permissions"), m.JobPermissionsOut,
                               _body(m.JobPermissionsIn, grants=list(grants)))  # fmt: skip

    @op("jobs_run_now")
    def run_now(self, slug: str, project: str, name: str, *, job_parameters: Mapping[str, str] | None = None,
                idempotency_key: str | None = None) -> m.JobRunInfo:  # fmt: skip
        body = {"job_parameters": dict(job_parameters)} if job_parameters else None
        return self._http.send("POST", self._path(slug, project, "jobs", name, "run-now"), m.JobRunInfo, body,
                               headers=_key(idempotency_key))  # fmt: skip

    @op("jobs_runs_list")
    def runs(self, slug: str, project: str, name: str, *, limit: int | None = None) -> Iterator[m.JobRunInfo]:
        return self._http.pages(self._path(slug, project, "jobs", name, "runs"), m.JobRunInfo.model_validate,
                                limit=limit)  # fmt: skip

    @op("jobs_runs_get")
    def run(self, slug: str, project: str, name: str, run_id: str) -> m.JobRunInfo:
        return self._http.get(self._path(slug, project, "jobs", name, "runs", run_id), m.JobRunInfo)

    def wait_run(self, slug: str, project: str, name: str, run_id: str, *, timeout: float | None = None,
                 interval: float = WAIT_INTERVAL) -> m.JobRunInfo:  # fmt: skip
        """Wait until the job run ends and return it, whatever its result. Reads the run on each change the
        caller's event stream (``/me/events``) reports for it, and every ``interval`` seconds. ``WaitTimeout``
        after ``timeout`` seconds (None: no limit); the run goes on."""
        return wait_until(self._http, f"{API}/workspaces/{slug}/projects/{project}/jobs/{name}/runs/{run_id}",
                          lambda: self.run(slug, project, name, run_id), lambda r: r.status in JOB_RUN_ENDED,
                          what=f"Job run {run_id}", timeout=timeout, interval=interval)  # fmt: skip

    @op("jobs_runs_cancel")
    def cancel_run(self, slug: str, project: str, name: str, run_id: str) -> m.JobRunInfo:
        return self._http.send("POST", self._path(slug, project, "jobs", name, "runs", run_id, "cancel"), m.JobRunInfo)

    @op("jobs_runs_retry")
    def retry_run(self, slug: str, project: str, name: str, run_id: str, *,
                  idempotency_key: str | None = None) -> m.JobRunInfo:  # fmt: skip
        """A new run of the failed tasks of ``run_id`` and what depends on them."""
        return self._http.send("POST", self._path(slug, project, "jobs", name, "runs", run_id, "retry"), m.JobRunInfo,
                               headers=_key(idempotency_key))  # fmt: skip

    @op("jobs_deployment_get")
    def deployment(self, slug: str, project: str) -> m.DeploymentOut:
        return self._http.get(self._path(slug, project, "deployment"), m.DeploymentOut)

    @op("jobs_deployment_put")
    def deploy(self, slug: str, project: str, *, target: str | None = None) -> m.JobsDeployOut:
        """Deploy the project's jobs from its default branch to ``target``."""
        return self._http.send("PUT", self._path(slug, project, "deployment"), m.JobsDeployOut,
                               _body(m.DeploymentIn, target=target))  # fmt: skip

    @op("jobs_deployment_delete")
    def destroy(self, slug: str, project: str) -> m.DestroyOut:
        """Undeploy every job of the project."""
        return self._http.send("DELETE", self._path(slug, project, "deployment"), m.DestroyOut)

    @op("jobs_deployment_validate")
    def validate_deployment(self, slug: str, project: str, *, target: str | None = None,
                            branch: str | None = None) -> m.DeploymentValidateOut:  # fmt: skip
        return self._http.send("POST", self._path(slug, project, "deployment", "validate"), m.DeploymentValidateOut,
                               _body(m.DeploymentValidateIn, target=target, branch=branch))  # fmt: skip

    @op("jobs_principal_get")
    def principal(self, slug: str, project: str) -> m.PrincipalOut:
        return self._http.get(self._path(slug, project, "principal"), m.PrincipalOut)

    @op("jobs_principal_put")
    def set_principal(self, slug: str, project: str, groups: Sequence[str]) -> m.PrincipalOut:
        """The project's service principal, in ``groups``, that scheduled runs use instead of the owner (D3)."""
        return self._http.send("PUT", self._path(slug, project, "principal"), m.PrincipalOut,
                               _body(m.PrincipalIn, groups=list(groups)))  # fmt: skip

    @op("jobs_principal_delete")
    def remove_principal(self, slug: str, project: str) -> m.JobsRevokedOut:
        return self._http.send("DELETE", self._path(slug, project, "principal"), m.JobsRevokedOut)

    @op("jobs_file_usage_list")
    def file_usage(self, slug: str, project: str, *, path: str | None = None,
                   limit: int | None = None) -> Iterator[m.FileUsageOut]:  # fmt: skip
        """Which jobs use which of the project's files."""
        return self._http.pages(self._path(slug, project, "file-usage"), m.FileUsageOut.model_validate, limit=limit,
                                path=path)  # fmt: skip

    @op("job_builder_validate")
    def validate(self, slug: str, project: str, branch: str, file: str, text: str, *,
                 target: str | None = None) -> m.JobBuilderCheckOut:  # fmt: skip
        """Check a job file's text before it is saved."""
        return self._http.send("POST", self._path(slug, project, "job-builder", "validate"), m.JobBuilderCheckOut,
                               _body(m.JobBuilderCheckIn, branch=branch, file=file, text=text,
                                     target=target))  # fmt: skip

    @op("job_builder_import")
    def import_job(self, slug: str, project: str, text: str, *, name: str | None = None,
                   strip_prefix: str | None = None) -> m.JobBuilderImportOut:  # fmt: skip
        """A Databricks job (its JSON or a bundle's YAML) as this platform's job file."""
        return self._http.send("POST", self._path(slug, project, "job-builder", "import"), m.JobBuilderImportOut,
                               _body(m.JobBuilderImportIn, text=text, name=name, strip_prefix=strip_prefix))  # fmt: skip

    @op("job_builder_export")
    def export_job(self, slug: str, project: str, branch: str, file: str, text: str, job: str, *,
                   target: str | None = None, format: str | None = None) -> m.JobBuilderExportOut:  # fmt: skip
        body = _body(m.JobBuilderExportIn, branch=branch, file=file, text=text, job=job, target=target, format=format)
        return self._http.send("POST", self._path(slug, project, "job-builder", "export"), m.JobBuilderExportOut, body)

    @op("workspace_jobs_list")
    def in_workspace(self, slug: str, *, project: str | None = None,
                     limit: int | None = None) -> Iterator[m.WorkspaceJobInfo]:  # fmt: skip
        """Every job of the workspace the caller may see, across projects."""
        return self._http.pages(_p("workspaces", slug, "jobs"), m.WorkspaceJobInfo.model_validate, limit=limit,
                                project=project)  # fmt: skip

    @op("workspace_job_runs_list")
    def runs_in_workspace(self, slug: str, *, project: str | None = None,
                          limit: int | None = None) -> Iterator[m.WorkspaceJobRunInfo]:  # fmt: skip
        return self._http.pages(_p("workspaces", slug, "job-runs"), m.WorkspaceJobRunInfo.model_validate, limit=limit,
                                project=project)  # fmt: skip

    @op("workspace_job_stats")
    def stats(self, slug: str, *, project: str | None = None) -> m.WorkspaceJobStats:
        return self._http.get(_p("workspaces", slug, "job-stats"), m.WorkspaceJobStats, project=project)


# ── ingest ────────────────────────────────────────────────────────────────────────────────────────────────────────


class Uploads(_Service):
    @op("ingest_uploads_list")
    def list(self, slug: str) -> list[m.Upload]:
        return self._http.items(_p("workspaces", slug, "uploads"), m.Upload)

    @op("ingest_uploads_create")
    def create(self, slug: str, data: bytes | IO[bytes], format: str, *, delimiter: str | None = None,
               header: bool | None = None, scope: str | None = None) -> m.Upload:  # fmt: skip
        """Stage a ``parquet``, ``csv`` or ``json`` file (bytes, or a binary file sent in chunks); it is scanned and
        staged before the answer, then ``load`` puts it in a table."""
        content, headers = raw_body(data)
        r = self._http.call("POST", _p("workspaces", slug, "uploads"), content=content,
                            params={"format": format, "delimiter": delimiter, "header": header, "scope": scope},
                            headers=headers)  # fmt: skip
        return m.Upload.model_validate(r.json())

    @op("ingest_uploads_preview")
    def preview(self, slug: str, upload_id: str) -> m.QueryOut:
        return self._http.get(_p("workspaces", slug, "uploads", upload_id, "preview"), m.QueryOut)

    @op("ingest_uploads_load")
    def load(self, slug: str, upload_id: str, schema: str, table: str, *, catalog: str | None = None,
             mode: str | None = None, confirm: bool | None = None,
             idempotency_key: str | None = None) -> m.Upload:  # fmt: skip
        """Load the staged file into ``schema.table`` of ``catalog`` (one of the workspace's catalogs, bound
        read-write; none: the home catalog), ``create`` or ``append``."""
        return self._http.send("POST", _p("workspaces", slug, "uploads", upload_id, "load"), m.Upload,
                               _body(m.UploadLoad, catalog=catalog, schema=schema, table=table, mode=mode,
                                     confirm=confirm),
                               headers=_key(idempotency_key))  # fmt: skip

    @op("ingest_uploads_delete")
    def delete(self, slug: str, upload_id: str) -> None:
        self._http.call("DELETE", _p("workspaces", slug, "uploads", upload_id))


# ── secrets and the caller ────────────────────────────────────────────────────────────────────────────────────────


class Me(_Service):
    @op("me_get")
    def get(self) -> m.MeOut:
        return self._http.get("/me", m.MeOut)

    @op("me_events")
    def events(self, *, since: str | None = None, follow: bool = True) -> Iterator[dict[str, Any]]:
        """The caller's changes as they commit (``GET /me/events``, stable): ``{"event": "change", "id", "data"}``
        each (``data``: type, resource, full_name, etag, status), then ``{"event": "reset"}`` when changes were lost
        (list again, then call without ``since``) or ``{"event": "reconnect"}`` when the token or the hour ended (call
        again with the last id), after which the iterator ends. ``since``: resume after that id. ``follow``: wait for
        new changes; otherwise stop at the service's first heartbeat. ``wait_run`` and ``cidp events`` resume on
        their own."""
        for event, data, ident in self._http.events("/me/events", params={"last_event_id": since}):
            if event == "ping":
                if not follow:
                    return
                continue
            if event in ("reset", "reconnect"):
                yield {"event": event}
                return
            if event != "change":
                continue
            try:
                body = json.loads(data)
            except ValueError:
                continue
            if isinstance(body, dict):
                yield {"event": "change", "id": ident, "data": body}

    @op("groups_list")
    def groups(self) -> m.Groups:
        """The known groups (every workspace's viewer and admin groups, the default owner group and the caller's
        own), each with its level and whether the caller is in it."""
        return self._http.get("/groups", m.Groups)

    @op("me_jobs_identity_get")
    def jobs_identity(self) -> m.JobsIdentityOut:
        """Whether the caller's jobs can run as them (the consented offline token, D3)."""
        return self._http.get("/me/jobs-identity", m.JobsIdentityOut)

    @op("me_jobs_identity_start")
    def start_jobs_identity(self) -> m.JobsConsentStartOut:
        """The URL where the caller consents; the identity provider sends ``code`` and ``state`` back."""
        return self._http.send("POST", "/me/jobs-identity/start", m.JobsConsentStartOut)

    @op("me_jobs_identity_complete")
    def complete_jobs_identity(self, code: str, state: str) -> m.JobsIdentityOut:
        return self._http.send("POST", "/me/jobs-identity/complete", m.JobsIdentityOut,
                               _body(m.JobsConsentComplete, code=code, state=state))  # fmt: skip

    @op("me_jobs_identity_delete")
    def revoke_jobs_identity(self) -> m.JobsRevokedOut:
        return self._http.send("DELETE", "/me/jobs-identity", m.JobsRevokedOut)

    @op("me_git_credentials_list")
    def git_credentials(self) -> list[m.GitCredentialOut]:
        return self._http.items("/me/git-credentials", m.GitCredentialOut)

    @op("me_git_credentials_put")
    def set_git_credential(self, host: str, token: str, *, username: str | None = None) -> m.GitCredentialOut:
        """A token for a git host; it is kept encrypted and never shown again."""
        return self._http.send("PUT", _p("me", "git-credentials", host), m.GitCredentialOut,
                               _body(m.GitToken, token=token, username=username))  # fmt: skip

    @op("me_git_credentials_delete")
    def delete_git_credential(self, host: str) -> None:
        self._http.call("DELETE", _p("me", "git-credentials", host))

    @op("me_git_providers_list")
    def git_providers(self) -> list[m.GitProviderOut]:
        return self._http.items("/me/git-providers", m.GitProviderOut)

    @op("me_git_oauth_start")
    def start_git_oauth(self, provider: str) -> m.GitOAuthStartOut:
        return self._http.send("POST", _p("me", "git-oauth", provider, "start"), m.GitOAuthStartOut)

    @op("me_git_oauth_complete")
    def complete_git_oauth(self, provider: str, code: str, state: str) -> m.GitCredentialOut:
        return self._http.send("POST", _p("me", "git-oauth", provider, "complete"), m.GitCredentialOut,
                               _body(m.GitOAuthComplete, code=code, state=state))  # fmt: skip

    @op("me_secrets_list")
    def secrets(self) -> list[m.SecretOut]:
        """The caller's own secrets: names and dates, never values."""
        return self._http.items("/me/secrets", m.SecretOut)

    @op("me_secrets_put")
    def put_secret(self, key: str, value: str) -> m.SecretOut:
        return self._http.send("PUT", _p("me", "secrets", key), m.SecretOut, _body(m.SecretValue, value=value))

    @op("me_secrets_delete")
    def delete_secret(self, key: str) -> None:
        self._http.call("DELETE", _p("me", "secrets", key))


class SecretScopes(_Service):
    @op("secret_scopes_list")
    def list(self, slug: str) -> list[m.SecretScopeOut]:
        return self._http.items(_p("workspaces", slug, "secret-scopes"), m.SecretScopeOut)

    @op("secret_scopes_create")
    def create(self, slug: str, name: str, *, owner_group: str | None = None) -> m.SecretScopeOut:
        return self._http.send("POST", _p("workspaces", slug, "secret-scopes"), m.SecretScopeOut,
                               _body(m.SecretScopeCreate, name=name, owner_group=owner_group))  # fmt: skip

    @op("secret_scopes_delete")
    def delete(self, slug: str, scope: str, *, confirm: str) -> None:
        """Delete the scope and its secrets; ``confirm`` is its name again."""
        self._http.call("DELETE", _p("workspaces", slug, "secret-scopes", scope), params={"confirm": confirm})

    @op("secret_scopes_permissions_get")
    def permissions(self, slug: str, scope: str) -> m.SecretPermissionsOut:
        return self._http.get(_p("workspaces", slug, "secret-scopes", scope, "permissions"), m.SecretPermissionsOut)

    @op("secret_scopes_permissions_update")
    def update_permissions(self, slug: str, scope: str, *,
                           grants: Sequence[Mapping[str, Any] | m.SecretGrantIn] | None = None,
                           owner_group: str | None = None) -> m.SecretPermissionsOut:  # fmt: skip
        body = _body(m.SecretPermissionsUpdate, grants=list(grants) if grants is not None else None,
                     owner_group=owner_group)  # fmt: skip
        return self._http.send("PUT", _p("workspaces", slug, "secret-scopes", scope, "permissions"),
                               m.SecretPermissionsOut, body)  # fmt: skip

    @op("secret_scopes_explain")
    def explain(self, slug: str, scope: str, *, need: str | None = None) -> m.SecretExplainOut:
        return self._http.get(_p("workspaces", slug, "secret-scopes", scope, "explain"), m.SecretExplainOut, need=need)

    @op("secrets_list")
    def secrets(self, slug: str, scope: str) -> list[m.SecretOut]:
        """The scope's secrets: names and dates, never values."""
        return self._http.items(_p("workspaces", slug, "secret-scopes", scope, "secrets"), m.SecretOut)

    @op("secrets_put")
    def put_secret(self, slug: str, scope: str, key: str, value: str) -> m.SecretOut:
        return self._http.send("PUT", _p("workspaces", slug, "secret-scopes", scope, "secrets", key), m.SecretOut,
                               _body(m.SecretValue, value=value))  # fmt: skip

    @op("secrets_delete")
    def delete_secret(self, slug: str, scope: str, key: str) -> None:
        self._http.call("DELETE", _p("workspaces", slug, "secret-scopes", scope, "secrets", key))


# ── notifications, system and audit ──────────────────────────────────────────────────────────────────────────────


class Notifications(_Service):
    @op("notifications_get")
    def get(self, slug: str) -> m.NotificationsOut:
        """The workspace's destinations and what they are sent."""
        return self._http.get(_p("workspaces", slug, "notifications"), m.NotificationsOut)

    @op("notification_destinations_create")
    def create_destination(self, slug: str, destination: m.DestinationWrite | Mapping[str, Any]) -> m.DestinationOut:
        return self._http.send("POST", _p("workspaces", slug, "notifications", "destinations"), m.DestinationOut,
                               _body(m.DestinationWrite, destination))  # fmt: skip

    @op("notification_destinations_update")
    def update_destination(self, slug: str, destination_id: str,
                           destination: m.DestinationWrite | Mapping[str, Any]) -> m.DestinationOut:  # fmt: skip
        return self._http.send("PUT", _p("workspaces", slug, "notifications", "destinations", destination_id),
                               m.DestinationOut, _body(m.DestinationWrite, destination))  # fmt: skip

    @op("notification_destinations_delete")
    def delete_destination(self, slug: str, destination_id: str) -> None:
        self._http.call("DELETE", _p("workspaces", slug, "notifications", "destinations", destination_id))

    @op("notification_destinations_test")
    def test_destination(self, slug: str, destination_id: str, *, idempotency_key: str | None = None) -> m.TestOut:
        return self._http.send("POST", _p("workspaces", slug, "notifications", "destinations", destination_id, "test"),
                               m.TestOut, headers=_key(idempotency_key))  # fmt: skip

    @op("notification_deliveries_list")
    def deliveries(self, slug: str, *, job_run: str | None = None, status: str | None = None,
                   limit: int | None = None) -> list[m.DeliveryOut]:  # fmt: skip
        return self._http.items(_p("workspaces", slug, "notifications", "deliveries"), m.DeliveryOut,
                                job_run=job_run, status=status, limit=limit)  # fmt: skip

    @op("notification_deliveries_retry")
    def retry_delivery(self, slug: str, delivery_id: str) -> m.DeliveryOut:
        return self._http.send("POST", _p("workspaces", slug, "notifications", "deliveries", delivery_id, "retry"),
                               m.DeliveryOut)  # fmt: skip


class System(_Service):
    @op("system_get")
    def get(self, slug: str) -> m.SystemOut:
        """The workspace's running kernels, runs and limits."""
        return self._http.get(_p("workspaces", slug, "system"), m.SystemOut)

    @op("system_queries_get")
    def queries(self, slug: str, *, window: str | None = None, scope: str | None = None,
                status: str | None = None) -> m.QueryStatsOut:  # fmt: skip
        """Statement statistics over ``24h``, ``7d`` or ``30d``, for ``me`` or the ``workspace``."""
        return self._http.get(_p("workspaces", slug, "system", "queries"), m.QueryStatsOut, window=window, scope=scope,
                              status=status)  # fmt: skip

    @op("system_kernels_delete")
    def stop_kernel(self, slug: str, kernel_id: str) -> None:
        self._http.call("DELETE", _p("workspaces", slug, "system", "kernels", kernel_id))

    @op("system_limits_update")
    def set_limits(self, slug: str, *, kernels_per_person: int | None = None,
                   kernels_total: int | None = None) -> m.LimitsOut:  # fmt: skip
        return self._http.send("PUT", _p("workspaces", slug, "system", "limits"), m.LimitsOut,
                               _body(m.Limits, kernels_per_person=kernels_per_person,
                                     kernels_total=kernels_total))  # fmt: skip

    @op("system_session_pip_update")
    def set_session_pip(self, slug: str, enabled: bool) -> m.LimitsOut:
        return self._http.send("PUT", _p("workspaces", slug, "system", "session-pip"), m.LimitsOut,
                               _body(m.SessionPip, enabled=enabled))  # fmt: skip


class Audit(_Service):
    @op("audit_events_list")
    def events(self, *, workspace: str | None = None, actor: str | None = None, activity: str | None = None,
               outcome: str | None = None, start: str | None = None, end: str | None = None,
               limit: int | None = None) -> Iterator[m.EventOut]:  # fmt: skip
        """The service's audit events (``start`` and ``end``: ISO times; the window is bounded)."""
        return self._http.pages("/audit/events", m.EventOut.model_validate, limit=limit, workspace=workspace,
                                actor=actor, activity=activity, outcome=outcome,
                                **{"from": start, "to": end})  # fmt: skip

    @op("audit_events_export")
    def export(self, *, workspace: str | None = None, actor: str | None = None, activity: str | None = None,
               outcome: str | None = None, start: str | None = None, end: str | None = None) -> str:  # fmt: skip
        """The same events as CSV."""
        params = {"workspace": workspace, "actor": actor, "activity": activity, "outcome": outcome, "from": start,
                  "to": end}  # fmt: skip
        return self._http.call("GET", "/audit/events/export", params=params).text

    @op("audit_events_get")
    def event(self, event_id: str) -> m.EventDetail:
        return self._http.get(_p("audit", "events", event_id), m.EventDetail)

    @op("audit_alerts_list")
    def alerts(self, *, status: str | None = None, workspace: str | None = None) -> list[m.AlertOut]:
        return self._http.items("/audit/alerts", m.AlertOut, status=status, workspace=workspace)

    @op("audit_alerts_status_update")
    def set_alert_status(self, alert_id: str, status: str, version: int) -> m.AlertOut:
        """``acknowledged`` or ``resolved``; ``version`` is the one seen."""
        return self._http.send("PUT", _p("audit", "alerts", alert_id, "status"), m.AlertOut,
                               _body(m.AlertStatus, status=status, version=version))  # fmt: skip

    @op("audit_detections_run_now")
    def run_detections(self) -> m.DetectionRunOut:
        return self._http.send("POST", "/audit/detections/run-now", m.DetectionRunOut)

    @op("audit_digest_get")
    def digest(self, *, days: int | None = None) -> m.DigestOut:
        return self._http.get("/audit/digest", m.DigestOut, days=days)

    @op("audit_chain_get")
    def chain(self) -> m.VerificationOut:
        """The last verification of the audit's hash chain."""
        return self._http.get("/audit/chain", m.VerificationOut)

    @op("audit_chain_verify")
    def verify_chain(self) -> m.VerifyOut:
        return self._http.send("POST", "/audit/chain/verify", m.VerifyOut)


# ── administration ────────────────────────────────────────────────────────────────────────────────────────────────


class Templates(_Service):
    @op("project_templates_get")
    def list(self) -> m.TemplatesOut:
        """The project templates a new project may start from."""
        return self._http.get("/project-templates", m.TemplatesOut)

    @op("template_repos_list")
    def repos(self) -> list[m.TemplateRepoOut]:
        return self._http.items("/template-repos", m.TemplateRepoOut)

    @op("template_repos_create")
    def create_repo(self, slug: str, url: str, *, ref: str | None = None, commit: str | None = None,
                    enabled: bool | None = None) -> m.TemplateRepoOut:  # fmt: skip
        return self._http.send("POST", "/template-repos", m.TemplateRepoOut,
                               _body(m.TemplateRepoCreate, slug=slug, url=url, ref=ref, commit=commit,
                                     enabled=enabled))  # fmt: skip

    @op("template_repos_update")
    def update_repo(self, repo_id: str, *, url: str | None = None, ref: str | None = None, commit: str | None = None,
                    enabled: bool | None = None) -> m.TemplateRepoOut:  # fmt: skip
        return self._http.send("PUT", _p("template-repos", repo_id), m.TemplateRepoOut,
                               _body(m.TemplateRepoChange, url=url, ref=ref, commit=commit, enabled=enabled))  # fmt: skip

    @op("template_repos_delete")
    def delete_repo(self, repo_id: str) -> None:
        self._http.call("DELETE", _p("template-repos", repo_id))

    @op("template_repos_sync")
    def sync_repo(self, repo_id: str) -> m.TemplateRepoOut:
        return self._http.send("POST", _p("template-repos", repo_id, "sync"), m.TemplateRepoOut)


class Admin(_Service):
    """Platform operations (``data.admin``): stray grants, dead letters, data subjects and the secrets store."""

    @op("governance_strays_list")
    def strays(self) -> m.StraysOut:
        """Ranger policies and roles the service made that no longer belong to anything."""
        return self._http.get("/governance/strays", m.StraysOut)

    @op("governance_strays_remove")
    def remove_strays(self, ids: Sequence[int]) -> m.RemovedOut:
        return self._http.send("POST", "/governance/strays/remove", m.RemovedOut, _body(m.StraysRemove, ids=list(ids)))

    @op("dead_letters_list")
    def dead_letters(self, *, workspace: str | None = None, status: str | None = None,
                     limit: int | None = None) -> list[m.DeadLetterOut]:  # fmt: skip
        return self._http.items("/events/dead-letters", m.DeadLetterOut, workspace=workspace, status=status,
                                limit=limit)  # fmt: skip

    @op("dead_letters_retry")
    def retry_dead_letter(self, dead_letter_id: str) -> None:
        self._http.call("POST", _p("events", "dead-letters", dead_letter_id, "retry"))

    @op("subjects_export")
    def export_subject(self, subject: str) -> m.SubjectExportOut:
        """What the service holds about one person (a data subject's access request)."""
        return self._http.get(_p("subjects", subject, "export"), m.SubjectExportOut)

    @op("subjects_erase")
    def erase_subject(self, subject: str) -> m.SubjectEraseOut:
        return self._http.send("POST", _p("subjects", subject, "erase"), m.SubjectEraseOut)

    @op("secrets_store_rewrap")
    def rewrap_secrets(self) -> m.SecretRewrapOut:
        """Encrypt every stored secret's key again under the active key-encryption key."""
        return self._http.send("POST", "/secrets/rewrap", m.SecretRewrapOut)

    @op("secrets_store_short_values")
    def short_secrets(self) -> list[m.ShortSecretOut]:
        """Secrets too short to be redacted from logs safely (names only)."""
        return self._http.items("/secrets/short-values", m.ShortSecretOut)

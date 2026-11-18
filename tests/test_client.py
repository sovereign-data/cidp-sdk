"""AC-5 (OpenSpec change data-api-sdk): the object tree, the session and the errors map to v1.

Against a fake v1 transport answering recorded shapes: each call is the documented operation (method and path from
``openapi-v1.json``), listings follow ``next_cursor``, a session submits, waits and pages its statement (JSON and
Arrow), and 404, 403, 409 and 429 come back as typed errors with the code, the status and the request id sent. The
generated models match the committed contract.
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
from pathlib import Path

import httpx
import pyarrow as pa
import pytest

from cidp_sdk import CIDPClient, Conflict, NotFound, PermissionDenied, StatementFailed, TooManyRequests

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "contract" / "openapi-v1.json").read_text())
HOST = "https://portal.example.org"
TOKEN = "eyJ.fixed-token.sig"


def operation(method: str, path: str) -> str:
    """The operationId the contract documents for this request."""
    for template, ops in CONTRACT["paths"].items():
        pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$"
        if re.match(pattern, path) and method.lower() in ops:
            return ops[method.lower()]["operationId"]
    raise AssertionError(f"{method} {path} is not in openapi-v1.json")


def arrow(rows: list[tuple[int, str]]) -> bytes:
    table = pa.table({"n": [r[0] for r in rows], "s": [r[1] for r in rows]})
    sink = io.BytesIO()
    with pa.ipc.new_stream(sink, table.schema) as w:
        w.write_table(table)
    return sink.getvalue()


def error(status: int, code: str, **headers: str) -> httpx.Response:
    return httpx.Response(status, json={"code": code, "message": f"{code} happened", "details": {}}, headers=headers)


class V1:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.request_ids: list[str] = []
        self.polls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path, q = request.url.path, dict(request.url.params)
        op = operation(request.method, path)
        self.calls.append((op, q))
        self.request_ids.append(request.headers["x-request-id"])
        if op != "config_get":
            assert request.headers["authorization"] == f"Bearer {TOKEN}"
        base = "/api/data/v1/workspaces/sales"
        stmt = {"id": "st1", "engine": "sqe", "catalog": "sales", "schema": "tpch",
                "submitted_at": "2026-10-24T10:00:00Z"}  # fmt: skip
        match op:
            case "config_get":
                return httpx.Response(200, json={
                    "api_version": "1", "service_version": "0.2.0", "issuer": "https://sso.example.org/realms/portal",
                    "client_id": "portal-data-cli", "audience": "portal-data", "polaris_uri": None,
                    "polaris_realm": "portal", "object_store_uri": None, "object_store_path_style": True,
                    "capabilities": ["statements"], "added_later": True,
                })  # fmt: skip
            case "workspaces_get" if path.endswith("/nope"):
                return error(404, "not_found")
            case "workspaces_get":
                return httpx.Response(200, json={
                    "slug": "sales", "display_name": "Sales", "home_catalog": "sales", "default_schema": "default",
                    "status": "ready", "viewer_groups": ["SG-A"], "admin_group": "SG-E", "allowed_actions": ["view"],
                    "external_id": None,
                })  # fmt: skip
            case "tables_get":
                assert path == f"{base}/catalogs/sales/schemas/tpch/tables/region"
                return httpx.Response(200, json={
                    "name": "region", "catalog_name": "sales", "schema_name": "tpch", "full_name": "sales.tpch.region",
                    "table_type": "ICEBERG", "storage_location": "s3://w/region", "format_version": 2,
                    "columns": [
                        {"name": "r_name", "type_text": "string", "nullable": True, "classification": "internal"}
                    ],
                    "partition_fields": [],
                    "current_snapshot_id": 7, "classification": "internal",
                })  # fmt: skip
            case "tables_list":
                item = {"catalog_name": "sales", "schema_name": "tpch"}
                if "cursor" not in q:
                    assert q == {"limit": "2"}
                    names, cursor = ["nation", "region"], "page-2"
                else:
                    assert q == {"limit": "2", "cursor": "page-2"}
                    names, cursor = ["supplier"], None
                items = [{**item, "name": n, "full_name": f"sales.tpch.{n}"} for n in names]
                return httpx.Response(200, json={"items": items, "next_cursor": cursor})
            case "statements_submit":
                body = json.loads(request.content)
                assert body == {"sql": "select n, s from t", "engine": "sqe", "schema": "tpch", "wait_timeout": 0,
                                "on_wait_timeout": "CONTINUE", "query_tag": "ac5"}  # fmt: skip
                return httpx.Response(200, json={**stmt, "state": "PENDING", "query_tag": "ac5"})
            case "statements_get":
                self.polls += 1
                if self.polls == 1:
                    return httpx.Response(200, json={**stmt, "state": "RUNNING"})
                manifest = {"columns": [{"name": "n", "type": "bigint"}, {"name": "s", "type": "varchar"}],
                            "row_count": 3, "page_count": 2, "byte_count": 30, "truncated": False}  # fmt: skip
                first = {"row_offset": 0, "row_count": 2, "rows": [[1, "a"], [2, "b"]], "next_cursor": "r2"}
                return httpx.Response(200, json={**stmt, "state": "SUCCEEDED", "manifest": manifest, "result": first})
            case "statements_result" if request.headers.get("accept") == "application/vnd.apache.arrow.stream":
                if "cursor" not in q:
                    return httpx.Response(200, content=arrow([(1, "a"), (2, "b")]), headers={"X-Next-Cursor": "r2"})
                return httpx.Response(200, content=arrow([(3, "c")]))
            case "statements_result":
                assert q == {"cursor": "r2"}
                return httpx.Response(200, json={"row_offset": 2, "row_count": 1, "rows": [[3, "c"]]})
            case "catalogs_list":
                return error(403, "permission_denied")
            case "schemas_create":
                return error(409, "conflict")
            case "jobs_run_now":
                return error(429, "too_many_requests", **{"Retry-After": "7"})
        raise AssertionError(op)


def test_ac5_the_object_tree_the_session_and_the_errors_map_to_v1():
    v1 = V1()
    client = CIDPClient(host=HOST, token=TOKEN, env={}, transport=httpx.MockTransport(v1))
    assert client.config.capabilities == ["statements"] and client.config.model_extra == {"added_later": True}

    # the object tree: lazy handles, one call when fetched; the home catalog resolves through the workspace
    ws = client.workspace("sales")
    assert v1.calls == [("config_get", {})]
    table = ws.catalog("sales").schema("tpch").table("region").fetch()
    assert (table.full_name, table.columns[0].name) == ("sales.tpch.region", "r_name")
    assert ws.catalog().name == "sales" and v1.calls[-1][0] == "workspaces_get"
    # a listing follows next_cursor; limit is the page size
    names = [t.name for t in client.tables.list("sales", "sales", "tpch", limit=2)]
    assert names == ["nation", "region", "supplier"]
    assert [c for c in v1.calls if c[0] == "tables_list"] == [
        ("tables_list", {"limit": "2"}), ("tables_list", {"limit": "2", "cursor": "page-2"})
    ]  # fmt: skip

    # the session: submit, wait (long poll), then the pages, as JSON rows and as Arrow
    v1.calls.clear()
    session = ws.session(schema="tpch", query_tag="ac5")
    result = session.sql("select n, s from t", wait_timeout=0)
    assert result.state == "PENDING"
    assert result.collect() == [{"n": 1, "s": "a"}, {"n": 2, "s": "b"}, {"n": 3, "s": "c"}]
    assert [op for op, _ in v1.calls] == ["statements_submit", "statements_get", "statements_get", "statements_result"]
    assert v1.calls[1][1] == {"wait_timeout": "30"}
    table = result.to_arrow()
    assert table.to_pylist() == [{"n": 1, "s": "a"}, {"n": 2, "s": "b"}, {"n": 3, "s": "c"}]
    assert [op for op, _ in v1.calls[-2:]] == ["statements_result", "statements_result"]

    # a statement that failed raises with its own code
    failed = type(result)(client.statements, "sales", result.info.model_copy(update={"state": "FAILED"}))
    with pytest.raises(StatementFailed) as e:
        failed.wait()
    assert e.value.code == "failed"

    # typed errors with the service's code, the status and the request id this call sent
    for call, cls, status, code in [
        (lambda: client.workspaces.get("nope"), NotFound, 404, "not_found"),
        (lambda: list(client.catalogs.list()), PermissionDenied, 403, "permission_denied"),
        (lambda: ws.catalog("sales").schemas.create("tpch"), Conflict, 409, "conflict"),
        (lambda: ws.project("etl").job("nightly").run_now(day="mon"), TooManyRequests, 429, "too_many_requests"),
    ]:
        with pytest.raises(cls) as e:
            call()
        assert (e.value.status, e.value.code, e.value.request_id) == (status, code, v1.request_ids[-1])
        assert e.value.message == f"{code} happened" and TOKEN not in repr(e.value)
    assert e.value.retry_after == 7.0
    client.close()


def test_ac5_generated_models_are_current():
    spec = importlib.util.spec_from_file_location("sdk_models", ROOT / "scripts" / "sdk_models.py")
    assert spec and spec.loader
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    target = ROOT / "src" / "cidp_sdk" / "_models.py"
    assert target.read_text() == gen.render((ROOT / "contract" / "openapi-v1.json").read_text()), "run make sdk-models"


def test_ac5_catalogs_are_created_and_dropped_as_in_a_metastore():
    """data-catalogs-metastore: the SDK's create and delete are the documented v1 operations with the right bodies."""
    seen: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/config"):
            return V1()(request)
        body = json.loads(request.content) if request.content else {}
        seen.append((operation(request.method, request.url.path), body))
        if request.method == "DELETE":
            return httpx.Response(204)
        if "/workspaces/" in request.url.path:
            return httpx.Response(201, json={"name": body["name"], "home": False, "binding": "read_write",
                                             "isolation": "isolated"})  # fmt: skip
        return httpx.Response(201, json={"name": body["name"], "isolation": body["isolation"], "bindings": []})

    client = CIDPClient(host=HOST, token=TOKEN, env={}, transport=httpx.MockTransport(handler))
    client.catalogs.create("pg3_gold", "SG-Eng", isolation="isolated", bindings={"dbx_main": "read_only"})
    client.workspaces.create_catalog("dbx_main", "pg3_silver", storage_location="finance_bucket")
    client.catalogs.delete("pg3_gold")
    assert seen == [
        ("catalogs_create", {"name": "pg3_gold", "owner_group": "SG-Eng", "isolation": "isolated",
                             "bindings": [{"workspace": "dbx_main", "binding": "read_only"}]}),
        ("workspaces_catalogs_create", {"name": "pg3_silver", "storage_location": "finance_bucket"}),
        ("catalogs_delete", {}),
    ]  # fmt: skip
    client.close()

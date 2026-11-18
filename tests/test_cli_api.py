"""OpenSpec change data-cli-coverage CC1 (scenarios CC-1, CC-2): ``cidp api list|describe|call`` against a fake v1.

``api call`` reaches every public operation through the SDK's session: path parameters filled and quoted (the
workspace from the connection), a missing or unknown one refused with exit 3, a JSON body from the option, a file
or stdin, a raw file streamed for the two upload operations, a DELETE only with --yes or a "yes" at a terminal, the
preview warning on stderr once, and the service's errors as ``code: message`` with their class's exit code. The
deployment is an ``httpx.MockTransport`` that records every request.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from rich.console import Console
from typer.testing import CliRunner

from cidp_sdk import CIDPClient, cli, services
from cidp_sdk._operations import OPERATIONS

HOST = "https://portal.example.org"
V1 = "/api/data/v1"
TOKEN = "eyJ.cli-api-token.sig"  # gitleaks:allow - a test stand-in
CONFIG = {"api_version": "1", "service_version": "0.2.0", "issuer": "https://sso.example.org/realms/portal",
          "client_id": "portal-data-cli", "audience": "portal-data", "polaris_uri": None, "polaris_realm": "portal",
          "object_store_uri": None, "object_store_path_style": True, "capabilities": ["statements"]}  # fmt: skip
OPENAPI = Path(__file__).resolve().parents[1] / "contract" / "openapi-v1.json"


class Recorder:
    """Answers ``answers[(method, path)]`` (default: 200 ``{"ok": true}``) and records each request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.seen: list[httpx.Request] = []
        self.bodies: list[bytes] = []
        self.answers: dict[tuple[str, str], httpx.Response] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        if request.url.path == f"{V1}/config":  # the client reads it on connect
            return httpx.Response(200, json=CONFIG)
        self.requests.append(request)
        self.bodies.append(request.read())
        key = (request.method, request.url.path.removeprefix(V1))
        return self.answers.get(key) or httpx.Response(200, json={"ok": True})

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]


@pytest.fixture
def server(monkeypatch) -> Recorder:
    rec = Recorder()
    transport = httpx.MockTransport(rec)
    env = {"CIDP_TOKEN": TOKEN, "CIDP_WORKSPACE": "sales", "CIDP_CONFIG_FILE": "/nonexistent"}

    def make_client(state: cli.State) -> CIDPClient:
        return CIDPClient(state.profile, host=state.host or HOST, workspace=state.workspace, env=env,
                            transport=transport)  # fmt: skip

    monkeypatch.setattr(cli, "make_client", make_client)
    monkeypatch.setattr(cli, "_interactive", lambda: False)
    monkeypatch.setattr(services, "_warned", set())
    return rec


def cidp(*args: str, input: str | bytes | None = None):  # noqa: A002 - click's name
    return CliRunner().invoke(cli.app, list(args), input=input)


def test_cc1_list_and_describe_come_from_operations(server):
    r = cidp("-o", "json", "api", "list")
    assert r.exit_code == 0, r.output
    listed = json.loads(r.stdout)
    assert {row["operation_id"] for row in listed} == set(OPERATIONS)
    r = cidp("-o", "json", "api", "list", "--service", "sql", "--level", "stable")
    rows = json.loads(r.stdout)
    assert rows and all(row["service"] == "sql" and row["level"] == "stable" for row in rows)

    r = cidp("-o", "json", "api", "describe", "statements_get")
    assert r.exit_code == 0, r.output
    described = json.loads(r.stdout)[0]
    assert described["path_parameters"] == ["workspace", "statement_id"]
    assert described["sdk"] == "Statements.get"
    r = cidp("-o", "json", "api", "describe", "audit_ingest")
    assert "not_in_sdk" in json.loads(r.stdout)[0]
    r = cidp("api", "describe", "no_such_operation")
    assert r.exit_code == 3
    assert "unknown_operation" in r.stderr
    assert not server.requests


def test_cc1_a_narrow_table_cuts_no_name(server, monkeypatch):
    """At 80 columns (a pipe, a small terminal) each operationId stays whole on one line and no cell ends in "…";
    longer cells fold onto more lines."""
    monkeypatch.setattr(cli, "out", Console(highlight=False, soft_wrap=True, width=80))
    r = cidp("api", "list")
    assert r.exit_code == 0, r.output
    assert "…" not in r.stdout
    lines = r.stdout.splitlines()
    assert all(len(line) <= 80 for line in lines)
    for op in OPERATIONS:
        assert any(f"│ {op} " in line for line in lines), op


def test_cc1_call_fills_and_quotes_path_parameters(server):
    r = cidp("api", "call", "tables_get", "-p", "catalog=sales", "-p", "schema=tp ch", "-p", "table=a/b",
               "-q", "include=columns", "-q", "include=stats")  # fmt: skip
    assert r.exit_code == 0, r.output
    req = server.last
    assert req.method == "GET"
    assert req.url.raw_path.decode().startswith(f"{V1}/workspaces/sales/catalogs/sales/schemas/tp%20ch/tables/a%2Fb")
    assert req.url.params.get_list("include") == ["columns", "stats"]
    assert req.headers["authorization"] == f"Bearer {TOKEN}"
    assert json.loads(r.stdout) == {"ok": True}
    assert TOKEN not in r.output

    # the workspace given explicitly wins over the connection's
    cidp("api", "call", "workspaces_get", "-p", "workspace=hr")
    assert server.last.url.path == f"{V1}/workspaces/hr"


def test_cc1_missing_or_unknown_parameter_is_exit_3(server):
    r = cidp("api", "call", "tables_get", "-p", "catalog=sales", "-p", "schema=tpch")
    assert r.exit_code == 3
    assert "missing_parameter" in r.stderr and "table" in r.stderr
    r = cidp("api", "call", "workspaces_get", "-p", "nope=1")
    assert r.exit_code == 3
    assert "unknown_parameter" in r.stderr
    r = cidp("api", "call", "workspaces_get", "-p", "novalue")
    assert r.exit_code == 2
    assert not server.requests


def test_cc1_body_from_option_file_and_stdin(server, tmp_path):
    body = {"name": "nightly", "sql": "select 1"}
    cidp("api", "call", "saved_queries_create", "--body", json.dumps(body), "--idempotency-key", "k1")
    assert json.loads(server.bodies[-1]) == body
    assert server.last.headers["idempotency-key"] == "k1"

    f = tmp_path / "body.json"
    f.write_text(json.dumps(body))
    cidp("api", "call", "saved_queries_create", "--body", f"@{f}")
    assert json.loads(server.bodies[-1]) == body

    r = cidp("api", "call", "saved_queries_update", "-p", "saved_query_id=q1", "--body", "-", "--if-match",
               '"e1"', input=json.dumps(body))  # fmt: skip
    assert r.exit_code == 0, r.output
    assert json.loads(server.bodies[-1]) == body
    assert server.last.headers["if-match"] == '"e1"'

    n = len(server.requests)
    r = cidp("api", "call", "saved_queries_create", "--body", "{not json")
    assert r.exit_code == 2
    assert len(server.requests) == n


def test_cc1_raw_body_is_streamed_from_the_file(server, tmp_path):
    f = tmp_path / "data.csv"
    f.write_bytes(b"a,b\n1,2\n")
    server.answers[("POST", "/workspaces/sales/uploads")] = httpx.Response(201, json={"upload_id": "u1"})
    r = cidp("api", "call", "ingest_uploads_create", "-q", "format=csv", "--body", f"@{f}")
    assert r.exit_code == 0, r.output
    assert server.bodies[-1] == b"a,b\n1,2\n"
    assert server.last.headers["content-type"] == "application/octet-stream"
    assert server.last.headers["content-length"] == "8"


def test_cc2_delete_needs_yes_or_a_terminal(server, monkeypatch):
    server.answers[("DELETE", "/workspaces/sales/saved-queries/q1")] = httpx.Response(204)
    r = cidp("api", "call", "saved_queries_delete", "-p", "saved_query_id=q1")
    assert r.exit_code == 2
    assert "--yes" in r.stderr
    assert not server.requests

    monkeypatch.setattr(cli, "_interactive", lambda: True)
    r = cidp("api", "call", "saved_queries_delete", "-p", "saved_query_id=q1", input="n\n")
    assert r.exit_code == 1
    assert not server.requests
    r = cidp("api", "call", "saved_queries_delete", "-p", "saved_query_id=q1", input="y\n")
    assert r.exit_code == 0, r.output
    assert server.last.method == "DELETE"

    r = cidp("api", "call", "saved_queries_delete", "-p", "saved_query_id=q1", "--yes")
    assert r.exit_code == 0
    assert r.stdout == ""  # 204: nothing printed


def test_cc1_preview_operation_warns_on_stderr_once(server):
    preview = next(k for k, v in OPERATIONS.items() if v[2] == "preview" and v[0] == "GET")
    params = [a for name in cli._PARAM.findall(OPERATIONS[preview][1]) if name != "workspace"
              for a in ("-p", f"{name}=x")]  # fmt: skip
    r = cidp("api", "call", preview, *params)
    assert r.exit_code == 0, r.output
    assert f"warning: {preview} is a preview operation" in r.stderr
    assert "warning" not in r.stdout
    stable = next(k for k, v in OPERATIONS.items() if v[2] == "stable" and v[0] == "GET" and "{" not in v[1])
    r = cidp("api", "call", stable)
    assert "warning" not in r.stderr


@pytest.mark.parametrize(("status", "code", "exit_code"),
                         [(400, "invalid", 1), (401, "unauthenticated", 4), (403, "forbidden", 5),
                          (404, "not_found", 6), (409, "conflict", 7), (429, "rate_limited", 8)])  # fmt: skip
def test_cc1_errors_exit_with_their_class_code(server, status, code, exit_code):
    server.answers[("GET", "/workspaces/sales")] = httpx.Response(
        status, json={"code": code, "message": f"{code} says <b>no</b>", "details": {}},
        headers={"x-request-id": "req-9"})  # fmt: skip
    r = cidp("api", "call", "workspaces_get")
    assert r.exit_code == exit_code
    assert f"{code}: {code} says <b>no</b>" in r.stderr
    assert "req-9" in r.stderr


def test_cc1_non_json_answer_is_written_as_bytes(server, tmp_path):
    server.answers[("GET", "/workspaces/sales/statements/s1/result")] = httpx.Response(
        200, content=b"x\n1\n", headers={"content-type": "text/csv"})  # fmt: skip
    r = cidp("api", "call", "statements_result", "-p", "statement_id=s1", "--accept", "text/csv")
    assert r.exit_code == 0, r.output
    assert server.last.headers["accept"] == "text/csv"
    assert r.stdout_bytes == b"x\n1\n"
    to = tmp_path / "out.csv"
    cidp("api", "call", "statements_result", "-p", "statement_id=s1", "--out", str(to))
    assert to.read_bytes() == b"x\n1\n"


def test_cc1_jsonl_prints_a_listing_item_per_line(server):
    server.answers[("GET", "/workspaces")] = httpx.Response(200, json={"items": [{"slug": "a"}, {"slug": "b"}]})
    r = cidp("-o", "jsonl", "api", "call", "workspaces_list")
    assert [json.loads(line) for line in r.stdout.splitlines()] == [{"slug": "a"}, {"slug": "b"}]


def test_cc1_stream_operations_point_to_the_curated_command(server):
    r = cidp("api", "call", "projects_runs_logs", "-p", "project=etl", "-p", "run_id=r1")
    assert r.exit_code == 3
    assert "cidp runs logs" in r.stderr
    assert not server.requests


@pytest.mark.parametrize("operation_id", sorted(OPERATIONS))
def test_cc1_every_operation_is_reachable(server, operation_id):
    """Each public operation: its method and its path with every parameter filled, as the contract names it."""
    method, template, _, _ = OPERATIONS[operation_id]
    args = [a for name in cli._PARAM.findall(template) for a in ("-p", f"{name}=v-{name}")]
    if method in ("POST", "PUT", "PATCH"):
        args += ["--body", "@/dev/null" if operation_id in cli.RAW_BODIES else "{}"]
    r = cidp("api", "call", operation_id, *args, "--yes")
    if operation_id in cli.STREAMS:
        assert r.exit_code == 3
        return
    assert r.exit_code == 0, r.output
    expected = template
    for name in cli._PARAM.findall(template):
        expected = expected.replace("{" + name + "}", f"v-{name}")
    assert (server.seen[-1].method, server.seen[-1].url.path) == (method, V1 + expected)


def test_cc1_streams_and_raw_bodies_match_the_contract():
    spec = json.loads(OPENAPI.read_text())
    streams, raw = set(), set()
    for item in spec["paths"].values():
        for op in item.values():
            if not isinstance(op, dict) or op.get("operationId") not in OPERATIONS:
                continue
            ok = op.get("responses", {}).get("200", {}).get("content", {})
            if "text/event-stream" in ok:
                streams.add(op["operationId"])
            if "application/octet-stream" in op.get("requestBody", {}).get("content", {}):
                raw.add(op["operationId"])
    assert streams == set(cli.STREAMS)
    assert raw == set(cli.RAW_BODIES)

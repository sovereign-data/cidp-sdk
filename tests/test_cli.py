"""OpenSpec change data-cli: the ``cidp`` command on a fake v1 deployment.

CLI-1: each command makes its v1 call and prints a table, json, jsonl or csv; listings follow ``next_cursor``; ``sql``
pages a statement and Ctrl-C cancels it; ``jobs run --wait`` follows the run; errors print ``code: message`` and
exit with their class's code. CLI-2: a token is never an option or printed, a browser login keeps its refresh token
in the keyring only and ``logout`` forgets it, people's text is printed without markup, and tracebacks never show
locals. The deployment and its issuer are an ``httpx.MockTransport``; the browser is a thread that follows the
redirect to the loopback callback, as in AC-4.
"""

from __future__ import annotations

import csv
import io
import json
import threading
import urllib.request
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from typer.testing import CliRunner

from cidp_sdk import CIDPClient, cli

HOST = "https://portal.example.org"
ISSUER = "https://sso.example.org/realms/portal"
TOKEN = "eyJ.cli-person-token.sig"
ACCESS = "eyJ.cli-browser-access.sig"
REFRESH = "cli-refresh-token-value"
V1 = "/api/data/v1"
NOW = "2026-10-25T10:00:00Z"
MARKUP = "[red]not markup[/red]"

WORKSPACE = {"slug": "sales", "display_name": "Sales", "home_catalog": "sales", "default_schema": "default",
             "status": "active", "viewer_groups": ["analysts"], "admin_group": "sales-admins",
             "allowed_actions": ["data.view"], "external_id": "dbx-123"}  # fmt: skip
TABLE = {"name": "region", "catalog_name": "sales", "schema_name": "tpch", "full_name": "sales.tpch.region",
         "table_type": "TABLE", "storage_location": None, "format_version": 2, "partition_fields": [],
         "current_snapshot_id": 7, "classification": "internal",
         "columns": [{"name": "r_name", "type_text": "string", "nullable": True, "comment": MARKUP,
                      "classification": "internal"}]}  # fmt: skip


def page(items: list[Any], cursor: str | None = None) -> httpx.Response:
    return httpx.Response(200, json={"items": items, "next_cursor": cursor})


def error(status: int, code: str, message: str) -> httpx.Response:
    return httpx.Response(status, json={"code": code, "message": message, "details": {}},
                          headers={"x-request-id": "req-1"})  # fmt: skip


def statement(sid: str, state: str, **extra: Any) -> dict[str, Any]:
    return {"id": sid, "state": state, "engine": "sqe", "catalog": "sales", "schema": None, "submitted_at": NOW,
            **extra}  # fmt: skip


def run(status: str) -> dict[str, Any]:
    return {"run_id": "r1", "number": 3, "trigger": "manual", "status": status, "commit_sha": "abc", "run_as": "owner",
            "started_by": "robin", "job_parameters": {"day": "2026-10-24"}, "error": None, "created_at": NOW,
            "started_at": NOW, "finished_at": None if status != "succeeded" else NOW, "tasks": None}  # fmt: skip


class Deployment:
    """``/v1/config``, the issuer, and the v1 calls the commands make; it records what it was asked."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []
        self.bodies: list[Any] = []
        self.authorization: set[str] = set()
        self.grants: list[str] = []
        self.polls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:  # noqa: C901, PLR0911, PLR0912 - one fake server
        path, q = request.url.path, dict(request.url.params)
        if path == f"{V1}/config":
            return httpx.Response(200, json={
                "api_version": "1", "service_version": "0.2.0", "issuer": ISSUER, "client_id": "portal-data-cli",
                "audience": "portal-data", "polaris_uri": None, "polaris_realm": "portal", "object_store_uri": None,
                "object_store_path_style": True, "capabilities": ["statements"],
            })  # fmt: skip
        if path == "/realms/portal/.well-known/openid-configuration":
            return httpx.Response(200, json={
                "issuer": ISSUER, "token_endpoint": f"{ISSUER}/protocol/openid-connect/token",
                "authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth",
            })  # fmt: skip
        if path == "/realms/portal/protocol/openid-connect/token":
            form = parse_qs(request.content.decode())
            self.grants.append(form["grant_type"][0])
            return httpx.Response(200, json={"access_token": ACCESS, "refresh_token": REFRESH, "expires_in": 300})
        self.authorization.add(request.headers.get("authorization", ""))
        self.calls.append((request.method, path.removeprefix(V1), q))
        if request.content:
            self.bodies.append(json.loads(request.content))
        ws = f"{V1}/workspaces"
        match (request.method, path.removeprefix(ws)):
            case ("GET", ""):
                if q.get("cursor") == "c2":
                    return page([{**WORKSPACE, "slug": "hr", "display_name": "HR", "external_id": None}])
                return page([WORKSPACE], "c2")
            case ("GET", "/sales"):
                return httpx.Response(200, json=WORKSPACE)
            case ("GET", "/nope"):
                return error(404, "not_found", "Workspace nope not found")
            case ("GET", "/secret"):
                return error(403, "forbidden", "You may not see workspace secret")
            case ("GET", "/expired"):
                return error(401, "unauthenticated", "Sign in again")
            case ("GET", "/sales/catalogs"):
                return page([{"name": "sales", "home": True, "binding": "read_write", "isolation": "isolated",
                              "comment": None}])  # fmt: skip
            case ("GET", "/sales/catalogs/sales/schemas"):
                return page([{"name": "tpch", "catalog_name": "sales", "full_name": "sales.tpch"}])
            case ("GET", "/sales/catalogs/shared/schemas/tpch/tables"):
                return page([{"name": "region", "catalog_name": "shared", "schema_name": "tpch",
                              "full_name": "shared.tpch.region"}])  # fmt: skip
            case ("GET", "/sales/catalogs/sales/schemas/tpch/tables/region"):
                return httpx.Response(200, json=TABLE)
            case ("POST", "/sales/statements"):
                sid = {"select 1": "s1", "select broken": "s2", "select slow": "s3"}[self.bodies[-1]["sql"]]
                return httpx.Response(200, json=statement(sid, "RUNNING"))
            case ("GET", "/sales/statements/s1"):
                manifest = {"columns": [{"name": "x", "type": "bigint"}, {"name": "note", "type": "varchar"}],
                            "row_count": 2, "page_count": 2, "byte_count": 40, "truncated": True}  # fmt: skip
                first = {"row_offset": 0, "row_count": 1, "rows": [[1, MARKUP]], "next_cursor": "p2"}
                return httpx.Response(200, json=statement("s1", "SUCCEEDED", manifest=manifest, result=first))
            case ("GET", "/sales/statements/s1/result"):
                assert q.get("cursor") == "p2"
                return httpx.Response(200, json={"row_offset": 1, "row_count": 1, "rows": [[2, "b,c"]]})
            case ("GET", "/sales/statements/s2"):
                failure = {"code": "failed", "message": "Table broken not found"}
                return httpx.Response(200, json=statement("s2", "FAILED", error=failure))
            case ("GET", "/sales/statements/s3"):
                raise KeyboardInterrupt  # the person presses Ctrl-C while the CLI waits
            case ("POST", "/sales/statements/s3/cancel"):
                return httpx.Response(200, json=statement("s3", "CANCELED"))
            case ("GET", "/sales/projects/etl/jobs"):
                return page([{"name": "nightly", "description": None, "run_as": "owner", "owner": "robin",
                              "deployed": True, "enabled": True, "disabled_reason": None, "schedule": "0 2 * * *",
                              "timezone": "UTC", "triggers": [], "tasks": 2, "next_fire_at": NOW,
                              "last_run": None}])  # fmt: skip
            case ("POST", "/sales/projects/etl/jobs/nightly/run-now"):
                return httpx.Response(200, json=run("queued"))
            case ("GET", "/sales/projects/etl/jobs/nightly/runs/r1"):
                self.polls += 1
                return httpx.Response(200, json=run("running" if self.polls == 1 else "succeeded"))
            case ("GET", "/sales/projects/etl/jobs/nightly/runs"):
                return page([run("succeeded"), run("failed")], "more")
        return error(404, "not_found", "Not found")


@pytest.fixture
def deployment(monkeypatch) -> Deployment:
    d = Deployment()
    transport = httpx.MockTransport(d)
    env = {"CIDP_TOKEN": TOKEN, "CIDP_WORKSPACE": "sales", "CIDP_CONFIG_FILE": "/nonexistent"}

    def make_client(state: cli.State) -> CIDPClient:
        return CIDPClient(state.profile, host=state.host or HOST, workspace=state.workspace, env=env,
                            transport=transport, opener=cli._open_browser)  # fmt: skip

    monkeypatch.setattr(cli, "make_client", make_client)
    monkeypatch.setattr(cli, "TABLE_ROWS", 1000)
    return d


def cidp(*args: str, input: str | None = None):  # noqa: A002 - click's name
    return CliRunner().invoke(cli.app, list(args), input=input)


def test_cli1_commands_call_v1_and_print_each_format(deployment):
    # workspaces: both pages, as json, jsonl, csv and a table
    r = cidp("-o", "json", "workspaces", "list")
    assert r.exit_code == 0, r.output
    assert [w["slug"] for w in json.loads(r.stdout)] == ["sales", "hr"]
    r = cidp("-o", "jsonl", "workspaces", "list", "--external-id", "dbx-123")
    assert [json.loads(line)["slug"] for line in r.stdout.splitlines()] == ["sales", "hr"]
    assert deployment.calls[-2][2]["external_id"] == "dbx-123"
    r = cidp("-o", "csv", "workspaces", "list")
    assert list(csv.reader(io.StringIO(r.stdout)))[:2] == [
        ["slug", "display_name", "home_catalog", "status", "external_id"],
        ["sales", "Sales", "sales", "active", "dbx-123"],
    ]
    r = cidp("workspaces", "get")  # the connection's workspace (CIDP_WORKSPACE)
    assert r.exit_code == 0 and "sales-admins" in r.stdout

    # catalogs, schemas in the home catalog, tables in another one, a table's columns
    assert "isolated" in cidp("catalogs", "list").stdout
    assert json.loads(cidp("-o", "json", "schemas", "list").stdout)[0]["full_name"] == "sales.tpch"
    r = cidp("-o", "json", "tables", "list", "tpch", "--catalog", "shared")
    assert json.loads(r.stdout)[0]["full_name"] == "shared.tpch.region"
    r = cidp("tables", "get", "tpch.region")
    assert r.exit_code == 0 and "r_name" in r.stdout and "string" in r.stdout
    assert json.loads(cidp("-o", "json", "tables", "get", "tpch.region").stdout)[0]["current_snapshot_id"] == 7
    assert cidp("tables", "get", "region").exit_code == 2  # schema.table, a usage error

    # sql: submitted as the caller, waited for, both pages, the cut announced on stderr
    r = cidp("-o", "csv", "sql", "select 1", "--limit", "10")
    assert r.exit_code == 0, r.output
    assert list(csv.reader(io.StringIO(r.stdout))) == [["x", "note"], ["1", MARKUP], ["2", "b,c"]]
    assert deployment.bodies[-1] == {"sql": "select 1", "engine": "sqe", "wait_timeout": 10,
                                     "on_wait_timeout": "CONTINUE", "row_limit": 10}  # fmt: skip
    assert "cut at 2 rows" in r.stderr
    r = cidp("-o", "jsonl", "sql", "-", input="select 1")
    assert [json.loads(line) for line in r.stdout.splitlines()] == [{"x": 1, "note": MARKUP}, {"x": 2, "note": "b,c"}]
    r = cidp("sql", "select broken")
    assert r.exit_code == 9 and "failed: Table broken not found" in r.stderr
    r = cidp("sql", "select slow")
    assert r.exit_code == 130 and "Cancelled statement s3" in r.stderr
    assert ("POST", "/workspaces/sales/statements/s3/cancel", {}) in deployment.calls

    # jobs: list, run with parameters and wait, runs (only as many as asked)
    assert "0 2 * * *" in cidp("jobs", "list", "etl").stdout
    r = cidp("-o", "json", "jobs", "run", "etl", "nightly", "-P", "day=2026-10-24", "--wait", "--poll", "0")
    assert r.exit_code == 0, r.output
    assert json.loads(r.stdout)[0]["status"] == "succeeded" and deployment.polls == 2
    assert {"job_parameters": {"day": "2026-10-24"}} in deployment.bodies
    assert cidp("jobs", "run", "etl", "nightly", "-P", "nokey").exit_code == 2
    r = cidp("-o", "jsonl", "jobs", "runs", "etl", "nightly", "--limit", "1")
    assert len(r.stdout.splitlines()) == 1

    # errors: code and message on stderr, an exit code per class, nothing on stdout
    for args, code, text in ((["workspaces", "get", "nope"], 6, "not_found: Workspace nope not found"),
                             (["workspaces", "get", "secret"], 5, "forbidden: You may not see"),
                             (["workspaces", "get", "expired"], 4, "unauthenticated: Sign in again")):  # fmt: skip
        r = cidp(*args)
        assert (r.exit_code, r.stdout) == (code, "") and text in r.stderr and "request id: req-1" in r.stderr
    assert deployment.authorization == {f"Bearer {TOKEN}"}  # every v1 call as the caller's token


def test_cli1_without_a_host_or_workspace_the_cli_says_so(monkeypatch):
    for key in ("CIDP_HOST", "CIDP_TOKEN", "CIDP_PROFILE", "CIDP_WORKSPACE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CIDP_CONFIG_FILE", "/nonexistent")
    r = cidp("workspaces", "list")
    assert r.exit_code == 3 and r.stderr.startswith("no_host:")


def test_cli2_no_token_in_options_output_or_tracebacks(deployment, memory_keyring, monkeypatch):
    # a token is never an option: it would show in ps and the shell history
    r = cidp("--token", TOKEN, "workspaces", "list")
    assert r.exit_code == 2 and TOKEN not in r.output
    # config shows where it connects, never the token
    r = cidp("-o", "json", "config")
    shown = json.loads(r.stdout)[0]
    assert shown["auth"] == "token" and shown["client_id"] == "portal-data-cli" and TOKEN not in r.output
    # people's text is printed as it is: brackets in a cell or a comment are not rich markup
    assert MARKUP in cidp("sql", "select 1").stdout
    assert MARKUP in cidp("tables", "get", "tpch.region").stdout
    # an unexpected error: typer's pretty traceback (which prints locals, the client and its token) is off
    assert cli.app.pretty_exceptions_enable is False

    # a browser login: PKCE over loopback, the refresh token in the keyring only; logout forgets it
    env = {"CIDP_HOST": HOST, "CIDP_CONFIG_FILE": "/nonexistent"}
    transport = httpx.MockTransport(deployment)
    opened: list[str] = []

    def browser(url: str) -> bool:
        opened.append(url)
        q = parse_qs(urlparse(url).query)
        assert q["code_challenge_method"] == ["S256"]
        callback = f"{q['redirect_uri'][0]}?code=the-code&state={q['state'][0]}"
        threading.Thread(target=urllib.request.urlopen, args=(callback,), daemon=True).start()
        return True

    monkeypatch.setattr(cli.webbrowser, "open", browser)
    monkeypatch.setattr(cli, "make_client", lambda _state: CIDPClient(env=env, transport=transport,
                                                                      opener=cli._open_browser))  # fmt: skip
    r = cidp("login")
    assert r.exit_code == 0, r.output
    assert "Signed in to https://portal.example.org (browser" in r.stderr and opened[0] in r.stderr
    assert deployment.grants == ["authorization_code"] and f"Bearer {ACCESS}" in deployment.authorization
    assert memory_keyring.values == {("cidp-sdk", f"{HOST}|default"): REFRESH}
    assert ACCESS not in r.output and REFRESH not in r.output
    r = cidp("logout")
    assert r.exit_code == 0 and memory_keyring.values == {}

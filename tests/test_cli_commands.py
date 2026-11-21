"""OpenSpec change data-cli-coverage CC2 (scenario CC-3): the curated commands on a fake v1 deployment.

projects, runs (start, list, get, cancel, logs), jobs deploy and retry, grants, volumes, ingest, statements and
events each make their v1 calls as the signed-in person and print what the service answers; a delete asks first,
a run that ended other than succeeded exits 9, a rejected upload loads nothing. The deployment is an
``httpx.MockTransport``; the change stream of ``events`` is a stand-in ``Follower``.
"""

from __future__ import annotations

import json
import queue
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from cidp_sdk import CIDPClient, cli
from cidp_sdk._events import Signal

HOST = "https://portal.example.org"
V1 = "/api/data/v1"
TOKEN = "eyJ.cli-commands-token.sig"  # gitleaks:allow - a test stand-in
NOW = "2026-11-12T08:00:00Z"
CONFIG = {"api_version": "1", "service_version": "0.2.0", "issuer": "https://sso.example.org/realms/portal",
          "client_id": "portal-data-cli", "audience": "portal-data", "polaris_uri": None, "polaris_realm": "portal",
          "object_store_uri": None, "object_store_path_style": True, "capabilities": ["statements"]}  # fmt: skip
WORKSPACE = {"slug": "sales", "display_name": "Sales", "home_catalog": "sales", "default_schema": "default",
             "status": "active", "viewer_groups": [], "admin_group": None, "allowed_actions": ["data.view"]}  # fmt: skip
PROJECT = {"id": "p1", "slug": "etl", "name": "ETL", "description": "", "git_url": None, "default_branch": "main",
           "owner_group": "engineers", "privileges": ["CAN_MANAGE"], "personal": False, "created_at": NOW,
           "branches": []}  # fmt: skip
P = "/workspaces/sales/projects/etl"


def project_run(status: str, run_id: str = "r1") -> dict[str, Any]:
    return {"run_id": run_id, "action": "dbt.build", "branch": "main", "path": "models", "parameters": {},
            "snapshot_sha": "abc", "draft": False, "writing": True, "status": status, "exit_code": None,
            "error": None, "summary": None, "started_by": "robin", "created_at": NOW, "started_at": NOW,
            "finished_at": None}  # fmt: skip


def job_run(status: str) -> dict[str, Any]:
    return {"run_id": "j2", "number": 8, "trigger": "retry", "status": status, "commit_sha": "abc", "run_as": "owner",
            "started_by": "robin", "job_parameters": {}, "error": None, "created_at": NOW, "started_at": NOW,
            "finished_at": None, "tasks": None}  # fmt: skip


def statement(state: str, **extra: Any) -> dict[str, Any]:
    return {"id": "s1", "state": state, "engine": "sqe", "catalog": "sales", "schema": None, "submitted_at": NOW,
            **extra}  # fmt: skip


def upload(state: str, **extra: Any) -> dict[str, Any]:
    return {"upload_id": "u1", "scope": "personal", "mine": True, "format": "csv", "options": {}, "size_bytes": 8,
            "catalog": "sales", "state": state, "scanner": "clamd", "created_at": NOW, **extra}  # fmt: skip


VOLUME = {"volume_id": "v1", "name": "raw", "catalog_name": "sales", "schema_name": "landing",
          "full_name": "sales.landing.raw", "comment": None, "owner_group": "engineers", "privileges": ["READ"],
          "read_only": False, "created_at": NOW, "created_by": "robin"}  # fmt: skip
VFILE = {"name": "a.csv", "path": "in/a.csv", "kind": "file", "size_bytes": 8, "modified_at": NOW}
GRANTS = {"securable_type": "table", "full_name": "sales.tpch.region", "owner": "engineers",
          "privilege_assignments": [{"principal": "analysts", "privileges": ["SELECT"]}],
          "inherited_assignments": [{"principal": "auditors", "privileges": ["SELECT"], "inherited_from": "sales"}],
          "valid_privileges": ["SELECT", "MODIFY"], "my_privileges": ["MANAGE"], "can_manage": True}  # fmt: skip
LOGS = ('id: 1\nevent: line\ndata: {"stream": "stdout", "line": "Running dbt"}\n\n'
        'id: 2\nevent: line\ndata: {"stream": "stderr", "line": "1 warning"}\n\n'
        ': ping\n\n'
        'event: end\ndata: {"status": "failed", "error": "model broke"}\n\n')  # fmt: skip


class Deployment:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []
        self.bodies: list[bytes] = []
        self.headers: list[httpx.Headers] = []
        self.status = "running"
        self.upload_state = "STAGED"
        self.deploy_errors: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:  # noqa: C901, PLR0911, PLR0912 - one fake server
        path = request.url.path.removeprefix(V1)
        if path == "/config":
            return httpx.Response(200, json=CONFIG)
        if path == "/me/events":
            return httpx.Response(404, json={"code": "not_found", "message": "none", "details": {}})
        self.calls.append((request.method, path, dict(request.url.params)))
        self.bodies.append(request.read())
        self.headers.append(request.headers)
        match (request.method, path):
            case ("GET", "/workspaces/sales"):
                return httpx.Response(200, json=WORKSPACE)
            case ("GET", "/workspaces/sales/projects"):
                return httpx.Response(200, json={"items": [PROJECT], "next_cursor": None})
            case ("POST", "/workspaces/sales/projects"):
                return httpx.Response(201, json=PROJECT)
            case ("GET", p) if p == P:
                return httpx.Response(200, json=PROJECT)
            case ("DELETE", p) if p == P:
                return httpx.Response(204)
            case ("POST", p) if p == f"{P}/actions/dbt.build":
                return httpx.Response(200, json={"action": "dbt.build", "run": project_run("queued")})
            case ("GET", p) if p == f"{P}/runs/r1":
                self.status = "failed" if self.status == "running" else self.status
                return httpx.Response(200, json=project_run(self.status))
            case ("GET", p) if p == f"{P}/runs":
                return httpx.Response(200, json={"items": [project_run("succeeded"), project_run("failed", "r0")],
                                                 "next_cursor": None})  # fmt: skip
            case ("POST", p) if p == f"{P}/runs/r1/cancel":
                return httpx.Response(200, json=project_run("cancelled"))
            case ("GET", p) if p == f"{P}/runs/r1/logs":
                return httpx.Response(200, content=LOGS.encode(), headers={"content-type": "text/event-stream"})
            case ("PUT", p) if p == f"{P}/deployment":
                return httpx.Response(200, json={"commit": "abc", "deployed": ["nightly"], "changed": [],
                                                 "undeployed": [], "errors": self.deploy_errors,
                                                 "target": None})  # fmt: skip
            case ("POST", p) if p == f"{P}/deployment/validate":
                body = json.loads(request.read() or b"{}")
                return httpx.Response(200, json={"commit": "abc", "branch": body.get("branch") or "main",
                                                 "file": "databricks.yml", "target": body.get("target") or "dev",
                                                 "deployed": ["nightly"], "errors": self.deploy_errors})  # fmt: skip
            case ("DELETE", p) if p == f"{P}/deployment":
                return httpx.Response(200, json={"target": "dev", "undeployed": ["nightly"], "cancelled": 1})
            case ("POST", p) if p == f"{P}/jobs/nightly/runs/j1/retry":
                return httpx.Response(200, json=job_run("queued"))
            case ("GET", p) if p == f"{P}/jobs/nightly/runs/j2":
                return httpx.Response(200, json=job_run("succeeded"))
            case ("GET", "/workspaces/sales/permissions/table/sales.tpch.region"):
                return httpx.Response(200, json=GRANTS)
            case ("PATCH", "/workspaces/sales/permissions/table/sales.tpch.region"):
                return httpx.Response(200, json=GRANTS)
            case ("GET", "/workspaces/sales/catalogs/sales/schemas/landing/volumes"):
                return httpx.Response(200, json={"items": [VOLUME]})
            case ("GET", "/workspaces/sales/catalogs/sales/schemas/landing/volumes/raw/files"):
                return httpx.Response(200, json={"items": [VFILE]})
            case ("PUT", "/workspaces/sales/catalogs/sales/schemas/landing/volumes/raw/files"):
                return httpx.Response(201, json=VFILE)
            case ("GET", "/workspaces/sales/catalogs/sales/schemas/landing/volumes/raw/files/content"):
                return httpx.Response(200, content=b"a,b\n1,2\n", headers={"content-type": "application/octet-stream"})
            case ("POST", "/workspaces/sales/uploads"):
                extra = {"error_code": "malware_found"} if self.upload_state == "REJECTED" else {}
                return httpx.Response(201, json=upload(self.upload_state, **extra))
            case ("POST", "/workspaces/sales/uploads/u1/load"):
                return httpx.Response(200, json=upload("LOADED", row_count=1, schema_name="landing",
                                                       table_name="orders"))  # fmt: skip
            case ("POST", "/workspaces/sales/statements"):
                return httpx.Response(200, json=statement("RUNNING"))
            case ("GET", "/workspaces/sales/statements/s1"):
                manifest = {"columns": [{"name": "x", "type": "bigint"}], "row_count": 2, "page_count": 2,
                            "byte_count": 8, "truncated": False}  # fmt: skip
                first = {"row_offset": 0, "row_count": 1, "rows": [[1]], "next_cursor": "p2"}
                return httpx.Response(200, json=statement("SUCCEEDED", manifest=manifest, result=first))
            case ("GET", "/workspaces/sales/statements/s1/result"):
                return httpx.Response(200, json={"row_offset": 1, "row_count": 1, "rows": [[2]]})
            case ("POST", "/workspaces/sales/statements/s1/cancel"):
                return httpx.Response(200, json=statement("CANCELED"))
        return httpx.Response(404, json={"code": "not_found", "message": f"{request.method} {path}", "details": {}})

    def made(self, method: str, path: str) -> bool:
        return any(c[0] == method and c[1] == path for c in self.calls)


@pytest.fixture
def deployment(monkeypatch) -> Deployment:
    d = Deployment()
    transport = httpx.MockTransport(d)
    env = {"CIDP_TOKEN": TOKEN, "CIDP_WORKSPACE": "sales", "CIDP_CONFIG_FILE": "/nonexistent"}

    def make_client(state: cli.State) -> CIDPClient:
        return CIDPClient(state.profile, host=state.host or HOST, workspace=state.workspace, env=env,
                            transport=transport)  # fmt: skip

    monkeypatch.setattr(cli, "make_client", make_client)
    monkeypatch.setattr(cli, "_interactive", lambda: False)
    return d


def cidp(*args: str, input: str | None = None):  # noqa: A002 - click's name
    return CliRunner().invoke(cli.app, list(args), input=input)


def test_cc3_projects(deployment):
    r = cidp("-o", "json", "projects", "list")
    assert r.exit_code == 0, r.output
    assert json.loads(r.stdout)[0]["slug"] == "etl"
    r = cidp("-o", "json", "projects", "get", "etl")
    assert json.loads(r.stdout)[0]["default_branch"] == "main"
    r = cidp("-o", "json", "projects", "create", "etl", "--git-url", "https://gitlab.com/x/etl.git")
    assert r.exit_code == 0, r.output
    sent = json.loads(deployment.bodies[-1])
    assert (sent["slug"], sent["git_url"]) == ("etl", "https://gitlab.com/x/etl.git")

    r = cidp("projects", "delete", "etl")
    assert r.exit_code == 2
    assert not deployment.made("DELETE", P)
    r = cidp("projects", "delete", "etl", "--yes")
    assert r.exit_code == 0, r.output
    assert deployment.made("DELETE", P)
    assert deployment.calls[-1][2] == {"confirm": "etl"}
    assert TOKEN not in r.output


def test_cc3_runs_start_wait_list_get_cancel(deployment):
    r = cidp("-o", "json", "runs", "start", "etl", "dbt.build", "--path", "models", "-P", "full=1")
    assert r.exit_code == 0, r.output
    body = json.loads(deployment.bodies[-1])
    assert body["branch"] == "main"  # the project's default branch
    assert body["params"] == {"full": "1"}
    assert json.loads(r.stdout)[0]["status"] == "queued"

    r = cidp("-o", "json", "runs", "start", "etl", "dbt.build", "--path", "models", "--branch", "dev", "--wait",
               "--poll", "0.01")  # fmt: skip
    assert r.exit_code == 9
    assert json.loads(r.stdout)[0]["status"] == "failed"
    assert "ended failed" in r.stderr

    r = cidp("-o", "json", "runs", "list", "etl", "--limit", "1")
    assert [x["run_id"] for x in json.loads(r.stdout)] == ["r1"]
    r = cidp("-o", "json", "runs", "get", "etl", "r1")
    assert json.loads(r.stdout)[0]["run_id"] == "r1"
    r = cidp("-o", "json", "runs", "cancel", "etl", "r1")
    assert json.loads(r.stdout)[0]["status"] == "cancelled"


def test_cc3_runs_logs(deployment):
    r = cidp("runs", "logs", "etl", "r1", "--follow")
    assert r.exit_code == 9
    assert r.stdout.splitlines() == ["Running dbt"]
    assert "1 warning" in r.stderr and "ended failed" in r.stderr
    assert deployment.calls[-1][2] == {"after": "0"}

    # without --follow: what is there, up to the first heartbeat
    r = cidp("-o", "jsonl", "runs", "logs", "etl", "r1", "--after", "0")
    assert r.exit_code == 0, r.output
    events = [json.loads(line) for line in r.stdout.splitlines()]
    assert [e["event"] for e in events] == ["line", "line"]
    assert events[1] == {"event": "line", "seq": 2, "stream": "stderr", "line": "1 warning"}


def test_cc3_jobs_deploy_and_retry(deployment):
    r = cidp("-o", "json", "jobs", "deploy", "etl")
    assert r.exit_code == 0, r.output
    assert json.loads(r.stdout)[0]["deployed"] == ["nightly"]
    deployment.deploy_errors = [{"path": "jobs/nightly", "message": "unknown task"}]
    r = cidp("-o", "json", "jobs", "deploy", "etl", "--target", "prod")
    assert r.exit_code == 1
    assert json.loads(deployment.bodies[-1]) == {"target": "prod"}

    r = cidp("-o", "json", "jobs", "retry", "etl", "nightly", "j1", "--wait", "--poll", "0.01")
    assert r.exit_code == 0, r.output
    assert json.loads(r.stdout)[0]["status"] == "succeeded"
    assert deployment.made("POST", f"{P}/jobs/nightly/runs/j1/retry")


def test_bundle_validate_deploy_destroy(deployment):
    """VPFDATA-882: `cidp bundle validate`, `deploy` and `destroy` send the deployment calls and exit as they
    should: 0 when clean, 1 with errors (nothing deployed), 2 for a destroy that is not confirmed."""
    r = cidp("-o", "json", "bundle", "validate", "etl", "--target", "dev", "--branch", "feature")
    assert r.exit_code == 0, r.output
    assert deployment.calls[-1][:2] == ("POST", f"{P}/deployment/validate")
    assert json.loads(deployment.bodies[-1]) == {"target": "dev", "branch": "feature"}
    out = json.loads(r.stdout)[0]
    assert (out["branch"], out["target"], out["deployed"], out["errors"]) == ("feature", "dev", ["nightly"], [])
    r = cidp("-o", "json", "bundle", "validate", "etl")  # the default target and branch: nothing sent
    assert r.exit_code == 0, r.output
    assert json.loads(deployment.bodies[-1]) == {}

    r = cidp("-o", "json", "bundle", "deploy", "etl", "-t", "dev")
    assert r.exit_code == 0, r.output
    assert deployment.calls[-1][:2] == ("PUT", f"{P}/deployment")
    assert json.loads(deployment.bodies[-1]) == {"target": "dev"}
    assert json.loads(r.stdout)[0]["deployed"] == ["nightly"]

    deployment.deploy_errors = [{"path": "jobs/nightly", "message": "unknown task"}]
    r = cidp("-o", "json", "bundle", "validate", "etl", "--target", "prod")
    assert r.exit_code == 1
    assert "Not valid: 1 error(s)." in r.stderr
    r = cidp("-o", "json", "bundle", "deploy", "etl", "--target", "prod")
    assert r.exit_code == 1
    assert "Not deployed: 1 error(s)." in r.stderr
    assert json.loads(deployment.bodies[-1]) == {"target": "prod"}

    n = len(deployment.calls)
    r = cidp("bundle", "destroy", "etl")  # no terminal and no --yes: refused before any call
    assert r.exit_code == 2
    assert not any(c[0] == "DELETE" for c in deployment.calls[n:])
    r = cidp("-o", "json", "bundle", "destroy", "etl", "--yes")
    assert r.exit_code == 0, r.output
    assert deployment.calls[-1][:2] == ("DELETE", f"{P}/deployment")
    assert json.loads(r.stdout)[0] == {"target": "dev", "undeployed": ["nightly"], "cancelled": 1}


def test_cc3_grants(deployment):
    r = cidp("-o", "csv", "grants", "list", "table", "sales.tpch.region")
    assert r.exit_code == 0, r.output
    r = cidp("grants", "list", "table", "sales.tpch.region")
    assert "analysts" in r.stdout and "auditors" in r.stdout
    r = cidp("grants", "add", "table", "sales.tpch.region", "analysts", "select", "modify")
    assert r.exit_code == 0, r.output
    assert json.loads(deployment.bodies[-1]) == {"changes": [{"principal": "analysts", "add": ["SELECT", "MODIFY"]}]}
    cidp("grants", "remove", "table", "sales.tpch.region", "analysts", "MODIFY")
    assert json.loads(deployment.bodies[-1]) == {"changes": [{"principal": "analysts", "remove": ["MODIFY"]}]}


def test_cc3_volumes(deployment, tmp_path):
    r = cidp("-o", "json", "volumes", "list", "landing")
    assert json.loads(r.stdout)[0]["full_name"] == "sales.landing.raw"
    r = cidp("-o", "json", "volumes", "ls", "landing.raw", "in")
    assert json.loads(r.stdout)[0]["path"] == "in/a.csv"
    assert deployment.calls[-1][2] == {"path": "in"}

    f = tmp_path / "a.csv"
    f.write_bytes(b"a,b\n1,2\n")
    r = cidp("volumes", "put", str(f), "landing.raw", "in/a.csv", "--overwrite")
    assert r.exit_code == 0, r.output
    assert deployment.bodies[-1] == b"a,b\n1,2\n"
    assert deployment.headers[-1]["content-type"] == "application/octet-stream"
    assert deployment.calls[-1][2] == {"path": "in/a.csv", "overwrite": "true"}

    r = cidp("volumes", "get", "landing.raw", "in/a.csv")
    assert r.stdout_bytes == b"a,b\n1,2\n"
    to = tmp_path / "copy.csv"
    cidp("volumes", "get", "landing.raw", "in/a.csv", "--out", str(to))
    assert to.read_bytes() == b"a,b\n1,2\n"


def test_cc3_ingest(deployment, tmp_path):
    f = tmp_path / "orders.csv"
    f.write_bytes(b"a,b\n1,2\n")
    r = cidp("-o", "json", "ingest", str(f), "--table", "landing.orders", "--mode", "append")
    assert r.exit_code == 0, r.output
    assert json.loads(r.stdout)[0]["state"] == "LOADED"
    create = next(c for c in deployment.calls if c[1] == "/workspaces/sales/uploads")
    assert create[2]["format"] == "csv"
    assert json.loads(deployment.bodies[-1]) | {"confirm": False} == {"schema": "landing", "table": "orders",
                                                                     "mode": "append", "confirm": False}  # fmt: skip

    r = cidp("-o", "json", "ingest", str(f), "--table", "landing.orders", "--catalog", "finance")
    assert r.exit_code == 0, r.output
    assert json.loads(deployment.bodies[-1])["catalog"] == "finance"

    deployment.upload_state = "REJECTED"
    n = len(deployment.calls)
    r = cidp("ingest", str(f), "--table", "landing.orders")
    assert r.exit_code == 1
    assert "malware_found" in r.stderr
    assert not any(c[1].endswith("/load") for c in deployment.calls[n:])

    r = cidp("ingest", str(tmp_path / "orders.csv"), "--table", "orders")
    assert r.exit_code == 2  # schema.table


def test_cc3_statements(deployment):
    r = cidp("-o", "json", "statements", "submit", "select 1", "--wait-timeout", "5")
    assert r.exit_code == 0, r.output
    assert json.loads(r.stdout)[0]["id"] == "s1"
    assert json.loads(deployment.bodies[-1])["wait_timeout"] == 5
    r = cidp("statements", "submit", "-", input="select 2")
    assert json.loads(deployment.bodies[-1])["sql"] == "select 2"
    r = cidp("-o", "json", "statements", "get", "s1")
    assert json.loads(r.stdout)[0]["state"] == "SUCCEEDED"
    r = cidp("-o", "jsonl", "statements", "result", "s1")
    assert [json.loads(line) for line in r.stdout.splitlines()] == [{"x": 1}, {"x": 2}]
    r = cidp("-o", "json", "statements", "cancel", "s1")
    assert json.loads(r.stdout)[0]["state"] == "CANCELED"


class FakeFollower:
    """Stands in for the change stream: the test fills ``script``; the last item ends the command."""

    script: list[tuple[Any, ...]] = []
    made: list[FakeFollower] = []

    def __init__(self, http: Any) -> None:
        self.out: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self.last_id: str | None = None
        self.stopped = False
        FakeFollower.made.append(self)

    def start(self) -> None:
        for item in self.script:
            self.out.put(item)

    def stop(self) -> None:
        self.stopped = True


def test_cc3_events(deployment, monkeypatch):
    monkeypatch.setattr(cli, "Follower", FakeFollower)
    FakeFollower.made = []
    FakeFollower.script = [
        Signal("open"),
        Signal("change", {"type": "portal.data.run.finished"}, "41"),
        Signal("reset"),
        Signal("gone"),
    ]
    r = cidp("events", "--since", "40")
    assert r.exit_code == 5  # the stream refused: gone
    lines = [json.loads(line) for line in r.stdout.splitlines()]
    assert lines == [{"event": "change", "id": "41", "data": {"type": "portal.data.run.finished"}},
                     {"event": "reset"}]  # fmt: skip
    assert "missed" in r.stderr
    follower = FakeFollower.made[-1]
    assert follower.last_id == "40"
    assert follower.stopped

    class Interrupting(FakeFollower):
        def start(self) -> None:
            self.out.put(Signal("open"))
            self.out.get = self._interrupt  # type: ignore[method-assign]

        def _interrupt(self, *a: Any, **k: Any) -> tuple[Any, ...]:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli, "Follower", Interrupting)
    r = cidp("events")
    assert r.exit_code == 130
    assert FakeFollower.made[-1].stopped

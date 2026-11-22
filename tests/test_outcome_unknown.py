"""``outcome_unknown`` (ai-portal-data issue 758, data-outcome-unknown; sql and jobs 1.7): a write whose outcome is
unknown becomes ``OutcomeUnknown`` on a synchronous call (504), a ``FAILED`` statement and a job run's
``error_code``, and the SDK never sends the request again: the transport sees each write exactly once.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from cidp_sdk import CIDPClient, CIDPError, OutcomeUnknown, StatementFailed, raise_for_outcome
from cidp_sdk import _models as m
from cidp_sdk.session import Result

HOST = "https://portal.example.org"
TOKEN = "eyJ.outcome-token.sig"  # gitleaks:allow - a test stand-in
V1 = "/api/data/v1"
NOW = "2026-11-22T08:00:00Z"
CONFIG = {"api_version": "1", "service_version": "0.2.0", "issuer": "https://sso.example.org/realms/portal",
          "client_id": "portal-data-cli", "audience": "portal-data", "polaris_uri": None, "polaris_realm": "portal",
          "object_store_uri": None, "object_store_path_style": True, "capabilities": ["statements"]}  # fmt: skip
STMT = {"id": "st1", "engine": "sqe", "catalog": "sales", "schema": "tpch", "submitted_at": NOW}


def unknown(code: str = "outcome_unknown", cause: str | None = "lost_answer") -> httpx.Response:
    details = {"cause": cause} if cause else {}
    return httpx.Response(504, json={"code": code, "message": "The write's outcome is unknown", "details": details},
                          headers={"x-request-id": "rid-504"})  # fmt: skip


def job_run(**kw: Any) -> dict[str, Any]:
    return {"run_id": "j1", "number": 7, "trigger": "manual", "status": "failed", "commit_sha": "abc",
            "run_as": "owner", "started_by": "robin", "job_parameters": {}, "error": "lost", "created_at": NOW,
            "started_at": NOW, "finished_at": NOW, "tasks": None, **kw}  # fmt: skip


class Deployment:
    """Counts each request by method and path; ``answers`` maps a path ending to its response."""

    def __init__(self, answers: dict[tuple[str, str], Any]):
        self.answers = answers
        self.calls: list[tuple[str, str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == f"{V1}/config":
            return httpx.Response(200, json=CONFIG)
        self.calls.append((request.method, path))
        for (method, end), answer in self.answers.items():
            if request.method == method and path.endswith(end):
                return answer() if callable(answer) else answer
        raise AssertionError(f"{request.method} {path}")

    def count(self, method: str, end: str) -> int:
        return sum(1 for mth, p in self.calls if mth == method and p.endswith(end))


def client(deployment: Deployment, workspace: str | None = None) -> CIDPClient:
    return CIDPClient(host=HOST, token=TOKEN, env={}, workspace=workspace, transport=httpx.MockTransport(deployment))


@pytest.mark.parametrize("code", ["outcome_unknown", "load_outcome_unknown"])
def test_a_sync_504_outcome_unknown_is_raised_once_and_never_sent_again(code: str):
    deployment = Deployment({("POST", "/statements"): lambda: unknown(code)})
    with client(deployment) as c, pytest.raises(OutcomeUnknown) as e:
        c.statements.submit("sales", "insert into t values (1)", idempotency_key="k1")
    assert (e.value.code, e.value.status, e.value.request_id, e.value.cause) == (code, 504, "rid-504", "lost_answer")
    assert isinstance(e.value, CIDPError) and not isinstance(e.value, StatementFailed)
    assert deployment.count("POST", "/statements") == 1


def test_a_504_without_the_code_stays_a_plain_error():
    deployment = Deployment({("POST", "/statements"): httpx.Response(504, json={"code": "statement_timeout"})})
    with client(deployment) as c, pytest.raises(CIDPError) as e:
        c.statements.submit("sales", "select 1")
    assert type(e.value) is CIDPError and e.value.code == "statement_timeout"


def test_a_cause_that_is_not_text_is_left_out():
    deployment = Deployment(
        {("POST", "/statements"): httpx.Response(504, json={"code": "outcome_unknown", "details": {"cause": 3}})}
    )
    with client(deployment) as c, pytest.raises(OutcomeUnknown) as e:
        c.statements.submit("sales", "insert into t values (1)")
    assert e.value.cause is None


def test_an_async_statement_failed_with_outcome_unknown_raises_it_and_is_submitted_once():
    failed = {
        **STMT,
        "state": "FAILED",
        "error": {"code": "outcome_unknown", "message": "The answer was lost", "cause": "replica_lost"},
    }
    deployment = Deployment({("POST", "/statements"): httpx.Response(200, json={**STMT, "state": "RUNNING"}),
                             ("GET", "/statements/st1"): httpx.Response(200, json=failed)})  # fmt: skip
    with client(deployment) as c:
        result = Result(c.statements, "sales", c.statements.submit("sales", "insert into t values (1)", wait_timeout=0))
        with pytest.raises(OutcomeUnknown) as e:
            result.wait()
    assert (e.value.code, e.value.cause, str(e.value)) == ("outcome_unknown", "replica_lost", "The answer was lost")
    assert deployment.count("POST", "/statements") == 1


def test_any_other_failed_statement_stays_statement_failed():
    failed = {**STMT, "state": "FAILED", "error": {"code": "failed", "message": "syntax"}}
    deployment = Deployment({("POST", "/statements"): httpx.Response(200, json=failed)})
    with client(deployment) as c:
        result = Result(c.statements, "sales", c.statements.submit("sales", "selec 1"))
        with pytest.raises(StatementFailed) as e:
            result.wait()
    assert e.value.code == "failed" and not isinstance(e.value, OutcomeUnknown)


def test_a_job_run_with_error_code_outcome_unknown_raises_it():
    run = m.JobRunInfo.model_validate(job_run(error_code="outcome_unknown"))
    with pytest.raises(OutcomeUnknown) as e:
        raise_for_outcome(run)
    assert e.value.code == "outcome_unknown" and "j1" in str(e.value)
    plain = m.JobRunInfo.model_validate(job_run())
    assert raise_for_outcome(plain) is plain


def test_cli_jobs_run_wait_exits_10_on_outcome_unknown_and_runs_once(monkeypatch: pytest.MonkeyPatch):
    from cidp_sdk import cli

    base = f"{V1}/workspaces/sales/projects/etl/jobs/nightly"
    deployment = Deployment({
        ("GET", f"{V1}/workspaces/sales"): httpx.Response(200, json={
            "slug": "sales", "display_name": "Sales", "home_catalog": "sales", "default_schema": "default",
            "status": "ready", "viewer_groups": [], "admin_group": "SG-E", "allowed_actions": ["view"],
            "external_id": None}),
        ("POST", f"{base}/run-now"): httpx.Response(200, json=job_run(error_code="outcome_unknown")),
    })  # fmt: skip
    monkeypatch.setattr(cli, "make_client", lambda state: client(deployment, "sales"))
    out = CliRunner().invoke(cli.app, ["jobs", "run", "etl", "nightly", "--wait"])
    assert out.exit_code == 10, out.output
    assert "outcome_unknown" in out.output and "check before you run it again" in out.output
    assert deployment.count("POST", f"{base}/run-now") == 1
    assert TOKEN not in out.output

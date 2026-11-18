"""``wait_run()`` on the caller's change stream (OpenSpec change data-api-consistency C18.3, task 3b.3b).

The deployment is an ``httpx.MockTransport``: ``/me/events`` answers a body the test feeds frame by frame, so each
test says exactly when a change arrives. A wait reads the run on a change to it, on the stream's open and reset, and
every ``interval`` seconds; the stream refused, limited or dropped leaves the timer.
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest

from cidp_sdk import CIDPError, WaitTimeout
from cidp_sdk._events import Follower, Signal
from cidp_sdk._http import Http
from cidp_sdk.auth import StaticToken
from cidp_sdk.services import Jobs, Projects

HOST = "https://portal.example.org"
V1 = "/api/data/v1"
P = f"{V1}/workspaces/sales/projects/etl"
NOW = "2026-11-12T08:00:00Z"
TOKEN = "tok-wait-0123456789"  # gitleaks:allow - a test stand-in


def project_run(status: str) -> dict[str, Any]:
    return {"run_id": "r1", "action": "dbt.build", "branch": "main", "path": "models", "parameters": {},
            "snapshot_sha": "abc", "draft": False, "writing": True, "status": status, "exit_code": None,
            "error": None, "summary": None, "started_by": "robin", "created_at": NOW, "started_at": NOW,
            "finished_at": None}  # fmt: skip


def job_run(status: str) -> dict[str, Any]:
    return {"run_id": "j1", "number": 7, "trigger": "manual", "status": status, "commit_sha": "abc", "run_as": "owner",
            "started_by": "robin", "job_parameters": {}, "error": None, "created_at": NOW, "started_at": NOW,
            "finished_at": None, "tasks": None}  # fmt: skip


def change(ident: str, resource: str, type_: str = "portal.data.run.finished") -> str:
    return f'id: {ident}\nevent: change\ndata: {{"type": "{type_}", "resource": "{resource}", "etag": null}}\n\n'


class Deployment:
    """One run, its reads counted, and the change stream: each ``/me/events`` request gets the next answer in
    ``streams`` (a status, or a feed the test writes frames into); none left: 404."""

    def __init__(self, run: Callable[[str], dict[str, Any]], path: str) -> None:
        self.run, self.path = run, path
        self.status = "running"
        self.reads = 0
        self.streams: list[int | queue.Queue[str | BaseException | None]] = []
        self.opened: list[httpx.Request] = []
        self.lock = threading.Lock()

    def feed(self) -> queue.Queue[str | BaseException | None]:
        q: queue.Queue[str | BaseException | None] = queue.Queue()
        self.streams.append(q)
        return q

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == f"{V1}/me/events":
            self.opened.append(request)
            answer = self.streams.pop(0) if self.streams else 404
            if isinstance(answer, int):
                return httpx.Response(answer, json={"code": "x", "message": "No stream", "details": None})

            def body(q: queue.Queue[str | BaseException | None] = answer) -> Iterator[bytes]:
                while True:
                    item = q.get()
                    if item is None:
                        return
                    if isinstance(item, BaseException):
                        raise item
                    yield item.encode()

            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body())
        if request.url.path == self.path:
            with self.lock:
                self.reads += 1
            return httpx.Response(200, json=self.run(self.status))
        return httpx.Response(404, json={"code": "not_found", "message": "Not found", "details": None})


def http(d: Deployment) -> Http:
    return Http(HOST, StaticToken(TOKEN), transport=httpx.MockTransport(d))


def until(check: Callable[[], bool], seconds: float = 5.0) -> None:
    end = time.monotonic() + seconds
    while not check():
        assert time.monotonic() < end, "timed out"
        threading.Event().wait(0.01)


def in_background(fn: Callable[[], Any]) -> tuple[threading.Thread, dict[str, Any]]:
    out: dict[str, Any] = {}

    def go() -> None:
        try:
            out["result"] = fn()
        except BaseException as e:  # noqa: BLE001 - handed to the test
            out["error"] = e

    t = threading.Thread(target=go, daemon=True)
    t.start()
    return t, out


def no_follower_left() -> bool:
    return not any(t.name == "cidp-events" and t.is_alive() for t in threading.enumerate())


def test_an_ended_run_returns_at_once_without_a_stream() -> None:
    d = Deployment(project_run, f"{P}/runs/r1")
    d.status = "succeeded"
    assert Projects(http(d)).wait_run("sales", "etl", "r1").status == "succeeded"
    assert d.reads == 1 and d.opened == []


def test_a_change_to_the_run_reads_it_again_and_another_resource_does_not() -> None:
    d = Deployment(project_run, f"{P}/runs/r1")
    feed = d.feed()
    t, out = in_background(lambda: Projects(http(d)).wait_run("sales", "etl", "r1", timeout=10, interval=60))
    until(lambda: d.reads == 2)  # the first read, and the read when the stream opened
    assert d.opened[0].headers["authorization"] == f"Bearer {TOKEN}"
    assert "last-event-id" not in d.opened[0].headers
    feed.put(": ping\n\n")
    feed.put(change("5.1", f"{P}/runs/r2"))
    feed.put(change("5.2", f"{P}/jobs/nightly/runs/r1", "portal.data.job.run.finished"))
    threading.Event().wait(0.3)
    assert d.reads == 2
    d.status = "failed"
    feed.put(change("5.3", f"{P}/runs/r1"))
    t.join(5)
    assert out["result"].status == "failed" and d.reads == 3  # ended is ended, whatever the result
    feed.put(None)
    until(no_follower_left)


def test_a_job_run_waits_on_its_own_resource() -> None:
    d = Deployment(job_run, f"{P}/jobs/nightly/runs/j1")
    feed = d.feed()
    t, out = in_background(lambda: Jobs(http(d)).wait_run("sales", "etl", "nightly", "j1", interval=60))
    until(lambda: d.reads == 2)
    d.status = "waiting"
    feed.put(change("1.1", f"{P}/jobs/nightly/runs/j1", "portal.data.job.run.waiting"))
    until(lambda: d.reads == 3)
    assert t.is_alive()  # waiting is not ended
    d.status = "skipped"
    feed.put(change("1.2", f"{P}/jobs/nightly/runs/j1", "portal.data.job.run.skipped"))
    t.join(5)
    assert out["result"].status == "skipped"
    feed.put(None)


def test_the_stream_resumes_after_the_last_change_and_drops_the_id_on_reset() -> None:
    d = Deployment(project_run, f"{P}/runs/r1")
    first, second, third = d.feed(), d.feed(), d.feed()
    f = Follower(http(d), pauses=(0.0,))
    f.start()
    try:
        assert f.out.get(timeout=5) == Signal("open")
        first.put(change("7.4", f"{P}/runs/r1"))
        assert f.out.get(timeout=5).kind == "change"
        first.put("event: reconnect\ndata: {}\n\n")
        assert f.out.get(timeout=5) == Signal("open")
        assert d.opened[1].headers["last-event-id"] == "7.4"
        second.put("event: reset\ndata: {}\n\n")
        assert f.out.get(timeout=5) == Signal("reset")
        assert f.out.get(timeout=5) == Signal("open")
        assert "last-event-id" not in d.opened[2].headers
        third.put(httpx.ReadTimeout("silent"))  # a drop: open again after a pause; none left answers 404
        assert f.out.get(timeout=5) == Signal("gone")
    finally:
        f.stop()
        for q in (first, second, third):
            q.put(None)
    f.join(5)
    assert not f.is_alive()


@pytest.mark.parametrize("refusal", [403, 404, 429, 503])
def test_a_refused_or_limited_stream_leaves_the_timer(refusal: int) -> None:
    d = Deployment(project_run, f"{P}/runs/r1")
    d.streams = [refusal]
    t, out = in_background(lambda: Projects(http(d)).wait_run("sales", "etl", "r1", timeout=10, interval=0.05))
    until(lambda: d.reads >= 3)
    d.status = "cancelled"
    t.join(5)
    assert out["result"].status == "cancelled"
    until(no_follower_left)


def test_a_wait_out_of_time_raises_wait_timeout_and_the_run_goes_on() -> None:
    d = Deployment(job_run, f"{P}/jobs/nightly/runs/j1")
    d.status = "queued"
    with pytest.raises(WaitTimeout) as caught:
        Jobs(http(d)).wait_run("sales", "etl", "nightly", "j1", timeout=0.2, interval=0.05)
    assert isinstance(caught.value, TimeoutError) and isinstance(caught.value, CIDPError)
    assert caught.value.code == "wait_timeout" and "j1" in str(caught.value)
    assert d.reads >= 2
    until(no_follower_left)

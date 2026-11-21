"""OpenSpec change data-cli-coverage CC3 (scenario CC-4): the SDK's server-sent stream reader and streamed request bodies.

``Http.events`` yields each event with its id and each heartbeat as a ``ping``, raises the error class of a refused
stream, and turns a broken connection into ``TransportError``; ``Projects.logs`` reads a run's log lines and ends at
the run's end (following) or at the first heartbeat (not following); ``raw_body`` sends a file in chunks with its
length, never read whole into memory.
"""

from __future__ import annotations

import io
from collections.abc import Iterator

import httpx
import pytest

from cidp_sdk import PermissionDenied, TransportError
from cidp_sdk._http import FileBody, Http, raw_body
from cidp_sdk.auth import StaticToken
from cidp_sdk.services import Me, Projects

HOST = "https://portal.example.org"
TOKEN = "tok-streams-0123456789"  # gitleaks:allow - a test stand-in
LOGS = ('id: 1\nevent: line\ndata: {"stream": "stdout", "line": "one"}\n\n'
        ': ping\n\n'
        'id: 2\nevent: line\ndata: {"stream": "stdout", "line": "two"}\n\n'
        'event: end\ndata: {"status": "succeeded", "error": null}\n\n'
        'id: 3\nevent: line\ndata: {"stream": "stdout", "line": "never"}\n\n')  # fmt: skip


def http(handler) -> Http:
    return Http(HOST, StaticToken(TOKEN), transport=httpx.MockTransport(handler))


def sse(body: str) -> httpx.Response:
    return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})


def test_cc4_events_yields_events_ids_and_pings():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return sse(LOGS)

    events = list(http(handler).events("/x", params={"after": 0}))
    assert events[0] == ("line", '{"stream": "stdout", "line": "one"}', "1")
    assert events[1] == ("ping", "", None)
    assert seen[0].headers["accept"] == "text/event-stream"
    assert seen[0].headers["authorization"] == f"Bearer {TOKEN}"


def test_cc4_logs_follow_ends_at_the_end_event_and_not_follow_at_a_ping():
    projects = Projects(http(lambda request: sse(LOGS)))
    followed = list(projects.logs("sales", "etl", "r1"))
    assert [e.get("line") for e in followed] == ["one", "two", None]
    assert followed[-1] == {"event": "end", "status": "succeeded", "error": None}
    assert list(projects.logs("sales", "etl", "r1", follow=False)) == [
        {"event": "line", "seq": 1, "stream": "stdout", "line": "one"}]  # fmt: skip


CHANGES = ('id: 7.1\nevent: change\ndata: {"type": "portal.data.run.finished", "status": "succeeded"}\n\n'
           ': ping\n\n'
           'id: 7.2\nevent: change\ndata: {"type": "portal.data.job.run.started"}\n\n'
           'event: reset\ndata: {}\n\n'
           'id: 8.1\nevent: change\ndata: {"type": "never"}\n\n')  # fmt: skip


def test_cc4_me_events_yields_changes_with_ids_and_ends_at_reset():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return sse(CHANGES)

    me = Me(http(handler))
    followed = list(me.events(since="6.9"))
    assert [e.get("id") for e in followed] == ["7.1", "7.2", None]
    assert followed[0]["data"]["status"] == "succeeded" and followed[-1] == {"event": "reset"}
    assert seen[0].url.path.endswith("/me/events") and seen[0].url.params["last_event_id"] == "6.9"
    assert [e["id"] for e in me.events(follow=False)] == ["7.1"]
    assert "last_event_id" not in seen[-1].url.params


def test_cc4_a_refused_stream_raises_its_error_class():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"code": "forbidden", "message": "Not your run", "details": {}})

    with pytest.raises(PermissionDenied) as e:
        list(Projects(http(handler)).logs("sales", "etl", "r1"))
    assert e.value.code == "forbidden"


def test_cc4_a_broken_stream_is_a_transport_error():
    def body() -> Iterator[bytes]:
        yield b'id: 1\nevent: line\ndata: {"line": "one"}\n\n'
        raise httpx.ReadError("reset by peer")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body(), headers={"content-type": "text/event-stream"})

    stream = http(handler).events("/x")
    assert next(stream)[0] == "line"
    with pytest.raises(TransportError):
        next(stream)


def test_cc4_raw_body_streams_a_file_in_chunks(monkeypatch):
    monkeypatch.setattr(FileBody, "CHUNK", 4)
    f = io.BytesIO(b"skip|0123456789")
    f.seek(5)
    content, headers = raw_body(f)
    assert isinstance(content, FileBody)
    assert headers == {"Content-Type": "application/octet-stream", "Content-Length": "10"}
    assert list(content) == [b"0123", b"4567", b"89"]
    assert list(content) == [b"0123", b"4567", b"89"]  # a retry reads it again from the start
    assert raw_body(b"abc") == (b"abc", {"Content-Type": "application/octet-stream"})

    got: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        got.append(request.read())
        return httpx.Response(204)

    f.seek(5)
    content, headers = raw_body(f)
    http(handler).call("PUT", "/x", content=content, headers=headers)
    assert got == [b"0123456789"]

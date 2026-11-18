"""Waiting for a run on the caller's change stream (OpenSpec change data-api-consistency C18.3, task 3b.3b).

``wait_until`` reads the run, opens ``GET /me/events`` in a daemon thread with the client's own token, and reads the
run again on each change to it, when the stream opens or resets, and every ``interval`` seconds whatever the stream
does. The stream only says *that* something changed; the run's state always comes from a read. A refused stream
(403, 404), a limit (429) or a dropped connection leaves the timer: the wait never fails because the stream did.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Callable
from typing import Any, NamedTuple

import httpx

from cidp_sdk._http import Http, log
from cidp_sdk.errors import WaitTimeout

PAUSES = (0.5, 1.0, 2.0, 5.0, 10.0, 15.0)  # between tries after a drop, as the data UI's MeEventsStream
LIMITED = 60.0  # after a 429 (five streams per person)
READ_SECONDS = 45.0  # the service sends ``: ping`` well within this; silence longer than it is a drop
GONE = (403, 404)  # not allowed or not there: no stream for this wait


class Signal(NamedTuple):
    """One message of a ``Follower``: ``open``, ``change`` (with the change and its event id), ``reset``, or ``gone``
    once the service refuses the stream for good."""

    kind: str
    change: dict[str, Any] | None = None
    id: str | None = None


class Follower(threading.Thread):
    """``/me/events`` read in the background, as ``Signal``s on ``out``."""

    def __init__(self, http: Http, *, pauses: tuple[float, ...] = PAUSES, limited: float = LIMITED,
                 read_seconds: float = READ_SECONDS):  # fmt: skip
        super().__init__(name="cidp-events", daemon=True)
        self.http = http
        self.out: queue.Queue[Signal] = queue.Queue()
        self.pauses, self.limited, self.read_seconds = pauses, limited, read_seconds
        self.last_id: str | None = None
        self._halt = threading.Event()
        self._response: httpx.Response | None = None

    def stop(self) -> None:
        self._halt.set()
        r = self._response
        if r is not None:
            try:
                r.close()  # ends a read the thread is blocked in
            except Exception as e:  # noqa: BLE001 - closing is best effort; the thread ends at its next line
                log.debug("event stream close (%s)", type(e).__name__)

    def run(self) -> None:
        failures = 0
        while not self._halt.is_set():
            outcome = self._once()
            if outcome == "gone":
                self.out.put(Signal("gone"))
                return
            if outcome == "again":
                failures = 0
                continue
            if outcome == "limited":
                pause = self.limited
            else:
                pause = self.pauses[min(failures, len(self.pauses) - 1)]
                failures += 1
            self._halt.wait(pause)

    def _once(self) -> str:
        """One connection: ``again`` (open it now), ``down`` (after a pause), ``limited`` or ``gone``."""
        headers = {"Accept": "text/event-stream", "Cache-Control": "no-cache"}
        if self.last_id:
            headers["Last-Event-ID"] = self.last_id
        timeout = httpx.Timeout(10.0, read=self.read_seconds)
        try:
            with self.http._client.stream("GET", "/me/events", headers=headers, timeout=timeout) as r:
                self._response = r
                if r.status_code in GONE:
                    return "gone"
                if r.status_code == 429:
                    return "limited"
                if r.status_code == 400:  # an id the service no longer knows
                    self.last_id = None
                    self.out.put(Signal("reset"))
                    return "again"
                if r.status_code != 200:
                    return "down"
                self.out.put(Signal("open"))
                return self._read(r)
        except Exception as e:  # noqa: BLE001 - a drop, a silence past the read limit, a close from stop()
            log.debug("event stream dropped (%s)", type(e).__name__)
            return "down"
        finally:
            self._response = None

    def _read(self, r: httpx.Response) -> str:
        event, data, ident = "message", "", None
        for line in r.iter_lines():
            if self._halt.is_set():
                return "down"
            if line == "":
                if event == "change" and data:
                    try:
                        change = json.loads(data)
                    except ValueError:
                        change = None
                    if isinstance(change, dict):
                        if ident:
                            self.last_id = ident
                        self.out.put(Signal("change", change, ident))
                elif event == "reset":
                    self.last_id = None
                    self.out.put(Signal("reset"))
                    return "again"
                elif event == "reconnect":
                    return "again"
                event, data, ident = "message", "", None
            elif line.startswith(":"):
                continue
            else:
                field, _, value = line.partition(":")
                value = value.removeprefix(" ")
                if field == "event":
                    event = value
                elif field == "data":
                    data = f"{data}\n{value}" if data else value
                elif field == "id":
                    ident = value
        return "down"


def wait_until[T](http: Http, resource: str, read: Callable[[], T], ended: Callable[[T], bool], *, what: str,
               timeout: float | None, interval: float, follower: Callable[[Http], Follower] = Follower,
               clock: Callable[[], float] = time.monotonic) -> T:  # fmt: skip
    """``read()`` until ``ended`` holds: on each change to ``resource``, on the stream's open and reset, and every
    ``interval`` seconds. ``WaitTimeout`` after ``timeout`` seconds (None: no limit); the run goes on."""
    deadline = None if timeout is None else clock() + timeout
    current = read()
    if ended(current):
        return current
    stream = follower(http)
    stream.start()
    try:
        while True:
            left = None if deadline is None else deadline - clock()
            if left is not None and left <= 0:
                raise WaitTimeout(f"{what} has not ended after {timeout} s; it goes on in the service",
                                  code="wait_timeout")  # fmt: skip
            try:
                message = stream.out.get(timeout=max(0.0, interval if left is None else min(interval, left)))
            except queue.Empty:
                message = Signal("tick")
            if message.kind == "gone":
                continue  # the timer goes on
            if message.kind == "change" and (message.change or {}).get("resource") != resource:
                continue
            if message.kind == "tick" and deadline is not None and clock() >= deadline:
                continue  # out of time: the check above raises
            current = read()
            if ended(current):
                return current
    finally:
        stream.stop()

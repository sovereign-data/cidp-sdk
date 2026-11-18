"""SQL as the caller (design A3): a ``Session`` submits statements, a ``Result`` waits for them and reads the pages.

``session.sql("select ...")`` returns at once with the statement running; reading rows waits for it. A ``Result``
used as a context manager cancels its statement on the way out when it has not ended.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import pyarrow as pa

from cidp_sdk import _models as m
from cidp_sdk.errors import StatementFailed, WaitTimeout

if TYPE_CHECKING:
    import pandas

    from cidp_sdk.services import Statements

OPEN = ("PENDING", "RUNNING")
POLL = 30  # seconds the service may hold one GET (the contract allows up to 50)


class Result:
    """One statement: its state, and its rows once it succeeded."""

    def __init__(self, statements: Statements, workspace: str, info: m.StatementInfo):
        self._statements = statements
        self.workspace = workspace
        self.info = info

    def __repr__(self) -> str:
        return f"Result(id={self.id!r}, state={self.state!r})"

    def __enter__(self) -> Result:
        return self

    def __exit__(self, *exc: object) -> None:
        if self.state in OPEN:
            self.cancel()

    @property
    def id(self) -> str:
        return self.info.id

    @property
    def state(self) -> str:
        return str(self.info.state)

    @property
    def columns(self) -> list[str]:
        manifest = self.wait().info.manifest
        return [c.name for c in manifest.columns] if manifest else []

    def refresh(self, wait_timeout: int | None = None) -> Result:
        self.info = self._statements.get(self.workspace, self.id, wait_timeout=wait_timeout)
        return self

    def wait(self, timeout: float | None = None) -> Result:
        """Wait until the statement ends; ``StatementFailed`` unless it succeeded."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while self.state in OPEN:
            left = POLL if deadline is None else min(POLL, max(0, int(deadline - time.monotonic())))
            if deadline is not None and left <= 0:
                raise WaitTimeout(f"Statement {self.id} still {self.state} after {timeout} s", code="wait_timeout")
            self.refresh(wait_timeout=left)
        if self.state != "SUCCEEDED":
            error = self.info.error
            raise StatementFailed(
                error.message if error else f"Statement {self.id} ended {self.state}",
                code=(error.code if error else self.state.lower()),
            )
        return self

    def cancel(self) -> Result:
        self.info = self._statements.cancel(self.workspace, self.id)
        return self

    def pages(self) -> Iterator[m.ResultPage]:
        self.wait()
        first = self.info.result
        page = first if first is not None and first.row_offset == 0 else None
        page = page or self._statements.result(self.workspace, self.id)
        while True:
            yield page
            if not page.next_cursor:
                return
            page = self._statements.result(self.workspace, self.id, cursor=page.next_cursor)

    def rows(self) -> Iterator[list[Any]]:
        for page in self.pages():
            yield from page.rows

    def collect(self) -> list[dict[str, Any]]:
        """Every row as a dict by column name."""
        names = self.columns
        return [dict(zip(names, row, strict=False)) for row in self.rows()]

    def to_arrow(self) -> pa.Table:
        """The whole result as one Arrow table, read page by page in the Arrow format."""
        self.wait()
        tables: list[pa.Table] = []
        cursor: str | None = None
        while True:
            table, cursor = self._statements.result_arrow(self.workspace, self.id, cursor=cursor)
            tables.append(table)
            if not cursor:
                break
        return pa.concat_tables(tables) if len(tables) > 1 else tables[0]

    def to_pandas(self) -> pandas.DataFrame:
        """Needs the ``pandas`` extra."""
        return self.to_arrow().to_pandas()


class Session:
    """Where statements run: a workspace, an engine, a catalog (None: the home) and a schema."""

    def __init__(self, statements: Statements, workspace: str, *, engine: str = "sqe", catalog: str | None = None,
                 schema: str | None = None, query_tag: str | None = None):  # fmt: skip
        self._statements = statements
        self.workspace = workspace
        self.engine = engine
        self.catalog = catalog
        self.schema = schema
        self.query_tag = query_tag

    def __repr__(self) -> str:
        return f"Session(workspace={self.workspace!r}, engine={self.engine!r}, schema={self.schema!r})"

    def sql(self, sql: str, *, wait_timeout: int = 10, row_limit: int | None = None) -> Result:
        """Submit a statement; the answer comes back after at most ``wait_timeout`` seconds, running or ended."""
        info = self._statements.submit(self.workspace, sql, engine=self.engine, catalog=self.catalog,
                                       schema=self.schema, wait_timeout=wait_timeout, row_limit=row_limit,
                                       query_tag=self.query_tag)  # fmt: skip
        return Result(self._statements, self.workspace, info)

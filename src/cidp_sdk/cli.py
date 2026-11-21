"""The ``cidp`` command (OpenSpec changes data-cli, data-cli-coverage): the SDK on a terminal, an extra of the
package (``[cli]``).

As Chameleon's CLI (``Applications/data-platform/cli``): typer sub-apps per area and ``--output`` table, json, jsonl
or csv. Unlike it, nothing signs in with a password and no engine runs locally: every command is a v1 call through
``CIDPClient``, as the person (browser login), a service principal (client credentials) or ``CIDP_TOKEN``.

A token is never an option (it would show in ``ps`` and the shell history), never printed, and never in a traceback:
pretty exceptions are off, and a ``CIDPError`` ends the command with ``code: message`` on stderr and the exit code
of its class (``EXIT``). People's text (SQL, cells, messages) is printed without rich markup.

``cidp api`` reaches every operation of API v1 by its operationId, as ``databricks api`` does, through the same
session as the SDK (data-cli-coverage CC1); the other groups are thin commands on the SDK's services (CC2).
"""

from __future__ import annotations

import csv
import itertools
import json
import queue
import re
import sys
import webbrowser
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, NoReturn

try:
    import typer
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
except ImportError as e:  # pragma: no cover - the extra is missing
    raise SystemExit("The cidp command needs the cli extra: pip install 'cidp-sdk[cli]'") from e

from cidp_sdk import __version__, auth, services
from cidp_sdk._events import Follower
from cidp_sdk._http import raw_body
from cidp_sdk._operations import OPERATIONS
from cidp_sdk.client import CIDPClient
from cidp_sdk.errors import (
    CIDPError,
    ConfigError,
    Conflict,
    NotFound,
    PermissionDenied,
    StatementFailed,
    TooManyRequests,
    Unauthenticated,
)

# Exit codes per error class (design C3), for scripts; 2 is typer's for a usage error, 130 an interrupt.
EXIT: dict[type[CIDPError], int] = {
    ConfigError: 3, Unauthenticated: 4, PermissionDenied: 5, NotFound: 6, Conflict: 7, TooManyRequests: 8,
    StatementFailed: 9,
}  # fmt: skip
JOB_OPEN = ("waiting", "queued", "running")
TABLE_ROWS = 1000  # rows a table on the terminal shows; csv and jsonl stream every row
KEY_WIDTH = 48  # the widest first column a table keeps on one line; longer names fold


class Output(StrEnum):
    table = "table"
    json = "json"
    jsonl = "jsonl"
    csv = "csv"


@dataclass
class State:
    profile: str | None = None
    host: str | None = None
    workspace: str | None = None
    output: Output = Output.table


out = Console(highlight=False, soft_wrap=True)
err = Console(stderr=True, highlight=False, soft_wrap=True)


def _open_browser(url: str) -> bool:
    """The sign-in page: opened when a browser is there, always printed (the URL carries no secret)."""
    err.print("Sign in in your browser. If it did not open, go to:", markup=False)
    err.print(url, markup=False)
    try:
        return webbrowser.open(url)
    except webbrowser.Error:
        return False


def make_client(state: State) -> CIDPClient:
    """The one place the CLI builds a client; tests replace it to pass a fake transport."""
    return CIDPClient(state.profile, host=state.host, workspace=state.workspace, opener=_open_browser)


app = typer.Typer(name="cidp", help="CIDP, the cloud independent data platform, from a terminal (API v1).",
                  no_args_is_help=True, pretty_exceptions_enable=False, add_completion=False)  # fmt: skip
workspaces_app = typer.Typer(help="Workspaces you may see.", no_args_is_help=True)
catalogs_app = typer.Typer(help="Catalogs bound to a workspace.", no_args_is_help=True)
schemas_app = typer.Typer(help="Schemas in a catalog.", no_args_is_help=True)
tables_app = typer.Typer(help="Tables in a schema.", no_args_is_help=True)
views_app = typer.Typer(help="Views in a schema.", no_args_is_help=True)
jobs_app = typer.Typer(help="Jobs of a project: list, run, runs, retry, deploy.", no_args_is_help=True)
api_app = typer.Typer(help="Any operation of API v1 by its operationId (as `databricks api`).", no_args_is_help=True)
projects_app = typer.Typer(help="Projects of a workspace.", no_args_is_help=True)
runs_app = typer.Typer(help="Runs of a project's actions (dbt, Python): start, list, get, cancel, logs.",
                       no_args_is_help=True)  # fmt: skip
grants_app = typer.Typer(help="Grants on a catalog, schema, table or view.", no_args_is_help=True)
volumes_app = typer.Typer(help="Volumes and their files.", no_args_is_help=True)
statements_app = typer.Typer(help="Asynchronous statements, step by step (`cidp sql` does it in one).",
                             no_args_is_help=True)  # fmt: skip
for sub, name in ((workspaces_app, "workspaces"), (catalogs_app, "catalogs"), (schemas_app, "schemas"),
                  (tables_app, "tables"), (views_app, "views"), (jobs_app, "jobs"), (api_app, "api"),
                  (projects_app, "projects"), (runs_app, "runs"), (grants_app, "grants"), (volumes_app, "volumes"),
                  (statements_app, "statements")):  # fmt: skip
    app.add_typer(sub, name=name)


def _version(value: bool) -> None:
    if value:
        out.print(f"cidp {__version__}", markup=False)
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    profile: Annotated[str | None, typer.Option("--profile", "-p", help="In ~/.cidp/connections.toml")] = None,
    host: Annotated[str | None, typer.Option("--host", help="The platform's address (over CIDP_HOST)")] = None,
    workspace: Annotated[str | None, typer.Option("--workspace", "-w", help="Over CIDP_WORKSPACE")] = None,
    output: Annotated[Output, typer.Option("--output", "-o", help="How results are printed")] = Output.table,
    version: Annotated[bool, typer.Option("--version", callback=_version, is_eager=True, help="The version")] = False,
) -> None:  # fmt: skip
    """Connect as the SDK does: options, then CIDP_* variables, then a profile. Tokens come from the environment
    (CIDP_TOKEN, CIDP_CLIENT_SECRET) or a browser sign-in kept in the OS keyring, never from an option."""
    ctx.obj = State(profile=profile, host=host, workspace=workspace, output=output)


def _fail(e: CIDPError) -> NoReturn:
    err.print(f"{e.code}: {e.message}", markup=False)
    if e.request_id:
        err.print(f"request id: {e.request_id}", markup=False)
    code = next((v for cls, v in EXIT.items() if isinstance(e, cls)), 1)
    raise typer.Exit(code)


def _run(ctx: typer.Context, work: Callable[[CIDPClient, State], None]) -> None:
    """Open a client, do the work, close it; errors become ``code: message`` and their exit code."""
    state: State = ctx.obj
    try:
        with make_client(state) as client:
            work(client, state)
    except CIDPError as e:
        _fail(e)


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    return value


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict | list):
        return json.dumps(value, default=str)
    return str(value)


def emit(state: State, rows: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> None:
    """Print records: a table of ``columns``, or every field as json, jsonl or csv (csv: ``columns`` only)."""
    if state.output is Output.jsonl:
        for r in rows:
            out.print(json.dumps(r, default=str), markup=False)
        return
    if state.output is Output.json:
        out.print(json.dumps(list(rows), default=str, indent=2), markup=False)
        return
    if state.output is Output.csv:
        writer = csv.writer(sys.stdout)
        writer.writerow(columns)
        for r in rows:
            writer.writerow([_cell(r.get(c)) for c in columns])
        return
    shown: list[list[str]] = []
    for r in rows:
        if len(shown) == TABLE_ROWS:
            err.print(f"Only the first {TABLE_ROWS} rows are shown; use --output csv or jsonl for all.", markup=False)
            break
        shown.append([_cell(r.get(c)) for c in columns])
    if not shown:
        err.print("No results.", markup=False)
        return
    # No cell is cut short: the first column (the name to copy or grep) keeps its width on one line, the others
    # fold onto more lines. Rich's default ("...") hid the end of long names at 80 columns, e.g. in a pipe.
    key = max(len(c) for c in (columns[0], *(row[0] for row in shown)))
    # Text, not str: rich reads markup in a plain string, and cells and column names are people's text
    table = Table(show_header=True, header_style="bold")
    for i, c in enumerate(columns):
        if i == 0:
            table.add_column(Text(c), no_wrap=True, min_width=min(key, KEY_WIDTH), overflow="fold")
        else:
            table.add_column(Text(c), overflow="fold")
    for row in shown:
        table.add_row(*[Text(v) for v in row])
    out.print(table, markup=False)


def emit_one(state: State, record: Mapping[str, Any]) -> None:
    """One record: fields and values on the terminal, the record itself otherwise."""
    if state.output is Output.table:
        emit(state, ({"field": k, "value": v} for k, v in record.items()), ["field", "value"])
    else:
        emit(state, [record], list(record))


def _models(items: Iterable[Any]) -> Iterator[dict[str, Any]]:
    return (_plain(i) for i in items)


# --- connection --------------------------------------------------------------------------------------------------


@app.command()
def login(ctx: typer.Context) -> None:
    """Sign in (a browser login with PKCE; the refresh token goes to the OS keyring) and prove the token."""

    def work(client: CIDPClient, state: State) -> None:
        if isinstance(client.tokens, auth.BrowserLogin):
            client.tokens.login()
        next(iter(client.workspaces.list(limit=1)), None)  # the service accepts the token
        c = client.connection
        err.print(f"Signed in to {c.host} ({c.auth}{f', profile {c.profile}' if c.profile else ''}).", markup=False)

    _run(ctx, work)


@app.command()
def logout(ctx: typer.Context) -> None:
    """Forget the browser sign-in of this host and profile (its refresh token in the keyring)."""

    def work(client: CIDPClient, state: State) -> None:
        client.logout()
        err.print("Signed out.", markup=False)

    _run(ctx, work)


@app.command("config")
def show_config(ctx: typer.Context) -> None:
    """Where the CLI connects and what the deployment announces (GET /v1/config). Never a token."""

    def work(client: CIDPClient, state: State) -> None:
        c = client.connection
        record = {"host": c.host, "profile": c.profile, "auth": c.auth, "workspace": c.workspace,
                  **{k: v for k, v in _plain(client.config).items()}}  # fmt: skip
        emit_one(state, record)

    _run(ctx, work)


# --- workspaces and catalogs -------------------------------------------------------------------------------------


@workspaces_app.command("list")
def workspaces_list(
    ctx: typer.Context,
    external_id: Annotated[str | None, typer.Option(help="Only the workspace with this external id")] = None,
) -> None:
    """Workspaces you may see."""
    _run(ctx, lambda client, state: emit(state, _models(client.workspaces.list(external_id=external_id)),
                                         ["slug", "display_name", "home_catalog", "status", "external_id"]))  # fmt: skip


SlugArg = Annotated[str | None, typer.Argument(help="Default: the connection's workspace")]


@workspaces_app.command("get")
def workspaces_get(ctx: typer.Context, slug: SlugArg = None) -> None:
    """One workspace."""
    _run(ctx, lambda client, state: emit_one(state, _plain(client.workspace(slug).fetch())))


@catalogs_app.command("list")
def catalogs_list(ctx: typer.Context) -> None:
    """The workspace's catalogs: its home first, then the bound and open ones."""
    _run(ctx, lambda client, state: emit(state, _models(client.workspace().catalogs()),
                                         ["name", "home", "binding", "isolation", "comment"]))  # fmt: skip


# --- schemas, tables, views --------------------------------------------------------------------------------------

CatalogOpt = Annotated[str | None, typer.Option("--catalog", "-c", help="Default: the workspace's home catalog")]


def _catalog(client: CIDPClient, catalog: str | None) -> tuple[str, str]:
    ws = client.workspace()
    return ws.slug, catalog or ws.home_catalog


@schemas_app.command("list")
def schemas_list(ctx: typer.Context, catalog: CatalogOpt = None) -> None:
    """Schemas in a catalog."""

    def work(client: CIDPClient, state: State) -> None:
        slug, cat = _catalog(client, catalog)
        emit(state, _models(client.schemas.list(slug, cat)), ["full_name"])

    _run(ctx, work)


@tables_app.command("list")
def tables_list(ctx: typer.Context, schema: str, catalog: CatalogOpt = None) -> None:
    """Tables in a schema."""

    def work(client: CIDPClient, state: State) -> None:
        slug, cat = _catalog(client, catalog)
        emit(state, _models(client.tables.list(slug, cat, schema)), ["full_name"])

    _run(ctx, work)


def _split(name: str) -> tuple[str, str]:
    schema, sep, table = name.rpartition(".")
    if not sep or not schema or not table:
        raise typer.BadParameter("give schema.table", param_hint="NAME")
    return schema, table


@tables_app.command("get")
def tables_get(ctx: typer.Context, name: Annotated[str, typer.Argument(help="schema.table")],
               catalog: CatalogOpt = None) -> None:  # fmt: skip
    """A table's columns (or, with --output json, everything the service tells)."""
    schema, table = _split(name)

    def work(client: CIDPClient, state: State) -> None:
        slug, cat = _catalog(client, catalog)
        info = client.tables.get(slug, cat, schema, table)
        if state.output is Output.table:
            emit(state, _models(info.columns), ["name", "type_text", "nullable", "classification", "comment"])
        else:
            emit_one(state, _plain(info))

    _run(ctx, work)


@views_app.command("list")
def views_list(ctx: typer.Context, schema: str, catalog: CatalogOpt = None) -> None:
    """Views in a schema."""

    def work(client: CIDPClient, state: State) -> None:
        slug, cat = _catalog(client, catalog)
        emit(state, _models(client.views.list(slug, cat, schema)), ["full_name"])

    _run(ctx, work)


# --- SQL ---------------------------------------------------------------------------------------------------------


@app.command()
def sql(
    ctx: typer.Context,
    text: Annotated[str | None, typer.Argument(help="The statement; '-' or none with --file reads it elsewhere")] = None,
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Read the statement from a file ('-': stdin)")] = None,
    engine: Annotated[str, typer.Option(help="sqe or spark")] = "sqe",
    catalog: CatalogOpt = None,
    schema: Annotated[str | None, typer.Option("--schema", "-s")] = None,
    limit: Annotated[int | None, typer.Option("--limit", help="Rows the service keeps at most")] = None,
) -> None:  # fmt: skip
    """Run one statement as you (asynchronous statements, A3) and print its rows. Ctrl-C cancels it."""
    if file is not None and text not in (None, "-"):
        raise typer.BadParameter("give the statement or --file, not both")
    if file is not None:
        statement = sys.stdin.read() if str(file) == "-" else file.read_text()
    elif text in (None, "-"):
        statement = sys.stdin.read()
    else:
        statement = text
    if not statement.strip():
        raise typer.BadParameter("the statement is empty")

    def work(client: CIDPClient, state: State) -> None:
        session = client.workspace().session(engine=engine, catalog=catalog, schema=schema)
        result = session.sql(statement, row_limit=limit)
        try:
            columns = result.columns  # waits; StatementFailed unless it succeeded
            emit(state, (dict(zip(columns, row, strict=False)) for row in result.rows()), columns)
        except KeyboardInterrupt:
            if result.state in ("PENDING", "RUNNING"):
                result.cancel()
            err.print(f"Cancelled statement {result.id}.", markup=False)
            raise typer.Exit(130) from None
        manifest = result.info.manifest
        if manifest is not None and manifest.truncated:
            err.print(f"The result was cut at {manifest.row_count} rows (the service's cap or --limit).", markup=False)

    _run(ctx, work)


# --- jobs --------------------------------------------------------------------------------------------------------

RUN_COLUMNS = ["run_id", "number", "trigger", "status", "run_as", "started_at", "finished_at", "error"]


@jobs_app.command("list")
def jobs_list(ctx: typer.Context, project: str) -> None:
    """Deployed jobs of a project."""
    _run(ctx, lambda client, state: emit(state, _models(client.jobs.list(client.workspace().slug, project)),
                                         ["name", "enabled", "schedule", "run_as", "tasks", "next_fire_at"]))  # fmt: skip


def _parameters(values: Sequence[str], hint: str = "--param") -> dict[str, str]:
    params: dict[str, str] = {}
    for v in values:
        key, sep, value = v.partition("=")
        if not sep or not key:
            raise typer.BadParameter(f"{v!r}: give key=value", param_hint=hint)
        params[key] = value
    return params


@jobs_app.command("run")
def jobs_run(
    ctx: typer.Context,
    project: str,
    job: str,
    param: Annotated[list[str] | None, typer.Option("--param", "-P", help="key=value (repeatable)")] = None,
    wait: Annotated[bool, typer.Option("--wait", help="Wait until the run ends; fail unless it succeeded")] = False,
    poll: Annotated[float, typer.Option(help="Seconds between reads while waiting, besides the change stream")] = 5.0,
) -> None:  # fmt: skip
    """Run a job now, as its identity (the deployer's consent or the project's service principal)."""
    params = _parameters(param or [])

    def work(client: CIDPClient, state: State) -> None:
        slug = client.workspace().slug
        run = client.jobs.run_now(slug, project, job, job_parameters=params or None)
        _job_run_done(client, state, slug, project, job, run, wait, poll)

    _run(ctx, work)


def _job_run_done(client: CIDPClient, state: State, slug: str, project: str, job: str, run: Any, wait: bool,
                  poll: float) -> None:  # fmt: skip
    """Print a job run; with ``wait``, once it ended, and exit 9 unless it succeeded."""
    if wait and run.status in JOB_OPEN:
        # On the caller's change stream, with a read every --poll seconds whatever it does (C18.3).
        run = client.jobs.wait_run(slug, project, job, run.run_id, interval=poll)
    emit_one(state, {k: v for k, v in _plain(run).items() if k != "tasks"})
    if wait and run.status != "succeeded":
        err.print(f"Run {run.number} ended {run.status}.", markup=False)
        raise typer.Exit(9)


@jobs_app.command("runs")
def jobs_runs(ctx: typer.Context, project: str, job: str,
              limit: Annotated[int, typer.Option(help="The newest runs to show")] = 20) -> None:  # fmt: skip
    """A job's runs, newest first."""

    def work(client: CIDPClient, state: State) -> None:
        runs = client.jobs.runs(client.workspace().slug, project, job, limit=limit)
        emit(state, itertools.islice(_models(runs), limit), RUN_COLUMNS)

    _run(ctx, work)


WaitOpt = Annotated[bool, typer.Option("--wait", help="Wait until the run ends; fail unless it succeeded")]
PollOpt = Annotated[float, typer.Option(help="Seconds between reads while waiting, besides the change stream")]
YesOpt = Annotated[bool, typer.Option("--yes", "-y", help="Do it without asking")]


@jobs_app.command("retry")
def jobs_retry(ctx: typer.Context, project: str, job: str, run_id: str, wait: WaitOpt = False,
               poll: PollOpt = 5.0) -> None:  # fmt: skip
    """A new run of a failed run's failed tasks and what depends on them."""

    def work(client: CIDPClient, state: State) -> None:
        slug = client.workspace().slug
        run = client.jobs.retry_run(slug, project, job, run_id)
        _job_run_done(client, state, slug, project, job, run, wait, poll)

    _run(ctx, work)


@jobs_app.command("deploy")
def jobs_deploy(ctx: typer.Context, project: str,
                target: Annotated[str | None, typer.Option(help="A target of project.yml")] = None) -> None:  # fmt: skip
    """Deploy the project's jobs from its default branch, as you. With errors nothing changes (exit 1)."""

    def work(client: CIDPClient, state: State) -> None:
        result = client.jobs.deploy(client.workspace().slug, project, target=target)
        emit_one(state, _plain(result))
        if result.errors:
            err.print(f"Not deployed: {len(result.errors)} error(s).", markup=False)
            raise typer.Exit(1)

    _run(ctx, work)


# --- confirmation ------------------------------------------------------------------------------------------------


def _interactive() -> bool:
    """A person at a terminal who can answer a question (tests replace it)."""
    return sys.stdin.isatty()


def _confirm(what: str, yes: bool) -> None:
    """A destructive call goes on with --yes, or when a person at a terminal says yes. Without a terminal and
    without --yes it is refused with exit 2 (a usage error: the call lacks --yes); a "no" ends with exit 1."""
    if yes:
        return
    if not _interactive():
        err.print(f"Refused: {what} needs --yes (there is no terminal to ask).", markup=False)
        raise typer.Exit(2)
    if not typer.confirm(f"{what}?", default=False, err=True):
        err.print("Not done.", markup=False)
        raise typer.Exit(1)


# --- api: any operation (design CC1) -----------------------------------------------------------------------------

# Operations whose answer is a server-sent stream: ``api call`` would wait for its end; the curated command reads it.
STREAMS: dict[str, str] = {
    "me_events": "use `cidp events [--since ID]` or the SDK's Me.events()",
    "projects_runs_logs": "use `cidp runs logs PROJECT RUN [--follow]`",
    "quality_runs_run_all": "use the data UI or the SDK's Quality.run() per table",
}
# Operations whose request body is a raw file, not JSON (sent as --body @file, streamed).
RAW_BODIES = frozenset({"ingest_uploads_create", "volumes_files_upload"})
_PARAM = re.compile(r"{(\w+)}")


def _operation(operation_id: str) -> tuple[str, str, str, str]:
    try:
        return OPERATIONS[operation_id]
    except KeyError:
        _fail(ConfigError(f"No public operation {operation_id!r}; `cidp api list` shows them",
                          code="unknown_operation"))  # fmt: skip


def _sdk_method(operation_id: str) -> str | None:
    """The SDK method of an operation, as ``Class.method``."""
    for name in dir(services):
        cls = getattr(services, name)
        if isinstance(cls, type) and issubclass(cls, services._Service):
            for attr, fn in vars(cls).items():
                if getattr(fn, "operation", None) == operation_id:
                    return f"{name}.{attr}"
    return None


def _fill(template: str, values: Mapping[str, str], workspace: str | None) -> str:
    """The path with its parameters filled, each quoted as one segment. ``workspace`` defaults to the
    connection's. An unknown or missing name is a ConfigError (exit 3)."""
    names = _PARAM.findall(template)
    unknown = sorted(set(values) - set(names))
    if unknown:
        takes = ", ".join(names) or "none"
        raise ConfigError(f"No path parameter {', '.join(unknown)}; this operation takes: {takes}",
                          code="unknown_parameter")  # fmt: skip
    filled = dict(values)
    if "workspace" in names and not filled.get("workspace") and workspace:
        filled["workspace"] = workspace
    missing = [n for n in names if not filled.get(n)]
    if missing:
        raise ConfigError(f"Missing path parameter {', '.join(missing)}: give -p {missing[0]}=VALUE",
                          code="missing_parameter")  # fmt: skip
    return _PARAM.sub(lambda m_: services._p(filled[m_.group(1)])[1:], template)


def _query(values: Sequence[str]) -> dict[str, Any]:
    query: dict[str, Any] = {}
    for v in values:
        key, sep, value = v.partition("=")
        if not sep or not key:
            raise typer.BadParameter(f"{v!r}: give name=value", param_hint="--query")
        query[key] = [*query[key], value] if isinstance(query.get(key), list) else (
            [query[key], value] if key in query else value)  # fmt: skip
    return query


def _json_body(body: str) -> Any:
    if body == "-":
        text = sys.stdin.read()
    elif body.startswith("@"):
        try:
            text = Path(body[1:]).read_text()
        except OSError as e:
            raise typer.BadParameter(f"cannot read {body[1:]} ({type(e).__name__})", param_hint="--body") from None
    else:
        text = body
    try:
        return json.loads(text)
    except ValueError:
        raise typer.BadParameter("not JSON (give JSON, @file or - for stdin)", param_hint="--body") from None


def _print_json(state: State, data: Any) -> None:
    """JSON as the service answered it; with --output jsonl a listing's items one per line."""
    if state.output is Output.jsonl:
        items = data["items"] if isinstance(data, dict) and isinstance(data.get("items"), list) else [data]
        for item in items:
            typer.echo(json.dumps(item, default=str))
    else:
        typer.echo(json.dumps(data, default=str, indent=2))


def _write_bytes(data: bytes, to: Path | None) -> None:
    """Bytes to a file, or as they are to stdout (never through rich)."""
    if to is not None:
        to.write_bytes(data)
        err.print(f"Wrote {len(data)} bytes to {to}.", markup=False)
    else:
        stream = typer.get_binary_stream("stdout")
        stream.write(data)
        stream.flush()


@api_app.command("list")
def api_list(
    ctx: typer.Context,
    service: Annotated[str | None, typer.Option(help="Only this service (sql, catalog, projects, jobs, ...)")] = None,
    level: Annotated[str | None, typer.Option(help="stable or preview")] = None,
) -> None:  # fmt: skip
    """Every public operation of API v1: its id, method, path, stability and service."""
    rows = [{"operation_id": k, "method": m_, "path": p, "level": lv, "service": sv}
            for k, (m_, p, lv, sv) in sorted(OPERATIONS.items(), key=lambda kv: (kv[1][3], kv[0]))
            if (service is None or sv == service) and (level is None or lv == level)]  # fmt: skip
    emit(ctx.obj, rows, ["operation_id", "method", "path", "level", "service"])


@api_app.command("describe")
def api_describe(ctx: typer.Context, operation_id: str) -> None:
    """One operation: its path parameters, its body, and the SDK method or curated command for it."""
    method, path, level, service = _operation(operation_id)
    record = {
        "operation_id": operation_id, "method": method, "path": f"/api/data/v1{path}", "level": level,
        "service": service, "path_parameters": _PARAM.findall(path),
        "body": "a raw file (--body @FILE)" if operation_id in RAW_BODIES else (
            "JSON (--body)" if method in ("POST", "PUT", "PATCH") else None),
        "confirm": "--yes or a terminal" if method == "DELETE" else None,
        "stream": STREAMS.get(operation_id), "sdk": _sdk_method(operation_id),
        "not_in_sdk": services.NOT_IN_SDK.get(operation_id),
    }  # fmt: skip
    emit_one(ctx.obj, {k: v for k, v in record.items() if v not in (None, [])})


@api_app.command("call")
def api_call(
    ctx: typer.Context,
    operation_id: str,
    path_param: Annotated[list[str] | None, typer.Option("--path-param", "-p", help="name=value (repeatable)")] = None,
    query: Annotated[list[str] | None, typer.Option("--query", "-q", help="name=value (repeatable)")] = None,
    body: Annotated[str | None, typer.Option("--body", "-b", help="JSON, @FILE or - (stdin)")] = None,
    idempotency_key: Annotated[str | None, typer.Option("--idempotency-key", help="Repeat-safe writes")] = None,
    if_match: Annotated[str | None, typer.Option("--if-match", help="The ETag the change is based on")] = None,
    accept: Annotated[str | None, typer.Option("--accept", help="Another answer type (text/csv, ...)")] = None,
    to: Annotated[Path | None, typer.Option("--out", help="Write a non-JSON answer to this file")] = None,
    yes: YesOpt = False,
) -> None:  # fmt: skip
    """Call one operation as you, through the SDK's session: its sign-in, errors and exit codes. Prints the JSON
    answer (nothing for 204); a DELETE needs --yes or a "yes" at a terminal. The workspace defaults to the
    connection's."""
    method, template, level, _ = _operation(operation_id)
    if operation_id in STREAMS:
        _fail(ConfigError(f"{operation_id} answers a server-sent stream: {STREAMS[operation_id]}",
                          code="stream_operation"))  # fmt: skip
    values = _parameters(path_param or [], "--path-param")
    params = _query(query or [])

    def work(client: CIDPClient, state: State) -> None:
        path = _fill(template, values, client.connection.workspace)
        if method == "DELETE":
            _confirm(f"{method} /api/data/v1{path}", yes)
        if level == "preview" and operation_id not in services._warned:
            services._warned.add(operation_id)
            err.print(f"warning: {operation_id} is a preview operation of the data API: it may change in a minor "
                      "release (see the CHANGELOG)", markup=False)  # fmt: skip
        headers: dict[str, str] = {**(services._key(idempotency_key) or {})}
        if if_match:
            headers["If-Match"] = if_match
        if accept:
            headers["Accept"] = accept
        payload: Any = None
        content: Any = None
        if body is not None and operation_id in RAW_BODIES:
            if body.startswith("@"):
                handle = Path(body[1:]).open("rb")
                ctx.call_on_close(handle.close)
                content, raw_headers = raw_body(handle)
            else:
                content, raw_headers = raw_body(sys.stdin.buffer.read() if body == "-" else body.encode())
            headers.update(raw_headers)
        elif body is not None:
            payload = _json_body(body)
        r = client._http.call(method, path, params=params, json=payload, content=content, headers=headers)
        if r.status_code == 204 or not r.content:
            return
        kind = r.headers.get("content-type", "").split(";")[0].strip()
        if kind == "application/json" or kind.endswith("+json"):
            _print_json(state, r.json())
        else:
            _write_bytes(r.content, to)

    _run(ctx, work)


# --- projects and their runs -------------------------------------------------------------------------------------

PROJECT_COLUMNS = ["slug", "name", "owner_group", "default_branch", "git_url", "personal"]
PROJECT_RUN_COLUMNS = ["run_id", "action", "branch", "path", "status", "started_by", "created_at", "finished_at",
                       "error"]  # fmt: skip


@projects_app.command("list")
def projects_list(ctx: typer.Context,
                  limit: Annotated[int | None, typer.Option(help="At most this many")] = None) -> None:  # fmt: skip
    """Projects of the workspace you may see."""

    def work(client: CIDPClient, state: State) -> None:
        found = _models(client.projects.list(client.workspace().slug))
        emit(state, itertools.islice(found, limit) if limit else found, PROJECT_COLUMNS)

    _run(ctx, work)


@projects_app.command("get")
def projects_get(ctx: typer.Context, project: str) -> None:
    """One project."""
    _run(ctx, lambda client, state: emit_one(state, _plain(client.projects.get(client.workspace().slug, project))))


@projects_app.command("create")
def projects_create(
    ctx: typer.Context,
    project: Annotated[str, typer.Argument(help="The new project's slug")],
    name: Annotated[str | None, typer.Option(help="Default: the slug")] = None,
    description: Annotated[str | None, typer.Option()] = None,
    owner_group: Annotated[str | None, typer.Option(help="The group that owns it")] = None,
    git_url: Annotated[str | None, typer.Option(help="Clone this repository")] = None,
    branch: Annotated[str | None, typer.Option(help="The branch to clone (default main)")] = None,
    template: Annotated[str | None, typer.Option(help="Start from this template")] = None,
) -> None:  # fmt: skip
    """A project, as you: empty, from a template, or a clone of a git repository."""

    def work(client: CIDPClient, state: State) -> None:
        created = client.projects.create(client.workspace().slug, project, name=name, description=description,
                                         owner_group=owner_group, git_url=git_url, branch=branch,
                                         template=template)  # fmt: skip
        emit_one(state, _plain(created))

    _run(ctx, work)


@projects_app.command("delete")
def projects_delete(ctx: typer.Context, project: str, yes: YesOpt = False) -> None:
    """Delete a project and its files (asks first, or --yes)."""

    def work(client: CIDPClient, state: State) -> None:
        slug = client.workspace().slug
        _confirm(f"Delete project {project} of {slug} and its files", yes)
        client.projects.delete(slug, project, confirm=project)
        err.print(f"Deleted project {project}.", markup=False)

    _run(ctx, work)


@runs_app.command("start")
def runs_start(
    ctx: typer.Context,
    project: str,
    action: Annotated[str, typer.Argument(help="As `cidp api call projects_actions_list` names it (dbt.build, ...)")],
    path: Annotated[str, typer.Option("--path", help="The file the action runs on")],
    branch: Annotated[str | None, typer.Option(help="Default: the project's default branch")] = None,
    selection: Annotated[str | None, typer.Option(help="dbt's --select")] = None,
    namespace: Annotated[str | None, typer.Option(help="The schema it writes to")] = None,
    catalog: CatalogOpt = None,
    param: Annotated[list[str] | None, typer.Option("--param", "-P", help="key=value (repeatable)")] = None,
    wait: WaitOpt = False,
    poll: PollOpt = 5.0,
) -> None:  # fmt: skip
    """Run an action on a project's file as you (dbt, a Python script, SQL)."""
    params = _parameters(param or [])

    def work(client: CIDPClient, state: State) -> None:
        slug = client.workspace().slug
        on = branch or client.projects.get(slug, project).default_branch
        result = client.projects.run_action(slug, project, action, on, path, selection=selection,
                                            namespace=namespace, params=params or None, catalog=catalog)  # fmt: skip
        run = result.run
        if run is None:  # an action that answers at once (sql.run, sql.explain)
            emit_one(state, _plain(result))
            return
        if wait and run.status not in services.PROJECT_RUN_ENDED:
            run = client.projects.wait_run(slug, project, run.run_id, interval=poll)
        emit_one(state, _plain(run))
        if wait and run.status != "succeeded":
            err.print(f"Run {run.run_id} ended {run.status}.", markup=False)
            raise typer.Exit(9)

    _run(ctx, work)


@runs_app.command("list")
def runs_list(ctx: typer.Context, project: str,
              branch: Annotated[str | None, typer.Option(help="Only this branch")] = None,
              limit: Annotated[int, typer.Option(help="The newest runs to show")] = 20) -> None:  # fmt: skip
    """A project's runs, newest first."""

    def work(client: CIDPClient, state: State) -> None:
        found = client.projects.runs(client.workspace().slug, project, branch=branch, limit=limit)
        emit(state, itertools.islice(_models(found), limit), PROJECT_RUN_COLUMNS)

    _run(ctx, work)


@runs_app.command("get")
def runs_get(ctx: typer.Context, project: str, run_id: str) -> None:
    """One run."""
    _run(ctx, lambda client, state: emit_one(state, _plain(client.projects.run(client.workspace().slug, project,
                                                                                run_id))))  # fmt: skip


@runs_app.command("cancel")
def runs_cancel(ctx: typer.Context, project: str, run_id: str) -> None:
    """Cancel a run (yours, or as CAN MANAGE); an ended run answers as it is."""
    _run(ctx, lambda client, state: emit_one(state, _plain(client.projects.cancel_run(client.workspace().slug,
                                                                                       project, run_id))))  # fmt: skip


@runs_app.command("logs")
def runs_logs(
    ctx: typer.Context,
    project: str,
    run_id: str,
    follow: Annotated[bool, typer.Option("--follow", "-f", help="Print new lines until the run ends")] = False,
    after: Annotated[int, typer.Option(help="Start after this line number")] = 0,
) -> None:  # fmt: skip
    """A run's log lines. Without --follow it stops once the service has nothing new; with it, when the run ends
    (exit 9 unless it succeeded). --output jsonl prints each line and the end as JSON."""

    def work(client: CIDPClient, state: State) -> None:
        try:
            for event in client.projects.logs(client.workspace().slug, project, run_id, after=after, follow=follow):
                if state.output in (Output.jsonl, Output.json):
                    typer.echo(json.dumps(event, default=str))
                elif event["event"] == "line":
                    typer.echo(event["line"], err=event.get("stream") == "stderr")
                if event["event"] == "end":
                    if event["status"] != "succeeded":
                        err.print(f"Run {run_id} ended {event['status']}.", markup=False)
                        raise typer.Exit(9 if follow else 0)
        except KeyboardInterrupt:
            raise typer.Exit(130) from None

    _run(ctx, work)


# --- grants (Permissions) ----------------------------------------------------------------------------------------

SecurableArg = Annotated[str, typer.Argument(help="catalog, schema, table or view")]
FullNameArg = Annotated[str, typer.Argument(help="catalog[.schema[.name]]")]


def _grant_rows(info: Any) -> Iterator[dict[str, Any]]:
    for a in [*info.privilege_assignments, *(info.inherited_assignments or [])]:
        yield {"principal": a.principal, "privileges": ", ".join(a.privileges), "inherited_from": a.inherited_from}


@grants_app.command("list")
def grants_list(ctx: typer.Context, securable_type: SecurableArg, full_name: FullNameArg) -> None:
    """Who holds what on a securable, its own grants and the inherited ones (--output json: everything)."""

    def work(client: CIDPClient, state: State) -> None:
        info = client.permissions.get(client.workspace().slug, securable_type, full_name)
        if state.output is Output.table:
            emit(state, _grant_rows(info), ["principal", "privileges", "inherited_from"])
        else:
            emit_one(state, _plain(info))

    _run(ctx, work)


def _grant_change(ctx: typer.Context, securable_type: str, full_name: str, principal: str, privileges: list[str],
                  change: str) -> None:  # fmt: skip
    def work(client: CIDPClient, state: State) -> None:
        info = client.permissions.update(client.workspace().slug, securable_type, full_name,
                                         [{"principal": principal, change: [p.upper() for p in privileges]}])  # fmt: skip
        emit(state, _grant_rows(info), ["principal", "privileges", "inherited_from"])

    _run(ctx, work)


PrivilegesArg = Annotated[list[str], typer.Argument(help="SELECT, MODIFY, USE SCHEMA, ... (quote ones with spaces)")]


@grants_app.command("add")
def grants_add(ctx: typer.Context, securable_type: SecurableArg, full_name: FullNameArg, principal: str,
               privileges: PrivilegesArg) -> None:  # fmt: skip
    """Grant privileges to a group, as you (you need MANAGE on the securable)."""
    _grant_change(ctx, securable_type, full_name, principal, privileges, "add")


@grants_app.command("remove")
def grants_remove(ctx: typer.Context, securable_type: SecurableArg, full_name: FullNameArg, principal: str,
                  privileges: PrivilegesArg) -> None:  # fmt: skip
    """Revoke privileges from a group, as you."""
    _grant_change(ctx, securable_type, full_name, principal, privileges, "remove")


# --- volumes -----------------------------------------------------------------------------------------------------

VolumeArg = Annotated[str, typer.Argument(help="schema.volume")]


@volumes_app.command("list")
def volumes_list(ctx: typer.Context, schema: str, catalog: CatalogOpt = None) -> None:
    """Volumes in a schema."""

    def work(client: CIDPClient, state: State) -> None:
        slug, cat = _catalog(client, catalog)
        emit(state, _models(client.volumes.list(slug, cat, schema)), ["full_name", "owner_group", "comment"])

    _run(ctx, work)


@volumes_app.command("ls")
def volumes_ls(ctx: typer.Context, volume: VolumeArg,
               path: Annotated[str | None, typer.Argument(help="A folder (default: the root)")] = None,
               catalog: CatalogOpt = None) -> None:  # fmt: skip
    """Files and folders in a volume."""
    schema, name = _split(volume)

    def work(client: CIDPClient, state: State) -> None:
        slug, cat = _catalog(client, catalog)
        emit(state, _models(client.volumes.files(slug, cat, schema, name, path=path)),
             ["name", "kind", "size_bytes", "modified_at", "path"])  # fmt: skip

    _run(ctx, work)


@volumes_app.command("put")
def volumes_put(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True, help="The local file")],
    volume: VolumeArg,
    path: Annotated[str | None, typer.Argument(help="Where in the volume (default: the file's name)")] = None,
    overwrite: Annotated[bool, typer.Option(help="Replace a file that is there")] = False,
    catalog: CatalogOpt = None,
) -> None:  # fmt: skip
    """Upload a file into a volume, streamed; it is scanned before it is kept."""
    schema, name = _split(volume)

    def work(client: CIDPClient, state: State) -> None:
        slug, cat = _catalog(client, catalog)
        with file.open("rb") as handle:
            stored = client.volumes.upload(slug, cat, schema, name, path or file.name, handle, overwrite=overwrite)
        emit_one(state, _plain(stored))

    _run(ctx, work)


@volumes_app.command("get")
def volumes_get(
    ctx: typer.Context,
    volume: VolumeArg,
    path: Annotated[str, typer.Argument(help="The file in the volume")],
    to: Annotated[Path | None, typer.Option("--out", help="Write it here (default: stdout)")] = None,
    catalog: CatalogOpt = None,
) -> None:  # fmt: skip
    """Download a file of a volume."""
    schema, name = _split(volume)

    def work(client: CIDPClient, state: State) -> None:
        slug, cat = _catalog(client, catalog)
        _write_bytes(client.volumes.download(slug, cat, schema, name, path), to)

    _run(ctx, work)


# --- ingest (Uploads) --------------------------------------------------------------------------------------------

FORMATS = {".parquet": "parquet", ".csv": "csv", ".json": "json", ".jsonl": "json", ".ndjson": "json"}


@app.command()
def ingest(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True, help="parquet, csv or json")],
    table: Annotated[str, typer.Option("--table", "-t", help="schema.table in --catalog")],
    catalog: CatalogOpt = None,
    format: Annotated[str | None, typer.Option(help="parquet, csv or json (default: from the file's extension)")] = None,
    mode: Annotated[str, typer.Option(help="create or append")] = "create",
    delimiter: Annotated[str | None, typer.Option(help="csv: the delimiter")] = None,
    header: Annotated[bool | None, typer.Option("--header/--no-header", help="csv: a header row")] = None,
    shared: Annotated[bool, typer.Option("--shared", help="Stage it for the workspace, not only for you")] = False,
    again: Annotated[bool, typer.Option("--again", help="Load a file already loaded into this table")] = False,
) -> None:  # fmt: skip
    """Load a file into a table as you: upload (streamed, scanned, staged), then load. Both answer when done."""
    schema, name = _split(table)
    kind = format or FORMATS.get(file.suffix.lower())
    if kind is None:
        raise typer.BadParameter("give --format (parquet, csv or json)", param_hint="--format")

    def work(client: CIDPClient, state: State) -> None:
        slug = client.workspace().slug
        with file.open("rb") as handle:
            upload = client.uploads.create(slug, handle, kind, delimiter=delimiter, header=header,
                                           scope="workspace" if shared else None)  # fmt: skip
        if upload.state != "STAGED":
            err.print(f"Upload {upload.upload_id} is {upload.state}"
                      f"{f' ({upload.error_code})' if upload.error_code else ''}; nothing was loaded.",
                      markup=False)  # fmt: skip
            raise typer.Exit(1)
        loaded = client.uploads.load(
            slug, upload.upload_id, schema, name, catalog=catalog, mode=mode, confirm=again or None
        )
        emit_one(state, _plain(loaded))
        if loaded.state != "LOADED":
            raise typer.Exit(1)

    _run(ctx, work)


# --- statements --------------------------------------------------------------------------------------------------

STATEMENT_FIELDS = ("id", "state", "engine", "catalog", "schema", "submitted_at", "finished_at", "error")


def _statement(state: State, info: Any) -> None:
    record = _plain(info)
    emit_one(state, {k: record.get(k) for k in STATEMENT_FIELDS} if state.output is Output.table else record)


@statements_app.command("submit")
def statements_submit(
    ctx: typer.Context,
    text: Annotated[str, typer.Argument(help="The statement ('-': stdin)")],
    engine: Annotated[str, typer.Option(help="sqe or spark")] = "sqe",
    catalog: CatalogOpt = None,
    schema: Annotated[str | None, typer.Option("--schema", "-s")] = None,
    wait_timeout: Annotated[int, typer.Option(help="Seconds the service holds the answer (0 to 50)")] = 0,
    row_limit: Annotated[int | None, typer.Option(help="Rows the service keeps at most")] = None,
    tag: Annotated[str | None, typer.Option(help="A query tag")] = None,
) -> None:  # fmt: skip
    """Submit a statement and print its id and state; it goes on in the service."""
    sql_text = sys.stdin.read() if text == "-" else text

    def work(client: CIDPClient, state: State) -> None:
        info = client.statements.submit(client.workspace().slug, sql_text, engine=engine, catalog=catalog,
                                        schema=schema, wait_timeout=wait_timeout, row_limit=row_limit,
                                        query_tag=tag)  # fmt: skip
        _statement(state, info)

    _run(ctx, work)


@statements_app.command("get")
def statements_get(ctx: typer.Context, statement_id: str,
                   wait_timeout: Annotated[int | None, typer.Option(help="Wait up to this many seconds")] = None,
                   ) -> None:  # fmt: skip
    """A statement's state."""
    _run(ctx, lambda client, state: _statement(state, client.statements.get(client.workspace().slug, statement_id,
                                                                             wait_timeout=wait_timeout)))  # fmt: skip


@statements_app.command("cancel")
def statements_cancel(ctx: typer.Context, statement_id: str) -> None:
    """Cancel a statement."""
    _run(ctx, lambda client, state: _statement(state, client.statements.cancel(client.workspace().slug,
                                                                                statement_id)))  # fmt: skip


@statements_app.command("result")
def statements_result(ctx: typer.Context, statement_id: str) -> None:
    """A statement's rows, every page (waits while it runs; exit 9 unless it succeeded)."""
    from cidp_sdk.session import Result

    def work(client: CIDPClient, state: State) -> None:
        slug = client.workspace().slug
        result = Result(client.statements, slug, client.statements.get(slug, statement_id))
        columns = result.columns
        emit(state, (dict(zip(columns, row, strict=False)) for row in result.rows()), columns)

    _run(ctx, work)


# --- events ------------------------------------------------------------------------------------------------------


@app.command()
def events(
    ctx: typer.Context,
    since: Annotated[str | None, typer.Option(help="Resume after this event id (Last-Event-ID)")] = None,
) -> None:  # fmt: skip
    """Your changes as they commit (GET /me/events), one JSON line each, until Ctrl-C. A dropped stream is resumed
    after the last id; a reset (changes may be missed) prints {"event": "reset"}."""

    def work(client: CIDPClient, state: State) -> None:
        stream = Follower(client._http)
        stream.last_id = since
        stream.start()
        opened = False
        try:
            while True:
                try:
                    message = stream.out.get(timeout=1.0)
                except queue.Empty:
                    continue
                if message.kind == "open" and not opened:
                    opened = True
                    err.print("Listening for your changes; Ctrl-C ends.", markup=False)
                elif message.kind == "change":
                    typer.echo(json.dumps({"event": "change", "id": message.id, "data": message.change}, default=str))
                elif message.kind == "reset":
                    err.print("The stream was reset: changes may have been missed.", markup=False)
                    typer.echo(json.dumps({"event": "reset"}))
                elif message.kind == "gone":
                    raise PermissionDenied("The service refuses the event stream (403 or 404)",
                                           code="events_unavailable")  # fmt: skip
        except KeyboardInterrupt:
            raise typer.Exit(130) from None
        finally:
            stream.stop()

    _run(ctx, work)

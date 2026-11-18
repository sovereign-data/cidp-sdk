# cidp-sdk

Python SDK and `cidp` command for CIDP, the cloud independent data platform: its data service's public API,
`/api/data/v1` (OpenSpec change `data-api-sdk`). Everything
runs as you: your token reaches the service and Polaris, so grants, masks, row filters and the audit always apply. No
engine runs locally.

```sh
# from a checkout of this repository (extras: [pandas], [iceberg], [cli])
uv add "cidp-sdk[cli] @ path/to/cidp-sdk"
pip install "path/to/cidp-sdk[cli]"
# or from a built wheel (make build)
pip install "dist/cidp_sdk-0.3.0-py3-none-any.whl[cli]"
```

## Connect

Settings come from arguments, then `CIDP_*` environment variables, then a profile, then the deployment's
`/v1/config`.

```toml
# ~/.cidp/connections.toml (chmod 600; CIDP_CONFIG_FILE moves it)
default_connection_name = "dev"

[dev]
host = "https://portal.example.org"
workspace = "sales"            # auth = "browser" (the default)

[ci]
host = "https://portal.example.org"
auth = "token_env"
token_env = "CI_TOKEN"         # the variable's name, never the token

[etl]
host = "https://portal.example.org"
auth = "client_credentials"
client_id = "svc-project-etl"  # the secret from CIDP_CLIENT_SECRET
```

- A profile with `token`, `secret` or `password`, or a file that group or others can read, is refused.
- The browser login uses code and PKCE over a loopback port. The refresh token is kept only in the OS keyring, or in
  memory with a warning when there is no keyring. `client.logout()` removes it.
- Environment: `CIDP_HOST`, `CIDP_PROFILE`, `CIDP_TOKEN`, `CIDP_CLIENT_ID`, `CIDP_CLIENT_SECRET`,
  `CIDP_WORKSPACE`.
- Tokens never appear in a `repr`, an exception or the `cidp_sdk` and `httpx` logs.

## Use

```python
from cidp_sdk import CIDPClient

with CIDPClient("dev") as client:
    ws = client.workspace()                     # the profile's workspace
    for schema in ws.catalog().schemas:         # catalog() without a name: the home catalog
        print(schema.full_name)
    region = ws.catalog().schema("tpch").table("region").fetch()

    session = ws.session(schema="tpch")
    with session.sql("SELECT * FROM region") as result:   # still open on exit: cancelled
        df = result.to_pandas()                 # or .collect(), .to_arrow(), .pages()

    nightly = ws.project("etl").job("nightly")
    run = nightly.run_now(day="mon")
    run = nightly.wait(run.run_id, timeout=3600)  # ended: succeeded, failed, cancelled, skipped or expired
    catalog = ws.iceberg()                      # pyiceberg RestCatalog on Polaris, vended credentials
```

- Every `stable` and `preview` operation of the v1 contract is a method of a service on the client:
  `client.workspaces`, `client.tables`, `client.statements`, `client.jobs`, `client.projects` and so on (one per
  resource). `services.NOT_IN_SDK` names the few left out and why (the machine ingest routes and the quality page's
  stream). `client.projects.logs(...)` reads a run's log lines as they come.
- A `preview` operation may still change: its first call in a process warns with `PreviewWarning`. Silence it with
  `warnings.filterwarnings("ignore", category=PreviewWarning)`.
- `client.versions` gives each service's version as the deployment states it (`/v1/config`).
- Listings are iterators that follow `next_cursor`.
- `client.jobs.wait_run(...)` and `client.projects.wait_run(...)` (or `JobRef.wait` and `ProjectRef.wait`) return a
  run once it has ended, whatever its result. They follow your change stream (`/v1/me/events`, with your own token),
  read the run when it changes, and read it every `interval` seconds (default 10) whatever the stream does. With a
  `timeout` they raise `WaitTimeout` (also a `TimeoutError`); the run goes on. A statement's `Result.wait` raises
  it too.
- Errors carry `code`, `status` and `request_id`. They are `InvalidParameter`, `Unauthenticated`, `PermissionDenied`,
  `NotFound`, `Conflict`, `TooManyRequests` (with `retry_after`), `Unavailable`, `StatementFailed` and `WaitTimeout`,
  all subclasses of `CIDPError`.

## Command line

The `cli` extra installs `cidp` (OpenSpec change `data-cli`): every command is a v1 call through the SDK, with
the same connection settings.

```sh
cidp login                                  # browser sign-in; the refresh token goes to the OS keyring
cidp -w sales tables list tpch -o csv
cidp sql "SELECT count(*) FROM tpch.region" # or -f query.sql, or stdin; Ctrl-C cancels the statement
cidp jobs run etl nightly -P day=mon --wait # exits 9 unless the run succeeded
```

Every public operation of the v1 contract is reachable with `cidp api` (OpenSpec change `data-cli-coverage`), the
way `databricks api` works. The operation list comes from the SDK's `_operations.py`:

```sh
cidp api list --service projects            # operation id, method, path, stability
cidp api describe tables_get                # its parameters and how to call it
cidp api call tables_get -p catalog=sales -p schema=tpch -p table=region
cidp api call saved_queries_create -b @query.json   # -b JSON, @file or - (stdin)
cidp api call volumes_files_upload -p catalog=sales -p schema=raw -p volume=docs -q path=a.csv -b @a.csv
                                              # a raw body (uploads) streams from the file
```

`-p` fills a path parameter (`workspace` defaults to the connection's), `-q` a query parameter. An unknown or
missing parameter exits 3, and so does a stream operation (`cidp api describe` names the command to use). `--idempotency-key`, `--if-match`, `--accept` and `--out` set what their names say. A
`DELETE` asks first; `--yes` skips the question, and without a terminal the call exits 2 unless `--yes` is given.

Curated commands for daily work:

```sh
cidp projects list|get|create|delete
cidp runs start etl dbt.build --path dbt_project.yml --wait   # also list, get, cancel
cidp runs logs etl <run-id> --follow     # stdout lines to stdout, stderr lines to stderr
cidp jobs deploy etl                     # exits 1 when the deploy has errors
cidp jobs retry etl nightly <run-id> --wait
cidp grants list catalog sales
cidp grants add schema sales.tpch SG-Analysts SELECT "USE SCHEMA"   # or remove
cidp volumes ls raw.docs                 # also list, put, get
cidp ingest orders.csv --table tpch.orders --mode append   # into the home catalog
cidp ingest orders.csv --table tpch.orders --catalog finance   # into another read-write catalog
cidp statements submit|get|cancel|result
cidp events --since <id>                 # your changes as they commit, until Ctrl-C
```

- `--output` (`-o`): `table` (default, at most 1,000 rows), `json`, `jsonl` or `csv`. Results go to stdout; notes
  and errors go to stderr.
- Exit codes: 2 usage, 3 configuration, 4 not signed in, 5 permission denied, 6 not found, 7 conflict, 8 too many
  requests, 9 statement or job run failed, 130 interrupted. Exit 2 is also an unconfirmed `DELETE` without a
  terminal.
- There is no option for a token or secret. Use `CIDP_TOKEN`, `CIDP_CLIENT_SECRET` or `cidp login`.
- Exit code 1: the command ran but what it asked for did not happen (a deploy with errors, an upload not staged or
  not loaded, a question answered no).

## Develop

```sh
make install          # uv sync --all-extras: a .venv with every extra, pytest and ruff
make test             # pytest
make lint             # ruff check + ruff format --check
make build            # sdist and wheel in dist/
```

- `contract/openapi-v1.json` is a copy of the data service's public contract (`services/data/openapi-v1.json` in
  ai-portal-data). `make contract` refreshes it from `../ai-portal-data` (`SERVICE_REPO=...` for another checkout).
- `_models.py` and `_operations.py` (each operation's method, path, stability and service) are generated from
  `contract/openapi-v1.json`: run `make sdk-models` and never edit them by hand. `make sdk-models-check` fails when
  they are stale.
- `tests/test_services.py` fails when a public operation has no method and is not in `NOT_IN_SDK`, when a method
  sends another method or path than its operation, or when `_operations.py` is stale.
- The contract test that runs the SDK against the real v1 app (`tests/test_sdk_dbx_migrator_contract.py`, dbx-migrator's
  team) needs the
  data service and its Postgres fixtures, so it stays in ai-portal-data.

## Changes

### 0.3.0

Renamed to CIDP (cloud independent data platform), with no aliases for the old names:

- package `portal-data-sdk` / `portal_data_sdk` is now `cidp-sdk` / `cidp_sdk`;
- `PortalClient` and `PortalError` are now `CIDPClient` and `CIDPError`;
- the `portal` command is now `cidp`;
- environment variables `PORTAL_*` are now `CIDP_*`;
- the profile file `~/.portal/connections.toml` is now `~/.cidp/connections.toml` (move it);
- the keyring service is now `cidp-sdk`: sign in again with `cidp login`.

Server-side names (the `portal-data-cli` client, `/api/data/v1`, the `portal.data.*` events) do not change.

## License

Apache License 2.0: see [LICENSE](LICENSE).

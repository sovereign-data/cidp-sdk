# Changelog

## Unreleased

- `outcome_unknown` (the data service's sql and jobs 1.7, data-outcome-unknown; ai-portal-data issue 758): callers
  can now receive it. It means the write may or may not have happened: check before you repeat it. The SDK raises
  `OutcomeUnknown` (a `CIDPError`, with `code`, `status`, `request_id` and the service's `cause`: `lost_answer`,
  `timeout` or `replica_lost`) for a 504 with that code (and ingest's `load_outcome_unknown`), for a statement that
  ended `FAILED` with it (before: `StatementFailed`), and from `raise_for_outcome(run)` for a job run whose
  `error_code` names it (`wait_run` still returns a run whatever its result). The SDK never sends such a request
  again. `cidp` exits 10 for it (before: 9 for a statement or a `jobs run --wait`, 1 otherwise).

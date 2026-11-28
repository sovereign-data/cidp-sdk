"""Models of the data service's public API v1, generated from openapi-v1.json.

Do not edit: `make sdk-models` writes this file (scripts/sdk_models.py). Unknown fields are kept and an enum
accepts values added within v1, so a newer service does not break this SDK.
"""

# contract sha256: 6ef3c048ef311933ab83c89fc13a4418dc111c2700bf4142a4e7111e246dcdcb
# ruff: noqa: E501

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ['AlertOut', 'AlertStatus', 'Alerts', 'AssignedTagOut', 'AuditEvents', 'AuditIngestOut', 'BundleEntryOut', 'BundleTargetOut', 'CatalogBindingInfo', 'CatalogBindingList', 'CatalogBindingUpdate', 'CatalogCreate', 'CatalogInfo', 'CatalogList', 'CatalogScope', 'CatalogUpdate', 'ChangeIn', 'CheckOut', 'ClassificationSuggestionOut', 'ClassificationSuggestions', 'ClassificationUpdate', 'ColumnInfo', 'ColumnQualityOut', 'ColumnRef', 'ColumnSchema', 'ColumnStatsOut', 'ConfigInfo', 'ConflictingMaskOut', 'ContractListItem', 'ContractOut', 'ContractPut', 'ContractStatusOut', 'DbtImportOut', 'DeadLetterOut', 'DeadLetters', 'Deliveries', 'DeliveryOut', 'DeploymentIn', 'DeploymentOut', 'DeploymentValidateIn', 'DeploymentValidateOut', 'DestinationOut', 'DestinationWrite', 'DestroyOut', 'DetectionRunOut', 'DigestOut', 'DigestWorkspace', 'DriftOut', 'ErrorInfo', 'EventDetail', 'EventOut', 'ExplainOut', 'ExportCheck', 'FileUsageList', 'FileUsageOut', 'FromDbt', 'GatewayAuditOut', 'GitCredentialOut', 'GitOAuthComplete', 'GitOAuthStartOut', 'GitProviderOut', 'GitProviders', 'GitToken', 'GlossaryImport', 'GlossaryTermCreate', 'GlossaryTermHistory', 'GlossaryTermStatus', 'GlossaryTermUpdate', 'GlossaryTerms', 'GovernanceChange', 'GovernanceChanges', 'GrantOut', 'GroupInfo', 'Groups', 'HistoryEntry', 'HistoryEntryList', 'IdentityRemovedOut', 'ImpactItemOut', 'ImpactOut', 'ImportOut', 'InactiveOut', 'InboxItem', 'InboxOut', 'IngestLedgerItem', 'IngestLedgerList', 'IngestLedgerSummary', 'IngestOut', 'ItemChangeOut', 'JobBuilderCheckIn', 'JobBuilderCheckOut', 'JobBuilderExportIn', 'JobBuilderExportOut', 'JobBuilderImportIn', 'JobBuilderImportOut', 'JobBuilderJobOut', 'JobEventPending', 'JobEventTriggerOut', 'JobEventTypeOut', 'JobForEachOut', 'JobGrantIn', 'JobGrantOut', 'JobInfo', 'JobList', 'JobPermissionsIn', 'JobPermissionsOut', 'JobRunEventOut', 'JobRunInfo', 'JobRunList', 'JobRunStatsOut', 'JobTaskOut', 'JobTaskRunInfo', 'JobUpdate', 'JobsConsentComplete', 'JobsConsentStartOut', 'JobsDeployOut', 'JobsIdentityOut', 'JobsProblemOut', 'JobsRevokedOut', 'JobsSummaryOut', 'LastDeliveryOut', 'Limits', 'LimitsOut', 'LineageColumnEdgeOut', 'LineageEdgeOut', 'LineageGraphOut', 'LineageJobOut', 'LineageNodeOut', 'LineageStatusOut', 'LinkOut', 'MaskChangeOut', 'MaskConflictOut', 'MaskOut', 'MeOut', 'MyGitCredentials', 'MySecrets', 'NodeQualityOut', 'NotificationsOut', 'OwnerOut', 'PermissionsChangeItem', 'PermissionsInfo', 'PermissionsOut', 'PermissionsUpdate', 'PreviewOut', 'PrincipalIn', 'PrincipalOut', 'PrivilegeAssignment', 'ProducerCreate', 'ProducerCreatedOut', 'ProducerOut', 'Producers', 'ProfileOut', 'ProfileSummaryOut', 'ProjectActionOut', 'ProjectActionResult', 'ProjectActionRun', 'ProjectActions', 'ProjectBranchCreate', 'ProjectBranchName', 'ProjectBranchOut', 'ProjectCommit', 'ProjectCommitCreate', 'ProjectCommitOut', 'ProjectCreate', 'ProjectCreated', 'ProjectDetail', 'ProjectDiff', 'ProjectDiffOut', 'ProjectDocsTicket', 'ProjectExplainOut', 'ProjectFileCreate', 'ProjectFileOut', 'ProjectFileSave', 'ProjectFiles', 'ProjectGrantIn', 'ProjectGrantOut', 'ProjectHead', 'ProjectHistory', 'ProjectInfo', 'ProjectLastRun', 'ProjectList', 'ProjectParamOut', 'ProjectPermissionsOut', 'ProjectPermissionsSet', 'ProjectPullOut', 'ProjectRunArtifact', 'ProjectRunInfo', 'ProjectRunList', 'ProjectScaffoldOut', 'ProjectTreeEntry', 'PropertyOut', 'QualityRunCreate', 'QualityRuns', 'QualitySummary', 'QueryEngine', 'QueryEngines', 'QueryItemOut', 'QueryOut', 'QueryStatsOut', 'RecentOut', 'RemoteBranch', 'RemoteBranches', 'RemovedOut', 'ResultManifest', 'ResultPage', 'RowFilterOut', 'RuleOut', 'RunCatalogScope', 'RunCatalogScopeInfo', 'RunNow', 'RunOut', 'RunScopeCapIn', 'RunScopeCapOut', 'RunSummaryOut', 'SampleColumn', 'SampleInfo', 'SavedQueryIn', 'SavedQueryList', 'SavedQueryOut', 'SavedQueryUpdate', 'SchemaCreate', 'SchemaInfo', 'SchemaList', 'SearchGroup', 'SearchHit', 'SearchOut', 'SearchResults', 'SearchTable', 'SearchTerm', 'SecretExplainOut', 'SecretGrantIn', 'SecretGrantOut', 'SecretOut', 'SecretPermissionsOut', 'SecretPermissionsUpdate', 'SecretRewrapOut', 'SecretScopeCreate', 'SecretScopeOut', 'SecretScopes', 'SecretUseOut', 'SecretValue', 'Secrets', 'SelectAdminMissing', 'SelectBackfillOut', 'SelectCatalog', 'SelectCoverageOut', 'SelectMissing', 'SessionPip', 'ShortSecretOut', 'ShortSecrets', 'SlaOut', 'SnapshotInfo', 'SnapshotList', 'SourceQualityOut', 'SparkOut', 'SqeOut', 'StatementColumn', 'StatementExecute', 'StatementExplain', 'StatementFailure', 'StatementInfo', 'StatementRows', 'StatementSubmit', 'StatementTranspile', 'StorageLocationIn', 'StorageLocationInfo', 'StorageLocationList', 'StorageLocationPatch', 'StrayOut', 'StraysOut', 'StraysRemove', 'SubjectEraseOut', 'SubjectExportOut', 'SuggestionOut', 'SuggestionSourceOut', 'SuggestionsApply', 'SuggestionsOut', 'SystemJobRunOut', 'SystemKernelOut', 'SystemOut', 'SystemRunOut', 'SystemTagOut', 'TableContracts', 'TableInfo', 'TableList', 'TableSummary', 'TableTermOut', 'TableTerms', 'TagOnColumnOut', 'TagOut', 'TagsOut', 'TemplateOut', 'TemplateRepoChange', 'TemplateRepoCreate', 'TemplateRepoOut', 'TemplateRepos', 'TemplateTypeOut', 'TemplatesOut', 'TermOut', 'TermVersionOut', 'TestOut', 'TranspileOut', 'TranspileReason', 'TranspiledStatement', 'Upload', 'UploadLoad', 'Uploads', 'UpstreamProblemOut', 'UpstreamProblemsOut', 'VerificationOut', 'VerificationRun', 'VerifyOut', 'ViewInfo', 'ViewList', 'VolumeCreate', 'VolumeExplanation', 'VolumeFile', 'VolumeFiles', 'VolumeGrant', 'VolumeGrantInfo', 'VolumeInfo', 'VolumePermissions', 'VolumePermissionsUpdate', 'Volumes', 'WorkspaceCatalogCreate', 'WorkspaceCatalogInfo', 'WorkspaceCatalogList', 'WorkspaceCreate', 'WorkspaceInfo', 'WorkspaceJobInfo', 'WorkspaceJobList', 'WorkspaceJobRunInfo', 'WorkspaceJobRunList', 'WorkspaceJobStats', 'WorkspaceList', 'WorkspaceStorageOut', 'WorkspaceSummaryOut', 'WorkspaceUpdate']


class _Model(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class AlertOut(_Model):
    id: str
    rule: str
    severity: str
    workspace: str | None
    actor: str | None
    summary: dict[str, Any]
    count: int
    first_seen: datetime
    last_seen: datetime
    status: str
    acked_at: datetime | None
    acked_by: str | None
    resolved_at: datetime | None
    resolved_by: str | None
    version: int
    runbook: str


class AlertStatus(_Model):
    "The new status (acknowledged or resolved) and the version read."

    status: Literal['acknowledged', 'resolved'] | str
    version: int


class Alerts(_Model):
    items: list[AlertOut]


class AssignedTagOut(_Model):
    "A tag of the portal's store as it reaches the object or one of its columns (data-tag-inheritance TI-3): its\nown, or inherited from the table, schema or catalog, the nearest value winning. Never enforced: no engine reads\nthe store (TI-4), so its mask does not apply here; the tags SQE applies are in `tags`."

    column: str | None = None
    tag: str = Field(description="The catalog's tag by its bare name")
    value: str | None = None
    source: Literal['column', 'table', 'schema', 'catalog'] | str = Field(description='Where the tag is assigned')
    mask_type: str | None = Field(default=None, description="The tag's mask, which would apply if an engine enforced it")
    enforcement: Literal['not_enforced'] | str = Field(default='not_enforced', description="Assignments in the portal's store classify; no engine reads them yet")


class AuditEvents(_Model):
    items: list[EventOut]
    next_cursor: str | None = None
    window_start_at: datetime
    window_end_at: datetime


class AuditIngestOut(_Model):
    received: int
    accepted: int
    duplicates: int
    skipped: int


class BundleEntryOut(_Model):
    kind: str
    action: str
    object: str
    group: str | None = None
    privilege: str | None = None
    reason: str | None = None
    status: int | None = None
    code: str | None = None


class BundleTargetOut(_Model):
    name: str
    default: bool = Field(default=False)
    mode: str | None = None


class CatalogBindingInfo(_Model):
    workspace: str
    binding: Literal['read_write', 'read_only'] | str


class CatalogBindingList(_Model):
    items: list[CatalogBindingInfo]
    next_cursor: str | None = None


class CatalogBindingUpdate(_Model):
    binding: Literal['read_write', 'read_only'] | str


class CatalogCreate(_Model):
    "A catalog outside a workspace, as in a Unity metastore: open, or isolated with its bindings."

    name: str
    owner_group: str = Field(description='A group, never a person')
    comment: str | None = None
    storage_location: str | None = Field(default=None, description="A registered storage location's name")
    isolation: Literal['open', 'isolated'] | str = Field(default='open')
    bindings: list[CatalogBindingInfo] | None = None


class CatalogInfo(_Model):
    name: str
    isolation: Literal['open', 'isolated'] | str
    comment: str | None = None
    owner_group: str | None = None
    home_workspace: str | None = None
    location: str | None = None
    storage_location: str | None = None
    bindings: list[CatalogBindingInfo]


class CatalogList(_Model):
    items: list[CatalogInfo]
    next_cursor: str | None = None


class CatalogScope(_Model):
    "``bindings`` (the default), ``narrow`` (a subset of the bindings; a list keeps each binding's mode), ``listed``\n(catalogs outside the bindings, each with a mode) or ``grants`` (every catalog the person's grants reach)."

    mode: Literal['bindings', 'narrow', 'listed', 'grants'] | str = Field(default='bindings')
    catalogs: dict[str, Literal['read_write', 'read_only'] | str] | list[str] | None = None


class CatalogUpdate(_Model):
    isolation: Literal['open', 'isolated'] | str | None = None
    comment: str | None = None


class ChangeIn(_Model):
    op: Literal['grant', 'revoke', 'transfer', 'clear_owner', 'forget', 'mask', 'unmask', 'row_filter', 'clear_row_filter', 'tag_define', 'tag_drop', 'tag_mask', 'tag_unmask', 'tag_row_filter', 'tag_clear_row_filter'] | str
    namespace: str | None = None
    table: str | None = None
    group: str | None = None
    privilege: str | None = None
    column: str | None = None
    mask_type: str | None = None
    expression: str | None = None
    groups: list[str] | None = None
    except_groups: list[str] | None = None
    tag: str | None = None
    description: str | None = None
    allowed_values: list[str] | None = None


class CheckOut(_Model):
    key: str
    name: str | None
    column: str | None
    kind: str
    metric: str | None
    dimension: str | None
    severity: str
    unit: str
    operator: str
    expected: str
    actual: float | None
    outcome: str
    error_kind: str | None
    elapsed_ms: int


class ClassificationSuggestionOut(_Model):
    column: str
    current: str
    suggested: str
    sources: list[SuggestionSourceOut]


class ClassificationSuggestions(_Model):
    items: list[ClassificationSuggestionOut]


class ClassificationUpdate(_Model):
    "``None`` clears a level (the column falls back to the table, the table to the service default)."

    table: str | None = None
    columns: dict[str, str | None] | None = None


class ColumnInfo(_Model):
    name: str
    type_text: str
    nullable: bool
    comment: str | None = None
    classification: str
    classification_explicit: bool = Field(default=False)


class ColumnQualityOut(_Model):
    "A column's checks in the latest run of each source (DL-7): the worst outcome, the source that gave it and, for a\nfailed or warned check, its failing row count."

    column: str
    status: Literal['passed', 'warning', 'failed', 'error'] | str
    source: Literal['contract', 'dbt'] | str
    failures: int | None = None


class ColumnRef(_Model):
    catalog: str | None = Field(default=None, description="One of the workspace's catalogs. None on a create: the home catalog; on an update: the catalog of the term's link to this column (422 link_catalog_ambiguous when it links it in several), else the home catalog")
    namespace: str
    table: str
    column: str


class ColumnSchema(_Model):
    name: str
    type: str


class ColumnStatsOut(_Model):
    "Counts only, never a value: also shown for personal columns (the profile computes them for every column)."

    nulls: int | None
    null_pct: float | None
    distinct: int | None


class ConfigInfo(_Model):
    api_version: str
    service_version: str
    issuer: str
    client_id: str
    audience: str
    polaris_uri: str | None
    polaris_realm: str
    object_store_uri: str | None
    object_store_path_style: bool
    capabilities: list[str]
    service_versions: dict[str, str] = Field(default={})
    run_catalog_scope: RunCatalogScope | None = None


class ConflictingMaskOut(_Model):
    "One of a column's masks of different types: the column's own (`source` as on a mask) or a tag's."

    mask_type: str
    source: Literal['explicit', 'unity', 'personal', 'tag'] | str
    tag: str | None = Field(default=None, description='The tag whose mask this is, named as in `tags`')
    applies_to_me: bool


class ContractListItem(_Model):
    id: str
    namespace: str
    table: str
    status: str
    version: int
    updated_at: datetime
    latest_run: RunSummaryOut | None
    owner_group: str | None = None
    owner_source: Literal['contract', 'table', 'workspace'] | str | None = None


class ContractOut(_Model):
    id: str
    namespace: str
    table: str
    yaml: str
    version: int
    status: str
    transitions: list[str] = Field(default=[])
    sla: list[SlaOut] = Field(default=[])
    odcs_id: str
    odcs_version: str
    owner_group: str | None
    updated_at: datetime
    updated_by: str
    properties: list[PropertyOut]
    table_rules: list[RuleOut]
    checks: int
    not_checked: int
    warnings: list[str]
    dbt_import: DbtImportOut | None = Field(default=None, description='Set on the answer to an import from dbt')


class ContractPut(_Model):
    "The contract as ODCS YAML, ``from_schema`` to draft one from the table's columns and classification (only\nwhen the table has none), or ``from_dbt`` to build it from a dbt model (with ``version``: import again, replacing\nonly what came from dbt). ``version`` is the version read: without it the table must have no contract yet (409\n``conflict`` otherwise); with it the contract must still be at that version (409 ``conflict`` otherwise)."

    yaml: str | None = None
    from_schema: bool = Field(default=False)
    from_dbt: FromDbt | None = None
    version: int | None = None


class ContractStatusOut(_Model):
    "The table's contract and its last full run, for the table header (OpenSpec change data-table-contract-status)."

    status: str
    version: int
    run_status: str | None
    score: float | None
    passed: int | None
    total: int | None
    run_at: datetime | None
    contract_changed: bool


class DbtImportOut(_Model):
    "Where an import from dbt came from (data-contracts-gap D5)."

    run: str
    project: str
    model: str = Field(description="The model's unique_id")
    dropped: list[str] = Field(description='Columns dbt lists that the table does not have; left out')


class DeadLetterOut(_Model):
    id: str
    subscriber: str
    topic: str
    event_id: str
    type: str
    workspace: str | None
    error: str
    attempts: int
    status: Literal['parked', 'retry', 'delivered'] | str
    created_at: datetime
    updated_at: datetime
    event: dict[str, Any]


class DeadLetters(_Model):
    items: list[DeadLetterOut]


class Deliveries(_Model):
    items: list[DeliveryOut]


class DeliveryOut(_Model):
    id: str
    event_id: str
    type: str
    job: str | None
    job_run: str | None
    number: int | None
    rule: str | None
    target: str
    kind: str
    status: Literal['pending', 'delivered', 'parked', 'refused'] | str
    attempts: int
    outcome_code: str | None
    created_at: datetime
    updated_at: datetime
    delivered_at: datetime | None


class DeploymentIn(_Model):
    target: str | None = None
    plan_digest: str | None = None


class DeploymentOut(_Model):
    "How the project's jobs deploy (B1, B5): the targets the default branch's project file declares, the one chosen\nfor this project (None: the file's default), the one that applies, and whether the jobs were destroyed."

    commit: str | None = None
    file: str | None = None
    targets: list[BundleTargetOut] = Field(default=[])
    chosen: str | None = None
    target: str | None = None
    destroyed_at: datetime | None = None
    destroyed_by: str | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None
    deployed: list[str] = Field(default=[])
    deployed_at: datetime | None = None
    deployed_by: str | None = None
    deployed_target: str | None = None
    errors: list[JobsProblemOut] = Field(default=[])


class DeploymentValidateIn(_Model):
    target: str | None = None
    branch: str | None = None


class DeploymentValidateOut(_Model):
    "A dry run (B6): what deploying would do, or the problems (with file and line) that stop it. Nothing changes."

    commit: str | None = None
    branch: str
    file: str | None = None
    targets: list[BundleTargetOut] = Field(default=[])
    target: str | None = None
    deployed: list[str] = Field(default=[])
    changed: list[str] = Field(default=[])
    undeployed: list[str] = Field(default=[])
    errors: list[JobsProblemOut] = Field(default=[])
    warnings: list[JobsProblemOut] = Field(default=[])
    resources: list[BundleEntryOut] = Field(default=[])
    plan_digest: str | None = None


class DestinationOut(_Model):
    id: str
    name: str
    kind: Literal['webhook', 'slack', 'teams', 'email'] | str
    host: str | None
    header_name: str | None
    recipients: list[str] | None
    audit_alerts: bool
    owner_group: str
    owner_source: Literal['set', 'workspace'] | str
    created_by: str
    created_at: datetime
    updated_at: datetime
    version: int
    used_by: list[str]
    last_delivery: LastDeliveryOut | None = None


class DestinationWrite(_Model):
    "A destination: its name and kind are fixed once created (jobs name it). On an update a missing ``url`` or\n``header_value`` keeps the stored one; ``version`` is the one read (a stale one is 409)."

    name: str
    kind: Literal['webhook', 'slack', 'teams', 'email'] | str
    url: str | None = None
    header_name: str | None = None
    header_value: str | None = None
    clear_header: bool = Field(default=False)
    recipients: list[str] | None = None
    audit_alerts: bool = Field(default=False)
    owner_group: str | None = None
    version: int | None = None


class DestroyOut(_Model):
    target: str | None = None
    undeployed: list[str]
    cancelled: int


class DetectionRunOut(_Model):
    findings: int


class DigestOut(_Model):
    days: int
    from_: datetime = Field(alias='from')
    to: datetime
    workspaces: list[DigestWorkspace]


class DigestWorkspace(_Model):
    workspace: str
    accesses: int
    failed: int
    exports: int
    rows_exported: int
    changes: int
    people: int
    alerts_opened: int
    alerts_resolved: int
    top_people: list[dict[str, Any]]


class DriftOut(_Model):
    drift: bool
    removed: list[dict[str, Any]]
    changed: list[dict[str, Any]]
    added: list[dict[str, Any]]


class ErrorInfo(_Model):
    "Every error: a stable code, a message for people, details where the code has them, and the request id."

    code: str
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None


class EventDetail(_Model):
    "One event with the whole shown statement and the engine records it links to (A2, A3.3)."

    seq: int
    time: datetime
    activity: str
    outcome: str
    actor: str | None
    workspace: str | None
    src_ip: str | None = None
    peer_ip: str | None = None
    target: dict[str, Any]
    attributes: dict[str, Any]
    actor_engine_user: bool = Field(default=False)
    tables: list[str] | None = None
    statement: str | None = None
    statement_cut: bool = Field(default=False)
    statement_truncated: bool = Field(default=False)
    tables_unknown: bool = Field(default=False)
    literals_stripped: bool = Field(default=False)
    redactions: dict[str, int] | None = None
    linked: list[EventOut] | None = None


class EventOut(_Model):
    seq: int
    time: datetime
    activity: str
    outcome: str
    actor: str | None
    workspace: str | None
    src_ip: str | None = None
    peer_ip: str | None = None
    target: dict[str, Any]
    attributes: dict[str, Any]
    actor_engine_user: bool = Field(default=False)
    tables: list[str] | None = None
    statement: str | None = None
    statement_cut: bool = Field(default=False)


class ExplainOut(_Model):
    plan: str


class ExportCheck(_Model):
    "The system tables' last exported audit row against the chain (data-system-tables ST-5). ``matches`` is None\nwhen the chain no longer holds that seq (purged)."

    seq: int | None
    hash: str | None
    matches: bool | None


class FileUsageList(_Model):
    items: list[FileUsageOut]
    next_cursor: str | None = None


class FileUsageOut(_Model):
    "A deployed job's task that runs a file of the project (data-file-job-usage F1): the path as deployed, the job and\ntask, the task's action, whether it is a for_each task's nested task, and whether the job is enabled."

    path: str
    job: str
    task: str
    action: str | None
    for_each: bool = Field(default=False)
    enabled: bool


class FromDbt(_Model):
    "Build the contract from a dbt model (data-contracts-gap D5). ``run``: a dbt run of a project the caller may\nsee; none: the newest succeeded one whose manifest has a model for the table. ``model``: a unique_id or a name;\nnone: the model that builds the table."

    run: str | None = None
    model: str | None = None


class GatewayAuditOut(_Model):
    accepted: int


class GitCredentialOut(_Model):
    host: str
    type: str
    provider: str | None
    username: str | None
    status: str
    updated_at: datetime
    last_used_at: datetime | None


class GitOAuthComplete(_Model):
    "The code and state the provider sent back to the UI."

    code: str
    state: str


class GitOAuthStartOut(_Model):
    authorize_url: str


class GitProviderOut(_Model):
    provider: str
    host: str


class GitProviders(_Model):
    items: list[GitProviderOut]


class GitToken(_Model):
    "A personal access token for the host, and the user name it belongs to where the host needs one."

    token: str
    username: str | None = None


class GlossaryImport(_Model):
    "Terms as YAML or CSV, as the export writes them; matched by name, links the steward cannot read are dropped."

    format: Literal['yaml', 'csv'] | str
    content: str


class GlossaryTermCreate(_Model):
    "A new term: its name (unique in the workspace, case and spacing ignored), definition, synonyms, an optional\nfilter expression, the owning group and the columns it describes (``catalog``, ``namespace``, ``table``,\n``column``, each one the steward can read; ``catalog`` is one of the workspace's, none for the home catalog; a new\nlink into a catalog bound read-only is 403 ``catalog_read_only``)."

    name: str
    definition: str = Field(default='')
    synonyms: list[str] | None = None
    filter_expression: str | None = None
    owner_group: str | None = None
    columns: list[ColumnRef] | None = None


class GlossaryTermHistory(_Model):
    items: list[TermVersionOut]


class GlossaryTermStatus(_Model):
    "Move the term to ``draft``, ``accepted`` or ``retired`` from the ``version`` read (409 when stale or the move\nis not allowed)."

    status: Literal['draft', 'accepted', 'retired'] | str
    version: int


class GlossaryTermUpdate(_Model):
    "The whole term, with the ``version`` read (409 ``conflict`` when it changed since). A link without ``catalog``\nkeeps the catalog of the term's link to that column (422 ``link_catalog_ambiguous`` when the term links it in\nseveral catalogs: name them), and is the home catalog's when the term does not link it yet."

    name: str
    definition: str = Field(default='')
    synonyms: list[str] | None = None
    filter_expression: str | None = None
    owner_group: str | None = None
    columns: list[ColumnRef] | None = None
    version: int


class GlossaryTerms(_Model):
    items: list[TermOut]


class GovernanceChange(_Model):
    "One change: a grant, a revoke, an owner, a column mask, a row filter, or a governed tag of the catalog with its\nmask and row filter (``tag_*``, neither ``schema`` nor ``table``). ``schema`` and ``table`` name the securable\n(neither: the catalog)."

    op: Literal['grant', 'revoke', 'transfer', 'clear_owner', 'forget', 'mask', 'unmask', 'row_filter', 'clear_row_filter', 'tag_define', 'tag_drop', 'tag_mask', 'tag_unmask', 'tag_row_filter', 'tag_clear_row_filter'] | str
    schema_: str | None = Field(default=None, alias='schema')
    table: str | None = None
    group: str | None = None
    privilege: str | None = None
    column: str | None = None
    mask_type: str | None = None
    expression: str | None = None
    groups: list[str] | None = None
    except_groups: list[str] | None = None
    tag: str | None = None
    description: str | None = None
    allowed_values: list[str] | None = Field(default=None, description="tag_define: the values the tag may take, in order; omitted keeps the tag's list, [] clears it")


class GovernanceChanges(_Model):
    changes: list[GovernanceChange]


class GrantOut(_Model):
    namespace: str | None
    table: str | None
    kind: str
    group: str
    privilege: str
    granted_by: str
    granted_at: datetime
    active: bool
    missing: str | None
    source: str = Field(default='portal')


class GroupInfo(_Model):
    name: str
    level: str
    parent: str | None
    mine: bool


class Groups(_Model):
    "The portal's ``GET /api/groups`` shape, which the portal SDK's group picker reads (not ``{items}``)."

    groups: list[GroupInfo]
    prefixes: dict[str, str]
    default_owner_group: str


class HistoryEntry(_Model):
    id: str
    sql: str
    catalog: str
    schema_name: str | None
    status: str
    row_count: int
    elapsed_ms: int
    engine: str
    started_at: datetime


class HistoryEntryList(_Model):
    items: list[HistoryEntry]
    next_cursor: str | None = None


class IdentityRemovedOut(_Model):
    "What the deprovision removed. ``found`` is false when nothing of the person this service made was left (or the\nname is someone else's): no Ranger or Polaris call changed anything, and a second call answers the same way.\n``record_removed`` can still be true then: the sync row of a name whose Ranger user someone else made."

    found: bool
    roles_removed: list[str]
    principal_removed: bool
    ranger_user_removed: bool
    record_removed: bool


class ImpactItemOut(_Model):
    workspace: str | None
    namespace: str
    table: str
    depth: int
    columns: list[str]
    owner_group: str | None
    quality: NodeQualityOut | None


class ImpactOut(_Model):
    column: str | None
    items: list[ImpactItemOut]
    hidden: int
    external: int
    truncated: bool


class ImportOut(_Model):
    created: int
    updated: int
    dropped_links: list[str]


class InactiveOut(_Model):
    namespace: str | None
    table: str | None
    group: str
    privilege: str
    missing: str


class InboxItem(_Model):
    contract_id: str | None
    source: Literal['contract', 'dbt'] | str = Field(default='contract')
    namespace: str
    table: str
    run_id: str
    check_key: str
    name: str | None
    column: str | None
    metric: str
    severity: str
    outcome: str
    error_kind: str | None
    expected: str
    operator: str
    actual: float | None
    unit: str
    since: datetime
    last_passed_at: datetime | None
    last_run_at: datetime
    contract_changed: bool
    downstream_tables: int = Field(default=0)
    recent: list[RecentOut] = Field(default=[])


class InboxOut(_Model):
    owner_group: str | None
    items: list[InboxItem]
    downstream_total: int = Field(default=0)
    downstream_truncated: bool = Field(default=False)


class IngestLedgerItem(_Model):
    "One file version the task saw. ``path`` (inside the volume) only for a caller who may read the volume."

    id: str
    state: str = Field(description='One of pending, loaded, failed, skipped')
    reason: str | None = Field(default=None, description='Why it failed or was skipped: a code (scan_refused, too_large, …)')
    attempts: int
    rows: int | None
    snapshot_id: str | None
    size_bytes: int
    modified_at: datetime | None
    created_at: datetime
    updated_at: datetime
    path: str | None = Field(default=None, description='Inside the volume; null unless the caller holds READ VOLUME on it')
    actions: list[str] | None = Field(default=None, description='What the caller may call on it next: retry')


class IngestLedgerList(_Model):
    items: list[IngestLedgerItem]
    next_cursor: str | None = None


class IngestLedgerSummary(_Model):
    "The ledger as a whole: what the list pages through, counted (as ``WorkspaceJobStats`` beside its list)."

    counts: dict[str, int] = Field(description='Files per state')
    volume: str | None = Field(default=None, description="The task's volume, when its parameters name it without a run")
    table: str | None = None
    paths_visible: bool = Field(description='The caller may read the volume, so each item carries its path')
    max_attempts: int = Field(description='Tries a failed file gets before only a retry by hand loads it')


class IngestOut(_Model):
    accepted: int
    duplicates: int


class ItemChangeOut(_Model):
    resource: str
    group: str
    added: list[str]
    removed: list[str]


class JobBuilderCheckIn(_Model):
    branch: str
    file: str
    text: str
    target: str | None = None


class JobBuilderCheckOut(_Model):
    file: str
    target: str | None = None
    targets: list[str] = Field(default=[])
    errors: list[JobsProblemOut] = Field(default=[])
    warnings: list[JobsProblemOut] = Field(default=[])
    jobs: list[JobBuilderJobOut] = Field(default=[])
    event_types: list[JobEventTypeOut] | None = None


class JobBuilderExportIn(_Model):
    branch: str
    file: str
    text: str
    target: str | None = None
    job: str
    format: Literal['json', 'bundle'] | str = Field(default='json')


class JobBuilderExportOut(_Model):
    job: str
    format: str
    text: str
    warnings: list[str] = Field(default=[])


class JobBuilderImportIn(_Model):
    text: str
    name: str | None = None
    strip_prefix: str | None = None


class JobBuilderImportOut(_Model):
    name: str
    job: dict[str, Any] | None
    settings: dict[str, Any] | None
    errors: list[JobsProblemOut] = Field(default=[])
    warnings: list[JobsProblemOut] = Field(default=[])


class JobBuilderJobOut(_Model):
    name: str
    display_name: str | None
    task_graph: list[JobTaskOut]
    schedule: str | None
    timezone: str | None
    triggers: list[str]
    next_fires: list[datetime]


class JobEventPending(_Model):
    "Events matched and not fired yet (the debounce or the cap): how many, since when, the last one's time."

    events: int
    since_at: datetime | None
    last_event_at: datetime | None


class JobEventTriggerOut(_Model):
    "An event trigger as deployed (data-job-event-triggers E1): the event type, the filter on its data, Databricks'\ndebounce, and whether it is paused."

    type: str
    filter: dict[str, Any]
    min_time_between_triggers_seconds: int
    wait_after_last_change_seconds: int
    paused: bool


class JobEventTypeOut(_Model):
    "An event type a trigger may name (data-job-event-triggers E1), short, and the fields its filter may use."

    type: str
    fields_: list[str] = Field(alias='fields')


class JobForEachOut(_Model):
    "A for_each task's loop (data-job-for-each): its inputs as written and the nested task it runs."

    inputs: str
    concurrency: int
    task_key: str
    action: str | None
    path: str | None
    run_job: str | None
    query: str | None = None
    dialect: str | None = None
    engine: str | None = None
    table: str | None = None
    operations: list[str] | None = None
    max_retries: int = Field(default=0)
    min_retry_interval_millis: int = Field(default=0)
    retry_on_timeout: bool = Field(default=False)
    timeout_seconds: int | None = None


class JobGrantIn(_Model):
    group: str
    privilege: str


class JobGrantOut(_Model):
    group: str
    privilege: str
    source: str
    granted_by: str
    granted_at: datetime


class JobInfo(_Model):
    name: str
    description: str | None
    run_as: str
    owner: str
    deployed: bool
    enabled: bool
    disabled_reason: str | None
    schedule: str | None
    timezone: str | None
    triggers: list[str]
    tasks: int
    consecutive_failures: int = Field(default=0)
    commit_sha: str | None = None
    target: str | None = Field(default=None, description='The bundle target it was deployed from')
    event_trigger: JobEventTriggerOut | None = None
    deployed_at: datetime | None = None
    next_fire_at: datetime | None
    last_run: JobRunInfo | None
    recent_runs: list[JobRunInfo] | None = Field(default=None, description='Its last runs, newest first; in lists')
    privileges: list[str] | None = Field(default=None, description="The caller's on the job; when one job is read")
    project_privileges: list[str] | None = Field(default=None, description="The caller's on its project; idem")
    actions: list[str] | None = Field(default=None, description='What the caller may call on the job next (C18.2): update, run-now, update-permissions; when one job is read')
    notifications: dict[str, Any] | None = None
    health_seconds: int | None = Field(default=None, description='Its run duration warning')
    event_pending: JobEventPending | None = None
    task_graph: list[JobTaskOut] | None = Field(default=None, description='expand=task_graph')
    stats: JobRunStatsOut | None = Field(default=None, description='expand=stats: its runs of the last `days`')
    definition_yaml: str | None = Field(default=None, description='expand=definition: as it would read in project.yml')


class JobList(_Model):
    items: list[JobInfo]
    next_cursor: str | None = None


class JobPermissionsIn(_Model):
    grants: list[JobGrantIn] | None = None


class JobPermissionsOut(_Model):
    "The job's grants (they add to what the project gives, J1), its owner (IS OWNER: whoever deployed it, J4; never\ngranted), the caller's privileges on it, and what each project privilege gives on a job."

    owner: str | None = None
    grants: list[JobGrantOut] = Field(default=[])
    privileges: list[str] = Field(default=[])
    from_project: dict[str, str] = Field(default={})


class JobRunEventOut(_Model):
    "The event that started an event-triggered run (data-job-event-triggers E4): the last one matched, its type, and\nhow many matched since the run before it (debounce and the cap gather them)."

    event: str
    type: str
    events: int
    first_event: str | None = None


class JobRunInfo(_Model):
    run_id: str
    number: int
    trigger: str
    status: str = Field(description='One of waiting, queued, running (not ended) or succeeded, failed, cancelled, skipped, expired (ended). A run moves waiting, queued, running, then to one of the ended states. `waiting`: fired while the job was at max_concurrent_runs with its queue on; it has no task runs until a slot frees, then it is `queued`. `skipped`: it never started (at the limit without a queue, the queue full or too old, the job undeployed). `expired`: the identity the job runs as was lost (the job is disabled; `error` says why). A client should treat a state it does not know as not ended.')
    commit_sha: str
    run_as: str
    identity_kind: str | None = Field(default=None, description='What run_as names: owner or service_principal')
    started_by: str | None
    repair_of: str | None = Field(default=None, description='The run this one retries')
    job_parameters: dict[str, str]
    trigger_event: JobRunEventOut | None = None
    error: str | None
    error_code: str | None = Field(default=None, description='`outcome_unknown`: a write was sent and its outcome is unknown (data-outcome-unknown); the task is never retried. Check the table before you run it again')
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    task_status: dict[str, str] | None = Field(default=None, description="Each task's status at its current attempt; in the job's run list")
    tasks: list[JobTaskRunInfo] | None = Field(default=None, description='Filled when one run is read')
    task_graph: list[JobTaskOut] | None = Field(default=None, description='The graph it ran; when one run is read')
    privileges: list[str] | None = Field(default=None, description="The caller's on the job; when one run is read")
    project_privileges: list[str] | None = Field(default=None, description="The caller's on the project; idem")
    actions: list[str] | None = Field(default=None, description='What the caller may call on the run next (C18.2): cancel, retry; when one run is read')


class JobRunList(_Model):
    items: list[JobRunInfo]
    next_cursor: str | None = None


class JobRunStatsOut(_Model):
    "How a job's runs went over a period (data-jobs-run-insight I4): runs created in the last ``days`` by status, and\nthe median and 90th percentile of the time the succeeded ones took (None: none succeeded)."

    days: int
    total: int
    counts: dict[str, int]
    succeeded: int
    failed: int
    median_seconds: float | None
    p90_seconds: float | None


class JobTaskOut(_Model):
    task_key: str
    description: str | None
    depends_on: list[str]
    run_if: str
    action: str | None
    path: str | None
    run_job: str | None
    query: str | None = None
    dialect: str | None = None
    engine: str | None = None
    table: str | None = None
    operations: list[str] | None = None
    for_each: JobForEachOut | None = None
    max_retries: int = Field(default=0)
    min_retry_interval_millis: int = Field(default=0)
    retry_on_timeout: bool = Field(default=False)
    timeout_seconds: int | None = None


class JobTaskRunInfo(_Model):
    id: str | None = None
    task_key: str
    iteration: int | None = None
    input: str | None = Field(default=None, description="A for_each iteration's item as {{input}} gives it, shortened")
    attempt: int
    status: str = Field(description='One of blocked, queued, running (not ended) or succeeded, failed, upstream_failed, excluded, cancelled, timed_out, skipped (ended). `blocked`: waiting for the tasks it depends on; `queued`: ready, or waiting for a retry interval; `upstream_failed`: a task it depends on failed; `excluded`: a repair kept its earlier result; `skipped`: its run_if was not met. A client should treat a state it does not know as not ended.')
    run_id: str | None
    outcome: str | None = Field(default=None, description="A condition task's branch: true or false")
    task_values: dict[str, Any] | None = Field(default=None, description='What the task set with dbutils.jobs.taskValues')
    error: str | None
    error_code: str | None = Field(default=None, description='`outcome_unknown`: a write was sent and its outcome is unknown (data-outcome-unknown); the task is never retried. Check the table before you run it again')
    created_at: datetime | None = None
    started_at: datetime | None
    finished_at: datetime | None


class JobUpdate(_Model):
    "``enabled``: false pauses the job (no schedule or trigger fires; active runs go on), true enables it again."

    enabled: bool


class JobsConsentComplete(_Model):
    "The code and state Keycloak sent back to the UI."

    code: str
    state: str


class JobsConsentStartOut(_Model):
    url: str


class JobsDeployOut(_Model):
    "What a commit or pull on the default branch deployed from ``project.yml`` (data-jobs J1); with errors,\nnothing changed."

    commit: str
    deployed: list[str]
    changed: list[str]
    undeployed: list[str]
    errors: list[JobsProblemOut]
    warnings: list[JobsProblemOut] = Field(default=[])
    target: str | None = None
    held: list[str] = Field(default=[])
    released: list[str] = Field(default=[])
    permissions: list[str] = Field(default=[])
    permissions_withheld: list[str] = Field(default=[])


class JobsIdentityOut(_Model):
    configured: bool
    consented: bool
    since: datetime | None
    last_used_at: datetime | None
    jobs: int


class JobsProblemOut(_Model):
    file: str | None = None
    path: str
    line: int | None = None
    message: str
    code: str | None = None


class JobsRevokedOut(_Model):
    stopped: int


class JobsSummaryOut(_Model):
    deployed: int
    enabled: int
    paused: int
    failing: int


class LastDeliveryOut(_Model):
    "A destination's newest delivery (data-notifications-last-delivery L1): its state and when it last changed."

    status: Literal['pending', 'delivered', 'parked', 'refused'] | str
    at: datetime
    attempts: int
    outcome_code: str | None


class Limits(_Model):
    "Kernels per person and in the workspace, never above the deployment's; null: the deployment's."

    kernels_per_person: int | None = None
    kernels_total: int | None = None


class LimitsOut(_Model):
    kernels_per_person: int
    kernels_total: int
    workspace_per_person: int | None
    workspace_total: int | None
    deployment_per_person: int
    deployment_total: int
    idle_minutes: float
    cell_timeout_seconds: int
    runs_per_person: int
    pip_offered: bool = Field(default=False)
    session_pip: bool = Field(default=False)


class LineageColumnEdgeOut(_Model):
    source: str
    source_column: str | None
    target: str
    target_column: str | None
    type: str
    subtype: str
    masked: bool
    stale: bool
    producers: list[str] = Field(default=[])
    also_typed: list[str] = Field(default=[])
    static: bool = Field(default=False)


class LineageEdgeOut(_Model):
    source: str
    target: str
    stale: bool
    jobs: list[LineageJobOut]


class LineageGraphOut(_Model):
    root: str
    direction: str
    depth: int
    column: str | None
    nodes: list[LineageNodeOut]
    edges: list[LineageEdgeOut]
    column_edges: list[LineageColumnEdgeOut]
    truncated: bool
    hidden: int


class LineageJobOut(_Model):
    kind: str
    producer: str
    last_seen: datetime
    stale: bool
    complete: bool
    runs: int
    run_by: str | None = None
    run_by_status: Literal['verified', 'denied', 'unchecked', 'erased'] | str | None = None


class LineageNodeOut(_Model):
    id: str
    kind: Literal['table', 'view', 'hidden', 'external', 'dropped'] | str
    root: bool
    depth: int
    workspace: str | None = None
    catalog: str | None = None
    namespace: str | None = None
    table: str | None = None
    classification: str | None = None
    quality: NodeQualityOut | None = None
    last_write: datetime | None = None
    columns: list[str] = Field(default=[])


class LineageStatusOut(_Model):
    enabled: bool
    producers: int
    datasets: int
    edges: int
    column_edges: int
    last_event_at: datetime | None


class LinkOut(_Model):
    catalog: str
    namespace: str
    table: str
    column: str
    missing: bool


class MaskChangeOut(_Model):
    name: str
    action: Literal['create', 'update', 'delete'] | str
    summary: str


class MaskConflictOut(_Model):
    "A column with masks of more than one type (data-tag-access TA-11): there is no winner. Spark refuses a\nstatement that reads the column for anyone two of the masks apply to, and so does SQE under `mask_precedence =\n\"refuse\"` (otherwise SQE applies one of them). Remove one mask, or make them the same type.\nMade past the portal (a tag set through SQE or Spark); the portal refuses it when written (409\n`mask_conflict`)."

    column: str
    masks: list[ConflictingMaskOut]
    refused_for_me: bool = Field(description='Two of the masks apply to the caller, so the column is refused to them')


class MaskOut(_Model):
    column: str
    mask_type: str
    source: Literal['explicit', 'unity', 'personal'] | str
    except_groups: list[str]
    applies_to_me: bool


class MeOut(_Model):
    username: str
    email: str
    groups: list[str]
    permissions: list[str]
    mode: str


class MyGitCredentials(_Model):
    items: list[GitCredentialOut]


class MySecrets(_Model):
    items: list[SecretOut]


class NodeQualityOut(_Model):
    status: str
    score: float | None
    at: datetime
    sources: list[SourceQualityOut] = Field(default=[])
    columns: list[ColumnQualityOut] = Field(default=[])


class NotificationsOut(_Model):
    operator: bool
    email: bool
    subscriber: bool
    email_domains: list[str]
    owner_groups: list[str]
    destinations: list[DestinationOut]


class OwnerOut(_Model):
    group: str
    namespace: str | None
    table: str | None
    inherited: bool
    kind: Literal['group', 'user'] | str = Field(default='group')


class PermissionsChangeItem(_Model):
    principal: str
    add: list[str] | None = None
    remove: list[str] | None = None


class PermissionsInfo(_Model):
    securable_type: Literal['catalog', 'schema', 'table'] | str
    full_name: str
    owner: str | None
    owner_inherited_from: str | None = None
    privilege_assignments: list[PrivilegeAssignment]
    inherited_assignments: list[PrivilegeAssignment]
    valid_privileges: list[str]
    my_privileges: list[str]
    can_manage: bool


class PermissionsOut(_Model):
    namespace: str | None
    table: str | None
    kind: str
    owner: OwnerOut | None
    grants: list[GrantOut]
    inherited: list[GrantOut]
    valid_privileges: list[str]
    mine: list[str]
    can_manage: bool
    masks: list[MaskOut] = Field(default=[])
    row_filter: RowFilterOut | None = None
    tags: list[TagOnColumnOut] = Field(default=[])
    mask_conflicts: list[MaskConflictOut] = Field(default=[])
    assigned_tags: list[AssignedTagOut] = Field(default=[], description="The portal store's tags on the object and each column, own and inherited (not enforced)")
    system_tags: list[SystemTagOut] = Field(default=[], description='`class=<level>` of a table or view and each of its columns (read only)')


class PermissionsUpdate(_Model):
    changes: list[PermissionsChangeItem]


class PreviewOut(_Model):
    masks: list[MaskChangeOut] = Field(default=[])
    tags: list[MaskChangeOut] = Field(default=[])
    ranger: list[ItemChangeOut]
    inactive: list[InactiveOut]
    suggestions: list[ChangeIn]


class PrincipalIn(_Model):
    groups: list[str]


class PrincipalOut(_Model):
    exists: bool
    client_id: str | None = None
    username: str | None = None
    groups: list[str] = Field(default=[])
    created_by: str | None = None
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    allowed_groups: list[str]
    available: bool
    cannot_run: str | None = None


class PrivilegeAssignment(_Model):
    principal: str
    privileges: list[str]
    inherited_from: str | None = Field(default=None, description='The securable it is granted on, when not this one')


class ProducerCreate(_Model):
    "A producer's name (lower case, 2 to 63 characters) and kind."

    name: str
    kind: Literal['sqe', 'spark', 'dbt', 'other'] | str


class ProducerCreatedOut(_Model):
    id: str
    name: str
    kind: str
    created_at: datetime
    revoked_at: datetime | None
    last_seen_at: datetime | None
    key: str


class ProducerOut(_Model):
    id: str
    name: str
    kind: str
    created_at: datetime
    revoked_at: datetime | None
    last_seen_at: datetime | None


class Producers(_Model):
    items: list[ProducerOut]


class ProfileOut(_Model):
    snapshot_id: int | None
    current_snapshot_id: int | None
    stale: bool
    cached: bool
    row_count: int | None
    scope: str
    scanned_rows: int | None
    columns: list[dict[str, Any]]
    elapsed_ms: int
    profiled_at: datetime


class ProfileSummaryOut(_Model):
    "The caller's latest profile of the table, for the schema table (OpenSpec change data-schema-profile-stats)."

    profiled_at: datetime
    snapshot_id: int | None
    stale: bool
    scope: str
    scanned_rows: int | None
    columns: dict[str, ColumnStatsOut]


class ProjectActionOut(_Model):
    id: str
    kind: str
    label: str
    permission: str
    allowed: bool
    available: bool
    reason: str | None
    selection: bool
    params: list[ProjectParamOut]


class ProjectActionResult(_Model):
    action: str
    query: QueryOut | None = Field(default=None, description='`sql.run`: the result')
    plan: str | None = Field(default=None, description='`sql.explain`: the plan')
    run: ProjectRunInfo | None = Field(default=None, description='An action that runs: the run it started')


class ProjectActionRun(_Model):
    branch: str
    path: str
    selection: str | None = None
    namespace: str | None = None
    params: dict[str, Any] | None = None
    catalog: str | None = None
    catalog_scope: CatalogScope | None = None
    run_as: Literal['owner', 'service_principal'] | str | None = None


class ProjectActions(_Model):
    items: list[ProjectActionOut]


class ProjectBranchCreate(_Model):
    name: str
    source: str | None = None


class ProjectBranchName(_Model):
    branch: str


class ProjectBranchOut(_Model):
    name: str
    head_sha: str | None
    on_remote: bool
    synced_at: datetime | None


class ProjectCommit(_Model):
    sha: str
    message: str
    author: str
    committed_at: datetime


class ProjectCommitCreate(_Model):
    branch: str
    message: str


class ProjectCommitOut(_Model):
    sha: str
    jobs: JobsDeployOut | None = None


class ProjectCreate(_Model):
    slug: str
    name: str = Field(default='')
    description: str = Field(default='')
    owner_group: str | None = None
    git_url: str | None = None
    branch: str = Field(default='main')
    template: str | None = None


class ProjectCreated(_Model):
    id: str
    slug: str
    name: str
    description: str
    git_url: str | None
    default_branch: str
    owner_group: str | None
    privileges: list[str]
    personal: bool
    created_at: datetime
    created_by: str | None = None
    type: str = Field(default='blank')
    template: str | None = None
    last_commit: ProjectHead | None = Field(default=None, description="The default branch's head; in the list only")
    job_count: int = Field(default=0, description='Deployed jobs; in the list only')
    last_run: ProjectLastRun | None = Field(default=None, description='The latest job run or run by hand; in the list only')
    branches: list[ProjectBranchOut]
    actions: list[str] | None = Field(default=None, description='What the caller may call on the project next (C18.2); a notebook is one of its files')
    scaffold: ProjectScaffoldOut | None = None
    jobs: JobsDeployOut | None = Field(default=None, description='What a project file imported from git deployed')


class ProjectDetail(_Model):
    id: str
    slug: str
    name: str
    description: str
    git_url: str | None
    default_branch: str
    owner_group: str | None
    privileges: list[str]
    personal: bool
    created_at: datetime
    created_by: str | None = None
    type: str = Field(default='blank')
    template: str | None = None
    last_commit: ProjectHead | None = Field(default=None, description="The default branch's head; in the list only")
    job_count: int = Field(default=0, description='Deployed jobs; in the list only')
    last_run: ProjectLastRun | None = Field(default=None, description='The latest job run or run by hand; in the list only')
    branches: list[ProjectBranchOut]
    actions: list[str] | None = Field(default=None, description='What the caller may call on the project next (C18.2); a notebook is one of its files')


class ProjectDiff(_Model):
    items: list[ProjectDiffOut]


class ProjectDiffOut(_Model):
    path: str
    state: str
    diff: str


class ProjectDocsTicket(_Model):
    url: str = Field(description="Serves the run's docs site once, to a frame of this service or the portal, no token")
    expires_at: datetime


class ProjectExplainOut(_Model):
    allowed: bool
    need: str
    via: str | None
    group: str | None
    privilege: str | None
    missing: str | None


class ProjectFileCreate(_Model):
    branch: str
    path: str
    starter: str


class ProjectFileOut(_Model):
    path: str
    branch: str
    sha: str
    state: str
    binary: bool
    large: bool
    content: str | None
    kinds: list[str]
    editor: str
    updated_by: str
    updated_at: datetime


class ProjectFileSave(_Model):
    branch: str
    path: str
    content: str
    base_sha: str | None = None


class ProjectFiles(_Model):
    items: list[ProjectTreeEntry]


class ProjectGrantIn(_Model):
    group: str
    privilege: str


class ProjectGrantOut(_Model):
    group: str
    privilege: str
    granted_by: str
    granted_at: datetime


class ProjectHead(_Model):
    sha: str
    moved_at: datetime | None = Field(default=None, description="When the default branch last moved here (commit, pull or import); not the author's time")


class ProjectHistory(_Model):
    items: list[ProjectCommit]


class ProjectInfo(_Model):
    id: str
    slug: str
    name: str
    description: str
    git_url: str | None
    default_branch: str
    owner_group: str | None
    privileges: list[str]
    personal: bool
    created_at: datetime
    created_by: str | None = None
    type: str = Field(default='blank')
    template: str | None = None
    last_commit: ProjectHead | None = Field(default=None, description="The default branch's head; in the list only")
    job_count: int = Field(default=0, description='Deployed jobs; in the list only')
    last_run: ProjectLastRun | None = Field(default=None, description='The latest job run or run by hand; in the list only')


class ProjectLastRun(_Model):
    kind: str = Field(description="`job` (a job run) or `run` (started by hand); a job task's own run counts as its job")
    run_id: str
    status: str
    started_at: datetime = Field(description='When it started, or was created when it has not started')
    job: str | None = None
    number: int | None = None
    action: str | None = None


class ProjectList(_Model):
    items: list[ProjectInfo]
    next_cursor: str | None = None


class ProjectParamOut(_Model):
    name: str
    type: str
    label: str
    default: Any | None = None
    options: list[str] = Field(default=[])


class ProjectPermissionsOut(_Model):
    owner_group: str | None
    grants: list[ProjectGrantOut]
    personal: bool = Field(default=False)


class ProjectPermissionsSet(_Model):
    grants: list[ProjectGrantIn] | None = None
    owner_group: str | None = None


class ProjectPullOut(_Model):
    updated: int
    merged: int
    conflicts: int
    removed: int
    jobs: JobsDeployOut | None = None


class ProjectRunArtifact(_Model):
    "An artifact file as the run stored it (dbt's ``manifest.json``, ``run_results.json``), sent as an attachment."


class ProjectRunInfo(_Model):
    run_id: str
    action: str
    branch: str
    path: str
    parameters: dict[str, Any]
    snapshot_sha: str | None
    draft: bool
    writing: bool
    status: str
    exit_code: int | None
    error: str | None
    summary: dict[str, Any] | None
    started_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    catalog: str | None = Field(default=None, description='The catalog it started in; null: the home catalog')
    catalog_binding: str | None = None
    catalog_scope: RunCatalogScopeInfo | None = Field(default=None, description='The catalog scope sent to SQE; null with PORTAL_DATA_RUN_CATALOG_SCOPE off')
    run_as: Literal['owner', 'service_principal'] | str | None = Field(default=None, description="The job identity it ran as; null: the starter's own token (started_by)")
    identity_label: str | None = Field(default=None, description="With run_as: the username the identity's token named")
    changed: list[str] | None = Field(default=None, description='In a single run: files changed since the last successful run of the action and branch')
    artifacts: list[str] | None = Field(default=None, description='In a single run: the names of its artifacts')


class ProjectRunList(_Model):
    items: list[ProjectRunInfo]
    next_cursor: str | None = None


class ProjectScaffoldOut(_Model):
    template: str
    version: int
    files: list[str]
    skipped: list[str]
    open: str | None


class ProjectTreeEntry(_Model):
    path: str
    sha: str
    state: str
    binary: bool
    large: bool
    size: int
    kinds: list[str]


class PropertyOut(_Model):
    name: str
    logical_type: str | None
    physical_type: str | None
    required: bool
    description: str | None
    classification: str | None
    rules: list[RuleOut]


class QualityRunCreate(_Model):
    "One check of the contract to run again (data-quality-runs R2); none: every check."

    check: str | None = None


class QualityRuns(_Model):
    items: list[RunSummaryOut] = Field(description="The table's latest 20 runs, newest first")


class QualitySummary(_Model):
    contracts: int
    passing: int
    failing: int
    not_run: int


class QueryEngine(_Model):
    id: str
    available: bool
    state: str | None = None


class QueryEngines(_Model):
    "Not a ``*List``: the engines with the defaults that go with them, never paged."

    items: list[QueryEngine]
    default: str
    row_cap: int
    row_limits: list[int]


class QueryItemOut(_Model):
    id: str
    sql: str | None
    namespace: str | None
    status: str
    row_count: int
    elapsed_ms: int
    engine: str
    owner: str
    mine: bool
    started_at: datetime


class QueryOut(_Model):
    status: str
    columns: list[dict[str, str]]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    row_cap: int
    elapsed_ms: int
    error: str | None = None
    engine: str = Field(default='sqe')
    ran_as: str | None = None
    bytes_scanned: int | None = None


class QueryStatsOut(_Model):
    scope: Literal['me', 'workspace'] | str
    window: str
    total: int
    failed: int
    timeouts: int
    avg_ms: int
    max_ms: int
    rows: int
    people: int
    by_engine: dict[str, int]
    by_namespace: dict[str, int]
    items: list[QueryItemOut]


class RecentOut(_Model):
    run_id: str
    at: datetime
    outcome: str


class RemoteBranch(_Model):
    name: str


class RemoteBranches(_Model):
    items: list[RemoteBranch]


class RemovedOut(_Model):
    removed: int
    policies: list[dict[str, Any]]


class ResultManifest(_Model):
    columns: list[ColumnSchema]
    row_count: int
    page_count: int
    byte_count: int
    truncated: bool


class ResultPage(_Model):
    row_offset: int
    row_count: int
    rows: list[list[Any]]
    next_cursor: str | None = None


class RowFilterOut(_Model):
    expression: str
    groups: list[str]
    except_groups: list[str]
    applies_to_me: bool
    source: Literal['portal', 'unity'] | str = Field(default='portal')


class RuleOut(_Model):
    key: str
    name: str | None
    column: str | None
    kind: str
    metric: str | None
    operator: str | None
    expected: str | None
    unit: str | None
    dimension: str | None
    severity: str | None
    checked: bool


class RunCatalogScope(_Model):
    "data-run-catalog-scope D5: ``sent`` when runs get a run token and a catalog scope for SQE. It says the scope is\nsent, never that it is enforced: enforcement is SQE's, where its ``[session.catalog_scope]`` is set."

    state: Literal['off', 'sent'] | str


class RunCatalogScopeInfo(_Model):
    "The catalog scope sent to SQE with the run's token (data-run-catalog-scope D3). Sent, not enforced: SQE\nenforces it where its ``[session.catalog_scope]`` is set (config ``run_catalog_scope.state``)."

    mode: Literal['bindings', 'narrow', 'listed', 'grants'] | str
    catalogs: dict[str, Literal['read_write', 'read_only'] | str]
    set_by: str | None = Field(default=None, description='A widened scope: who set it (a person reference)')


class RunNow(_Model):
    job_parameters: dict[str, str] | None = None
    idempotency_token: str | None = Field(default=None, description="Databricks' name for the Idempotency-Key header; the same value in both, or one of them")


class RunOut(_Model):
    id: str
    namespace: str
    table: str
    status: str
    total: int
    passed: int
    failed: int
    errored: int
    score: float | None
    contract_version: int | None
    contract_changed: bool
    snapshot_id: int | None
    started_at: datetime
    started_by: str
    elapsed_ms: int
    scope: str = Field(default='full')
    source: Literal['contract', 'dbt'] | str = Field(default='contract')
    warned: int = Field(default=0)
    job_run_id: str | None = None
    checks: list[CheckOut]
    table_state: Literal['published', 'unchanged', 'refused', 'skipped'] | str | None = None


class RunScopeCapIn(_Model):
    cap: Literal['bindings', 'listed', 'grants'] | str


class RunScopeCapOut(_Model):
    workspace: str
    cap: Literal['bindings', 'listed', 'grants'] | str


class RunSummaryOut(_Model):
    id: str
    namespace: str
    table: str
    status: str
    total: int
    passed: int
    failed: int
    errored: int
    score: float | None
    contract_version: int | None
    contract_changed: bool
    snapshot_id: int | None
    started_at: datetime
    started_by: str
    elapsed_ms: int
    scope: str = Field(default='full')
    source: Literal['contract', 'dbt'] | str = Field(default='contract')
    warned: int = Field(default=0)
    job_run_id: str | None = None


class SampleColumn(_Model):
    name: str
    type: str
    classification: str


class SampleInfo(_Model):
    columns: list[SampleColumn]
    rows: list[list[Any]]
    truncated: bool


class SavedQueryIn(_Model):
    name: str
    description: str = Field(default='')
    sql: str
    shared: bool = Field(default=False)
    folder: str = Field(default='')


class SavedQueryList(_Model):
    items: list[SavedQueryOut]
    next_cursor: str | None = None


class SavedQueryOut(_Model):
    id: str
    name: str
    description: str
    sql: str
    shared: bool
    folder: str
    owner: str
    mine: bool
    version: int
    created_at: datetime
    updated_at: datetime
    actions: list[str] | None = Field(default=None, description='What the caller may call on the query next (C18.2); when one query is read')


class SavedQueryUpdate(_Model):
    "A partial update: only the fields sent change. The version edited comes in ``If-Match``."

    name: str | None = None
    description: str | None = None
    sql: str | None = None
    shared: bool | None = None
    folder: str | None = None


class SchemaCreate(_Model):
    name: str
    location_name: str | None = None


class SchemaInfo(_Model):
    name: str
    catalog_name: str
    full_name: str
    location_name: str | None = None
    storage_root: str | None = None


class SchemaList(_Model):
    items: list[SchemaInfo]
    next_cursor: str | None = None


class SearchGroup(_Model):
    kind: Literal['table', 'column', 'term', 'project', 'file'] | str
    hits: list[SearchHit]
    more: bool


class SearchHit(_Model):
    kind: Literal['table', 'column', 'term', 'project', 'file'] | str
    workspace: str
    title: str
    match: Literal['name', 'synonym', 'description', 'path', 'content'] | str
    catalog: str | None = None
    namespace: str | None = None
    table: str | None = None
    column: str | None = None
    type: str | None = None
    term: str | None = None
    status: str | None = None
    project: str | None = None
    branch: str | None = None
    snippet: str | None = None
    owner: str | None = None
    updated_at: datetime | None = None


class SearchOut(_Model):
    terms: list[SearchTerm]
    tables: list[SearchTable]
    truncated: bool


class SearchResults(_Model):
    groups: list[SearchGroup]
    truncated: bool


class SearchTable(_Model):
    catalog: str
    namespace: str
    table: str
    match: str
    term: str | None = None


class SearchTerm(_Model):
    id: str
    name: str
    synonyms: list[str]
    status: str


class SecretExplainOut(_Model):
    allowed: bool
    need: str
    via: str | None
    group: str | None
    privilege: str | None
    missing: str | None
    summary: str


class SecretGrantIn(_Model):
    group: str
    privilege: str


class SecretGrantOut(_Model):
    group: str
    privilege: str
    granted_by: str
    granted_at: datetime
    source: str


class SecretOut(_Model):
    key: str
    version: int
    kind: str
    meta: dict[str, Any]
    updated_at: datetime
    updated_by: str
    last_used_at: datetime | None
    used_by: list[SecretUseOut] | None = None


class SecretPermissionsOut(_Model):
    owner_group: str | None
    grants: list[SecretGrantOut]


class SecretPermissionsUpdate(_Model):
    "Every grant of the scope (groups only) and, optionally, a new owner group."

    grants: list[SecretGrantIn] | None = None
    owner_group: str | None = None


class SecretRewrapOut(_Model):
    rewrapped: int
    remaining: dict[str, int]


class SecretScopeCreate(_Model):
    "A scope's name (unique in the workspace) and its owner group (one of the workspace's groups; default: its\nadmin group)."

    name: str
    owner_group: str | None = None


class SecretScopeOut(_Model):
    id: str
    name: str
    kind: str
    owner_group: str | None
    privileges: list[str]
    secrets: int
    created_at: datetime
    created_by: str
    source: str


class SecretScopes(_Model):
    items: list[SecretScopeOut]


class SecretUseOut(_Model):
    "A project file that read the secret, from a run or a notebook, and the job when it ran in one; never who."

    project: str
    path: str
    kind: str
    job: str | None
    used_at: datetime
    uses: int


class SecretValue(_Model):
    "The secret's value; it is encrypted at rest and never answered."

    value: str


class Secrets(_Model):
    items: list[SecretOut]


class SelectAdminMissing(_Model):
    role: str
    catalog: str
    tables: list[str]


class SelectBackfillOut(_Model):
    applied: list[str]
    coverage: SelectCoverageOut


class SelectCatalog(_Model):
    catalog: str
    tables: int
    missing: list[SelectMissing]
    outside: Literal['samples', 'system'] | str | None = None
    listed: bool
    note: str | None = None


class SelectCoverageOut(_Model):
    checked_at: str
    ranger_select: bool
    complete: bool
    catalogs: list[SelectCatalog]
    platform_admin_roles: list[SelectAdminMissing]


class SelectMissing(_Model):
    namespace: str
    table: str
    principals: list[str]


class SessionPip(_Model):
    "Whether ``%pip install`` works in this workspace's kernels."

    enabled: bool


class ShortSecretOut(_Model):
    scope_kind: str
    workspace: str
    scope: str
    owner_ref: str | None = None
    key: str


class ShortSecrets(_Model):
    items: list[ShortSecretOut]


class SlaOut(_Model):
    "An ODCS ``slaProperties`` entry; ``checked`` when a run evaluates it (a freshness SLA, data-contracts-gap D4)."

    key: str | None
    property: str
    value: Any | None = None
    unit: str | None = None
    element: str | None = None
    checked: bool


class SnapshotInfo(_Model):
    snapshot_id: int
    parent_snapshot_id: int | None
    timestamp_ms: int | None
    operation: str | None
    added_records: int | None
    deleted_records: int | None
    added_files: int | None
    deleted_files: int | None
    total_records: int | None
    current: bool
    time_travel_sql: str | None = None


class SnapshotList(_Model):
    items: list[SnapshotInfo]
    next_cursor: str | None = None


class SourceQualityOut(_Model):
    "The latest quality run of one source on a table (data-dbt-lineage-quality DL-7, design D4)."

    source: Literal['contract', 'dbt'] | str
    status: Literal['passed', 'warning', 'failed', 'error'] | str
    score: float | None
    checked_at: datetime
    run_id: str


class SparkOut(_Model):
    state: str
    kernels: int
    runs: int


class SqeOut(_Model):
    status: str
    version: str | None = None
    uptime_seconds: int | None = None
    workers: int | None = None
    healthy_workers: int | None = None


class StatementColumn(_Model):
    name: str
    type: str


class StatementExecute(_Model):
    "A statement to run now. The rows come back in the answer and nothing of them is kept; a long run or a result\nto page through is a submitted statement (``statements_submit``)."

    sql: str
    engine: Literal['sqe', 'spark'] | str = Field(default='sqe')
    catalog: str | None = None
    schema_: str | None = Field(default=None, alias='schema')
    row_limit: int | None = None


class StatementExplain(_Model):
    sql: str
    engine: Literal['sqe', 'spark'] | str = Field(default='sqe')
    catalog: str | None = None
    schema_: str | None = Field(default=None, alias='schema')


class StatementFailure(_Model):
    "Why a statement failed: the code the synchronous route answers a 403 or 422 with (a refusal:\n``policy_conflict``, ``privilege_refused``, ``service_account``, ``catalog_*``; the engine failed it:\n``statement_failed``, its message the engine's), ``failed`` (a failure with no code of its own), ``timeout``,\n``token_expired``, ``unauthenticated``, ``unavailable`` (the engine could not be reached), ``too_many_requests``\n(the engine was busy; submit it again in a few seconds), ``replica_lost``, ``outcome_unknown`` or ``internal``.\n\n``outcome_unknown`` (sql 1.7): a write was sent and its answer was lost, it ran out of time, or the service stopped\nwhile it ran. It may or may not have changed the table: check the table before you run it again, never retry it\nblindly. ``cause`` says why. ``timeout`` and ``replica_lost`` are then a read's only."

    code: str
    message: str
    cause: Literal['lost_answer', 'timeout', 'replica_lost'] | str | None = Field(default=None, description='Why the outcome is unknown; only with code outcome_unknown (sql 1.7), left out otherwise.')


class StatementInfo(_Model):
    id: str
    state: Literal['PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED', 'CLOSED'] | str
    engine: str
    catalog: str
    schema_: str | None = Field(default=None, alias='schema')
    query_tag: str | None = None
    submitted_at: datetime
    finished_at: datetime | None = None
    expires_at: datetime | None = None
    error: StatementFailure | None = None
    manifest: ResultManifest | None = None
    result: ResultPage | None = None


class StatementRows(_Model):
    "A finished statement's rows. A failure is an ``ErrorInfo`` (``statement_failed`` with ``details.line`` when\nthe engine named one, ``privilege_refused``, ``catalog_*``, ``too_many_requests`` with ``Retry-After`` when the\nengine was busy), never an answer with an error inside."

    state: Literal['SUCCEEDED'] | str = Field(default='SUCCEEDED')
    columns: list[StatementColumn]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    row_cap: int
    elapsed_ms: int
    engine: str
    ran_as: str | None = None
    bytes_scanned: int | None = None


class StatementSubmit(_Model):
    sql: str
    engine: Literal['sqe', 'spark'] | str = Field(default='sqe')
    catalog: str | None = None
    schema_: str | None = Field(default=None, alias='schema')
    wait_timeout: int = Field(default=10)
    on_wait_timeout: Literal['CONTINUE', 'CANCEL'] | str = Field(default='CONTINUE')
    row_limit: int | None = None
    query_tag: str | None = None


class StatementTranspile(_Model):
    sql: str
    dialect: Literal['sqe', 'databricks', 'spark', 'trino', 'athena', 'snowflake', 'bigquery', 'redshift', 'postgres'] | str = Field(default='databricks')
    engine: Literal['sqe', 'spark'] | str | None = None
    schema_: str | None = Field(default=None, alias='schema')


class StorageLocationIn(_Model):
    name: str
    url: str
    comment: str | None = None


class StorageLocationInfo(_Model):
    name: str
    url: str
    comment: str | None = None
    catalogs: int = Field(default=0)
    schemas: int = Field(default=0)


class StorageLocationList(_Model):
    items: list[StorageLocationInfo]
    next_cursor: str | None = None


class StorageLocationPatch(_Model):
    comment: str | None = None


class StrayOut(_Model):
    id: int
    name: str
    catalog: str
    resource: str


class StraysOut(_Model):
    policies: list[StrayOut]


class StraysRemove(_Model):
    "The ids of the stray policies to delete (the ones still stray are deleted, the rest left alone)."

    ids: list[int]


class SubjectEraseOut(_Model):
    subject_ref: str
    audit_events_pseudonymised: int
    erased: dict[str, int]


class SubjectExportOut(_Model):
    subject_ref: str
    audit_events: list[dict[str, Any]]
    data: dict[str, list[dict[str, Any]]]


class SuggestionOut(_Model):
    id: str
    column: str | None
    kind: str
    rule: dict[str, Any]
    reason: str


class SuggestionSourceOut(_Model):
    workspace: str | None
    namespace: str
    table: str
    column: str
    classification: str
    transformation: str


class SuggestionsApply(_Model):
    "The suggestions to merge, by id; the server computes them again, the client never sends rules."

    ids: list[str]
    version: int


class SuggestionsOut(_Model):
    snapshot_id: int | None
    current_snapshot_id: int | None
    stale: bool
    scope: str
    profiled_at: datetime
    suggestions: list[SuggestionOut]


class SystemJobRunOut(_Model):
    id: str
    project: str
    job: str
    number: int
    status: str
    trigger: str
    identity: str
    created_at: datetime
    started_at: datetime | None
    can_cancel: bool


class SystemKernelOut(_Model):
    id: str
    project: str
    project_name: str
    path: str
    branch: str | None
    job: bool
    owner: str
    mine: bool
    status: str
    running: bool
    engine: str
    created_at: datetime
    last_used_at: datetime
    can_stop: bool
    memory_bytes: int | None = None
    memory_limit_bytes: int | None = None


class SystemOut(_Model):
    operator: bool
    executor: bool
    limits: LimitsOut
    kernels: list[SystemKernelOut]
    runs: list[SystemRunOut]
    job_runs: list[SystemJobRunOut]
    jobs: JobsSummaryOut
    spark: SparkOut
    sqe: SqeOut
    statements: int = Field(default=0)


class SystemRunOut(_Model):
    id: str
    project: str
    project_name: str
    action: str
    path: str
    branch: str
    status: str
    engine: str
    started_by: str
    mine: bool
    created_at: datetime
    started_at: datetime | None
    can_cancel: bool


class SystemTagOut(_Model):
    "A tag the portal computes from the object and nobody sets (data-tag-inheritance TI-5): ``class=<level>``, the\nclassification of a table or view (``column`` null) and of each of its columns. Read only: changed by\nclassifying, refused by tagging (422 ``system_tag``)."

    column: str | None = None
    tag: str
    value: str
    source: Literal['column', 'table', 'default'] | str = Field(description="Where the level comes from: the column's own classification, the table's, or the default")
    read_only: bool = Field(default=True)


class TableContracts(_Model):
    items: list[ContractListItem] = Field(description="The catalog's contracts on tables the caller can read")


class TableInfo(_Model):
    name: str
    catalog_name: str
    schema_name: str
    full_name: str
    table_type: str = Field(default='ICEBERG')
    storage_location: str | None
    format_version: int | None
    columns: list[ColumnInfo]
    partition_fields: list[str]
    current_snapshot_id: int | None
    current_snapshot: SnapshotInfo | None = None
    classification: str
    classification_explicit: bool = Field(default=False)
    contract: ContractStatusOut | None = Field(default=None, description='With expand=contract; None: no contract')
    profile: ProfileSummaryOut | None = Field(default=None, description='With expand=profile: your latest profile')
    expand_errors: list[str] | None = Field(default=None, description='Expanded parts that could not be read now')
    actions: list[str] | None = Field(default=None, description='What the caller may call on the table next (C18.2)')


class TableList(_Model):
    items: list[TableSummary]
    next_cursor: str | None = None


class TableSummary(_Model):
    name: str
    catalog_name: str
    schema_name: str
    full_name: str


class TableTermOut(_Model):
    id: str
    name: str
    definition: str
    column: str
    status: str


class TableTerms(_Model):
    items: list[TableTermOut]


class TagOnColumnOut(_Model):
    "A governed tag on a column (data-tag-access TA-5): its mask and row filter and whether they apply to me."

    column: str
    tag: str = Field(description="The catalog's tag by its bare name (`pii`); another catalog's tag as `<catalog>.<name>`")
    mask_type: str | None
    mask_applies_to_me: bool
    row_filter: str | None
    filter_applies_to_me: bool
    source: Literal['column', 'table', 'schema'] | str = Field(default='column', description='Where the tag sits: on the column itself, or on its table (`sqe.table-tags`) or its schema (`sqe.schema-tags`, while SQE inherits schema tags), whose tags count on every top-level column')


class TagOut(_Model):
    "A governed tag of the catalog, by its bare name: the catalog it belongs to is the route's (data-tag-access\nTA-13). Ranger names it ``<catalog>.<name>``, and so does the service in ``sqe.column-tags`` (task 6.7)."

    name: str
    description: str
    mask_type: str | None
    mask_except: list[str]
    row_filter: str | None
    filter_groups: list[str]
    filter_except: list[str]
    allowed_values: list[str] | None = None
    set_by: str
    set_at: datetime


class TagsOut(_Model):
    items: list[TagOut]
    policies: bool
    can_manage: bool


class TemplateOut(_Model):
    id: str
    kind: str
    type: str
    version: int
    label: str
    description: str
    source: str
    builtin: bool
    pending: str | None
    open: str | None
    extension: str | None
    files: list[str]


class TemplateRepoChange(_Model):
    "What changes; a missing field keeps the stored one."

    url: str | None = None
    ref: str | None = None
    commit: str | None = None
    enabled: bool | None = None


class TemplateRepoCreate(_Model):
    "A repository of project templates: its slug, URL, ref and (optionally) the commit to pin."

    slug: str
    url: str
    ref: str = Field(default='main')
    commit: str | None = None
    enabled: bool = Field(default=True)


class TemplateRepoOut(_Model):
    id: str
    slug: str
    url: str
    ref: str
    commit: str
    enabled: bool
    templates: list[str]
    files: int
    size: int
    synced_at: datetime
    synced_by: str
    created_at: datetime


class TemplateRepos(_Model):
    items: list[TemplateRepoOut]


class TemplateTypeOut(_Model):
    id: str
    pending: str | None


class TemplatesOut(_Model):
    types: list[TemplateTypeOut]
    projects: list[TemplateOut]
    starters: list[TemplateOut]


class TermOut(_Model):
    id: str
    name: str
    definition: str
    synonyms: list[str]
    filter_expression: str | None
    owner_group: str
    status: str
    version: int
    updated_at: datetime
    updated_by: str
    columns: list[LinkOut]
    hidden_links: int
    warnings: list[str]
    actions: list[str] | None = Field(default=None, description='What the caller may call on the term (C18.2): update, update-status, delete; null in a list')


class TermVersionOut(_Model):
    version: int
    change: str
    changed_at: datetime
    changed_by: str
    snapshot: dict[str, Any]


class TestOut(_Model):
    ok: bool
    code: str | None = None
    message: str | None = None


class TranspileOut(_Model):
    dialect: str
    target: str = Field(default='sqe')
    statements: list[TranspiledStatement]
    translated: int
    needs_review: int
    blocked: int


class TranspileReason(_Model):
    code: str
    message: str


class TranspiledStatement(_Model):
    index: int
    line: int
    status: Literal['translated', 'needs_review', 'blocked'] | str
    sql: str | None = None
    reasons: list[TranspileReason] = Field(default=[])
    notes: list[TranspileReason] = Field(default=[])
    check: Literal['explained', 'failed', 'not_checked', 'skipped'] | str


class Upload(_Model):
    upload_id: str
    scope: Literal['personal', 'workspace'] | str = Field(description="personal: the uploader's alone; workspace: anyone who may see the workspace")
    mine: bool = Field(description='The caller uploaded it (who else did is not said)')
    format: Literal['parquet', 'csv', 'json'] | str
    options: dict[str, Any]
    size_bytes: int
    state: Literal['RECEIVING', 'STAGED', 'LOADING', 'LOADED', 'FAILED', 'REJECTED', 'EXPIRED'] | str
    scanner: str
    catalog: str = Field(description='The catalog the file is loaded into (the home catalog until a load names another)')
    schema_name: str | None = None
    table_name: str | None = None
    mode: Literal['create', 'append'] | str | None = None
    row_count: int | None = None
    error_code: str | None = None
    created_at: datetime


class UploadLoad(_Model):
    catalog: str | None = Field(default=None, description="One of the workspace's catalogs, bound read-write (403 catalog_read_only otherwise); none: the home catalog")
    schema_: str = Field(alias='schema', description='A schema of that catalog')
    table: str
    mode: Literal['create', 'append'] | str = Field(default='create')
    confirm: bool = Field(default=False, description='Load a file already loaded into this table again (I7)')


class Uploads(_Model):
    items: list[Upload]


class UpstreamProblemOut(_Model):
    workspace: str | None
    namespace: str
    table: str
    depth: int
    reason: Literal['failing', 'changed'] | str
    status: str
    last_run_at: datetime
    last_write: datetime | None
    source: Literal['contract', 'dbt'] | str = Field(default='contract')
    sources: list[SourceQualityOut] = Field(default=[])


class UpstreamProblemsOut(_Model):
    items: list[UpstreamProblemOut]
    hidden: int
    truncated: bool


class VerificationOut(_Model):
    "When the chain was last walked (data-audit-last-verified V2): the detection run and an admin's check."

    scheduled: VerificationRun | None
    manual: VerificationRun | None
    interval_hours: float


class VerificationRun(_Model):
    at: datetime
    ok: bool | None
    checked: int | None


class VerifyOut(_Model):
    ok: bool
    checked: int
    first_broken_seq: int | None
    reason: str | None
    purged_through_seq: int | None
    verified_at: datetime | None = None
    export: ExportCheck | None = None


class ViewInfo(_Model):
    name: str
    catalog_name: str
    schema_name: str
    full_name: str
    columns: list[ColumnInfo]
    view_definition: str | None
    default_schema: str | None = None
    version_id: int | None
    versions: int = Field(default=1)
    classification: str
    classification_explicit: bool = Field(default=False)
    reads: list[str] | None = Field(default=None, description='Tables and views the definition reads, as you see it')
    reads_known: bool = Field(default=False)


class ViewList(_Model):
    items: list[TableSummary]
    next_cursor: str | None = None


class VolumeCreate(_Model):
    name: str
    comment: str | None = None
    owner_group: str | None = Field(default=None, description="None: the workspace's admin group")


class VolumeExplanation(_Model):
    allowed: bool
    need: str
    via: str | None
    group: str | None
    privilege: str | None
    missing: str | None
    summary: str


class VolumeFile(_Model):
    name: str
    path: str
    kind: Literal['file', 'directory'] | str
    size_bytes: int | None
    modified_at: datetime | None


class VolumeFiles(_Model):
    items: list[VolumeFile]


class VolumeGrant(_Model):
    group: str
    privilege: str


class VolumeGrantInfo(_Model):
    group: str
    privilege: str
    granted_by: str
    granted_at: datetime


class VolumeInfo(_Model):
    volume_id: str
    name: str
    catalog_name: str
    schema_name: str
    full_name: str
    volume_type: Literal['MANAGED'] | str = Field(default='MANAGED')
    comment: str | None
    owner_group: str | None
    privileges: list[str] = Field(description="The caller's privileges on the volume")
    read_only: bool = Field(description='The catalog is bound read-only to this workspace')
    created_at: datetime
    created_by: str
    actions: list[str] | None = Field(default=None, description='What the caller may call on the volume next (C18.2); when one volume is read')


class VolumePermissions(_Model):
    owner_group: str | None
    grants: list[VolumeGrantInfo]


class VolumePermissionsUpdate(_Model):
    grants: list[VolumeGrant] | None = None
    owner_group: str | None = None


class Volumes(_Model):
    items: list[VolumeInfo]


class WorkspaceCatalogCreate(_Model):
    "A catalog in the workspace: isolated and bound read-write there."

    name: str
    comment: str | None = None
    storage_location: str | None = None
    owner_group: str | None = Field(default=None, description="Default: the workspace's admin group")


class WorkspaceCatalogInfo(_Model):
    name: str
    home: bool
    binding: Literal['read_write', 'read_only'] | str
    isolation: Literal['open', 'isolated'] | str
    comment: str | None = None
    default: bool = Field(default=False)


class WorkspaceCatalogList(_Model):
    items: list[WorkspaceCatalogInfo]
    next_cursor: str | None = None


class WorkspaceCreate(_Model):
    slug: str
    display_name: str
    viewer_groups: list[str]
    admin_group: str | None = None
    external_id: str | None = Field(default=None, description='Your own label for it: unique, no grants')


class WorkspaceInfo(_Model):
    slug: str
    display_name: str
    home_catalog: str
    default_schema: str
    status: str
    viewer_groups: list[str]
    admin_group: str | None
    allowed_actions: list[str]
    actions: list[str] | None = Field(default=None, description='What the caller may call on the workspace next (C18.2); when one workspace is read')
    external_id: str | None = None
    default_catalog: str | None = Field(default=None, description='Where runs, notebooks and jobs that name no catalog start; None: the home catalog')
    run_scope_cap: Literal['bindings', 'listed', 'grants'] | str = Field(default='bindings', description="The widest catalog scope the workspace's admin may give a run (data-run-catalog-scope D3); data.admin sets it")


class WorkspaceJobInfo(_Model):
    name: str
    description: str | None
    run_as: str
    owner: str
    deployed: bool
    enabled: bool
    disabled_reason: str | None
    schedule: str | None
    timezone: str | None
    triggers: list[str]
    tasks: int
    consecutive_failures: int = Field(default=0)
    commit_sha: str | None = None
    target: str | None = Field(default=None, description='The bundle target it was deployed from')
    event_trigger: JobEventTriggerOut | None = None
    deployed_at: datetime | None = None
    next_fire_at: datetime | None
    last_run: JobRunInfo | None
    recent_runs: list[JobRunInfo] | None = Field(default=None, description='Its last runs, newest first; in lists')
    privileges: list[str] | None = Field(default=None, description="The caller's on the job; when one job is read")
    project_privileges: list[str] | None = Field(default=None, description="The caller's on its project; idem")
    actions: list[str] | None = Field(default=None, description='What the caller may call on the job next (C18.2): update, run-now, update-permissions; when one job is read')
    notifications: dict[str, Any] | None = None
    health_seconds: int | None = Field(default=None, description='Its run duration warning')
    event_pending: JobEventPending | None = None
    task_graph: list[JobTaskOut] | None = Field(default=None, description='expand=task_graph')
    stats: JobRunStatsOut | None = Field(default=None, description='expand=stats: its runs of the last `days`')
    definition_yaml: str | None = Field(default=None, description='expand=definition: as it would read in project.yml')
    project: str
    project_name: str
    mine: bool = Field(description='The caller deployed it')
    active_runs: int
    can_run: bool = Field(description='CAN MANAGE RUN on the job: run now, cancel its runs')
    can_manage: bool = Field(description='CAN MANAGE on the job: pause, enable, its permissions')


class WorkspaceJobList(_Model):
    items: list[WorkspaceJobInfo]
    next_cursor: str | None = None


class WorkspaceJobRunInfo(_Model):
    run_id: str
    number: int
    trigger: str
    status: str = Field(description='One of waiting, queued, running (not ended) or succeeded, failed, cancelled, skipped, expired (ended). A run moves waiting, queued, running, then to one of the ended states. `waiting`: fired while the job was at max_concurrent_runs with its queue on; it has no task runs until a slot frees, then it is `queued`. `skipped`: it never started (at the limit without a queue, the queue full or too old, the job undeployed). `expired`: the identity the job runs as was lost (the job is disabled; `error` says why). A client should treat a state it does not know as not ended.')
    commit_sha: str
    run_as: str
    identity_kind: str | None = Field(default=None, description='What run_as names: owner or service_principal')
    started_by: str | None
    repair_of: str | None = Field(default=None, description='The run this one retries')
    job_parameters: dict[str, str]
    trigger_event: JobRunEventOut | None = None
    error: str | None
    error_code: str | None = Field(default=None, description='`outcome_unknown`: a write was sent and its outcome is unknown (data-outcome-unknown); the task is never retried. Check the table before you run it again')
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    task_status: dict[str, str] | None = Field(default=None, description="Each task's status at its current attempt; in the job's run list")
    tasks: list[JobTaskRunInfo] | None = Field(default=None, description='Filled when one run is read')
    task_graph: list[JobTaskOut] | None = Field(default=None, description='The graph it ran; when one run is read')
    privileges: list[str] | None = Field(default=None, description="The caller's on the job; when one run is read")
    project_privileges: list[str] | None = Field(default=None, description="The caller's on the project; idem")
    actions: list[str] | None = Field(default=None, description='What the caller may call on the run next (C18.2): cancel, retry; when one run is read')
    project: str
    project_name: str
    job: str
    job_run_as: str = Field(description='What the job runs as: owner or service_principal')
    can_cancel: bool = Field(description='Not ended, and CAN MANAGE RUN on the job')


class WorkspaceJobRunList(_Model):
    items: list[WorkspaceJobRunInfo]
    next_cursor: str | None = None


class WorkspaceJobStats(_Model):
    days: int
    succeeded: int = Field(description='Runs of the jobs the caller may see that succeeded in the last `days`')


class WorkspaceList(_Model):
    items: list[WorkspaceInfo]
    next_cursor: str | None = None


class WorkspaceStorageOut(_Model):
    location: str | None
    size_bytes: int | None
    files: int | None
    tables_measured: int
    tables_unknown: int
    tables_unreadable: int
    truncated: bool


class WorkspaceSummaryOut(_Model):
    tables: int
    projects: int
    jobs: int
    quality: QualitySummary
    last_change: datetime | None
    truncated: bool


class WorkspaceUpdate(_Model):
    "Only what is sent changes. ``default_catalog``: one of the workspace's catalogs, or null for the home one.\nAny other field is refused (422), so a client never takes an ignored field for a change."

    default_catalog: str | None = None


for _m in (AlertOut, AlertStatus, Alerts, AssignedTagOut, AuditEvents, AuditIngestOut, BundleEntryOut, BundleTargetOut, CatalogBindingInfo, CatalogBindingList, CatalogBindingUpdate, CatalogCreate, CatalogInfo, CatalogList, CatalogScope, CatalogUpdate, ChangeIn, CheckOut, ClassificationSuggestionOut, ClassificationSuggestions, ClassificationUpdate, ColumnInfo, ColumnQualityOut, ColumnRef, ColumnSchema, ColumnStatsOut, ConfigInfo, ConflictingMaskOut, ContractListItem, ContractOut, ContractPut, ContractStatusOut, DbtImportOut, DeadLetterOut, DeadLetters, Deliveries, DeliveryOut, DeploymentIn, DeploymentOut, DeploymentValidateIn, DeploymentValidateOut, DestinationOut, DestinationWrite, DestroyOut, DetectionRunOut, DigestOut, DigestWorkspace, DriftOut, ErrorInfo, EventDetail, EventOut, ExplainOut, ExportCheck, FileUsageList, FileUsageOut, FromDbt, GatewayAuditOut, GitCredentialOut, GitOAuthComplete, GitOAuthStartOut, GitProviderOut, GitProviders, GitToken, GlossaryImport, GlossaryTermCreate, GlossaryTermHistory, GlossaryTermStatus, GlossaryTermUpdate, GlossaryTerms, GovernanceChange, GovernanceChanges, GrantOut, GroupInfo, Groups, HistoryEntry, HistoryEntryList, IdentityRemovedOut, ImpactItemOut, ImpactOut, ImportOut, InactiveOut, InboxItem, InboxOut, IngestLedgerItem, IngestLedgerList, IngestLedgerSummary, IngestOut, ItemChangeOut, JobBuilderCheckIn, JobBuilderCheckOut, JobBuilderExportIn, JobBuilderExportOut, JobBuilderImportIn, JobBuilderImportOut, JobBuilderJobOut, JobEventPending, JobEventTriggerOut, JobEventTypeOut, JobForEachOut, JobGrantIn, JobGrantOut, JobInfo, JobList, JobPermissionsIn, JobPermissionsOut, JobRunEventOut, JobRunInfo, JobRunList, JobRunStatsOut, JobTaskOut, JobTaskRunInfo, JobUpdate, JobsConsentComplete, JobsConsentStartOut, JobsDeployOut, JobsIdentityOut, JobsProblemOut, JobsRevokedOut, JobsSummaryOut, LastDeliveryOut, Limits, LimitsOut, LineageColumnEdgeOut, LineageEdgeOut, LineageGraphOut, LineageJobOut, LineageNodeOut, LineageStatusOut, LinkOut, MaskChangeOut, MaskConflictOut, MaskOut, MeOut, MyGitCredentials, MySecrets, NodeQualityOut, NotificationsOut, OwnerOut, PermissionsChangeItem, PermissionsInfo, PermissionsOut, PermissionsUpdate, PreviewOut, PrincipalIn, PrincipalOut, PrivilegeAssignment, ProducerCreate, ProducerCreatedOut, ProducerOut, Producers, ProfileOut, ProfileSummaryOut, ProjectActionOut, ProjectActionResult, ProjectActionRun, ProjectActions, ProjectBranchCreate, ProjectBranchName, ProjectBranchOut, ProjectCommit, ProjectCommitCreate, ProjectCommitOut, ProjectCreate, ProjectCreated, ProjectDetail, ProjectDiff, ProjectDiffOut, ProjectDocsTicket, ProjectExplainOut, ProjectFileCreate, ProjectFileOut, ProjectFileSave, ProjectFiles, ProjectGrantIn, ProjectGrantOut, ProjectHead, ProjectHistory, ProjectInfo, ProjectLastRun, ProjectList, ProjectParamOut, ProjectPermissionsOut, ProjectPermissionsSet, ProjectPullOut, ProjectRunArtifact, ProjectRunInfo, ProjectRunList, ProjectScaffoldOut, ProjectTreeEntry, PropertyOut, QualityRunCreate, QualityRuns, QualitySummary, QueryEngine, QueryEngines, QueryItemOut, QueryOut, QueryStatsOut, RecentOut, RemoteBranch, RemoteBranches, RemovedOut, ResultManifest, ResultPage, RowFilterOut, RuleOut, RunCatalogScope, RunCatalogScopeInfo, RunNow, RunOut, RunScopeCapIn, RunScopeCapOut, RunSummaryOut, SampleColumn, SampleInfo, SavedQueryIn, SavedQueryList, SavedQueryOut, SavedQueryUpdate, SchemaCreate, SchemaInfo, SchemaList, SearchGroup, SearchHit, SearchOut, SearchResults, SearchTable, SearchTerm, SecretExplainOut, SecretGrantIn, SecretGrantOut, SecretOut, SecretPermissionsOut, SecretPermissionsUpdate, SecretRewrapOut, SecretScopeCreate, SecretScopeOut, SecretScopes, SecretUseOut, SecretValue, Secrets, SelectAdminMissing, SelectBackfillOut, SelectCatalog, SelectCoverageOut, SelectMissing, SessionPip, ShortSecretOut, ShortSecrets, SlaOut, SnapshotInfo, SnapshotList, SourceQualityOut, SparkOut, SqeOut, StatementColumn, StatementExecute, StatementExplain, StatementFailure, StatementInfo, StatementRows, StatementSubmit, StatementTranspile, StorageLocationIn, StorageLocationInfo, StorageLocationList, StorageLocationPatch, StrayOut, StraysOut, StraysRemove, SubjectEraseOut, SubjectExportOut, SuggestionOut, SuggestionSourceOut, SuggestionsApply, SuggestionsOut, SystemJobRunOut, SystemKernelOut, SystemOut, SystemRunOut, SystemTagOut, TableContracts, TableInfo, TableList, TableSummary, TableTermOut, TableTerms, TagOnColumnOut, TagOut, TagsOut, TemplateOut, TemplateRepoChange, TemplateRepoCreate, TemplateRepoOut, TemplateRepos, TemplateTypeOut, TemplatesOut, TermOut, TermVersionOut, TestOut, TranspileOut, TranspileReason, TranspiledStatement, Upload, UploadLoad, Uploads, UpstreamProblemOut, UpstreamProblemsOut, VerificationOut, VerificationRun, VerifyOut, ViewInfo, ViewList, VolumeCreate, VolumeExplanation, VolumeFile, VolumeFiles, VolumeGrant, VolumeGrantInfo, VolumeInfo, VolumePermissions, VolumePermissionsUpdate, Volumes, WorkspaceCatalogCreate, WorkspaceCatalogInfo, WorkspaceCatalogList, WorkspaceCreate, WorkspaceInfo, WorkspaceJobInfo, WorkspaceJobList, WorkspaceJobRunInfo, WorkspaceJobRunList, WorkspaceJobStats, WorkspaceList, WorkspaceStorageOut, WorkspaceSummaryOut, WorkspaceUpdate):
    _m.model_rebuild()

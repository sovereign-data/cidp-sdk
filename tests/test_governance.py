"""Governance: column masks, row filters, governed tags and their batches (internal operations, ``client.governance``).

Against a fake v1 transport: each call is the documented operation, a change goes out with ``schema`` and without its
unset fields, the object helpers build the documented change, answers parse into the generated models, 409 and 422
come back as ``Conflict`` and ``InvalidParameter`` with the service's code and details, and the first call of each
operation warns with ``InternalWarning`` (a ``PreviewWarning``).
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import Any

import httpx
import pytest

from cidp_sdk import CIDPClient, Conflict, InternalWarning, InvalidParameter, PreviewWarning, services
from cidp_sdk import _models as m

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "contract" / "openapi-v1.json").read_text())
HOST = "https://portal.example.org"
TOKEN = "eyJ.fixed-token.sig"
BASE = "/api/data/v1/workspaces/sales/catalogs/finance/governance"

CONFIG = {"api_version": "1", "service_version": "0.2.0", "issuer": "https://sso.example.org/realms/portal",
          "client_id": "portal-data-cli", "audience": "portal-data", "polaris_uri": None, "polaris_realm": "portal",
          "object_store_uri": None, "object_store_path_style": True, "capabilities": []}  # fmt: skip
PREVIEW = {"masks": [{"name": "finance.raw.orders.card", "action": "create", "summary": "MASK_SHOW_LAST_4"}],
           "tags": [], "ranger": [{"resource": "finance/raw", "group": "SG-A", "added": ["SELECT"], "removed": []}],
           "inactive": [], "suggestions": [{"op": "grant", "namespace": "raw", "group": "SG-A",
                                             "privilege": "USE SCHEMA"}]}  # fmt: skip
TAGS = {"items": [{"name": "pii", "description": "Personal data", "mask_type": "MASK_HASH", "mask_except": ["SG-DPO"],
                   "row_filter": None, "filter_groups": [], "filter_except": [], "set_by": "ann",
                   "set_at": "2026-11-20T10:00:00Z"}],
        "policies": True, "can_manage": True}  # fmt: skip
GOVERNANCE = {"namespace": "raw", "table": "orders", "kind": "table",
              "owner": {"group": "SG-E", "namespace": None, "table": None, "inherited": True, "kind": "group"},
              "grants": [], "inherited": [], "valid_privileges": ["SELECT", "MODIFY"], "mine": ["SELECT"],
              "can_manage": True,
              "masks": [{"column": "card", "mask_type": "MASK_SHOW_LAST_4", "source": "explicit",
                         "except_groups": ["SG-Fin"], "applies_to_me": True}],
              "row_filter": {"expression": "region = 'EU'", "groups": [], "except_groups": ["SG-Fin"],
                             "applies_to_me": True, "source": "portal"},
              "tags": [{"column": "email", "tag": "pii", "mask_type": "MASK_HASH", "mask_applies_to_me": True,
                        "row_filter": None, "filter_applies_to_me": False}]}  # fmt: skip


def operation(method: str, path: str) -> str:
    for template, ops in CONTRACT["paths"].items():
        if re.match("^" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$", path) and method.lower() in ops:
            return ops[method.lower()]["operationId"]
    raise AssertionError(f"{method} {path} is not in openapi-v1.json")


class Fake:
    """Answers the governance operations; ``refuse`` makes the next change batch answer that error instead."""

    def __init__(self):
        self.calls: list[tuple[str, dict[str, str], Any]] = []
        self.refuse: httpx.Response | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        op = operation(request.method, request.url.path)
        body = json.loads(request.content) if request.content else None
        if op != "config_get":
            self.calls.append((op, dict(request.url.params), body))
        match op:
            case "config_get":
                return httpx.Response(200, json=CONFIG)
            case "governance_get":
                return httpx.Response(200, json=GOVERNANCE)
            case "governance_tags_list":
                return httpx.Response(200, json=TAGS)
            case "governance_changes_apply" | "governance_changes_preview":
                if self.refuse is not None:
                    return self.refuse
                return httpx.Response(200, json=PREVIEW)
        raise AssertionError(op)

    @property
    def last(self) -> tuple[str, dict[str, str], Any]:
        return self.calls[-1]


@pytest.fixture
def fake() -> Fake:
    return Fake()


@pytest.fixture
def client(fake: Fake):
    c = CIDPClient(host=HOST, token=TOKEN, env={}, transport=httpx.MockTransport(fake))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InternalWarning)
        yield c
    c.close()


def test_service_get_tags_apply_preview(client: CIDPClient, fake: Fake) -> None:
    g = client.governance.get("sales", "finance", schema="raw", table="orders")
    assert fake.last[:2] == ("governance_get", {"schema": "raw", "table": "orders"})
    assert isinstance(g, m.PermissionsOut)
    assert g.masks[0].mask_type == "MASK_SHOW_LAST_4" and g.row_filter and g.row_filter.except_groups == ["SG-Fin"]
    assert g.tags[0].tag == "pii"

    client.governance.get("sales", "finance")
    assert fake.last[:2] == ("governance_get", {})

    tags = client.governance.tags("sales", "finance")
    assert fake.last[0] == "governance_tags_list"
    assert tags.policies and tags.can_manage and tags.items[0].name == "pii" and tags.items[0].mask_except == ["SG-DPO"]

    out = client.governance.apply("sales", "finance", [
        {"op": "grant", "schema": "raw", "group": "SG-A", "privilege": "SELECT"},
        m.GovernanceChange(op="mask", schema="raw", table="orders", column="card", mask_type="MASK_HASH"),
    ])  # fmt: skip
    assert fake.last == ("governance_changes_apply", {}, {"changes": [
        {"op": "grant", "schema": "raw", "group": "SG-A", "privilege": "SELECT"},
        {"op": "mask", "schema": "raw", "table": "orders", "column": "card", "mask_type": "MASK_HASH"},
    ]})  # fmt: skip
    assert isinstance(out, m.PreviewOut)
    assert out.masks[0].action == "create" and out.ranger[0].added == ["SELECT"]
    assert out.suggestions[0].namespace == "raw"

    client.governance.preview("sales", "finance", [{"op": "tag_define", "tag": "pii"}])
    assert fake.last == ("governance_changes_preview", {}, {"changes": [{"op": "tag_define", "tag": "pii"}]})


def test_table_helpers(client: CIDPClient, fake: Fake) -> None:
    orders = client.workspace("sales").catalog("finance").schema("raw").table("orders")
    t = {"schema": "raw", "table": "orders"}

    orders.mask("card", "MASK_SHOW_LAST_4", except_groups=["SG-Fin"])
    assert fake.last == (
        "governance_changes_apply",
        {},
        {
            "changes": [
                {"op": "mask", **t, "column": "card", "mask_type": "MASK_SHOW_LAST_4", "except_groups": ["SG-Fin"]}
            ]
        },
    )
    orders.mask("card", "MASK_NULL")
    assert fake.last[2] == {"changes": [{"op": "mask", **t, "column": "card", "mask_type": "MASK_NULL"}]}
    orders.unmask("card")
    assert fake.last[2] == {"changes": [{"op": "unmask", **t, "column": "card"}]}
    orders.row_filter("region = 'EU'", groups=("SG-A",), except_groups=["SG-Fin"])
    assert fake.last[2] == {"changes": [{"op": "row_filter", **t, "expression": "region = 'EU'", "groups": ["SG-A"],
                                         "except_groups": ["SG-Fin"]}]}  # fmt: skip
    orders.clear_row_filter()
    assert fake.last[2] == {"changes": [{"op": "clear_row_filter", **t}]}

    g = orders.governance()
    assert fake.last[:2] == ("governance_get", t)
    assert g.kind == "table"


def test_catalog_tag_helpers_and_governance_ref(client: CIDPClient, fake: Fake) -> None:
    finance = client.workspace("sales").catalog("finance")

    finance.define_tag("pii", "Personal data")
    assert fake.last == (
        "governance_changes_apply",
        {},
        {"changes": [{"op": "tag_define", "tag": "pii", "description": "Personal data"}]},
    )
    finance.define_tag("pii")
    assert fake.last[2] == {"changes": [{"op": "tag_define", "tag": "pii"}]}
    finance.tag_mask("pii", "MASK_HASH", except_groups=["SG-DPO"])
    assert fake.last[2] == {"changes": [{"op": "tag_mask", "tag": "pii", "mask_type": "MASK_HASH",
                                         "except_groups": ["SG-DPO"]}]}  # fmt: skip
    finance.tag_unmask("pii")
    assert fake.last[2] == {"changes": [{"op": "tag_unmask", "tag": "pii"}]}
    finance.tag_row_filter("pii", "region = 'EU'", groups=["SG-A"])
    assert fake.last[2] == {"changes": [{"op": "tag_row_filter", "tag": "pii", "expression": "region = 'EU'",
                                         "groups": ["SG-A"]}]}  # fmt: skip
    finance.tag_clear_row_filter("pii")
    assert fake.last[2] == {"changes": [{"op": "tag_clear_row_filter", "tag": "pii"}]}
    finance.drop_tag("pii")
    assert fake.last[2] == {"changes": [{"op": "tag_drop", "tag": "pii"}]}

    gov = finance.governance()
    assert gov.tags().items[0].name == "pii"
    gov.preview({"op": "tag_define", "tag": "a"}, m.GovernanceChange(op="tag_define", tag="b"))
    assert fake.last == ("governance_changes_preview", {}, {"changes": [{"op": "tag_define", "tag": "a"},
                                                                        {"op": "tag_define", "tag": "b"}]})  # fmt: skip
    gov.apply({"op": "grant", "group": "SG-A", "privilege": "USE CATALOG"})
    assert fake.last[0] == "governance_changes_apply"
    assert gov.fetch(schema="raw").namespace == "raw"
    assert fake.last[:2] == ("governance_get", {"schema": "raw"})


def test_a_row_filter_conflict_is_a_conflict_with_its_details(client: CIDPClient, fake: Fake) -> None:
    details = {"table": "raw.orders", "filter": "tag pii", "conflicts_with": "raw.orders row filter"}
    fake.refuse = httpx.Response(409, json={"code": "row_filter_conflict", "message": "Another row filter",
                                            "details": details, "request_id": "r1"},
                                 headers={"x-request-id": "r1"})  # fmt: skip
    finance = client.workspace("sales").catalog("finance")
    with pytest.raises(Conflict) as e:
        finance.tag_row_filter("pii", "region = 'EU'")
    assert e.value.code == "row_filter_conflict" and e.value.status == 409 and e.value.request_id == "r1"
    assert e.value.details == details and e.value.message == "Another row filter"

    fake.refuse = httpx.Response(409, json={"code": "conflict", "message": "Tag masks and row filters are off",
                                            "details": None})  # fmt: skip
    with pytest.raises(Conflict) as e:
        finance.tag_mask("pii", "MASK_HASH")
    assert e.value.code == "conflict" and e.value.details == {}


def test_validation_is_invalid_parameter(client: CIDPClient, fake: Fake) -> None:
    errors = [{"loc": ["body", "changes", 0, "mask_type"], "msg": "too long"}]
    fake.refuse = httpx.Response(422, json={"code": "invalid_parameter", "message": "The request is not valid",
                                            "details": {"errors": errors}})  # fmt: skip
    orders = client.workspace("sales").catalog("finance").schema("raw").table("orders")
    with pytest.raises(InvalidParameter) as e:
        orders.mask("card", "MASK_SOMETHING_ELSE")
    assert e.value.status == 422 and e.value.code == "invalid_parameter" and e.value.details["errors"] == errors


def test_a_change_without_op_is_refused_before_sending(client: CIDPClient, fake: Fake) -> None:
    with pytest.raises(ValueError):
        client.governance.apply("sales", "finance", [{"schema": "raw"}])
    assert not fake.calls


def test_internal_operations_warn_once(fake: Fake, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "_warned", set())
    with CIDPClient(host=HOST, token=TOKEN, env={}, transport=httpx.MockTransport(fake)) as client:
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            client.governance.tags("sales", "finance")
            client.governance.tags("sales", "finance")
            client.workspace("sales").catalog("finance").define_tag("pii")
    kinds = [(type(w.message), str(w.message).split()[0]) for w in seen]
    assert kinds == [(InternalWarning, "governance_tags_list"), (InternalWarning, "governance_changes_apply")]
    assert issubclass(InternalWarning, PreviewWarning)

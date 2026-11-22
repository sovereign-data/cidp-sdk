"""The SDK's models from the public contract (OpenSpec change data-api-sdk, A4): `make sdk-models`.

Reads `contract/openapi-v1.json` and writes `src/cidp_sdk/_models.py`: one pydantic model per
component schema a ``stable`` or ``preview`` operation reaches (``internal`` ones, the data UI's own, are left out as
in the reference docs, except those of the few operations in ``INTERNAL_IN_SDK``), forward-compatible (unknown fields
kept, an enum is `Literal[...] | str`, so a value added within v1 does not break an older SDK). Only the JSON Schema
the service's pydantic models produce is supported; anything else stops the run rather than guessing. It also writes
`_operations.py`: each ``stable`` and ``preview`` operation's method, path, level and service, which the SDK's
services are checked against and which flags a preview call (OpenSpec change data-api-consistency, AC-9), and in
``INTERNAL_OPERATIONS`` the same for the operations in ``INTERNAL_IN_SDK``, which the SDK calls with a warning
(``InternalWarning``). `--check` exits 1 when either committed file is stale (the SDK tests do the same through
`render` and `render_operations`).
"""

from __future__ import annotations

import hashlib
import json
import keyword
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contract" / "openapi-v1.json"
TARGET = ROOT / "src" / "cidp_sdk" / "_models.py"
OPERATIONS = TARGET.with_name("_operations.py")
API = "/api/data/v1"
METHODS = ("get", "put", "post", "delete", "patch")
REF = "#/components/schemas/"
# Names a field cannot have on a pydantic model; they get a trailing underscore and the wire name as alias.
RESERVED = {"schema", "json", "copy", "dict", "validate", "construct", "fields", "model_config", "model_fields"}
# Internal operations the SDK calls all the same: governance's masks, row filters and governed tags, whose public shape
# waits for VPFDATA-713 (ai-portal-data routers/v1/governance.py). They may change without notice; the SDK warns.
INTERNAL_IN_SDK = frozenset({"governance_get", "governance_changes_apply", "governance_changes_preview",
                             "governance_tags_list"})  # fmt: skip
KNOWN = {"$ref", "anyOf", "type", "format", "enum", "items", "additionalProperties", "properties", "required",
         "title", "description", "default", "maxLength", "minLength", "maxItems", "minItems", "maximum", "minimum",
         "pattern", "maxProperties", "const", "patternProperties"}  # fmt: skip


def _type(s: dict[str, Any]) -> str:
    unknown = set(s) - KNOWN
    if unknown:
        raise ValueError(f"unsupported JSON Schema keywords {sorted(unknown)}")
    if "$ref" in s:
        return s["$ref"].removeprefix(REF)
    if "anyOf" in s:
        parts = [_type(x) for x in s["anyOf"]]
        return " | ".join(dict.fromkeys(parts))
    if "const" in s:
        return f"Literal[{s['const']!r}] | str"
    t = s.get("type")
    if t == "string":
        if "enum" in s:
            return "Literal[" + ", ".join(repr(v) for v in s["enum"]) + "] | str"
        return "datetime" if s.get("format") == "date-time" else "str"
    if t == "integer":
        return "int"
    if t == "number":
        return "float"
    if t == "boolean":
        return "bool"
    if t == "null":
        return "None"
    if t == "array":
        return f"list[{_type(s['items']) if 'items' in s else 'Any'}]"
    if t == "object" or t is None and "additionalProperties" in s:
        # A map whose keys must match a pattern (a catalog scope: name -> access): the values' type; the service
        # checks the key, the SDK does not.
        if "patternProperties" in s and "additionalProperties" not in s:
            values = " | ".join(dict.fromkeys(_type(v) for v in s["patternProperties"].values()))
            return f"dict[str, {values or 'Any'}]"
        extra = s.get("additionalProperties", True)
        return f"dict[str, {_type(extra) if isinstance(extra, dict) else 'Any'}]"
    if t is None:
        return "Any"
    raise ValueError(f"unsupported JSON Schema type {t!r}")


def _field(name: str, s: dict[str, Any], required: bool) -> str:
    attr = name + "_" if keyword.iskeyword(name) or name in RESERVED else name
    if not attr.isidentifier():
        raise ValueError(f"field {name!r} is not a Python name")
    t = _type(s)
    args: list[str] = []
    if not required:
        if "default" in s:
            args.append(f"default={s['default']!r}")
        else:
            args.append("default=None")
            if "None" not in t.split(" | "):
                t += " | None"
    if attr != name:
        args.append(f"alias={name!r}")
    if s.get("description"):
        args.append(f"description={s['description']!r}")
    if not args:
        return f"    {attr}: {t}"
    if args == ["default=None"]:
        return f"    {attr}: {t} = None"
    return f"    {attr}: {t} = Field({', '.join(args)})"


def _model(name: str, s: dict[str, Any]) -> list[str]:
    # An open object (a run artifact: any JSON object) is a model without fields; _Model keeps every key.
    if s.get("type") != "object" or ("properties" not in s and s.get("additionalProperties") is not True):
        raise ValueError(f"schema {name} is not an object with properties")
    out = [f"class {name}(_Model):"]
    if s.get("description"):
        out.append(f"    {json.dumps(s['description'], ensure_ascii=False)}")
        out.append("")
    required = set(s.get("required", []))
    fields = [_field(k, v, k in required) for k, v in s.get("properties", {}).items()]
    if fields:
        return out + fields
    return out[:2] if len(out) > 1 else [*out, "    pass"]


def _refs(node: Any) -> set[str]:
    if isinstance(node, dict):
        found = {node["$ref"].removeprefix(REF)} if isinstance(node.get("$ref"), str) else set()
        return found.union(*(_refs(v) for v in node.values()))
    if isinstance(node, list):
        return set().union(*(_refs(v) for v in node))
    return set()


def _in_sdk(op: dict[str, Any]) -> bool:
    return op.get("x-stability") in ("stable", "preview") or op.get("operationId") in INTERNAL_IN_SDK


def public_schemas(doc: dict[str, Any]) -> dict[str, Any]:
    """The component schemas the ``stable`` and ``preview`` operations, and those in ``INTERNAL_IN_SDK``, reach,
    through every reference."""
    schemas = doc["components"]["schemas"]
    ops = [op for item in doc.get("paths", {}).values() for op in item.values() if isinstance(op, dict)]
    todo = _refs([op for op in ops if _in_sdk(op)])
    seen: set[str] = set()
    while todo:
        name = todo.pop()
        if name in seen or name not in schemas:
            continue
        seen.add(name)
        todo |= _refs(schemas[name])
    return {n: schemas[n] for n in sorted(seen)}


def render(text: str) -> str:
    """The module for the contract `text` (the bytes of openapi-v1.json, so the digest is the file's)."""
    doc = json.loads(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    schemas = public_schemas(doc)
    lines = [
        f'"""Models of the data service\'s public API v{doc["info"]["version"]}, generated from openapi-v1.json.',
        "",
        "Do not edit: `make sdk-models` writes this file (scripts/sdk_models.py). Unknown fields are kept and an enum",
        "accepts values added within v1, so a newer service does not break this SDK.",
        '"""',
        "",
        f"# contract sha256: {digest}",
        "# ruff: noqa: E501",
        "",
        "from __future__ import annotations",
        "",
        "from datetime import datetime",
        "from typing import Any, Literal",
        "",
        "from pydantic import BaseModel, ConfigDict, Field",
        "",
        "__all__ = [" + ", ".join(repr(n) for n in sorted(schemas)) + "]",
        "",
        "",
        "class _Model(BaseModel):",
        '    model_config = ConfigDict(extra="allow", populate_by_name=True)',
    ]
    for name in sorted(schemas):
        lines += ["", "", *_model(name, schemas[name])]
    lines += ["", "", f"for _m in ({', '.join(sorted(schemas))}):", "    _m.model_rebuild()", ""]
    return "\n".join(lines)


def render_operations(text: str) -> str:
    """The operation table for the contract `text`: operationId -> (method, path under /api/data/v1, level, service)."""
    doc = json.loads(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    rows: dict[str, tuple[str, str, str, str]] = {}
    internal: dict[str, tuple[str, str, str, str]] = {}
    for path, item in doc.get("paths", {}).items():
        for method in METHODS:
            op = item.get(method)
            if not isinstance(op, dict) or not _in_sdk(op):
                continue
            table = rows if op.get("x-stability") in ("stable", "preview") else internal
            table[op["operationId"]] = (method.upper(), path.removeprefix(API), op["x-stability"], op["x-service"])
    missing = INTERNAL_IN_SDK - set(internal)
    if missing:
        raise ValueError(f"INTERNAL_IN_SDK names operations that are not internal in the contract: {sorted(missing)}")
    lines = [
        f'"""The public operations of the data service\'s API v{doc["info"]["version"]}, generated from openapi-v1.json.',
        "",
        "Do not edit: `make sdk-models` writes this file (scripts/sdk_models.py). operationId -> (method, path under",
        "/api/data/v1, level, service). A ``preview`` operation may change in a minor release; the SDK warns on its",
        "first use (``PreviewWarning``). ``internal`` operations, the data UI's own, are not here, except those in",
        "``INTERNAL_OPERATIONS``: the SDK calls them all the same and warns (``InternalWarning``); they may change",
        "without notice.",
        '"""',
        "",
        f"# contract sha256: {digest}",
        "# ruff: noqa: E501",
        "",
        "OPERATIONS: dict[str, tuple[str, str, str, str]] = {",
        *(f"    {k!r}: {v!r}," for k, v in sorted(rows.items())),
        "}",
        "",
        "INTERNAL_OPERATIONS: dict[str, tuple[str, str, str, str]] = {",
        *(f"    {k!r}: {v!r}," for k, v in sorted(internal.items())),
        "}",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    contract = CONTRACT.read_text()
    outputs = {TARGET: render(contract), OPERATIONS: render_operations(contract)}
    if "--check" in argv:
        stale = [t for t, text in outputs.items() if not t.exists() or t.read_text() != text]
        for t in stale:
            print(f"{t.relative_to(ROOT)} is stale: run make sdk-models", file=sys.stderr)
        return 1 if stale else 0
    for t, text in outputs.items():
        t.write_text(text)
        print(f"wrote {t.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""The SDK's services against the contract (OpenSpec change data-api-consistency, task 4.1, AC-9).

Every ``stable`` and ``preview`` operation of ``openapi-v1.json`` is a method of a service or named in
``NOT_IN_SDK`` with a reason; every method, called with stand-in arguments, sends its operation's method and path;
``_operations.py`` is the one the generator writes from the committed contract.
"""

from __future__ import annotations

import importlib.util
import inspect
import re
import warnings
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pydantic
import pytest

from cidp_sdk import PreviewWarning, services
from cidp_sdk._http import Http
from cidp_sdk._operations import OPERATIONS

ROOT = Path(__file__).resolve().parents[1]
API = "/api/data/v1"

# Arguments a stand-in string cannot fill: bodies passed whole, and lists of grants or changes.
WHOLE = {
    "term": {"name": "t", "version": 1},
    "destination": {"name": "d", "kind": "webhook", "url": "https://hooks.example.org/x"},
    "changes": [{"principal": "SG-A", "add": ["SELECT"]}],
    "grants": [],
    "ids": ["a"],
}


def methods() -> Iterator[tuple[str, str, Callable[..., Any]]]:
    """(class, method name, function) for every method marked with an operation."""
    for cls_name, cls in inspect.getmembers(services, inspect.isclass):
        if issubclass(cls, services._Service) and cls is not services._Service:
            for name, fn in vars(cls).items():
                if hasattr(fn, "operation"):
                    yield cls_name, name, fn


def stand_in(name: str, annotation: str) -> Any:
    if name == "ids" and "int" in annotation:
        return [1]
    if name in WHOLE:
        return WHOLE[name]
    if "bytes" in annotation:
        return b"data"
    if annotation.startswith("Sequence"):
        return ["a"]
    if annotation.startswith("bool"):
        return True
    if annotation.startswith("int"):
        return 1
    return "x1"


def arguments(fn: Callable[..., Any]) -> dict[str, Any]:
    """Stand-ins for the required parameters (the optional ones keep their defaults)."""
    sig = inspect.signature(inspect.unwrap(fn))
    return {n: stand_in(n, str(p.annotation)) for n, p in list(sig.parameters.items())[1:]
            if p.default is inspect.Parameter.empty and p.kind is not p.VAR_KEYWORD}  # fmt: skip


def template(operation_id: str) -> re.Pattern[str]:
    path = OPERATIONS[operation_id][1]
    return re.compile("^" + re.escape(API) + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(path)) + "$")


def test_every_public_operation_is_in_the_sdk_or_named_as_left_out() -> None:
    covered = {fn.operation for _, _, fn in methods()}
    assert covered <= set(OPERATIONS), covered - set(OPERATIONS)
    left_out = set(services.NOT_IN_SDK)
    assert left_out <= set(OPERATIONS), left_out - set(OPERATIONS)
    assert not covered & left_out, covered & left_out
    assert set(OPERATIONS) == covered | left_out, sorted(set(OPERATIONS) - covered - left_out)
    assert all(reason.strip() for reason in services.NOT_IN_SDK.values())


@pytest.mark.parametrize(("cls", "name", "fn"), list(methods()), ids=lambda v: v if isinstance(v, str) else "")
def test_each_method_sends_its_operation(cls: str, name: str, fn: Callable[..., Any]) -> None:
    sent: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"items": []}, headers={"etag": '"1"'})

    http = Http("https://portal.example.org", None, transport=httpx.MockTransport(answer))
    service = getattr(services, cls)(http)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PreviewWarning)
        try:
            result = getattr(service, name)(**arguments(fn))
            if isinstance(result, Iterator):
                list(result)
        except (pydantic.ValidationError, KeyError, TypeError, ValueError, OSError):
            pass  # the stand-in answer fits no model; the request is what is checked
    assert sent, f"{cls}.{name} sent nothing"
    method, _, _, _ = OPERATIONS[fn.operation]
    last = sent[-1]
    assert last.method == method, f"{cls}.{name}: {last.method}, the contract says {method}"
    assert template(fn.operation).match(last.url.path), f"{cls}.{name}: {last.url.path} is not {fn.operation}"


def test_operations_are_current() -> None:
    spec = importlib.util.spec_from_file_location("sdk_models", ROOT / "scripts" / "sdk_models.py")
    assert spec and spec.loader
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    contract = (ROOT / "contract" / "openapi-v1.json").read_text()
    committed = (ROOT / "src" / "cidp_sdk" / "_operations.py").read_text()
    assert committed == gen.render_operations(contract), "run make sdk-models"

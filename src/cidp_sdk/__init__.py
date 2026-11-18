"""Python SDK for the data service's public API v1 (OpenSpec change data-api-sdk).

from cidp_sdk import CIDPClient

with CIDPClient("prod") as client:
    rows = client.workspace("sales").sql("select 1 as x").collect()
"""

__version__ = "0.3.0"

from cidp_sdk.client import CIDPClient  # noqa: E402
from cidp_sdk.errors import (  # noqa: E402
    CIDPError,
    ConfigError,
    Conflict,
    InvalidParameter,
    NotFound,
    PermissionDenied,
    PreviewWarning,
    StatementFailed,
    TooManyRequests,
    TransportError,
    Unauthenticated,
    Unavailable,
    WaitTimeout,
)
from cidp_sdk.session import Result, Session  # noqa: E402

__all__ = [
    "ConfigError", "Conflict", "InvalidParameter", "NotFound", "PermissionDenied", "CIDPClient", "CIDPError",
    "PreviewWarning",
    "Result", "Session", "StatementFailed", "TooManyRequests", "TransportError", "Unauthenticated", "Unavailable",
    "WaitTimeout", "__version__",
]  # fmt: skip

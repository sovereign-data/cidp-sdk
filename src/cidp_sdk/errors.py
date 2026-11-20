"""Errors of the SDK (design A1). Each carries the service's ``code``, the HTTP ``status`` and the ``request_id``.

Messages come from the service's ``message`` (written for people, never an echo of the request) or name the call and
the status. Request headers are never kept on an error, so a bearer token cannot reach a log through one.
"""

from __future__ import annotations

from typing import Any


class PreviewWarning(UserWarning):
    """A ``preview`` operation of the API: it may change in a minor release, with a CHANGELOG entry and at least 30
    days' notice (OpenSpec change data-api-consistency, AC-9). Raised once per operation and process; silence it with
    ``warnings.filterwarnings("ignore", category=PreviewWarning)``."""


class InternalWarning(PreviewWarning):
    """An ``internal`` operation of the API, the data UI's own, that the SDK calls all the same (governance's masks,
    row filters and governed tags, ``client.governance``): it may change or go away in any release, without notice.
    Raised once per operation and process. A ``PreviewWarning``, so the filter that silences those silences it too;
    ``warnings.filterwarnings("ignore", category=InternalWarning)`` silences only these."""


class CIDPError(Exception):
    """Any failure of a call to the data service."""

    def __init__(self, message: str, *, code: str = "error", status: int | None = None,
                 request_id: str | None = None, details: dict[str, Any] | None = None):  # fmt: skip
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.request_id = request_id
        self.details = details or {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, status={self.status!r}, request_id={self.request_id!r})"


class ConfigError(CIDPError):
    """The SDK could not be set up: no host, a profile it refuses, no way to get a token."""


class TransportError(CIDPError):
    """The service did not answer (connection, TLS, timeout)."""


class InvalidParameter(CIDPError):
    """400 or 422: the request is not valid."""


class Unauthenticated(CIDPError):
    """401: no token, or one the service refuses. Sign in again."""


class PermissionDenied(CIDPError):
    """403: the caller may not do this."""


class NotFound(CIDPError):
    """404: it does not exist, or the caller may not see it (the service does not tell the two apart)."""


class Conflict(CIDPError):
    """409: it exists already, or its state does not allow this."""


class TooManyRequests(CIDPError):
    """429: a limit was reached; ``retry_after`` is the service's hint in seconds, when it gave one."""

    def __init__(self, message: str, *, retry_after: float | None = None, **kw: Any):
        super().__init__(message, **kw)
        self.retry_after = retry_after


class Unavailable(CIDPError):
    """503: the service or one of its dependencies is unavailable for now."""


class WaitTimeout(CIDPError, TimeoutError):
    """A ``wait()`` ran out of time before the run (or statement) ended; it goes on in the service. Also a
    ``TimeoutError``, so ``except TimeoutError`` catches it."""


class StatementFailed(CIDPError):
    """A statement ended ``FAILED`` or ``CANCELED``; ``code`` is the statement's own (``failed``, ``timeout``…)."""


BY_STATUS: dict[int, type[CIDPError]] = {
    400: InvalidParameter,
    401: Unauthenticated,
    403: PermissionDenied,
    404: NotFound,
    409: Conflict,
    422: InvalidParameter,
    429: TooManyRequests,
    503: Unavailable,
}

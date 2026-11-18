"""The SDK's tests: an in-memory keyring for every test (never the OS keychain).

The contract test that runs the SDK against the real v1 app (AC-6) lives with the data service (ai-portal-data).
"""

from __future__ import annotations

from collections.abc import Iterator

import keyring
import pytest
from keyring.backend import KeyringBackend


class MemoryKeyring(KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self):
        super().__init__()
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


@pytest.fixture(autouse=True)
def memory_keyring() -> Iterator[MemoryKeyring]:
    before = keyring.get_keyring()
    ring = MemoryKeyring()
    keyring.set_keyring(ring)
    yield ring
    keyring.set_keyring(before)

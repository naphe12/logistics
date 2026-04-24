import os
import uuid

import pytest
import requests


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@pytest.fixture(scope="session")
def base_url() -> str:
    return _env("LOGIX_TEST_BASE_URL")


@pytest.fixture(scope="session")
def token() -> str:
    return _env("LOGIX_TEST_TOKEN")


@pytest.fixture(scope="session")
def timeout_seconds() -> float:
    raw = _env("LOGIX_TEST_TIMEOUT_SECONDS", "20")
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 20.0


@pytest.fixture(scope="session")
def sender_phone() -> str:
    return _env("LOGIX_TEST_SENDER_PHONE", "+25762019001")


@pytest.fixture(scope="session")
def receiver_phone() -> str:
    return _env("LOGIX_TEST_RECEIVER_PHONE", "+25762019002")


@pytest.fixture(scope="session")
def run_id() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="session")
def client(base_url: str, token: str, timeout_seconds: float):
    if not base_url or not token:
        pytest.skip("LOGIX_TEST_BASE_URL and LOGIX_TEST_TOKEN are required for API tests")
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    )
    return {
        "session": session,
        "base_url": base_url.rstrip("/"),
        "timeout": timeout_seconds,
    }


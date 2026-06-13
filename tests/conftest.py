"""pytest 共享 fixture"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _mock_llm():
    """全局 mock ask_llm，覆盖直接引用 (main.py) 和 lazy import (memory.py, router.py)"""
    async def _mock_ask_llm(prompt, system_prompt=None, messages=None):
        return "mock response"

    with (
        patch("server.main.ask_llm", new=_mock_ask_llm),
        patch("server.llm.ask_llm", new=_mock_ask_llm),
    ):
        yield

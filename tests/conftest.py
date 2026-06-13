"""pytest 共享 fixture"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from server.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _mock_llm():
    """全局 mock ask_llm + classify_intent_l1，避免测试中意外调用真实 API"""
    async def _mock_ask_llm(prompt, system_prompt=None, messages=None):
        return "mock response"

    with (
        patch("server.main.ask_llm", new=_mock_ask_llm),
        patch("server.main.classify_intent_l1", new=AsyncMock(return_value="textual")),
    ):
        yield

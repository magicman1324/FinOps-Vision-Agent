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
    """全局 mock ask_llm，避免测试中意外调用真实 API"""
    with patch("server.main.ask_llm", new=AsyncMock(return_value="mock response")):
        yield

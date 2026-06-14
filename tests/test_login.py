"""测试 /login 端点 — 用户创建与宠物分配"""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from server.main import app


@pytest.fixture
def client():
    # 切换到临时目录避免污染开发数据库
    import server.db as dbmod
    old_path = dbmod.DB_PATH
    dbmod.DB_PATH = os.path.join(tempfile.gettempdir(), "x3_test_login.db")
    try:
        # 重新初始化到临时 DB
        import asyncio
        asyncio.run(dbmod.init_db())
    finally:
        dbmod.DB_PATH = old_path

    with TestClient(app) as c:
        yield c

    # 清理
    try:
        os.unlink(os.path.join(tempfile.gettempdir(), "x3_test_login.db"))
    except OSError:
        pass


class TestLogin:
    def test_new_user_gets_random_pet(self, client):
        resp = client.post("/login", json={"username": "testuser1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser1"
        assert data["pet_type"] in ("robot", "cat", "dog", "alien")

    def test_same_user_gets_same_pet(self, client):
        r1 = client.post("/login", json={"username": "consistent"})
        r2 = client.post("/login", json={"username": "consistent"})
        assert r1.json()["pet_type"] == r2.json()["pet_type"]

    def test_empty_username_rejected(self, client):
        resp = client.post("/login", json={"username": ""})
        data = resp.json()
        assert "error" in data

    def test_whitespace_only_rejected(self, client):
        resp = client.post("/login", json={"username": "   "})
        data = resp.json()
        assert "error" in data

    def test_long_username_rejected(self, client):
        resp = client.post("/login", json={"username": "a" * 21})
        data = resp.json()
        assert "error" in data

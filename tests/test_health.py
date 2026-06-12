"""测试 /health 端点"""


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_health_method_not_allowed(client):
    resp = client.post("/health")
    assert resp.status_code == 405

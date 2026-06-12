"""测试 /ws WebSocket 端点"""

import json

def test_ws_echo(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "ping", "msg": "hello"})
        data = ws.receive_json()
        assert data["type"] == "echo"
        assert data["data"]["msg"] == "hello"


def test_ws_invalid_json(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_text("not valid json")
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "invalid json" in data["message"]

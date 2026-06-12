"""FastAPI WebSocket 入口 — AI 视觉对话助手"""

import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Vision Dialogue", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket connected")
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "invalid json"})
                continue
            msg_type = data.get("type", "")
            logger.info("received: type=%s", msg_type)
            await ws.send_json({"type": "echo", "data": data})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")

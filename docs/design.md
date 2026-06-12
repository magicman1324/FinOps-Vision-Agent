# AI 视觉对话助手 — 设计文档

## 1. 产品定位

实时端云协同视觉对话：用户打开摄像头和麦克风，AI 看到画面、听到语音、用语音回应。

**核心场景：** 视障辅助、物体辨识、AR 对话、远程协作。

## 2. 系统架构

```
┌─ 浏览器 (Client) ─────────────────────┐
│                                        │
│  index.html                            │
│  ├── vad.js       RMS VAD + 环形缓冲  │
│  ├── camera.js    512x512 JPEG压缩    │
│  └── websocket.js WS通信 + PCM编码    │
│                                        │
│  getUserMedia → 16kHz mono PCM         │
│  Canvas → Base64 JPEG q=0.7            │
└────────────┬───────────────────────────┘
             │  WebSocket ws://host:8765/ws
             │  {type: "audio"} | {type: "image"}
             ▼
┌─ 服务端 (Python/FastAPI) ──────────────┐
│                                        │
│  server/main.py     WebSocket 单端点   │
│  ├── asr.py         DashScope 通义听悟 │
│  ├── router.py      L0正则+L1 LLM路由 │
│  ├── vlm.py         Qwen-VL-Max       │
│  ├── llm.py         DeepSeek-V3 (SSE) │
│  ├── tts.py         CosyVoice v2      │
│  ├── memory.py      三层语义压缩      │
│  └── config.py      环境变量配置      │
│                                        │
│  推理链路:                             │
│  audio → ASR → L0/L1路由 → 降级链    │
│       → _cascade_visual/_cascade_text │
│       → TTS流式 → MP3 chunk           │
└────────────────────────────────────────┘
```

## 3. WebSocket 协议

所有消息走单一 `/ws` 端点，按 `type` 字段路由。

```
前端 → 后端:
  {"type": "audio", "audio": "<base64_pcm_16khz_mono>"}
  {"type": "image", "image": "<base64_jpeg_512x512>"}

后端 → 前端:
  {"type": "asr_result",  "text": "识别文本"}
  {"type": "vlm_result",  "text": "画面描述"}
  {"type": "audio", "audio": "<base64_mp3>", "is_final": false}
  {"type": "audio", "audio": "",        "is_final": true}
  {"type": "error",     "message": "降级文案"}
  {"type": "echo",      "data": {...}}
```

**注意：** TTS chunk 的 JSON 中**没有 `type` 字段**。`is_final: true` 时 `audio` 为空串。

## 4. 意图路由

双层降级设计，零延迟优先：

| 层 | 机制 | 延迟 | 准确率 |
|----|------|------|--------|
| L0 | 22 个中文正则关键词 | 0ms | ~85% |
| L1 | DeepSeek-V3 二分类 | ~200ms | ~98% |

L0 覆盖：对象辨识、颜色/形状、空间方位、数量统计、感知动词、画面指代、第一人称锚点。

L1 prompt 约束只输出 `visual` / `textual`，无解释无标点。

## 5. 三级降级链

每层失败自动降级，用户无感知：

### 视觉问题 (`_cascade_visual`)
```
L1: Qwen-VL-Max (看图回答)
  ↓ VLMError
L2: DeepSeek-V3 (看不到图，凭常识回答)
  ↓ LLMError
L3: 预设文案 ("抱歉，我暂时无法处理这个问题，请稍后再试")
```

### 文本问题 (`_cascade_text`)
```
L1: DeepSeek-V3 (注入记忆上下文)
  ↓ LLMError
L2: 预设文案
```

## 6. 三层语义压缩记忆

渐进式压缩，平衡上下文窗口与信息保真：

```
┌─ Short (最近3轮，精确文本) ──┐
│  evict → raw text 推入 Mid   │
├─ Mid (最多7条，LLM压缩摘要) ─┤
│  溢出 → 最旧丢弃             │
│  compress_mid() → 40字摘要   │
├─ Background (≤150字元摘要)  ─┤
│  compress_background()       │
│  注入 system prompt          │
└──────────────────────────────┘
```

- `add_turn()`: 写入 short，自动 evict → mid
- `compress_mid()`: 异步 LLM 压缩 mid raw → 结构化摘要
- `compress_background()`: 异步 LLM 压缩 mid → 元摘要
- `get_context()`: 组装 bg + mid + short 作为对话上下文

## 7. VAD 语音检测

基于 RMS 能量，纯前端 JavaScript：

| 参数 | 值 | 说明 |
|------|-----|------|
| VAD_SAMPLE_RATE | 16000 | 采样率 |
| BUFFER_SIZE | 4096 | 帧大小 |
| RING_BUFFER_SEC | 3 | 环形缓冲 |
| LOOKBACK_SEC | 0.3 | speech start 回溯 |
| SILENCE_TIMEOUT_SEC | 1.5 | 静音判定结束 |
| RMS_THRESHOLD | 0.01 | 能量阈值 |

状态机：`silence → (连续N帧>阈值) → speaking → (连续M帧<阈值) → silence + onSpeechEnd`

## 8. TTS 回调桥接

DashScope CosyVoice v2 使用同步回调 `ResultCallback.on_data(bytes)`。通过 `asyncio.Queue` 桥接为 async generator：

```python
# server/tts.py
queue = asyncio.Queue()

class _Callback(ResultCallback):
    def on_data(self, data: bytes):
        queue.put_nowait({"audio": base64(data), "is_final": False})

# 生成器端
async for chunk in stream:  # 从 queue 取
    yield chunk
```

## 9. 测试策略

### 分层

| 层 | 文件 | 数量 | 说明 |
|----|------|------|------|
| 单元 | test_asr/tts/vlm/llm/router/memory | ~50 | mock 外部 API |
| 集成 | test_integration/test_cascade/test_e2e | ~31 | WebSocket 端到端 |
| 真实 API | test_live | ~25 | 需 DASHSCOPE_API_KEY |

### 关键约定

- `tests/conftest.py::_mock_llm` autouse fixture 全局 mock `server.main.ask_llm`
- 需要 LLM 失败路径时显式 `patch("server.main.ask_llm", side_effect=LLMError)`
- L1 router 测试 patch `server.llm.ask_llm`（lazy import，非 `server.router.ask_llm`）
- async generator mock 复用需 `side_effect=[gen1, gen2]`，不可用 `return_value`

## 10. 部署

```bash
pip install -r server/requirements.txt
uvicorn server.main:app --host 0.0.0.0 --port 8765
```

环境变量：
- `DASHSCOPE_API_KEY` — 通义听悟 ASR + CosyVoice TTS + Qwen-VL-Max
- `DEEPSEEK_API_KEY` — DeepSeek-V3 文本推理

客户端直接打开 `client/index.html`，自动连接 `ws://<host>:8765/ws`。

## 11. 项目阶段

| 阶段 | PR 范围 | 内容 |
|------|---------|------|
| Phase 1: 音频管线 | #1-#12 | ASR + TTS + VAD + WebSocket |
| Phase 2: 视觉管线 | #13-#17 | Camera + VLM + 双通道 E2E |
| Phase 3: 意图路由 | #18-#21 | LLM + L0/L1 路由 + 集成 |
| Phase 4: 记忆系统 | #22-#24 | 三层压缩 + 记忆注入 |
| Phase 5: 容错降级 | #25-#26 | 三级降级链 + WS 重连 |
| Phase 6: 打磨 | #27-#29 | UI 气泡 + 测试强化 + 文档 |

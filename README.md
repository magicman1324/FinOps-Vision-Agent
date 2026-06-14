# FinOps-Vision-Agent

> 七牛云 × XEngineer AI 视觉对话助手 —— 打开摄像头，AI 看到你的画面、听懂你的声音、用语音回答你。

## Demo 演示

📹 [观看演示视频](https://pan.baidu.com/s/1FOOHg4k103f6b2wXufh-8Q?pwd=x2bx) — 百度网盘，提取码 `x2bx`

---

## 它是做什么的

按住按钮说话，松开发送。AI 同时接收你的**语音**和**摄像头画面**，理解你在问什么，然后用语音回答你。

- 指着桌上的东西问"这是什么颜色" → AI 看着画面回答
- 问"今天天气怎么样" → AI 当普通语音助手用
- 对话有记忆，多轮聊天不掉上下文

## 快速开始

```bash
# 1. 安装依赖
pip install -r server/requirements.txt

# 2. 设置 API Key
export DASHSCOPE_API_KEY=sk-xxx    # 阿里云 DashScope（ASR + VLM + TTS）
export DEEPSEEK_API_KEY=sk-xxx     # DeepSeek（LLM 文本生成）

# 3. 启动后端
uvicorn server.main:app --host 127.0.0.1 --port 8765

# 4. 打开浏览器
# 直接打开 client/index.html，或者访问 http://127.0.0.1:8765
```

> **Python 路径（Windows）：** `C:/Users/magic/AppData/Local/Programs/Python/Python312/python.exe`

## 怎么用

1. 浏览器打开页面，允许摄像头和麦克风权限
2. **按住**"按住说话"按钮开始录音
3. 对着摄像头说话，**松开**按钮发送
4. AI 识别语音 → 分析画面 → 语音回复

状态栏指示灯：🟢 就绪 · 🟡 处理中/录音中 · 🔴 出错

## 架构

```
浏览器 (HTML5 + JS)
├── vad.js          RMS 环形缓冲区 + 噪音裁剪
├── camera.js       Canvas 512×512 JPEG 截图
├── websocket.js    WS 通信 + PCM 动态归一化 + 指数退避重连
└── pet.js          像素吉祥物 (4 种宠物 × 4 状态)

↕ WebSocket (全双工)

服务端 (Python + FastAPI)
├── asr.py          通义听悟语音识别
├── router.py       L0 关键词正则路由（22 patterns）
├── llm.py          DeepSeek 文本生成（httpx SSE 流式）
├── vlm.py          Qwen-VL-Max 视觉推理
├── tts.py          CosyVoice 流式语音合成
├── memory.py       三层语义压缩记忆
├── db.py           SQLite 用户-宠物映射
└── main.py         WebSocket 端点 + 三级降级链 + 输入限制
```

**推理链路：** `audio → ASR → L0 意图路由 → VLM/LLM → 记忆 → TTS → 语音播放`

**三级降级：** VLM 失败 → LLM 兜底 → 预设文案。每层独立 catch，永不崩溃。

**三层记忆：** 短窗口（3 轮精确对话）→ 中距摘要（7 条压缩）→ 背景元摘要（≤150 字）。异步 LLM 压缩，不阻塞主链路。

**像素宠物 + 登录：** 首次登录随机分配 4 种像素宠物（机器人/猫/狗/外星人），纯 CSS 像素风绘制，随应用状态切换动画（idle/listening/processing/speaking）。用户名持久化 SQLite（WAL），刷新自动登录，支持切换账号。

**输入防护：** 音频消息 ≤512KB、图片消息 ≤256KB，base64 解码前拦截，防止内存耗尽。

## WebSocket 消息协议

| 方向 | 消息 | 说明 |
|------|------|------|
| 前端 → 后端 | `{"type":"audio","audio":"<base64>"}` | PCM 16kHz 16bit mono, Int16LE |
| 前端 → 后端 | `{"type":"image","image":"<base64>"}` | JPEG Base64, 512×512 |
| 后端 → 前端 | `{"type":"asr_result","text":"..."}` | 语音识别结果 |
| 后端 → 前端 | `{"type":"text_result","text":"..."}` | AI 文字回复 |
| 后端 → 前端 | `{"type":"vlm_result","text":"..."}` | 视觉分析结果 |
| 后端 → 前端 | `{"type":"audio","audio":"<base64>","is_final":false}` | TTS 流式音频块 |
| 后端 → 前端 | `{"type":"audio","audio":"","is_final":true}` | TTS 播放完成 |
| 后端 → 前端 | `{"type":"error","message":"..."}` | 降级通知 |

> TTS 音频块带 `type: "audio"`，前端按 `data.type === 'audio'` 分发。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | HTML5, Canvas API, Web Audio API, WebSocket |
| 后端 | Python 3.12, FastAPI, uvicorn |
| ASR | 阿里云 DashScope 通义听悟 `fun-asr-realtime` |
| LLM | DeepSeek `deepseek-v4-flash`（httpx 直连，不走代理） |
| VLM | 阿里云 DashScope `qwen-vl-max` |
| TTS | 阿里云 DashScope CosyVoice v1 `longxiaochun` 音色 |
| 测试 | pytest + pytest-asyncio, asyncio_mode=auto |
| CI | GitHub Actions — unit（每次 push）+ live（仅 PR） |

## 配置

```bash
# DashScope — ASR / VLM / TTS
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_ASR_MODEL=fun-asr-realtime          # 默认值
DASHSCOPE_TTS_MODEL=cosyvoice-v1              # 默认值
DASHSCOPE_VLM_MODEL=qwen-vl-max               # 默认值

# DeepSeek — LLM 文本生成
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1 # 默认值
DEEPSEEK_MODEL=deepseek-v4-flash               # 默认值

# 超时（秒）
ASR_TIMEOUT=10          # 默认
VLM_TIMEOUT=15          # 默认
LLM_TIMEOUT=10          # 默认
TTS_TIMEOUT=10          # 默认
```

## 测试

```bash
# 全部 mock 测试（不需要 API Key）
pytest tests/ -v --ignore=tests/test_live.py   # 108 passed

# 单个文件
pytest tests/test_cascade.py -v

# 单个函数
pytest tests/test_router.py::TestL0VisualHits::test_color_inquiry -v

# 真实 API 测试（需要 API Key 环境变量）
DASHSCOPE_API_KEY=sk-xxx DEEPSEEK_API_KEY=sk-xxx pytest tests/test_live.py -v
```

## 项目结构

```
XEngineer3/
├── server/
│   ├── main.py         WebSocket 端点 + 降级链编排
│   ├── asr.py          语音识别（DashScope）
│   ├── llm.py          文本生成（DeepSeek，流式 SSE）
│   ├── vlm.py          视觉推理（Qwen-VL-Max）
│   ├── tts.py          语音合成（CosyVoice，流式回调→生成器桥接）
│   ├── memory.py       三层语义压缩记忆
│   ├── router.py       L0 关键词正则意图路由
│   ├── db.py           SQLite 用户-宠物映射 (aiosqlite, WAL)
│   └── config.py       环境变量 + 代理清除
├── client/
│   ├── index.html      主页面 + UI 编排
│   ├── vad.js          音频采集 + 环形缓冲 + 噪音裁剪
│   ├── camera.js       截图（512×512 JPEG）
│   ├── websocket.js    WebSocket + PCM 编码 + 重连
│   └── pet.js          像素吉祥物类型 + 状态管理
├── tests/
│   ├── test_cascade.py     三级降级链测试
│   ├── test_integration.py 音频全链路集成测试
│   ├── test_memory.py      记忆压缩测试
│   ├── test_router.py      L0 路由测试
│   ├── test_ws.py          WebSocket 协议测试
│   ├── test_e2e.py         端到端测试
│   ├── test_llm.py         LLM 模块测试
│   ├── test_vlm.py         VLM 模块测试
│   ├── test_asr.py         ASR 模块测试
│   ├── test_tts.py         TTS 模块测试
│   ├── test_login.py       登录 + 宠物分配测试
│   └── conftest.py         mock 夹具
├── 总结X.md            前两次选拔深度归纳
├── 总结3.md            本次架构评审
└── README.md
```

## License

MIT

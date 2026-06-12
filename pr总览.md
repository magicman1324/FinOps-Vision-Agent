# PR 总览 — AI 视觉对话助手

31 个 PR，6 个 Phase，每个 PR 独立分支 / 独立测试 / 独立得分。
一个模块崩了只丢 1 个 PR 的分，不影响其他。

---

## Phase 0：地基

| PR | 分支 | 文件 | 做什么 | 得分点 | 测试标准 | 时间 |
|----|------|------|--------|--------|----------|------|
| #1 | `feat/init` | `.gitignore`、`server/requirements.txt`、`server/config.py`、`.env.example` | Python 项目骨架、依赖清单、环境变量配置 | 项目可 clone 即跑 `pip install` | `pip install` 无报错，`python -c "from server.config import *"` 成功 | 0.5h |
| #2 | `feat/ws-skeleton` | `server/main.py` | FastAPI app + `/ws` WebSocket + `/health` | WebSocket 链路通，前后端可握手 | `wscat` 连 `/ws` 收到 echo，`curl /health` 返回 ok | 1.5h |

## Phase 1：音频链路（得分维度：交互自然度）

| PR | 分支 | 文件 | 做什么 | 得分点 | 测试标准 | 时间 |
|----|------|------|--------|--------|----------|------|
| #3 | `feat/asr-module` | `server/asr.py` | DashScope 通义听悟 ASR，音频→文本 | 语音→文本准确率独立可测 | pytest：预录音频文件转 Base64 调 ASR，返回正确中文 | 2h |
| #4 | `feat/tts-module` | `server/tts.py` | CosyVoice 流式 TTS，文本→音频流 | 文本→语音首块延迟 < 500ms | pytest：调 TTS 流，拼接 MP3 写入文件播放验证 | 2h |
| #5 | `feat/ws-asr-tts` | 更新 `server/main.py` | WebSocket 内 ASR→TTS 串联 | 后端音频处理链路通 | Python 脚本模拟前端，发 Base64 音频，收 TTS chunk 流 | 1.5h |
| #6 | `feat/frontend-shell` | `client/index.html` | HTML 外壳，摄像头+麦克风权限 | 浏览器端权限获取、视频预览 | 浏览器打开页面，摄像头灯亮，画面可见 | 1h |
| #7 | `feat/vad-ringbuffer` | `client/vad.js` | VAD + 3s 环形缓冲区 + 回溯 300ms | VAD 准确检测说话起止，不丢首字 | 说话时 console 看到 speech_start → speech_end | 3h |
| #8 | `feat/ws-send` | `client/websocket.js`，更新 `client/index.html` | 前端 WebSocket 发送音频上行 | 音频从浏览器抵达后端 | 说话后后端终端打印收到 audio 消息日志 | 1.5h |
| #9 | `feat/ws-receive-play` | 更新 `client/websocket.js` | 前端 WebSocket 接收 TTS 音频播放 | AI 语音在浏览器端播放 | 后端手动推 TTS chunk，浏览器正常播放 | 1.5h |
| #10 | `feat/audio-full-loop` | 更新 `server/main.py`、`client/websocket.js` | 音频全链路闭环：说话→ASR→TTS→播放 | 纯音频对话闭环 | 说"你好"，3 秒内听到 AI 语音回复 | 2h |

## Phase 2：视觉链路（得分维度：视觉理解准确性）

| PR | 分支 | 文件 | 做什么 | 得分点 | 测试标准 | 时间 |
|----|------|------|--------|--------|----------|------|
| #11 | `feat/frame-capture` | 更新 `client/websocket.js` | 从 `<video>` 截取 1 帧→Base64 JPEG | 截图功能独立可测 | 加截图按钮，点击预览截取结果 | 1h |
| #12 | `feat/image-compress` | 更新 `client/websocket.js` | Canvas resize 512×512，JPEG q=0.7 | 图片体积可控 | 压缩后 Base64 < 50KB | 1h |
| #13 | `feat/vlm-module` | `server/vlm.py` | Qwen-VL-Max API，stream=True | 视觉问答独立可测 | pytest：静态图片 + 问题，验证返回文字准确 | 2h |
| #14 | `feat/vlm-streaming-tts` | 更新 `server/vlm.py`、`server/main.py` | VLM 流式→语义分块（句号边界）→TTS | TTFB < 800ms | WebSocket 端收多个 TTS chunk，首块 < 1s | 2h |
| #15 | `feat/visual-full-loop` | 更新 `server/main.py`、`client/websocket.js` | VAD end-of-speech 时抓帧→VLM→TTS | 展示物品→AI 准确描述 | 展示水杯说"这是什么"，听到正确回答 | 2h |

## Phase 3：成本控制（得分维度：端云协同 FinOps）

| PR | 分支 | 文件 | 做什么 | 得分点 | 测试标准 | 时间 |
|----|------|------|--------|--------|----------|------|
| #16 | `feat/llm-module` | `server/llm.py` | DeepSeek-V3 API，stream=True | 纯文本 LLM 通路独立可测 | pytest：调 ask_llm("你好")，返回流式文本 | 1.5h |
| #17 | `feat/router-l0` | `server/router.py` | 关键词正则 → visual/textual | 80% 视觉意图零延迟零成本 | pytest：19 个关键词命中/未命中用例 | 1h |
| #18 | `feat/router-l1` | 更新 `server/router.py` | DeepSeek-V3 二分类意图判断 | L0 漏网视觉意图被 LLM 兜底 | pytest：边界句"我手里这东西贵吗"→visual | 1.5h |
| #19 | `feat/router-integration` | 更新 `server/main.py` | 路由决策节点 + 模型调度 + 成本日志 | 非视觉走便宜模型，成本对比可视化 | 问"你好"→LLM，展示物品→VLM，日志验证 | 2h |

## Phase 4：语义记忆（得分维度：创新加分）

| PR | 分支 | 文件 | 做什么 | 得分点 | 测试标准 | 时间 |
|----|------|------|--------|--------|----------|------|
| #20 | `feat/memory-short` | `server/memory.py` | ConversationMemory 类，3 轮短窗口 | AI 记住最近 3 轮对话 | 第 4 轮问"刚才我说了什么"能引用 | 1.5h |
| #21 | `feat/memory-mid` | 更新 `server/memory.py` | 4-10 轮结构化摘要（LLM 生成） | 中距历史信息不丢失 | 第 5 轮问第 1 轮内容能正确回答 | 2h |
| #22 | `feat/memory-background` | 更新 `server/memory.py` | 11 轮+ 元摘要（≤150 字） | Context 增长 < 30% | 模拟 15 轮对话，context 总长可控 | 1.5h |
| #23 | `feat/memory-integration` | 更新 `server/main.py`、`vlm.py`、`llm.py` | 记忆注入 system prompt + 端到端指代消解 | 跨轮视觉指代准确 | "刚才那个红色的呢？"→正确回答 | 2h |

## Phase 5：容错降级（得分维度：工程完备性）

| PR | 分支 | 文件 | 做什么 | 得分点 | 测试标准 | 时间 |
|----|------|------|--------|--------|----------|------|
| #24 | `feat/fallback-asr` | 更新 `server/asr.py`、`server/main.py` | ASR 故障→推 error 消息→前端红字提示 | ASR 故障不白屏 | 改错 API Key，前端显示错误提示 | 1h |
| #25 | `feat/fallback-ai` | 更新 `server/vlm.py`、`llm.py`、`tts.py`、`main.py` | VLM 超时→LLM 兜底→预置文本→文本显示 | 任何单点故障有降级路径 | 逐个改错 Key，每次有降级回复 | 1.5h |
| #26 | `feat/ws-reconnect` | 更新 `client/websocket.js` | 指数退避重连 1s→2s→4s，最多 3 次 | 网络抖动用户无感恢复 | 杀后端→显示重连→重启后端→恢复 | 1.5h |

## Phase 6：打磨 + 文档

| PR | 分支 | 文件 | 做什么 | 得分点 | 测试标准 | 时间 |
|----|------|------|--------|--------|----------|------|
| #27 | `feat/ui-chat` | 更新 `client/index.html` | 对话气泡（用户蓝/AI 灰）、自动滚动 | 对话体验完整可回溯 | 多轮对话气泡正确排列 | 2h |
| #28 | `feat/ui-status` | 更新 `client/index.html` | 状态指示器（绿/黄/红）+ 摄像头小窗 | 用户始终知道系统状态 | 说话时状态切换绿→黄→绿 | 1.5h |
| #29 | `feat/integration-test` | 各模块 bugfix | 端到端用户旅程测试 + 边界 case | 核心路径无阻塞 bug | 按 checklist 逐项通过 | 3h |
| #30 | `feat/design-doc` | `docs/design.md` | 设计文档（用户故事/FinOps/模型选择） | 题目要求文档完整提交 | 自检清单全部勾选 | 2h |
| #31 | `feat/readme` | `README.md` | README + 最终审查 | 评委 clone 后 5 分钟可跑 | 另一台机器 clone→按 README 操作→成功 | 1h |

---

```
总计：31 PR × 平均 1.5h = ~47h 开发 + 3h buffer = 50h
每 PR = 独立分支 → 独立测试 → 独立得分 → merge main
```

<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能或修改行为。在实现之前先探索用户意图、需求和设计。
- **chinese-code-review**: 中文 review 沟通参考——话术模板、分级标注（必须修复/建议修改/仅供参考）、国内团队常见反模式应对。仅在用户显式 /chinese-code-review 时调用，不要根据上下文自动触发。
- **chinese-commit-conventions**: 中文 commit 与 changelog 配置参考——Conventional Commits 中文适配、commitlint/husky/commitizen 中文模板、conventional-changelog 中文配置。仅在用户显式 /chinese-commit-conventions 时调用，不要根据上下文自动触发。
- **chinese-documentation**: 中文文档排版参考——中英文空格、全半角标点、术语保留、链接格式、中文文案排版指北约定。仅在用户显式 /chinese-documentation 时调用，不要根据上下文自动触发。
- **chinese-git-workflow**: 国内 Git 平台配置参考——Gitee、Coding.net、极狐 GitLab、CNB 的 SSH/HTTPS/凭据/CI 接入差异与镜像同步配置。仅在用户显式 /chinese-git-workflow 时调用，不要根据上下文自动触发。
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你有一份书面实现计划需要在单独的会话中执行，并设有审查检查点时使用
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成工作时使用——通过提供合并、PR 或清理等结构化选项来引导开发工作的收尾
- **mcp-builder**: MCP 服务器构建方法论 — 系统化构建生产级 MCP 工具，让 AI 助手连接外部能力
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发，或在执行实现计划之前使用——通过原生工具或 git worktree 回退机制确保隔离工作区存在
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Claude Code / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->

## 项目概述

**AI 视觉对话助手** — 七牛云 Hackathon 项目，FastAPI + WebSocket + HTML5 端云协同实时视觉对话应用。

用户打开摄像头与麦克风，AI 看到画面、听到语音，并给予语音回应。

### 运行命令

```bash
# 安装依赖
pip install -r server/requirements.txt

# 启动后端
uvicorn server.main:app --host 127.0.0.1 --port 8765

# 启动前端（直接打开浏览器）
# 打开 client/index.html

# 跑全部 mock 测试（不需要 API Key）
pytest tests/ -v --ignore=tests/test_live.py

# 跑单个测试文件
pytest tests/test_ws.py -v

# 跑单个测试函数
pytest tests/test_ws.py::test_audio_pipeline -v

# 跑真实 API 测试（需要 DASHSCOPE_API_KEY 环境变量）
DASHSCOPE_API_KEY=sk-xxx pytest tests/test_live.py -v
```

### 技术栈

- **前端：** 纯 HTML5 + JavaScript，getUserMedia 捕获音视频，RMS 能量 VAD + 环形缓冲区
- **后端：** Python + FastAPI + WebSocket，全双工通信
- **AI 引擎：** DashScope ASR（通义听悟 paraformer-realtime-v2）→ CosyVoice TTS v2 流式合成
- **测试：** pytest + pytest-asyncio，asyncio_mode=auto
- **CI：** GitHub Actions ubuntu-latest，unit job（每次 push/PR）+ live job（仅 PR，需 secret）

### 已实现 vs 计划中

| 已实现 | 计划中 |
|--------|--------|
| `server/main.py` WebSocket ASR→TTS 管线 | `server/vlm.py` Qwen-VL-Max 视觉推理 |
| `server/asr.py` DashScope 通义听悟 | `server/llm.py` DeepSeek-V3 纯文本 |
| `server/tts.py` CosyVoice 流式 TTS | `server/router.py` L0/L1 双层意图路由 |
| `server/config.py` 环境变量配置 | `server/memory.py` 三层语义压缩 |
| `client/index.html` 摄像头+状态栏+日志 | `client/websocket.js` WebSocket 通信（当前为 stub） |
| `client/vad.js` RMS VAD + 3s Ring Buffer | `docs/design.md` 设计文档 |

### 核心架构模式

**TTS 回调→async generator 桥接** (`server/tts.py`)：
DashScope TTS v2 使用同步回调 `ResultCallback.on_data(bytes)` 交付音频。通过 `asyncio.Queue` 将回调解耦为 `async for chunk in text_to_speech_stream(text)` 的流式生成器。

**ASR 回调收集** (`server/asr.py`)：
`RecognitionCallback.on_event(RecognitionResult)` 逐句收集文本，`call()` 结束后返回拼接结果。

**VAD 能量检测** (`client/vad.js`)：
RMS 阈值 + 连续帧计数判定语音起止。`start` 时从环形缓冲区回溯 300ms，`end`（静音 >1.5s）触发 `onSpeechEnd(pcmFloat32Array)` 回调。

### WebSocket 消息协议

```
前端 → 后端:
  {“type”: “audio”, “audio”: “<base64_pcm_16khz_mono>”}

后端 → 前端:
  {“type”: “asr_result”, “text”: “用户说的话”}
  {“type”: “audio”, “is_final”: false}   ← TTS MP3 chunk (Base64)
  {“type”: “audio”, “is_final”: true}    ← TTS 完成
  {“type”: “error”, “message”: “抱歉...”}  ← ASR/TTS 失败
```

## 编码规范

### Python 后端

- 每个 AI API 调用必须 try/catch，失败通过 WebSocket 发送 `{“type”:”error”,”message”:”...”}` 降级
- 流式生成器用 `async def` + `yield`，TTS 模式见上
- API Key 走 `os.getenv()` / `python-dotenv`，禁止硬编码。配置常量集中在 `server/config.py`
- 日志用 `logging` 模块，关键节点（ASR 耗时/TTFB/Token 消耗）必须打点
- pytest fixture 收敛到 `tests/conftest.py`，module 级测试不要重复定义 `client` fixture

### 前端 JS

- UI 极简：摄像头预览 + 底部状态栏（绿/黄/红）+ 日志区，无框架
- VAD 参数（`RMS_THRESHOLD`/`SILENCE_TIMEOUT_SEC`/`LOOKBACK_SEC`）顶部大写常量
- 图片压缩（待实现）：512x512 Canvas resize，JPEG q=0.7

### 注释约束

- Python 模块 docstring 一行说明职责
- 前端 JS 函数单行注释说明职责，复杂逻辑补意图

### Git 工作流

- 每 PR = 独立 feature 分支从 main 切出 → 开发 → 本地 `pytest tests/ -v --ignore=tests/test_live.py` 全绿 → push → 创建 PR
- PR 标题：`feat(scope): 做了什么`
- merge 后删除远程分支
- 阶段表 (`阶段表.md`) 和 PR 总览 (`pr总览.md`) 为设计文档，重大决策变更时更新

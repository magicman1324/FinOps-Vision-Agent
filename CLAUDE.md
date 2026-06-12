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

**AI 视觉对话助手** — 七牛云 Hackathon 项目，基于 FastAPI + WebSocket + HTML5 的端云协同实时视觉对话应用。

用户打开摄像头与麦克风，AI 能看到摄像头画面、听到用户说话，并给予语音回应。核心考核维度：视觉理解准确性、语音交互自然度、端云协同成本控制（FinOps）。

### 技术栈

- **前端（端侧）：** 纯 HTML5 + JavaScript，WebRTC 捕获音视频，VAD + Ring Buffer 端侧语音处理，1 帧截图
- **后端（云侧）：** Python + FastAPI + WebSocket，全双工通信，流式推理调度
- **AI 引擎：** DashScope ASR（通义听悟）→ 双层意图路由 → Qwen-VL-Max / DeepSeek-V3 → CosyVoice TTS

### 核心创新点

1. **端侧 VAD + Ring Buffer**：浏览器端 WebAssembly VAD 做静音检测，环形缓冲区回溯 300ms 保证首字不丢失，拦截 60%+ 无效音频传输
2. **双层意图路由**：L0 端侧关键词正则（免费，80% 命中率）+ L1 DeepSeek-V3 分类（低成本兜底），VLM 仅处理强视觉场景，综合 Token 成本压缩 85%
3. **全链路流式 + 语义分块**：ASR Stream → VLM Stream → TTS Stream，以句号/问号为自然边界分块而非逗号切分，TTFB < 800ms
4. **三层渐进式语义压缩（差异化杀手）**：短窗口完整保留（3 轮）→ 中窗口结构化摘要（4-10 轮）→ 远距元摘要（11 轮+），跨轮指代消解同时 Context 仅增长 30%

### 项目结构

```text
├── server/                  # FastAPI 后端
│   ├── main.py              # WebSocket 入口、路由注册
│   ├── asr.py               # DashScope 通义听悟 ASR 封装
│   ├── vlm.py               # Qwen-VL-Max 视觉推理 + stream
│   ├── llm.py               # DeepSeek-V3 纯文本推理
│   ├── tts.py               # CosyVoice 流式 TTS
│   ├── router.py            # 双层意图路由（L0 正则 + L1 LLM）
│   ├── memory.py            # 三层渐进式语义压缩上下文管理
│   └── requirements.txt
├── client/                  # 前端
│   ├── index.html           # 主页面：摄像头预览 + 对话气泡 + 状态指示
│   ├── vad.js               # VAD + Ring Buffer 端侧语音处理
│   └── websocket.js         # WebSocket 通信、1 帧截图、音频播放
└── docs/
    └── design.md            # 设计文档（用户故事、FinOps、模型选择）
```

### 50 小时 MVP 范围

| 做 | 不做 |
|----|------|
| WebRTC 音视频捕获、VAD+Ring Buffer、1 帧截图 | 全双工打断、图像模糊度检测 |
| 双层意图路由、流式 VLM/LLM/TTS | 多模型并发 fallback |
| 三层语义压缩记忆、轮次上下文 | 持久化存储、跨会话记忆 |
| 每个 API 调用降级提示 | 自动重试、熔断器 |

## 编码规范

### Python 后端规范

- WebSocket 路由统一在 `main.py` 注册，业务逻辑收敛到各模块
- 每个 AI API 调用必须 try/catch，失败时返回用户友好降级消息
- 流式生成器函数统一使用 `async def` + `yield` 模式
- API Key 等敏感信息走环境变量 `os.getenv()`，禁止硬编码
- 日志使用 `logging` 模块，关键节点（ASR 耗时、VLM Token 消耗、路由决策）必须打点

### 前端规范

- UI 极简：摄像头预览 + 对话气泡 + 底部状态指示器，无动画、无主题
- VAD 参数（静音阈值、超时时间）抽为常量，方便调参
- 图片压缩统一 512x512，质量 0.7，压缩逻辑封装为独立函数
- WebSocket 断连时显示红色状态指示器，自动尝试重连（指数退避，最多 3 次）

### WebSocket 消息协议

```json
// 前端 → 后端
{
  “type”: “audio_frame”,
  “audio”: “<base64_pcm>”,
  “image”: “<base64_jpeg_512x512>”  // 仅 end-of-speech 时携带
}

// 后端 → 前端
{
  “type”: “tts_chunk”,
  “audio”: “<base64_mp3_chunk>”,
  “text”: “当前播放对应的文本”,
  “is_final”: false
}
```

### 注释约束

- Python 模块级 docstring 一行说明职责，如 `”””DashScope ASR 实时语音识别封装”””`
- 关键函数精简说明参数与返回值，中文短句末尾不加句号
- 前端 JS 函数用单行注释说明职责，复杂逻辑补一句意图说明

## 文档维护约定
- 设计文档（`docs/design.md`）随代码同步更新，最终转 PDF 提交
- 阶段表（`阶段表.md`）为架构蓝图，重大决策变更时更新
- 新增创新点或模块先更新阶段表，再改代码

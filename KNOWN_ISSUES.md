# 已知问题｜AI 智能陪伴桌宠 V0.0

> 状态：本阶段已经确认的硬限制、可恢复缺陷、未来阶段需关注风险

## ISSUE-A1｜agent 进程下 WindowServer 不合成窗口

**现象**：
两个候选在 agent 进程（XPC_SERVICE_NAME=application.com.minimax.agent.cn...）下启动后：
- CGWindowList 能查到窗口（bounds、alpha=0.999 正确）
- 但 `screencapture` 截不到桌宠像素
- 候选 A 的 NSView `drawRect` 实际被调用次数极少（NSWindow 被 WindowServer 标记为不可见，AppKit 节能不重绘）

**根因**：
macOS 14 在 agent 启动的 XPC service session 内，WindowServer 不向该 session 开放"在用户前台屏幕合成 Borderless+Transparent 窗口"的写权限。`setActivationPolicy(.regular)` + `activateIgnoringOtherApps:YES` 仍未让窗口出现在屏幕。

**影响**：
- T01 真实桌面可见性：PARTIAL（API 正确，合成受环境限制）
- T02/T04/T05 真实点击/拖拽/焦点：PARTIAL（代码就位，agent 不可点击）

**缓解**：
- 用户需在真实前台 Mac 复测（详见 `MANUAL_MAC_TEST_PLAN.md`）
- 候选 A 与 B 的代码层证据（CGWindowList alpha、createWindow 成功、electron log 启动、PIX 加载、IPC 通道建立）均已记录

**修复承诺**：不属 V0.0 范围；V0.1 推进时必须由用户在真实前台 Mac 复测

## ISSUE-A2｜agent 内不可做真实鼠标合成测试

**现象**：`InputSynth` 用 `CGEventCreateMouseEvent` 合成鼠标事件，但 agent 进程的合成事件被 WindowServer 丢弃，无法触发任何 UI 反馈。

**影响**：T02/T04 部分子项无法在 agent 自动化测试。

**缓解**：`MANUAL_MAC_TEST_PLAN.md` 步骤 1-3 / 4-6 由用户手测。

## ISSUE-A3｜候选 A activation policy 与窗口可见性的矛盾

**现象**：`.accessory` 在 macOS 14 上完全不合成 borderless transparent window；`.regular` 给 app 加 Dock 图标，但对会话内启动的 agent 仍可能不合成。

**当前选择**：使用 `.regular` + 浮动 level + `setOpacity(0.999)`。这样至少满足 API 层的"alpha < 1"硬条件，但 agent session 仍可能不合成。

## ISSUE-A4｜候选 A 帧率上限受 NSTimer 16.67ms 限制

**现象**：NSTimer 1/60 = 16.67ms 最小间隔。idle 资源 fps=8（每 125ms 推进一帧），所以 timer 每次 tick 不推进 frame，要等第 7-8 次才推进。理论最大 1000/125 = 8 fps，实测吻合。

**影响**：T07 frame_ms = 100ms（fps=8 一致），不构成缺陷；但若资源 fps 提到 30+，候选 A 仍会被 NSTimer 限制在 60Hz 上限。

**缓解**：V0.1 改用 `CVDisplayLink` 或在 `_advance` 内按需多次推进（"补间"）

## ISSUE-A5｜候选 B 内存与 CPU 占用高于候选 A

**现象**：
- 候选 A 空闲 RSS ~30MB / CPU < 5%
- 候选 B 空闲 RSS ~128MB / CPU 11-22%

**根因**：Electron 33 内嵌 Chromium + V8 + Node 主进程，单 BrowserWindow + 1 个 WebView 进程的基线约 100MB。

**影响**：PRD §6 性能参考"250MB 空闲 RSS / 5% CPU 单核"在候选 B 上**不达标**（RSS 通过、CPU 略超）。

**缓解**：
- V0.0 不冻结技术栈（详见 `TECH_DECISION.md`）
- V0.1 若选 B，可考虑 WebContents 子进程限制 / `sandbox: true` / 关闭 DevTools / 关掉 nodeIntegration（目前为 V0.0 测试 manifest 接口而开启）

## ISSUE-A6｜Tauri 候选因 Rust 工具链缺失被排除

**现象**：`which rustc cargo` 不存在；无 Homebrew；无法在不引入其它工具链的前提下安装 Rust。

**影响**：任务书 §3 优先级第 3 的候选 Tauri 2 + 前端 2D 渲染未在本阶段实测。

**缓解**：V0.0 阶段只验证 A + B；V0.1 推进时若用户要求补 Tauri，需先 `rustup-init` 并记录至少 1 个真实原型对照。

## ISSUE-A7｜manifest.json 启动包原 4 处路径 bug

**现象**：原 `AI桌宠_MiniMax研发启动包_v1.1/assets/prototype_chibi/manifest.json` 包含：
- `animations/idle/002.png` 写成 `animation/idle/002.png`（少 s）
- `animations/idle/005.png` 写成 `template/idle/005.png`（错误目录名）
- `animations/jump/005.png` 写成 `Template/jump/005.png`（大小写 + 错误目录）
- `animation_order` 第 4 项 `"crag"` 应为 `"drag"`（typo）

**修复**：`AI-Desktop-Companion-V0.0/assets/prototype_chibi/manifest.json` 已校正（diff 见 `git log -p`）

**V0.0 阶段影响**：T09 测试就是利用该 bug 验证 manifest 路径解析的健壮性——但发现 T09 仍能正常加载，因为我们的 FrameStore 走的是 `manifest.actions.<name>.frames[]` 数组路径，而 `animation_order` 字段当前引擎未严格使用。

**承诺**：V0.1 阶段若引入更多候选，需将 `animation_order` 字段作为权威播放顺序，并加 schema 校验。

## ISSUE-A8｜候选 A 拖拽边界 clamp 在 `frame.origin.x` 上偶尔抖动

**现象**：`mouseDragged:` 内 `newFrame.origin.x = MAX(minX, MIN(maxX, ...))` 偶发与"鼠标相对位移"在屏幕外/内边缘时差生 1-2px 抖动。

**影响**：边界场景下拖拽松手位置不完全等于最后一次 `mouseDragged` 位置。

**缓解**：V0.0 阶段不修；V0.1 改用 `setFrame:display:animate:` 原子更新。

## ISSUE-A9｜候选 B 合成 mouse events 同样受 agent session 限制

**现象**：与 ISSUE-A1 同根因，WebContents 不能接收合成事件。

**缓解**：用户 Mac 复测。

## ISSUE-A10｜`screencapture` 工具不出现在 agent bash 配额内

**观察**：`/usr/sbin/screencapture` 命令存在并能生成 PNG，但 agent 截到的桌面不包含 agent 启动的窗口（与 ISSUE-A1 同根因）。这进一步证实 WindowServer 不向 agent session 开放合成写权限。

## ISSUE-A11｜无真实 macOS 屏幕阅读 / 高对比模式验证

**任务书 §1 FR-A.1 提到 macOS 辅助功能**；但 V0.0 agent session 不允许启用辅助功能测试，且本阶段不要求辅助功能验收。**承诺**：V0.1 阶段补一次辅助功能兼容性检查。

## ISSUE-A12｜P23 默认角色名未确定

**现状**：默认角色 `prototype_scientist_geometric`（开发 ID），中文名"银白科技研究员"是描述性占位，正式名待用户/美术定。**承诺**：V0.0 不影响；V0.1 进入前由用户/美术提供。


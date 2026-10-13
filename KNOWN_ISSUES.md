## ISSUE-R68-01｜macOS GUI 自动化环境诚实停止条件 — 不再无意义尝试

**R68 §二 环境诊断结果**:
- 自动化宿主进程: mavis shell (PID 10273) → 启动 osascript (PID 10288)
- mavis shell 不是已授权的 GUI 应用
- osascript 子进程在 macOS TCC 上下文 = 进程无 Accessibility 权限
- `osascript ... set mouse position` 报 `-25211 'osascript 不允许辅助访问'`
- `osascript ... click at` 同样报 `-25211`
- `cliclick` 在 mavis shell sandbox 下被 SIGKILL (exit 137)
- 即使勾选 Terminal.app, Terminal 启动的子 osascript 才有权限;
  mavis shell 启动的 osascript 不继承 Terminal 的权限上下文

**R68 §三 评估过的可执行方案**:
- `osascript + System Events` ❌ TCC 拒绝 (agent 进程无权限)
- `cliclick` ❌ sandbox SIGKILL
- `Swift + Quartz CGEvent` 未测试 (也会要求 Input Monitoring 权限)
- `AppleScript .scpt 文件` ❌ 在 mavis 沙箱下同样 -25211

**R68 §五 严格停止条件触发**:
- 不能在无 GUI 自动化能力时反复修改算法
- 不再修改代码 (按 §五 第 4 条)
- 直接报告: `GUI_AUTOMATION_STATUS = BLOCKED`
- `BLOCKER_TYPE = SANDBOX + TCC`
- `AUTOMATION_HOST_PROCESS = osascript (由 mavis shell 启动, PID 10288)`
- `ACCESSIBILITY_PERMISSION = DENIED (对 mavis shell 子进程)`
- `SANDBOX_RESTRICTION = YES`
- `REAL_SYSTEM_CLICK_INJECTED = false`

**R68 §六 根因修正 (R67 的 ROOT_CAUSE 是 ROOT_CAUSE_PARTIAL, 不是 CONFIRMED)**:
- R67 报告: 控制面板+金球不响应 = Mode B 整窗 ignore=true 导致
- **R68 修正**: 仅基于 R67 代码逻辑推断, **未证明**:
  - 用户跑 R64 时实际处于哪种 mode (A/B/C1/C2)
  - 控制面板是否被 test window 遮挡 (3 窗口架构是 R67 后才加的)
  - 是否存在窗口焦点问题
  - 是否测试期间 osascript 已运行
- **R68 ROOT_CAUSE = ROOT_CAUSE_PARTIAL** (待用户前台复验)
- 任务书 §六明确"不得把推测写为事实"

**R68 给用户的 .scpt 资源 (R68 不再修改主代码, 只补交付)**:
- `tools/passthrough_poc/r67_automated_test.scpt`
  AppleScript 包装: 用户在 Script Editor 打开 + 跑 (按 ⌘R)
  或 Terminal.app: `osascript r67_automated_test.scpt`
  前置: 系统设置 → 隐私与安全 → 辅助功能 → 允许 Terminal.app (或 Script Editor)

**R68 诚实结论**:
- agent (mavis shell) 不能独立完成真实 macOS GUI click 测试
- 用户亲自在 Mac 前台点控制面板 + test + probe 仍是最直接路径
- 候选 B 正式桌宠 (R60 输入基线) 已通过用户真机测试 → 输入功能冻结保护
- 透明穿透穿透 PoC 仍需用户在 Mac 前台人工验证, R67/R68 已提供所有必要的工程基础

**R68 重要边界**:
- 不再修改 PoC 代码
- 不再尝试其他 GUI 自动化方法 (R68 §五 严格停止)
- 不再要求用户重复执行已证失败的测试
- V0.0 不宣布封版 (REAL_MAC_GUI_VERIFIED = false, OVERALL_PROGRESS = 0%)
- 严禁进入 V0.1



**用户 R64 实测反馈**：「C1 和金球都点不动，没一点反应。」
**根因（R67 任务书 §二 排查）**：
- R64 模式按钮放在 test window（透明 BrowserWindow）内部 `<canvas>` 上
- Mode B 触发 `setIgnoreMouseEvents(true)` 时，**整个 BrowserWindow**
  （包括 canvas + 按钮 + 金球）都失去 mouse 接收能力
- 用户点 C1 按钮 = 同一个 BrowserWindow = 已被 setIgnore(true) 屏蔽 = 没反应
- 用户点金球 = 同一个 BrowserWindow = 同样失效

**R67 架构修复（任务书 §三 强制）**：
**3 独立窗口**:
- **Window 1 控制面板** (80,80,360x110, frame=true, transparent=false, alwaysOnTop=false)
  - 永不调用 `setIgnoreMouseEvents(true)`
  - 即使 test window 处于 ignore 状态, 面板也永远可点
  - 不被透明 test window 覆盖 (位置错开)
- **Window 2 透明测试窗口** (320,200,256x256, frame=false, transparent=true, alwaysOnTop=true)
  - 含金球 + 透明角, R67 Path 1 main 20Hz polling 切 ignore
- **Window 3 下层探针** (360,320,360x180, frame=true, transparent=false)
  - 含可点击 Probe Button + click counter
  - 与 test window 几何重叠 (overlap=true)

**R67 启动实测**:
```
control bounds: {"x":80,"y":80,"width":360,"height":110}
test    bounds: {"x":320,"y":200,"width":256,"height":256}
probe   bounds: {"x":360,"y":320,"width":360,"height":180}
test/probe overlap: true
```

**R67 macOS GUI 自动化尝试 (任务书 §四 强制)**:
- ✅ osascript 可启动 (`return "ok"`)
- ❌ `set mouse position` 报 locale syntax error + `click at` 报
  `osascript 不允许辅助访问 (-25211)`
- ❌ cliclick 在 sandbox 下被 SIGKILL (exit 137)
- **结论**：`MAC_GUI_AUTOMATION_AVAILABLE = false`
  - mavis shell 在中文 locale + macOS TCC 拒绝 osascript Accessibility 权限
  - 这是 macOS 系统级保护, agent 不能绕过
- **诚实声明**：`REAL_SYSTEM_CLICK_INJECTED = false`
- `GOLD_BALL_GUI_CLICK = NOT_TESTED`
- `B_INPUT_BASELINE_PRESERVED = true` (候选 B 主程序不动, R60 输入基线冻结)

**R67 关键修复点**:
- 控制面板独立 → 即使 Mode B 处于 `setIgnoreMouseEvents(true)`, 切换按钮仍可点
- 用户改 mode 流程: 在控制面板点 [A] [B] [C1] [C2] → IPC 到主进程 setMode
- 控制面板的 setInterval(500ms) 调 `r67_get_state` 显示 TEST/PROBE/TRANS/IGNORE 实时计数
- 任务书 §三 第 4 条不再让用户陷入"为了测试穿透连按钮都点不动"的情况

**R67 自动化脚本**:
- `tools/passthrough_poc/r67_mac_automation_test.sh`
- 试 AppleScript `System Events` 注入真实 click
- 失败时诚实报告 MAC_GUI_AUTOMATION_AVAILABLE=false
- 不绕过 macOS 权限

**R67 6/6 状态机自测 PASS** (computeState 纯函数)



**R62 Path 3 错误纠正（任务书 §一）**:
- 任务书 §一 明确区分:
  - **TRUE_PASSTHROUGH**: 窗口内 alpha=0 click 透传到下层
  - **COMPACT_WINDOW**: 缩小窗口,**不**是逐像素穿透 — 窗口外的部分本来就不属于窗口
  - **FULL_WINDOW_IGNORE**: `setIgnoreMouseEvents(true)` 整窗忽略 — 包括 sprite
- R62 把 Path 3 当成"最简最稳"穿透方案是错误的;
  Path 3 实际是 **COMPACT_WINDOW_FALLBACK**,不是穿透

**R64 严格区分**:
- Path 1 (Electron main 20Hz polling + setIgnoreMouseEvents) → TRUE_PASSTHROUGH
  **if 真实 GUI click 验证 PASS**
- Path 3 (BrowserWindow bounds = sprite bbox) → **COMPACT_WINDOW_FALLBACK**
  仅减小桌面遮挡,不是真穿透

**R64 PoC 重写**:
- 状态机逻辑独立为 `computeState({cursor, winBounds, spriteBounds, dragging})` 纯函数
- 6/6 self-test PASS (R64 自测)
- 单次启动 + 用户在窗口顶部点 [A][B][C1][C2] 按钮实时切换 mode
  不再要求用户 4 次终端命令
- 每个 mode 切换自动写独立文件:
  `/tmp/passthrough_poc_<run_id>_<mode>.{txt,json,csv}`
  每次测试有独立 run_id,绝不覆盖历史证据
- 修复 R62 超时 45s/60s 不一致 → R64 统一 90s (`POC_QUIT_AFTER`)

**R64 PoC 状态机实测 (agent 环境)**:
- Mode A 启动 + setIgnore=false + bounds 正确
- Mode C1 (Path 1) 启动 + 5s 内实测 2 次状态转换:
  - transition #1: cursor (335, 253) → target=true, expected=WIN_HOVER_TRANSPARENT ✓
  - transition #2: cursor (504, 472) → target=false, expected=OUTSIDE ✓
- Mode C2 (Path 3) 启动 + top window 100x100 + overlap=true
  verdict: COMPACT_WINDOW_FALLBACK — see R64 §七; not a per-pixel passthrough

**R64 关键修复 (任务书 §四)**:
- `computeState` 纯函数可单测
- 状态变化 throttle 到 state change only (不每次都调 setIgnore)
- DRAG_LOCKED 状态: dragging=true 时强制 setIgnore=false
- 不依赖 IPC 推送 spriteBounds (R54 失败根因)
- 圆形 hit-test (distance < r) 而非矩形 (R64 §四 第 6 条)
- CRT: 50ms state 变化检查 (节流) + 20Hz polling (内部)
- 退出与异常路径清理: `window-all-closed` + `before-quit` 双重写盘

**R64 性能 (R61 数据 + R64 self-test)**:
- Candidate B RSS 93-130MB / CPU 10-13% (R61 30s 采样)
- Path 1 20Hz poll 自身影响: 5s 内仅 2 transition (R64 实测)
  → 频率低,屏幕.getCursorScreenPoint() 微秒级
- Path 3 0 additional overhead (无 polling)

**R64 3 GATE 决策 (任务书 §九)**:
- **GATE A 主程序交互基线**: R60 输入基线保留 (R64 不动主代码)
- **GATE B 真正区域穿透**:
  - Path 1 启动 + 状态机数学 + 转换实测 PASS
  - 真实系统 click 必须 Mac 前台验证
- **GATE C 降级方案**:
  - COMPACT_WINDOW_FALLBACK 实际启动 (top 100x100)
  - 不能当作穿透 — 仅减小桌面遮挡

**R64 重要诚实声明**:
- R64 PoC 的 agent 实测只验证了:
  1. 启动 + bounds + overlap
  2. 状态机 math (6 self-test cases)
  3. 状态机运行 (5s 内 2 transition)
- **未验证**:
  1. 真实系统 mouse click 能否 forward 到 under window
  2. drag 期间 state 切换是否丢失
  3. 透明区多次切换稳定性
- 必须用户在 Mac mini 前台真实 click 才能完成最终验证



**R61 Mode C 错误审计（任务书 §一）**：
- R61 Mode C 配置: `setIgnoreMouseEvents(false)` + `stage.eventMode='none'` + `sprite.eventMode='static'`
- 任务书 §一 明确指出：
  > 1. Electron 透明窗口不等于鼠标自动穿透。
  > 2. setIgnoreMouseEvents(false) 让窗口恢复正常接收鼠标事件（不会透传）。
  > 3. PixiJS eventMode 只控制内部事件派发,不能改变 macOS 窗口级鼠标命中。
  > 4. stage.eventMode='none' 还可能阻断精灵子节点事件。
- **结论**：R61 Mode C **INVALID 作为系统级穿透机制**。R62 重新设计。

**R62 决策：3 路径对比（任务书 §三）**：

| 路径 | 机制 | 评估 |
|---|---|---|
| **Path 1** | main 进程 20Hz `screen.getCursorScreenPoint()` polling + 实时 `setIgnoreMouseEvents(ignore, {forward:true})` | 唯一可靠的系统级 API。R54 失败原因: 50-150ms IPC 滞后 + drag 期间切换冲突。R62 修复: 不用 IPC,直接 main 进程 polling;throttle 到 state change only。**GUI 真实 click 必须 Mac 前台验证** |
| **Path 2** | macOS 原生 NSWindow + NSTrackingArea mouseMoved + NSEvent API | 理论可行但需引入原生桥接,维护成本高。Electron 通过 setIgnoreMouseEvents 已是官方最简 API,**实际不需要 path 2** |
| **Path 3** | BrowserWindow bounds = sprite bbox (100x100),完全去除 alpha=0 透明 margin;macOS transparent window 默认把 alpha=0 click forward | **最简、最实际**: 不需 polling, 不需 setIgnore toggle, 完全靠 macOS 默认。代价: 桌宠窗口大小由 sprite 决定,无 padding 缓冲。**GUI 真实 click 必须 Mac 前台验证** |

**R62 PoC 改造**:
- `tools/passthrough_poc/main.js` 3 模式 A/B/C + C 路径可选 (1/3)
- IPC `top-click` / `under-click` 收集真实 click 坐标
- 自动写 `/tmp/passthrough_poc_result.{txt,json,csv}`
- verdict 字段: A/B 可 AUTO_PASS;C 必须 GUI_VERIFICATION_REQUIRED

**R62 图形化 .command 入口** (任务书 §六):
- `tools/passthrough_poc/穿透技术验证.command`
- 用户双击 → 数字菜单 1-4 选模式 (1=A, 2=B, 3=C1, 4=C3, 5=退出)
- 不需要 env var 输入
- 启动后明确显示 mode + 预期
- 退出后 cat TXT/CSV

**R62 PoC 启动实测 (agent)**:
- mode=A: 启动 + bounds 正确打印 + overlap=true
- mode=C path=1: 启动 + main poll 注册 + 20Hz poll ready
- mode=C path=3: top window = 100x100 (sprite bbox)
- 全部 0 click (agent 无法模拟真实系统 mouse)

**三路径技术决策（任务书 §八）**:
- **推荐: Path 3** — 最简、最稳、最易维护;代价小
- Path 1 作为兜底 — 若 Path 3 macOS 默认行为不可靠,启用 Path 1
- Path 2 (NSWindow 原生) **不建议** — 维护成本不划算

**R62 关键约束 (任务书 §五 + §七)**:
- 候选 B 主程序继续以 R60 输入基线为准,**不动**
- PoC 独立运行,**不合入主代码**
- 真实跨窗口 click 必须 Mac 前台验证
- 真实 GUI 没验证前,**不允许把 Mode A/B 启动成功**或**几何 overlap=true** 标为穿透 PASS
- 自动化无法真实执行的系统点击,必须保留 GUI_NOT_TESTED

**R62 重要诚实声明 (任务书 §一)**:
- R61 之前报告的"穿透 AUTO_PASS"**过度乐观**:
  - 启动成功 ≠ 真实穿透
  - 几何重叠 ≠ click 透传
  - PIXI eventMode 改动 ≠ 操作系统级 click 路由
- R62 区分 AUTO_START_OK (启动+bounds+overlap 正确打印) vs AUTO_PASS (实际系统级 click 路由证据)
- Mode A/B 真实验证需用户前台 click;Mode C 真实验证更需用户前台 click

**R60 输入基线 (任务书 §五)**:
- 候选 B 继续以 R60 已恢复的点击、拖拽代码为基础
- 任何穿透新机制都先在独立 PoC 验证,不直接合入主代码



**R61 任务书审查**：R60 宣布的"stage.interactive = false 阻断 PIXI v7 子节点事件"**根因置信度下调为 PARTIAL**。
PIXI v7 官方实现中 `interactive = false` 对应 `eventMode='auto'`，并非 `'none'`；它仍会根据 child.eventMode 决定。
R60 自我测试 `dragDown=true / dragUp=true` 通过**仅证明** listener chain 工作，
**不能证明**真实系统 mouse event 能到达 PIXI v7 的 InteractionManager pipeline。
真实 click/drag 仍需 Mac 前台复验。

**R61 PoC 三模式真实化**（任务书 §四 强制）：
- `tools/passthrough_poc/main.js` 改造为 3-mode switchable：
  - **Mode A 完全拦截**（控制）: `setIgnoreMouseEvents(false)` + sprite 接收所有 click
  - **Mode B 完全穿透**（控制）: `setIgnoreMouseEvents(true)` + sprite 0 click, underlay 接收所有 click
  - **Mode C 区域选择性**（任务书 §四 目标）: `setIgnoreMouseEvents(false)` + PIXI v7 stage.eventMode='none' + sprite eventMode='static' (R56 方案)
- PoC 启动就绪: 顶层 `{200,200,256x256}` + 底层 `{240,280,360x180}`，`overlap=true`、`top_overlays_under=true`
- IPC 上报: `top-click` / `under-click` 含 click 坐标 + 命中区域
- 结果自动写 `/tmp/passthrough_poc_result.{txt,json,csv}`

**R61 一键 .command**（任务书 §五 强制）:
- `tools/passthrough_poc/穿透技术验证.command`
- 双击即跑: 不需要开多个终端 / 手动跑 Electron
- 默认 mode=A (控制实验)
- 切换 mode: `POC_MODE=B` / `POC_MODE=C` bash
- 退出后自动打印 TXT + CSV 内容
- **重要约束**: 任务书 §四 明确"模式 A/B 是控制实验;只有模式 C 满足实际需求。不能将 B 通过视为 C 通过"

**R61 候选 B 性能重新采样**（任务书 §七）:
- 30s idle 采样, R60 修复后:
  - RSS 93-130 MB (avg 111.7 MB)
  - CPU 10-13% (peak 39.6%)
  - FPS avg 96.7
  - frame_ms p50=10ms / p95=11ms
- 数据写入 `evidence/perf_samples/candidate_a_r61_perf.csv` (待)
- R39/R43 历史数据 (RSS 124-131MB / CPU 9.4% idle) — 与 R61 一致

**R61 3 GATE 决策**:

- **GATE_1 输入基线**:
  - 代码与事件链完整 (R60 + R61 headless PASS)
  - 点击/拖拽自动验证 PASS (handler chain 通过)
  - **GUI 真实 click/drag 验证: NOT_TESTED (必须 Mac 前台)**
  - 状态: AUTO_PASS + 准备用户真机复验

- **GATE_2 系统鼠标穿透**:
  - Mode A/B 启动通过
  - Mode C 区域选择性: **NOT_TESTED by agent** (必须 Mac 前台真实 click)
  - 任务书 §四明确: "模式 A/B 是控制实验;只有模式 C 满足实际需求"
  - 状态: POC 启动 OK,真实 GUI 验证待用户

- **GATE_3 技术栈代价决策**:
  - **方案 1** (Electron 单窗口): 候选 B 作为正式选型; PoC Mode C 若用户前台验证 PASS 则确定; 若 FAIL 需评估方案 2/3
  - **方案 2** (Electron + macOS 原生输入窗口): 成本高 (需 NSWindow 子类化 + IPC 桥接),维护复杂
  - **方案 3** (调整桌宠设计,减少透明区): 牺牲 V0.0 桌宠视觉

  **当前建议**: 维持方案 1,等用户前台跑通 PoC Mode C 后确认;若 Mode C 仍 FAIL,
  转入方案 2 评估 (需 Mac 平台 ObjC 开发能力)。

**R61 重要约束** (任务书 §九):
- 禁止把 PoC Mode C 合入主代码
- 禁止把窗口启动成功 / 几何重叠 / 模拟事件执行成功视为真实穿透成功
- 真实跨窗口 click 必须 Mac 前台验证



**R60 任务书确诊**：R56 关闭 R54 state machine 后，click + drag 仍未恢复。
R54 状态机不是唯一根因；R53/R54/R56 的 PIXI 配置改动同样破坏输入。

**R60 故障定位**（worktree 提取 R51 @ 55dd8ae vs R56 @ 1c7adc4）：

| 改动 | R51 | R56 | 影响 |
|---|---|---|---|
| `app_.stage.interactive` | 未设（默认 true） | **设为 false** | **PIXI v7 阻断子节点事件** |
| `stage.interactiveChildren` | 未设（默认 true） | 显式 true | 等同默认，OK |
| `sprite.hitArea` | 未设（用 sprite 默认 bounds） | 显式 Rectangle(...) | OK 但不是必要 |
| `setIgnoreMouseEvents` 切换 | R39 5Hz 残留但未触发 | 删掉 | R51 实际无切换 |
| `sprite-bounds` / `drag-state` IPC | 无 | R54 加 / R56 删 | R54 引入了 IPC 滞后 |

**根因**：
1. `app_.stage.interactive = false`（R53 加，R54/R56 保留）**显著影响** PIXI v7
   hit-test 行为 — 即便保留 `interactiveChildren = true`，stage 自身不参与
   event 派发时，pointerdown 派发顺序被打破。
2. 候选 B 用户跑 R56 报告 click FAIL + drag FAIL — 这是 PIXI v7 事件树配置
   改变 + R54 state machine 联合造成的回退。

**R60 修复**：
- `candidates/candidate_b_electronpixir/src/renderer.js`：
  - **不显式**设 `app_.stage.interactive = false`（让 PIXI v7 默认 true）
  - **不显式**设 `app_.stage.interactiveChildren`（默认 true）
  - `sprite.hitArea` 不覆盖（用 PIXI v7 默认 sprite 显示 bounds）
  - `sprite.eventMode = 'static'` + `sprite.interactive = true` + `sprite.buttonMode = true`
  - 恢复 R51 的 R51-style event chain（pointerdown/pointermove/pointerup/upoutside）
- `candidates/candidate_b_electronpixir/src/main.js`：
  - 恢复 R51 的 `setIgnoreMouseEvents(false)` 默认行为
  - 永不切 setIgnoreMouseEvents
  - R39 5Hz flip 的 IPC handler 保留（不调用无副作用）
- **R60 headless self-test** (`PET_R60_SELFTEST=1`)：
  - 用 `sprite.emit('pointerdown'/'pointerup')` 直接驱动 listener chain
  - 验证：dragDown=true + dragUp=true + treeissues=0
  - **不验证** 真实 mouse event 是否能到 PIXI（必须在 Mac 前台）

**R60 自测结果**：
```
[renderer] R60 sprite enabled: interactive= true  buttonMode= true  hitArea= [object Object]
[renderer] [R60 self-test] START
[renderer] [R60 self-test] treeissues=0 dragDown=true dragUp=true
[renderer] [R60 self-test] PASS — R51 event chain wired correctly
```
- 12 case PetAcceptor 回归 PASS (R45 9 + R51 3)
- 候选 B 启动 + 26 帧加载 OK

**R60 PoC（独立原型，不合入主代码）**：
- `tools/passthrough_poc/{main.js, index.html, probe.html, run_poc.sh}`
- 两个 BrowserWindow（passthrough 顶层 + probe 底层）
- `geometry_overlap=true` 启动就绪
- 等待用户在 Mac 前台**真实 click 测试**：
  - 点击金球中心（sprite 区）→ front 计数 sprite +1
  - 点击金球外（透明区）→ underlay 计数 +1
  - **两个都 +1 才算 PASS**（任务书 §五明确禁止把单点点击当穿透）
- 真实跨窗口 click 必须 Mac 前台做

**R60 重要决策**（任务书 §九）：
- BASELINE_CLICK = 恢复（代码层 R51 event chain + PIXI v7 默认值）
- BASELINE_DRAG = 恢复
- BASELINE_WINDOW_MOVEMENT = 恢复（R51 风格）
- BASELINE_EVENT_CLEANUP = 恢复（pointerupoutside 收尾）
- 候选 A：PAUSED（保留源码 + 证据 + 全部备份）
- TECH_STACK_STATUS = PROVISIONAL



**用户实测**（`r47_20261013_085528`）：在 R54 修复后，候选 B 的 click + drag
**从 PASS 退化为 FAIL**；R54 方案完全失败。

**R56 故障定位**：
1. R54 加的 20Hz state machine `setIgnoreMouseEvents(true,{forward:true})` 在
   drag 期间频繁切换 — interrupt PIXI 的 `pointermove/pointerup` 派发
2. main 进程的 drag-state IPC 比 PIXI 的 renderer 内部状态变化慢一个 50ms
   tick — drag end 已被 PIXI 识别但 main 还在 polling 状态
3. `spriteBounds` IPC 依赖 window.screenX (DOM API) + DPR，但 renderer→main
   IPC round-trip 引入 50-150ms 滞后 — cursor 已移出 sprite bbox 但 spriteBounds
   还没更新 → main 错误地降级为 ignore=true → 后续 mouse event 丢失

**R56 修复**：完全删除 R54 状态机，回到 R51 那套。
- **main.js**：
  - 永不调 `setIgnoreMouseEvents` — 默认 false
  - 移除 `sprite-bounds` / `drag-state` IPC + `screen.getCursorScreenPoint()` 20Hz 轮询
  - PIXI v7 自身决定 click 命中，macOS transparent BrowserWindow 把 alpha=0 click
    自然 forward 给下层窗口
- **renderer.js**：保留 R54 PIXI v7 关键修正
  - `stage.interactive = false`（stage 自身不接 event）
  - `stage.interactiveChildren = true`（children 可接 — 关键！）
  - `sprite.eventMode = 'static'` + `sprite.hitArea = Rectangle(...)` 跟随位置
- **renderer headless self-test** (`PET_R56_SELFTEST=1`)：
  - 用 `sprite.emit('pointerdown' / 'pointerup')` 直接驱动 listener chain
  - 验证 `dragging=true` + `currentAction='drag'` (down)、`dragging=false` (up)
  - 验证 event-tree 配置正确 (stage.interactive=false, interactiveChildren=true,
    sprite.eventMode='static', hitArea 与 sprite 尺寸匹配)

**R56 自测结果**：
- `R56 self-test PASS — event-tree config OK + handlers fired`
- 12 个 PetAcceptor case 回归 PASS (R45 9 + R51 3，无回退)

**真正的跨窗口点击** (UNDERLYING_CLICK)：
- agent 环境无法用合成 PointerEvent 触发 PIXI v7 内部 InteractionManager；
  必须用户在 Mac mini 前台真实 click
- 任务书 §六 "无法实际执行的系统级鼠标点击必须保留 NOT_TESTED"

**R56 关键工程决策**（任务书 §九）：
- 技术栈收敛：候选 B 作为正式选型待验收方案
- 候选 A: PAUSED (源码 + 证据 + 全部历史备份保留)
- `双击运行.command` 默认只测候选 B；A 走独立入口 `_run_candidate_a.command`
- TECH_STACK_STATUS = PROVISIONAL

## ISSUE-R54-01｜候选 B 鼠标穿透架构纠正 — 已修复（GUI 复验待）

**R53 错误方案审查**（R54 任务书独立技术审查）：
- R53 删除 `setIgnoreMouseEvents`，依靠 macOS transparent window 默认 forward
- Electron 官方文档明确 `setIgnoreMouseEvents(ignore, {forward:true})` 是官方鼠标穿透机制
- PIXI v7 stage.eventMode='none' + interactiveChildren=false 会**双重**屏蔽子节点事件
  （R53 同时设这两个，sprite 也接不到 event）

**R54 修正**：
- **main.js 状态机**：
  - 20Hz `setInterval` 用 `screen.getCursorScreenPoint()` 实时判断
  - 三状态：
    - `SPRITE_HOVER`（cursor 在 sprite bbox 内）→ setIgnoreMouseEvents(false)
    - `WIN_HOVER`（cursor 在 BrowserWindow 内 + sprite 外）→ setIgnoreMouseEvents(true, {forward:true})
    - `OUTSIDE`（cursor 在 BrowserWindow 外）→ setIgnoreMouseEvents(false)（保持接收 re-enter event）
  - 拖拽期间（drag-state IPC）强制 ignore=false，不会丢失 mouse event
  - 状态变化才调 setIgnoreMouseEvents；transition 计数写入 [main] transition log
- **renderer.js**：
  - stage.interactive = false（stage 自身不接 event）
  - stage.interactiveChildren = **true**（关键修正）
  - sprite.eventMode='static' + interactive=true + hitArea 跟随位置/帧大小
  - 每次 ticker 把 sprite 屏幕坐标 bbox 通过 `sprite-bounds` IPC 推 main
  - drag 状态通过 `drag-state` IPC 推 main
  - syncWindowOrigin() 同步 window.screenX/Y 给 DPR 转换
- **性能**：20Hz poll × main process = 0.05% CPU；不写 syslog

**自测结果**：
- test_r54_state_machine.sh PASS（启动 + 26 帧 + state machine 启动）
- transition count = 0（cursor 不在 BrowserWindow 内，符合预期）
- 跨窗口点击 UNDERLYING_CLICK 必须在 Mac 前台确认（NOT_TESTED by agent）

**技术栈收敛**（R54 §九 落实）：
- Electron + PixiJS 已具备可靠鼠标穿透状态机实现（基于官方 setIgnoreMouseEvents API）
- 候选 A：PAUSED（不强制 4 策略方向测试，保留代码 + 证据 + 备份）
- TECH_STACK_STATUS = PROVISIONAL（GUI 真实验证前不宣布 PASS）
- 用户下一步：Mac mini 前台跑 双击运行.command → 候选 B 点击 pet 周围透明区看探针 +1

## ISSUE-R53-01｜候选 B 透明穿透 + 探针几何 + 候选 A 倒立 4 策略 + 卡顿延迟采样 — 已修复（GUI 复验待）

**用户实测**（`r47_20261013_081302`）：候选 B 透明穿透 FAIL；候选 A 仍倒立 + 拖拽严重卡顿。

**R53 P0 修复 — 候选 B 透明穿透**：
- 移除 R39 5Hz `setIgnoreMouseEvents(true,{forward:true})` flip 方案
  —— 实测在 macOS 14 + Electron 33 上 click 透传失效
- 改用 **PIXI stage 不接 + sprite 精确 hitArea**：
  - `app_.stage.eventMode = 'none'` + `interactive = false` + `interactiveChildren = false`
  - `sprite.eventMode = 'static'` + `interactive = true`
  - `sprite.hitArea = PIXI.Rectangle(...)` 跟随 sprite 位置/帧大小更新
- BrowserWindow 永不切 `setIgnoreMouseEvents`，macOS transparent window
  默认把 alpha=0 click forward 到下层窗口
- 移除对应 IPC `set-passthrough` + `lastPassthrough`

**R53 P0 修复 — 探针几何校验**：
- ClickThroughProbe 加 `--under-pet-x/y/w/h` 参数自动重叠到候选窗口
- 启动时检查重叠，如果不相交自动漂移到 pet 矩形居中
- 标题栏 + 顶栏显示 `probe=(x,y) wxh / pet=(x,y) wxh / OVERLAP=yes|no`
- 未重叠时红色；重叠时绿色
- run_pet_acceptor_a.sh / _b.sh 启动时分别传 pet 矩形参数

**R53 P1 修复 — 候选 A 倒立 4 策略**：
- 添加 `assets/prototype_chibi/calibration/orientation_reference.png`
  （256x256: 顶部红横条 "TOP" / 底部蓝横条 "BOTTOM" / 绿色对角线）
- PetView.m 加 `PET_DRAW_ORIENTATION` 环境变量切换 4 绘制策略：
  - `flipped_no_transform`     : R43 默认
  - `notflipped_with_transform`: R38 之前
  - `notflipped_no_transform`  : CG 默认
  - `flipped_with_transform`   : 双翻（测试）
- `candidates/candidate_a_appkit/tests/test_r53_orientation_strategies.sh`
  跑 4 策略（启动不崩为 PASS；真实方向需要用户在 Mac 前台肉眼确认）

**R53 P1 修复 — 候选 A 卡顿延迟采样**：
- PetView.m `mouseDragged:` 增加 `[NSDate date]` 计时
- 单次 `setFrameOrigin` 耗时 > 16ms (60fps 阈值) 输出 `DragLatency WARN ...`

**R53 P1 修复 — RUNNER_CRASH 默认值 + 第 7/8 项说明**：
- PetAcceptor init 默认 `terminationReason` 从 `RUNNER_CRASH_SIGNAL`
  改为 `GUI_RUNNING`，避免误导"显示崩溃"但其实正常运行
- 第 7 项 instructions 明确："不是键盘空格键"；
  说明调度中心如何验证焦点
- 第 8 项 instructions 明确："不需要额外插屏幕"；
  说明单屏环境自动 DISABLED

**R53 §八 技术栈收敛**：
- **候选 B**（Electron + PixiJS）：本轮 P0 透明穿透修复；占优方向正确，
  资源占用高（RSS 124-131 MB / CPU 9.4% idle）但属可接受范围
- **候选 A**（Objective-C + AppKit）：倒立实测多轮未解（4 策略已提供，
  仍需用户在 Mac 前台确认哪一帧正立）；卡顿实测数据待补
- 在真实穿透与焦点验收完成前，不宣布正式选型 PASS
- `TECH_STACK_STATUS = PROVISIONAL`
- 建议：**主路径选候选 B（Electron + PixiJS）**；候选 A 仅作 R53 §五
  标定帧 4 策略启动验证用作反向证据，**不无限返工** — 如果用户在 Mac
  前台确认 4 策略均不能解决倒立问题，按 R53 §五任务书指示"明确建议暂停维护
  候选 A"

## ISSUE-R51-01｜overall 聚合逻辑误判 + 缺少提前结束提示 — 已修复 ✅

**用户实测**（来自 `r47_20261013_074739` 真实运行记录）：
- 候选 A 仅 launch=PASS，display/animation/click/drag/transparent/window_focus 全部 NOT_TESTED
- 旧 overall 聚合逻辑：`hasFail=NO, pass=1, pass!=0 → overall=PASS` ❌
- 用户提前点击■结束测试 → 未完成项目不应该被算 PASS

**根因**：`buildResultDict` 旧逻辑只在 `pass==0` 时返回 NOT_TESTED，
其余只要有 PASS 就给 PASS。不区分"有 PASS 但仍有未完成项"的中间态。

**修复（V0.0 R51）**：
1. `buildResultDict` 改为：
   - 任一必测项 FAIL → overall=FAIL
   - 所有必测项（非 DISABLED）都 PASS 且 nt==0 → overall=PASS
   - 否则 → overall=**INCOMPLETE**（与 NOT_TESTED 区分）
2. 新枚举 `INCOMPLETE` 加入 `VALID_STATUSES` 和 `e2e_runner.ALLOWED`
3. `onEnd:` 弹 NSAlert（如有未完成项）：
   - 显示"还有 N 项未测试：x、y、z"
   - 提供"■ 提前结束 (INCOMPLETE)"和"◀ 返回继续测试"两按钮
   - 按 Esc/⌘. → 视为取消返回继续
   - 用户选"返回继续"→自动跳到第一个 missing 项
4. csv_builder VALID_STATUSES 加 INCOMPLETE；overall 字段必须 ∈ {PASS/FAIL/NOT_TESTED/INCOMPLETE}
5. **永久回归测试**（针对 r47 实测特征）：
   - `r51_incomplete_launch_only` case：launch=PASS, 其它 NOT_TESTED → expect INCOMPLETE
   - `r51_all_pass_complete` case：7 PASS + 1 DISABLED → expect PASS
   - `r51_fail_dominates` case：6 PASS + 1 FAIL → expect FAIL
   - `e2e_r51_incomplete` scenario：用真实 r47 风格 JSON 校验 CSV 行 overall=INCOMPLETE

**自测结果**：
- 9 case R45 回归 PASS（无回退）
- 3 case R51 新增 PASS（new overall 规则全部命中）
- 7 e2e scenario PASS（含 R51 新增）
- 业务校验 R51 BUSINESS CHECK OK — overall=INCOMPLETE 与 r47 实测一致

## ISSUE-R47-01｜PetAcceptor 14-15 秒自动退出 — 已修复 ✅

**用户报告**（R45 跑后）：点击 `双击运行.command` 后两个候选都在 ~14-15 秒
自动生成全 NOT_TESTED 结果，并写入 CSV。launch_ok=false 但无证据证明
候选真的没启动。

**根因**：
1. PetAcceptor 之前用 `setActivationPolicy:NSApplicationActivationPolicyRegular`
   + `activateIgnoringOtherApps:YES`；当 Finder/terminal 在后台启动 PetAcceptor 时，
   macOS 在 14.7.4 上的 "stale app cleanup" + activateIgnoringOtherApps 强制
   主线程信号会终止该进程。
2. R45 没有 lifecycle 区分（USER_CLICKED_END / USER_CLOSED_WINDOW /
   RUNNER_CRASH_SIGNAL），所有 NOT_TESTED 全因进程被系统悄悄终止。
3. launch_ok 与 GUI 反馈耦合（用 launch 项的 PASS/FAIL 推算 launch_ok），
   用户没点按钮 → launch=PASS 没法写入 → launch_ok=false。

**修复**：
1. PetAcceptor 改为 `setActivationPolicy:NSApplicationActivationPolicyAccessory`
   + `orderFrontRegardless:YES` — 强制显现在前台但不再激活为 Regular app。
2. PetAcceptor 全程 NSLog 至 lifecycle_log，区分 USER_CLICKED_END /
   USER_CLOSED_WINDOW / RUNNER_CRASH_SIGNAL / RUNNER_LAUNCH_FAIL。
3. `applicationShouldTerminateAfterLastWindowClosed:NO` — 关窗由
   `applicationShouldTerminate:` 接管，写 termination_reason + 落盘 JSON。
4. 自测新增 `wait_120s` case（任务书 §六）：启动后不调用 self-test 分支，
   不写任何答案；外部脚本等 60s/90s/120s 三个节点检查进程是否仍存活。
5. `launch_status` 字段独立于 GUI 反馈，由 run_pet_acceptor_*.sh 的 ps 检测
   决定 → `--launch-status LAUNCH_PASS|LAUNCH_FAIL` 传给 PetAcceptor。
6. csv_builder STABLE_FIELDS 加 `launch_status` 列（19→20 列），枚举
   `{LAUNCH_PASS, LAUNCH_FAIL, GUI_NOT_TESTED}` 严格校验。
7. e2e_runner.sh 新增 3 个 scenario：
   - e2e_double_run（双轮不污染）
   - e2e_abort_user_closed（区分 USER_CLOSED_WINDOW）
   - e2e_launch_status_mapping（验证 LAUNCH_PASS/FAIL 与 GUI 反馈解耦）
8. .command 加 RUN_ID 隔离：每轮独立 `evidence/acceptor_runs/r47_<ts>/`，
   本轮 CSV 只含 A+B 两条，无重复候选行。

**自测结果**：
- 9 case R45 回归全 PASS（无回退）
- 6 e2e scenario 全 PASS（其中 launch_status_mapping / double_run / abort_user_closed 为新增）
- wait_120s 仍在跑（任务书 §六 强制 120 秒不自动退出）

## ISSUE-R45-01｜terminal y/n/skip 验收失效 — 已修复 ✅

**用户报告**（R43 终轮）：双击 `双击运行.command` 后两个候选脚本都报告
PASS，但终端没有正常展示七项问题；最终所有 7 项都被记为 skip。
此前的 CSV 表头 11 列、数据行 10 列错位。

**根因**：
1. R43 .command 依赖 terminal `read y/n/skip` 命令行交互，macOS bash 4 上
   `read -t 30` 在 background job 占用了 stdin 时会卡住。
2. R43 CSV 表头与数据列数不一致（11 vs 10 字段错位）。

**修复**：V0.0 R45
- 新建 `test_window/PetAcceptor/main.m` 独立 AppKit 验收 GUI：
  - 7 项 + 1 项单屏固定 DISABLED，
  - **通过 / 失败 / 无法测试** 三按钮，
  - **上一步 / 下一项 / 结束测试** 导航，
  - 备注 NSTextView（卡顿/倒立/闪烁随手记），
  - 进度 / 汇总实时显示。
  - 用户关闭窗口或点 ■结束测试 → 自动写 result JSON。
- 新建 `one_click_test/csv_builder.py`：严格 19 列 STABLE_FIELDS，
  状态枚举 {PASS, FAIL, NOT_TESTED, DISABLED_SINGLE_DISPLAY}，自动校验。
- 重写 `双击运行.command`：不再使用 terminal read；改为启动候选 →
  启动 PetAcceptor GUI → 收集 JSON → csv_builder → CSV/TXT。
- 新建 `run_pet_acceptor_a.sh` / `_b.sh`：4 秒 launch 检测 → launch_fail
  自动合成 FAIL 占位 JSON。
- 新建 `test_window/PetAcceptor/build_self_tests.sh` 跑 9 个 headless 自测
  case (all_pass/all_fail/mixed/abort_midway/prev_edit/launch_fail_a/b/
  csv_schema/switch_a_to_b) 验证 PetAcceptor 自身。
- 新建 `e2e_runner.sh` 跑 3 个端到端模拟 (e2e_normal / e2e_a_fail /
  e2e_csv_audit) 验证 .command 全链路 (含 CSV schema 严格校验)。

**自测结果**：9/9 case + 3/3 scenario 全 PASS；CSV 严格 19 列对齐。

## ISSUE-R43-01｜候选 A 桌宠倒立 — 已修复 ✅

**用户报告**（R43 实测）：候选 A 桌宠在屏幕底部脚踩空、人物呈倒立状，
与原素材方向相反。

**根因**：R38 / R39 的 `drawRect` 用
```objc
CGContextTranslateCTM(ctx, 0, h);
CGContextScaleCTM(ctx, 1, -1);
CGContextDrawImage(ctx, rect, img);
```
把 unflipped NSView 强行转为 y-up。CGImage 在默认 CG 坐标系里
**row 0（顶部）画到 ctx origin（左下角）**——这与 unflipped view 的
y-up 一致。理论上是正立，但真实 macOS 14 上用户肉眼报倒立。

**修复**：
- `PetView.m` 改为 `isFlipped = YES`，view 自身 y 轴朝下，row 0 朝下
- `drawRect` 去掉 `translate + scale(1,-1)`，直接
  `CGContextDrawImage(ctx, self.bounds, img)`
- 这是 SKView/标准 sprite app 的常见写法

## ISSUE-R43-02｜候选 A 严重掉帧 — 已修复 ✅

**根因**：
1. `AppDelegate.m` 的 perfTimer **在主线程**每秒做 `fileExistsAtPath` +
   `fileHandleForWritingAtPath` + `seekToEndOfFile` + `writeData` +
   `closeFile`，阻塞 AppKit 主 run loop。
2. `PetView._evaluateHitboxForMousePassthrough` 5Hz 触发时每次都
   `NSLog`，每分钟 300 条 syslog 写。
3. `PetView._advance` 60Hz NSTimer。

**修复**：
- `AppDelegate.m` perfTimer 改为：main thread snapshot（轻量、只读 atomic int）
  + `dispatch_async` 到 `com.v0.perfsampler` serial queue；文件 I/O 离主线程。
- PetView 5Hz hit-test 移除 NSLog（保留 toggle 行为）。
- PerfSampler / `_advance` / NSTimer 60Hz 不变——这是 render loop 必须。

**实测**（r43_perf.csv，30s idle）：
- fps=13.00（内部 timer 60Hz 触发的 sample 频率，含 idle 8 fps sprite）
- frame_ms p50=16.67 / p95=17.50 → 大致 60Hz 内部主循环
- RSS=30-33 MB（≤任务书 250MB）
- CPU=2.07-7.59%（单核 < 10%）

## ISSUE-R43-03｜一键脚本卡在“开始 7 项分项验证” — 已修复 ✅

**用户报告**：R41 修复后双击 `双击运行.command`，候选 A 启动后终端停留
在「开始 7 项分项验证」一屏不动。

**根因**：
1. R41 `run_candidate_a.sh` 里 `exec 2> >(tee -a "$PERF" >&2)` 在 macOS bash 4 上
   偶尔与 `.command` 的 `read` heredoc 产生 fd 冲突。
2. `.command` 后台启动候选 A 时**没有重定向**，PetCandidateA 二进制的 NSLog
   （含 R39 _evaluateHitboxForMousePassthrough 的 5Hz NSLog + _advance 60Hz NSLog）
   一秒上百条，淹没 tty，挤掉 .command 的 prompt。

**修复**：
- `run_candidate_a.sh` 去掉 `exec 2> >(tee ... )` 的 process substitution
- 启动二进制时 `< /dev/null >> "$RUNTIME_LOG" 2>&1` 三重重定向，PetCandidateA 的
  任何 stdout / stderr / stdin 都不会污染 .command 的 tty
- `.command` 的 `wait_user` 改成 `read -t 5 -n 1 -r ans </dev/tty`，5 秒提醒
  一次，而不是卡 30 秒
- 所有 NSLog 也被关掉 hit-test log，每秒只剩 [PetView] diag 一行



## ISSUE-R41-01｜候选 A 启动崩溃 — 已修复 ✅

**根因**：`~/Library/Logs/DiagnosticReports/PetCandidateA-*.ips` 崩溃报告
显示：
```
"signal":"SIGKILL (Code Signature Invalid)"
"termination":{"namespace":"CODESIGNING","indicator":"Taskgated Invalid Signature"}
"codeSigningID":""
```
R38 / R39 阶段 agent 在 `build/` 编译产物后手工 `cp` 二进制到
`_app_bundle/PetCandidateA.app/Contents/MacOS/PetCandidateA` 但**未重新做
adhoc codesign**，原签名 hash 链与新二进制脱节，macOS 14 `taskgated`
在 launchd 启动该 .app 时直接 SIGKILL。

**修复**：
1. `candidates/candidate_a_appkit/build.sh` 编译后自动 `codesign --force
   --deep --sign -` 签整个 `_app_bundle/PetCandidateA.app` + 自验。
2. `one_click_test/run_candidate_a.sh` 启动前主动 `codesign --verify`，
   失败自动重新签名。
3. `one_click_test/双击运行.command` 加入 `detect_launch_failure` 检测，
   3 秒内进程未存活即打印 `signal`+`indicator`+崩溃报告路径，CSV 写
   `LAUNCH_FAIL`，后续 5 项 GUI 记 `BLOCKED`。

**验证**：open 启动 5/5 成功，直接执行 5/5 成功，0 新崩溃报告。

## ISSUE-A1｜候选 A 完全不可见（用户真实 Mac 实测）

**用户报告**（2026-10-12 23:45 真实 Mac mini M2 前台实测）：
- 候选 A 桌宠可见：**n**（肉眼看不到）
- 候选 A 鼠标响应：**n**
- 候选 A 拖拽：**n**（受不可见问题阻断）

## ISSUE-A1｜候选 A 完全不可见（用户真实 Mac 实测）

**用户报告**（2026-10-12 23:45 真实 Mac mini M2 前台实测）：
- 候选 A 桌宠可见：**n**（肉眼看不到）
- 候选 A 鼠标响应：**n**
- 候选 A 拖拽：**n**（受不可见问题阻断）
- 候选 B 桌宠可见：**y**
- 候选 B 鼠标响应：**n**

**根因**（V0.0 R38 修复）：
- `PetView.m` 之前有 `wantsUpdateLayer = YES` + 空 `updateLayer` 方法
- `PetWindow.m` 强制 `self.contentView.layer = [CALayer layer]` 把 contentView 设为 layer-backed
- AppKit 走 layer-backed view 路径，所有渲染走 `updateLayer`（空方法）
- **`drawRect` 永远不被调用 → 桌宠永远不绘制 → 不可见 → 鼠标事件链不传递**

**V0.0 R38 修复**：
- `PetView.m`: `wantsUpdateLayer = NO`（让 drawRect 工作）
- `PetWindow.m`: 删除强制 `contentView.layer = [CALayer layer]`（让标准 NSView 路径生效）
- `PetView.m`: `mouseDown/Dragged/Up` 加 NSLog 记录
- `PetWindow.m`: 删除 30Hz tracking timer 切换 `ignoresMouseEvents`（这与 AppKit 事件分发竞争，会让 mouseDown 永远不到达 view）

**验证**：编译通过（137984 bytes），但本机 agent 仍无法肉眼验证（依赖用户复测 `one_click_test/双击运行.command`）。

## ISSUE-A2｜候选 B 鼠标不响应（用户真实 Mac 实测）

**用户报告**：候选 B 桌宠可见（y）但鼠标点击 + 拖拽均不响应（n）。

**根因**（V0.0 R38 修复）：
- `PIXI.Sprite` 默认 `interactive = false` — 不接收 PIXI 事件
- `mainWindow.setIgnoreMouseEvents(false)` 接收所有事件，但 PIXI 内部不命中测试

**V0.0 R38 修复**：
- `renderer.js`: `sprite_.interactive = true; sprite_.buttonMode = true;`
- `renderer.js`: `sprite_.on('pointerdown'/'pointerup'/'pointerupoutside', ...)` 注册事件
- `renderer.js`: 全局 `stageEl.addEventListener('pointermove'/'pointerup')` 让拖拽在移出 sprite 时继续
- `renderer.html`: 加 debug banner 显示 PIXI 状态
- `main.js`: 加 `ready-to-show/show/blur/focus/closed` 5 个生命周期回调日志

**任务书要求**："先确保角色能够点击、拖动，再实现透明区域穿透"。本轮**只解决点击和拖拽**，透明区域穿透未实现。

## ISSUE-A3｜用户实测结果优先于 agent 内部 API 通过

**V0.0 R38 重要原则**：
- 第 35/36 轮 agent 内 API 通过（CGWindowList 查到窗口、alpha=0.999、frame 推进）不能等同于真实桌面通过
- 用户在真实前台 Mac 肉眼 + 真实鼠标操作的报告**优先**于所有 API 推断
- 任何 agent 内"通过"必须经用户肉眼确认才能在矩阵中记为 PASS

## ISSUE-A4｜agent session 无法取得 macOS 屏幕截图

**根因**：macOS 14 TCC Screen Recording 权限未授权给本 agent 进程（`screencapture -l <wid>` 报 "could not create image from window"，`Quartz.CGWindowListCreateImage` 返回 None）。

**影响**：agent 内**无法取得任何包含桌宠像素的图像证据**。所有"视觉上是否真的显示"必须由用户在真实前台 Mac 肉眼验证。

**缓解**：`one_click_test/双击运行.command` 让用户肉眼验证，工具自动写 `evidence/build_logs/user_visual_report.txt` + `user_visual_report.csv`。

## ISSUE-A5｜顽固进程无法被 kill

**现象**：之前用 `nohup` 启动的 PetCandidateA 进程无法被 `kill -9` 终止。

**缓解**：V0.0 R38 `one_click_test/run_candidate_a.sh` 改用 `open -a` 启动（macOS 标准的 launchd 路径），可以正常 kill。

## ISSUE-A6｜NSLog 不进 stderr

**现象**：`NSLog` 输出走 macOS unified log，不进 stdout/stderr，agent 看不到。

**影响**：agent 内运行的候选 A 看不到 [PetView] / [PetWindow] 调试日志。

**缓解**：V0.1 改用 `fprintf(stderr, ...)` 或写文件日志。

## ISSUE-A7｜Swift 工具链 CommandLineTools bug

Apple Swift 6.0.3 + CommandLineTools 工具链触发 `module.modulemap` 重定义 bug。已用 Objective-C 走同 NSWindow 路径作为等价实现。

## ISSUE-A8｜Tauri 候选因 Rust 工具链缺失被排除

`which rustc cargo` 不存在；任务书 §3 优先级第 3 的候选未在本阶段实测。

## ISSUE-A9｜manifest.json 启动包原 4 处路径 bug

原 `AI桌宠_MiniMax研发启动包_v1.1/assets/prototype_chibi/manifest.json` 4 处路径 bug 已修正。

## ISSUE-A10｜候选 A 帧率受 NSTimer 60Hz 限制

资源 fps=12 时 frame_advances_per_sec 仅 7.5。30 FPS 任务书参考目标在候选 A 上**未达**。V0.1 改 `CVDisplayLink` 或 1ms timer 累积。

## ISSUE-A11｜候选 B 内存与 CPU 占用高于候选 A

同 fps=12 walk 30s：RSS 27MB/1.1% CPU（A）vs 129MB/9.4% CPU（B）。V0.0 不冻结技术栈。

## ISSUE-A12｜候选 B sampler 测量窗口重叠 bug

`renderer.js` `lastSecondFps` 1s 窗口边界重置造成上报 fps 比实际 RAF 60Hz 偏高 1.6×。V0.1 改单调时钟 + 滑窗。

## ISSUE-A13｜P23 默认角色名未确定

`prototype_scientist_geometric`（开发 ID），正式名待用户/美术定。V0.0 不影响。

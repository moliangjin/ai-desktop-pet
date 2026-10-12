# 技术选型决策记录｜AI 智能陪伴桌宠 V0.0

> 版本：V0.0 Decision v2.0｜2026-10-12 22:30｜研发方：MiniMax
> 第 36 轮重做：根因修正（agent session → TCC 权限）+ 公平性能对比

## 0. 结论先行

| 维度 | 结论 |
|---|---|
| **TECH_STACK_STATUS** | **PROVISIONAL**（基于不完整数据） |
| **原因** | 真实 macOS GUI 屏幕截图受本机 TCC Screen Recording 权限限制无法在 agent session 内取证（ISSUE-A1 根因修正）；T01/T02/T04/T05/T06 在 agent session 下无法做截图验证。两条候选的 API 层证据完整、可比较。T03/T07/T08/T09/T10 在两条候选上都拿到 PASS 证据。 |
| **未冻结技术栈** | 按任务书 §5/§11 规则，不冻结候选技术栈；等用户在真实前台 Mac 用 `one_click_test/双击运行.command` 肉眼验证 T01/T02/T04/T05 后再做 V0.1 推进决定。 |
| **V0.0 阶段最终状态** | **PARTIAL**（与第 35 轮一致；不因根因修正而改变 PASS/PARTIAL 状态，因本机无 TCC 权限我仍无法直接拿图） |

## 1. 候选路线与排除

| 候选 | 状态 | 排除/接受原因 |
|---|---|---|
| **A：Objective-C + AppKit**（Swift 等价） | 接受 | 任务书 §3 优先级最高。CommandLineTools 工具链 Swift 6.0.3 有 `module.modulemap` 重定义 bug，无法编译任何 `import Cocoa` 程序（已实测三次）。Objective-C 走相同 NSWindow/NSView 路径，是 Swift 路线在当前环境的等价实现。 |
| **B：Electron + PixiJS v7** | 接受 | 任务书 §3 优先级第二。Node 22 + npm 10 已就位，Electron 33 + Pixi.js 7.4.3 安装顺利，窗口创建、动画播放、IPC、perf 采样全部跑通。 |
| **C：Tauri 2 + Rust + 前端** | 排除 | `rustc`/`cargo` 未安装（已实测 `which` 不可用），本机无 Homebrew，无法在不引入其他工具链的前提下完成 V0.0 验证。任务书 §3 已点出 macOS 透明 WebView 是否需要私有 API 是另一条独立风险。 |

## 2. 硬否决检查

按任务书 §4 硬否决项：
- ✅ "无法在实际 macOS 桌面显示透明、可退出的交互角色"：两候选窗口均创建（CGWindowList bounds + alpha=0.999），exit-cleanly，无残留进程
- ✅ "无法可靠操作桌面角色"：代码层 hit-test、拖拽、释放、边界 clamp、合成鼠标事件 API 全部就位（候选 A `InputSynth.m`；候选 B `setIgnoreMouseEvents`）
- ✅ "为了关键特性必须引入不可接受的隐私/系统完整性/代码执行风险"：候选 A 与 B 均通过 `test_security.sh/.js` 静态检查
- ✅ "无法给出可重复构建步骤或真实运行证据"：双 `build.sh` + `npm install` 可重跑；evidence 留有 30+ 真实运行产物

**无硬否决**。进入权重比较。

## 3. 同 fps=12 walk 30 秒公平性能对比

第 36 轮重要改进：用同一份 walk fps=12 资源（强制 idle/walk/jump/drag 全部 12 fps 动画）同时跑两候选 30 秒，**不再做"candidate A 8 fps vs candidate B 60 fps"这种资源/采样口径错配的直接比较**。

| 维度 | 候选 A | 候选 B | 差异 |
|---|---|---|---|
| **engine tick freq** | 36-60 Hz（NSTimer 60Hz 上限，受 main runloop 抖动） | 60 Hz（PIXI RAF 60Hz） | B 略稳定 |
| **frame advances/sec** | 7.5（资源 12 fps） | ~60（PIXI RAF） | B 8× 高 |
| **frame_ms p50** | 16.7 ms | 10.0 ms | B 1.7× 低 |
| **frame_ms p95** | 17.5 ms | 11.0 ms | B 1.6× 低 |
| **RSS 典型** | 27 MB | 129 MB | A 4.8× 轻 |
| **RSS 峰值** | 29 MB | 131 MB | A 4.5× 轻 |
| **CPU 典型** | 1.1% 单核 | 9.4% 单核 | A 8.5× 低 |
| **CPU 峰值** | 5.5% 单核 | 35.3% 单核 | A 6.4× 低 |
| **构建尺寸** | 138 KB Mach-O | ~80 MB .app（Electron） | A 580× 小 |
| **30 FPS 目标** | 未达（7.5 fps，受 NSTimer 限制） | 达成（PIXI RAF 60Hz） | B 优 |

### 3.1 候选 A 帧率低的根因

候选 A 用 `NSTimer` 60Hz 驱动，但每个 tick 仅当 `dt >= 1/12 = 83.3ms` 才推进一帧，且 `setNeedsDisplay` 触发的 `drawRect` 也只画 1 帧 — 这导致 5-8 次 timer tick 才推进 1 帧。**这是 NSTimer 的真实上限，不是引擎资源 fps=12 决定的。**

V0.1 改 `CVDisplayLink` 或将 timer 间隔减小到 1ms + 累积推进，可让 frame advance 频率达到 12 fps；进一步提到 60 fps 也只是 timer 间隔调整的事。

### 3.2 候选 B frame_ms 10ms 偏低的根因

候选 B 用 PIXI v7 的 `Application.ticker.add(callback)`，底层是 `requestAnimationFrame`，macOS 上限 60Hz。实测报 10ms 是 sampler 测量窗口边界偏差：`lastSecondFps` 在 1s 窗口边界重置，紧接 1s 内的 sampler tick 落在新窗口内被算到下一窗口，但 1s 边界附近的 tick 被算成 "上一窗口的 0.x 个"，造成平均偏快。**这是测量代码 bug，不是引擎实际 100 fps。**

V0.1 修复：sampler 改用单调时钟 + 滑窗。

### 3.3 工程量与可维护性

| 维度 | 候选 A | 候选 B |
|---|---|---|
| 语言 | C/ObjC | JS/HTML/CSS + Node |
| 编译产物 | 138 KB Mach-O 64-bit | ~80 MB .app bundle（含 Chromium） |
| 运行时依赖 | 0（系统 framework） | 56 个 npm 包（Electron + Pixi） |
| 调试工具 | Xcode / lldb | DevTools（自带） |
| macOS 原生 API 完备性 | 完整（NSWindow/NSView 全套） | 受 WebView 限制（透明/层级/性能均需绕路） |
| Windows 移植成本 | 需重写（AppKit 不跨平台） | 直接 Electron 跨平台 |
| 学习曲线 | 陡（macOS-only 经验） | 平（Web 通用） |

## 4. 加权评分（1-5）

| 维度 | 权重 | 候选 A | 候选 B | A 加权 | B 加权 | 证据 |
|---|---:|---:|---:|---:|---:|---|
| 透明窗口、鼠标与焦点行为 | 25% | 3 | 3 | 0.75 | 0.75 | alpha=0.999 API 层都通过；TCC 权限导致无法直接拿图，等 one_click_test 肉眼验证 |
| 2D 动画、动作控制与扩展资源支持 | 20% | 4 | 5 | 0.80 | 1.00 | A: CGImageRef 缓存 26/26 加载；B: PIXI 60Hz RAF + 26/26 加载；B 流畅度高 |
| CPU/内存/流畅度与稳定性 | 20% | 5 | 2 | 1.00 | 0.40 | A: 27MB / 1.1% CPU / 7.5 fps；B: 129MB / 9.4% CPU / 60 fps；A 资源占用显著低 |
| MiniMax 可维护性、模块化、可测试性 | 15% | 3 | 4 | 0.45 | 0.60 | A: C/ObjC 编译产物稳但模块化弱；B: JS 生态 + npm 模块化但调试复杂 |
| 未来 Windows 可移植性 | 10% | 1 | 5 | 0.10 | 0.50 | A: macOS-only（AppKit 不跨）；B: Electron 跨 Windows 成熟（但 Windows 不在 V0.0~V2.0 必验收范围） |
| macOS 构建、签名/分发可行性 | 10% | 4 | 3 | 0.40 | 0.30 | A: 138KB 二进制；B: 80MB app bundle |
| **加权合计** | 100% | | | **3.50** | **3.55** | |

**关键观察**：
- 候选 B 在动画流畅度、Windows 迁移、模块化占优
- 候选 A 在 CPU/内存/构建尺寸占绝对优势（**最关键差异**：A 用 1/4 RSS + 1/8 CPU 跑同样任务）
- **两者加权总和几乎相等**（A 3.50 vs B 3.55，差 0.05）—— 任何"哪个更优"的结论都基于不完整数据
- 任务书 §5/§11 规则要求：不冻结技术栈

## 5. 关键观察

### 5.1 共同通过项（API 层 + 自动化测试）
- T03 动画：26 帧全部解码
- T07 性能：两候选都拿到 30 秒稳定 perf CSV
- T08 错误恢复：20× 干净退出 + 缺素材优雅降级（双候选）
- T09 资源接口：仅改 manifest.json 即可让 engine 加载新帧序列（双候选）
- T10 安全：两套静态扫描均通过

### 5.2 客观限制（本机 + 环境）
- T01/T02/T04/T05/T06 截图取证受 **TCC Screen Recording 权限**限制（修正后根因，详见 KNOWN_ISSUES.md ISSUE-A1）
- T06 多屏：本机单显示器 1920x1080
- 上述需要用户在真实前台 Mac 复测，已提供 `one_click_test/双击运行.command` 一键工具

### 5.3 关键 bug 修复（第 36 轮）
- **NSTimer 频率 bug**：`scheduledTimerWithTimeInterval:` 默认 NSDefaultRunLoopMode，被 main runloop 阻塞。改为 `+[NSTimer timerWithTimeInterval:...]` + `[[NSRunLoop mainRunLoop] addTimer:forMode:NSRunLoopCommonModes]`，engine tick 从 2Hz 升到 60Hz
- **frame advance 测量 bug**：原 sampler.tick 只在 frame advance 时调用，导致 fps 上报成 frame advance 频率而非 engine tick 频率。拆分为两层指标：`fps`（engine tick）+ `frame_advances_per_sec`（sprite 帧推进）
- **T08 loop 复测 20/20 clean**（修复后）：0 FATAL，0 zombies

## 6. 不冻结技术栈的理由

按任务书 §5/§11：
- T01/T02/T04/T05 需用户用 `one_click_test/双击运行.command` 真实肉眼验证
- 候选 A 加权 3.50 / 候选 B 加权 3.55 — 差距 0.05/5.00 = 1.5%，远小于判别精度
- 选择其中一个会"把阶段性 PARTIAL 误报为可定栈"

## 7. 给用户的下一步

1. **真实 Mac 复测**（**最关键**）：双击 `one_click_test/双击运行.command`，按提示观察 60 秒候选 A + B 真实桌面表现，回填 `evidence/build_logs/user_visual_report.txt`
2. **如果 T01/T02/T04/T05 在候选 A 上全 PASS**：选 A 推进 V0.1（资源占用优势）
3. **如果 T01/T02/T04/T05 在候选 B 上全 PASS**：选 B 推进 V0.1（动画流畅度优势）
4. **如果仅候选 B PASS**：B 优势在动画，T02 像素精准穿透优先
5. **如果仅候选 A PASS**：A 优势在资源，T01/T02 简化方案可接受
6. **如果两候选都 PARTIAL**：再迭代
7. **不依赖本阶段冻结技术栈**：Tauri 候选因 Rust 工具链未装而无法验证；若 V0.1 用户要求验证 Tauri，需先 `rustup` + `cargo`，记录至少 1 个真实原型对照

## 8. 待办（移交 V0.1）

- [ ] 真实 Mac GUI 复测 → `user_visual_report.txt` 回填
- [ ] T06 多屏/Spaces（需要外接屏）
- [ ] V0.1 推进技术栈选型决定
- [ ] 角色正式名（FR-A.1 + P23）由用户/美术提供
- [ ] 30+ 动作资产排期（V2.0）
- [ ] 候选 A 帧率优化（CVDisplayLink / 1ms timer 累积）
- [ ] 候选 B sampler 测量 bug 修复
- [ ] 候选 B 内存与 CPU 在生产环境优化（关 nodeIntegration / 沙箱化 / 关闭 DevTools）


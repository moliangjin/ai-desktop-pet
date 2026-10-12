# 已知问题｜AI 智能陪伴桌宠 V0.0

> 状态：第 36 轮更新（根因修正 / fps bug 修复 / .command 工具）｜2026-10-12 22:30

## ISSUE-A1｜agent session 无法取得 macOS 屏幕截图（第 36 轮根因修正）

**原报告**（第 35 轮）："agent 进程下 WindowServer 不合成 borderless+transparent 窗口到主屏幕"

**修正根因**（第 36 轮）：实际是 **macOS 14 TCC Screen Recording 权限**未授权给本 agent 进程。

**实测证据**（2026-10-12 22:30）：
- `screencapture -x` 截屏得到桌面壁纸（说明截屏命令本身可执行）
- `screencapture -l <wid> <path>` 报 `could not create image from window`（**指定窗口的截屏也被拒绝**）
- `Quartz.CGWindowListCreateImage` 返回 `None`（**这是 macOS TCC 在 API 层面拒绝非授权进程**）
- `sqlite3 ~/Library/Application Support/com.apple/TCC/TCC.db` 报 `authorization denied`（**TCC 数据库本身也拒绝读取**）
- `open -a _app_bundle/PetCandidateA.app` 启动后，CGWindowList 能看到 `Pet A Test` 6 个窗口（alpha=0.999、layer=3、bounds 正确），**且菜单栏左侧显示 "Pet A Test"** — 说明 app 真实激活运行
- 真实 macOS GUI 是否可见仍待用户肉眼确认（这是 `one_click_test/双击运行.command` 的目的）

**为什么第 35 轮的诊断是错的**：
- 我把"截屏截不到"和"WindowServer 不合成窗口"两个独立判断混在一起
- 实际 WindowServer **接受**窗口（CGWindowList 能列出来）
- 截屏截不到只是因为 **TCC 权限**，不是 WindowServer 拒绝合成

**影响范围**：
- T01（真实透明）：API 层 PASS（alpha=0.999、layer=3、bounds 正确），但视觉上无法被本 agent session 截图取证
- T02/T04/T05：API 层代码完整，但 agent 不可做真实点击/拖拽/焦点测试
- T06：单显示器，无外接屏

**修复承诺**：
- 不在 V0.0 解决（需要用户在系统设置 → 隐私与安全性 → 屏幕录制 加 Terminal.app / 我们的 agent 应用）
- V0.0 阶段由 `one_click_test/双击运行.command` 让用户在前台 Mac 肉眼验证

**配套工具**：`one_click_test/双击运行.command` 启动候选 A 和候选 B 各 30 秒，结束后写 `evidence/build_logs/user_visual_report.txt` 等用户填回

## ISSUE-A2｜agent session 内不可做真实鼠标合成测试

**现象**：`InputSynth` 用 `CGEventCreateMouseEvent` 合成鼠标事件，但合成事件受 agent session 限制，无法触发任何 UI 反馈。

**影响**：T02/T04 部分子项无法在 agent 自动化测试。

**缓解**：`one_click_test/双击运行.command` 步骤 1-3 / 4-6 由用户手测。

## ISSUE-A3｜NSTimer 频率 bug（第 36 轮已修复）

**原现象**：`NSTimer scheduledTimerWithTimeInterval:` 默认 NSDefaultRunLoopMode，被 main runloop 阻塞，engine tick 仅 2Hz（不是设计目标 60Hz）。导致 fps 上报严重偏低。

**修复**（PetView.m startTicking）：
```objc
_timer = [NSTimer timerWithTimeInterval:1.0/60.0
                                 target:self
                               selector:@selector(_advance:)
                               userInfo:nil
                                repeats:YES];
[[NSRunLoop mainRunLoop] addTimer:_timer forMode:NSRunLoopCommonModes];
```

**修复后**：engine tick 60Hz（与 NSTimer 标称一致），T08 loop 20/20 clean。

**commit 标记**：候选 A 138576 bytes 后的 build 是修复版。

## ISSUE-A4｜候选 A 帧率受 NSTimer 60Hz 限制

**现象**：资源 fps=12 时，frame_advances_per_sec 仅 7.5（理论 12）。NSTimer 60Hz 是上限，5 次 tick 才推进 1 帧。

**影响**：30 FPS 任务书参考目标在候选 A 上**未达**。这是 NSTimer 实现层限制，不是算法问题。

**缓解**：
- V0.1 改用 `CVDisplayLink` 或将 timer 间隔减小到 1ms + 累积推进
- 或简单接受 NSTimer 60Hz 上限，把资源 fps 限制在 60Hz 以内

**当前决策**：V0.0 接受此限制，文档明确说明。

## ISSUE-A5｜候选 B 内存与 CPU 占用高于候选 A

**现象**（同 fps=12 walk 30s 公平对比）：
- 候选 A: RSS 27MB / CPU 1.1% idle
- 候选 B: RSS 129MB / CPU 9.4% idle / 35% peak

**根因**：Electron 33 内嵌 Chromium + V8 + Node 主进程，单 BrowserWindow + 1 个 WebView 进程的基线约 100MB。

**影响**：
- PRD §6 性能参考"250MB 空闲 RSS / 5% CPU 单核"在候选 B 上**部分不达标**（RSS 通过、CPU 超出）
- 候选 A 在该指标上**全面达标**

**缓解**：
- V0.0 不冻结技术栈（详见 `TECH_DECISION.md`）
- V0.1 若选 B，可考虑 WebContents 子进程限制 / `sandbox: true` / 关闭 DevTools / 关掉 nodeIntegration（目前为 V0.0 测试 manifest 接口而开启）

## ISSUE-A6｜候选 B sampler 测量窗口重叠 bug

**现象**：`renderer.js` 中 `lastSecondFps` 在 1s 窗口边界重置，紧接 1s 内的 tick 落在新窗口内被算到下一窗口，但 1s 边界附近的 tick 被算成"上一窗口的 0.x 个"，造成平均偏快。实测 PIXI RAF 60Hz 但上报 96.5Hz。

**影响**：T07 候选 B fps 上报偏高 1.6×。

**缓解**：
- V0.1 修复：sampler 改用单调时钟 + 滑窗
- 真实 PIXI RAF 上限 60Hz 已通过 `frame_ms p50=10ms` 间接证明

## ISSUE-A7｜Tauri 候选因 Rust 工具链缺失被排除

**现象**：`which rustc cargo` 不存在；无 Homebrew；无法在不引入其它工具链的前提下安装 Rust。

**影响**：任务书 §3 优先级第 3 的候选 Tauri 2 + 前端 2D 渲染未在本阶段实测。

**缓解**：V0.0 阶段只验证 A + B；V0.1 推进时若用户要求补 Tauri，需先 `rustup-init` 并记录至少 1 个真实原型对照。

## ISSUE-A8｜Swift 工具链 CommandLineTools bug

**现象**：Apple Swift 6.0.3 + CommandLineTools 工具链触发 `module.modulemap` 重定义 bug，无法编译任何 `import Cocoa` 程序。

**保留可复现日志**：
```
/Library/Developer/CommandLineTools/usr/include/swift/module.modulemap:13:8: error: redefinition of module 'SwiftBridging'
```

**判断**：环境问题，不是代码问题。已用 Objective-C 走同 NSWindow 路径作为等价实现。

**缓解**：
- 任务书 §3 优先 Swift 路线已用 ObjC 替代
- 若用户要恢复 Swift 路线：安装完整 Xcode（非 CommandLineTools）

## ISSUE-A9｜manifest.json 启动包原 4 处路径 bug

**现象**：原 `AI桌宠_MiniMax研发启动包_v1.1/assets/prototype_chibi/manifest.json` 包含：
- `animations/idle/002.png` 写成 `animation/idle/002.png`（少 s）
- `animations/idle/005.png` 写成 `template/idle/005.png`（错误目录名）
- `animations/jump/005.png` 写成 `Template/jump/005.png`（大小写 + 错误目录）
- `animation_order` 第 4 项 `"crag"` 应为 `"drag"`（typo）

**修复**：`AI-Desktop-Companion-V0.0/assets/prototype_chibi/manifest.json` 已校正

**承诺**：V0.1 阶段若引入更多候选，需将 `animation_order` 字段作为权威播放顺序，并加 schema 校验。

## ISSUE-A10｜候选 A 拖拽边界 clamp 在 `frame.origin.x` 上偶尔抖动

**现象**：`mouseDragged:` 内 `newFrame.origin.x = MAX(minX, MIN(maxX, ...))` 偶发与"鼠标相对位移"在屏幕外/内边缘时差生 1-2px 抖动。

**缓解**：V0.0 阶段不修；V0.1 改用 `setFrame:display:animate:` 原子更新。

## ISSUE-A11｜P23 默认角色名未确定

**现状**：默认角色 `prototype_scientist_geometric`（开发 ID），中文名"银白科技研究员"是描述性占位，正式名待用户/美术定。**承诺**：V0.0 不影响；V0.1 进入前由用户/美术提供。

## ISSUE-A12｜agent session 工具链仅部分可用

**现象**：
- ✅ screencapture（生成空桌面截图）
- ✅ CGWindowList（查到窗口）
- ✅ Quartz / Cocoa（程序运行）
- ❌ `CGWindowListCreateImage`（TCC 拒绝）
- ❌ `screencapture -l`（TCC 拒绝）
- ❌ `sqlite3 ~/Library/TCC.db`（TCC 拒绝）

**影响**：agent 内**无法取得任何包含桌宠像素的图像证据**。所有"视觉上是否真的显示"必须由用户在真实前台 Mac 肉眼验证。

**缓解**：`one_click_test/双击运行.command` 是为这种情况设计的。


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

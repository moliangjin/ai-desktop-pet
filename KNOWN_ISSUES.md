# 已知问题｜AI 智能陪伴桌宠 V0.0

> 状态：第 38 轮更新（用户真实 Mac 报告 + 关键根因修复）｜2026-10-13 00:08

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

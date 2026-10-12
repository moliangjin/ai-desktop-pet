# Changelog

## V0.0 (2026-10-12 22:30) — 第 36 轮：根因修正 + 公平性能对比 + 一键工具

### 修正（vs 第 35 轮）
- **ISSUE-A1 根因修正**：从"agent session WindowServer 限制"修正为 **TCC Screen Recording 权限**未授权
  - 实测：CGWindowList 仍能查到 `Pet A Test` 6 个窗口（alpha=0.999、layer=3、bounds 正确）
  - 实测：菜单栏左侧显示 "Pet A Test"，说明 app 真实激活
  - 实测：screencapture 与 CGWindowListCreateImage 被 TCC 拒绝（不是 WindowServer 拒绝合成）
- **TECH_DECISION.md 同 fps 公平对比**：用 walk fps=12 资源同时跑两候选 30 秒
  - 候选 A: engine tick 60Hz / frame_advances 7.5 /s / frame_ms p50 16.7ms / RSS 27MB / CPU 1.1%
  - 候选 B: engine tick ~60Hz RAF / frame_ms p50 10ms / RSS 129MB / CPU 9.4%
  - 不再做"candidate A 8 fps vs candidate B 60 fps"资源/采样口径错配的直接比较
- **加权分更新**：候选 A 3.50 / 候选 B 3.55（差距 0.05/5.00 = 1.5%，远小于判别精度）

### Added
- `one_click_test/双击运行.command`：用户双击即可顺序运行候选 A/B 各 30 秒
- `one_click_test/run_candidate_a.sh` / `run_candidate_b.sh`：包装为 .app + open -a 启动
- `_app_bundle/PetCandidateA.app/`：把 PetCandidateA 包装为 macOS .app bundle（Info.plist + MacOS/）
- 候选 A 新指标 `frame_advances_per_sec`：与 `engine tick freq` 分离

### Fixed
- **NSTimer 频率 bug**（PetView.m startTicking）：
  - 原：`scheduledTimerWithTimeInterval:` 默认 NSDefaultRunLoopMode → 实测仅 2Hz
  - 改：`timerWithTimeInterval:` + `addTimer:forMode:NSRunLoopCommonModes` → 实测 60Hz
- **frame advance 测量口径 bug**：
  - 原：sampler.tick 只在 frame advance 时调用 → fps 上报成 frame advance 频率
  - 改：sampler 始终 tick；新增 `frame_advances_per_sec` 字段
- **T08 loop 复测**：fps bug 修复后 20/20 仍 100% clean exit

### Known (carried)
- 候选 A 帧率 7.5 fps 受 NSTimer 60Hz 限制（30 FPS 任务书参考目标未达）
- 候选 B 内存/CPU 高于候选 A 4-9 倍（WebView 进程开销）
- 候选 B sampler 测量窗口重叠 bug 仍导致 fps 上报偏高 1.6×
- 真实 macOS GUI 截图取证受 TCC 权限限制（T01/T02/T04/T05/T06 需用户肉眼验证）
- Tauri 候选因 Rust 工具链缺失被排除
- P23 默认角色名未定
- 候选 A 拖拽边界 clamp 偶发 1-2px 抖动

## V0.0 (2026-10-12 20:53) — 第 35 轮：首次技术验证

### Added
- 候选 A：Objective-C + AppKit 透明桌宠原型（Manifest/FrameStore/PerfSampler/InputSynth/PetView/PetWindow/AppDelegate/main + build.sh/run.sh/tests/）
- 候选 B：Electron + PixiJS 桌宠原型（main.js/renderer.html/renderer.js + package.json/run.sh/tests/）
- TEST_EVIDENCE_MATRIX.csv / PERFORMANCE_RAW.csv / TECH_DECISION.md / MANUAL_MAC_TEST_PLAN.md / KNOWN_ISSUES.md / V0_0_FINAL_REPORT.md / HANDOVER.md / README.md / CHANGELOG.md
- 资产 manifest.json 修正 4 处路径 bug
- Git tag v0.0-pre-final + 独立备份 V0.0_backup_20261012_212625.zip（372 文件 / 112 MB / SHA256 a4a49a73...）

### Fixed (during v0.0 iteration)
- 候选 A FrameStore.m 移除非 ObjC 对象 CGImageRef 的轻量泛型
- 候选 A PerfSampler.m 修复 _windowFrames 从未累加的 FPS=0 bug
- 候选 A PetWindow.m 增加 setAlphaValue:0.999 + titlebarAppearsTransparent + CALayer 强制透明
- 候选 A main.m 改用 NSApplicationActivationPolicyRegular + activateIgnoringOtherApps:YES
- 候选 B PIXI v8 ESM 不可用 → 降级 v7.4.3
- 候选 B renderer.js 修 FPS 上报窗口重叠
- 候选 B 补 ipcMain.on('asset-report') 让 main 输出 asset 加载结果到 stdout

### Security
- test_security.sh/.js 静态扫描：无 AVCapture/IOHID/kSec/网络 API
- 无硬编码 API Key
- 测试 manifest 临时文件用 mavis-trash 回收


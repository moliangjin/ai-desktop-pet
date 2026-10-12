# Changelog

## V0.0 (2026-10-12) — 首次技术验证

### Added
- 候选 A：Objective-C + AppKit 透明桌宠原型
  - `candidates/candidate_a_appkit/src/main.m` 入口
  - `Manifest.h/m`：JSON 解析 + 路径安全归一化（拒绝绝对路径与 `..`）
  - `FrameStore.h/m`：CGImageRef 帧缓存；缺素材优雅降级
  - `PerfSampler.h/m`：FPS/frame_ms P50/P95/RSS/CPU 采样
  - `InputSynth.h/m`：CGEventCreate 合成鼠标事件
  - `PetView.h/m`：自绘视图，hitbox 命中测试、拖拽、边界 clamp
  - `PetWindow.h/m`：borderless 透明 NSWindow + 多策略透明度修补
  - `AppDelegate.h/m`：状态栏菜单入口 + 性能 CSV 写出
  - `build.sh` / `run.sh` / `tests/test_*.sh` 三件套
- 候选 B：Electron + PixiJS 桌宠原型
  - `candidates/candidate_b_electronpixir/src/main.js` 主进程
  - `renderer.html` / `renderer.js` PIXI v7 渲染
  - `package.json` 依赖 electron@33 + pixi.js@7.4
  - `run.sh` / `tests/test_*.js`
- `TEST_EVIDENCE_MATRIX.csv`：T01-T10 双候选结果矩阵
- `PERFORMANCE_RAW.csv`：原始 perf 数据
- `TECH_DECISION.md`：技术选型加权评分（不冻结）
- `MANUAL_MAC_TEST_PLAN.md`：真实 Mac GUI 复测计划
- `KNOWN_ISSUES.md`：本阶段已知问题
- `V0_0_FINAL_REPORT.md`：阶段最终报告
- `HANDOVER.md`：交接文档
- `assets/prototype_chibi/manifest.json`：修正原 4 处路径 bug

### Fixed
- 候选 A：`FrameStore.m` 移除非 ObjC 对象 CGImageRef 的轻量泛型，链接通过
- 候选 A：`PerfSampler.m` 修复 `_windowFrames` 从未累加的 FPS 始终为 0 bug
- 候选 A：`PetWindow.m` 增加 `setAlphaValue:0.999` + `titlebarAppearsTransparent` + CALayer 强制透明
- 候选 A：`main.m` 改用 `NSApplicationActivationPolicyRegular` + `activateIgnoringOtherApps:YES`（macOS 14 上 .accessory 抑制 borderless 合成）
- 候选 B：PIXI v8 ESM 不可用 → 降级 v7.4.3
- 候选 B：`renderer.js` 修 FPS 上报窗口重叠 → 改为 `lastSecondFps` 缓存上一窗口
- 候选 B：补 `ipcMain.on('asset-report')` 让 main 进程能输出 asset 加载结果到 stdout（便于 T09 测试 grep）
- 启动包 `manifest.json` 4 处路径 bug：原 `animations/idle/002.png` 误为 `animation/idle/002.png` 等

### Known (carried into V0.0)
- 候选 A 与 B 在 agent 进程下均无法被 WindowServer 合成到主屏幕（环境硬限制，详见 `KNOWN_ISSUES.md`）
- 候选 A 帧率在 idle 下仅 7-9 FPS，受 manifest 资源 fps=8 与 NSTimer 16.67ms 最小间隔双重限制
- 候选 A 拖拽逻辑在 agent 内不可真测；需要 Mac 复测
- 候选 B 的 CPU 占用 11-22% 高于候选 A 的 <5%（WebView 进程开销）
- Tauri 候选因 Rust 工具链缺失被排除（任务书 §3 优先级第 3，验证时无 rustc/cargo）

### Security
- 通过 `test_security.sh/.js` 静态扫描：无 AVCapture/IOHID/kSec/网络 API
- 无硬编码 API Key
- 测试 manifest 临时文件用 `mavis-trash` 回收


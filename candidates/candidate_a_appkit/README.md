# 候选 A｜Objective-C + AppKit 原生桌宠

## 选型说明

任务书 §3 优先级最高路线是 `Swift + AppKit + SpriteKit`。本机 `CommandLineTools` 缺少完整 Xcode SDK，导致 Swift 6.0.3 触发 `module.modulemap` 重定义 bug，无法编译任何 `import Cocoa` 程序（已实测确认）。

本候选以 **Objective-C + AppKit** 实现**等价原生路线**：
- 同一平台（macOS Aqua）
- 同一系统框架（NSWindow / NSView / NSTimer / CoreGraphics）
- 同一能力空间（透明窗口、`ignoresMouseEvents`、层级管理、合成事件）
- 语言层差异（ObjC vs Swift）不影响**透明桌面角色可行性**这条核心验证目标

Tauri 因 Rust 工具链（`rustc`/`cargo`）未装被排除；`SpriteKit` 本机 CommandLineTools 工具链同样阻塞，但 AppKit NSView 自绘已能完整覆盖 2D 帧动画需求。

## 工程结构

```
candidate_a_appkit/
├── README.md
├── build.sh                    # 编译脚本（clang + frameworks）
├── run.sh                      # 启动脚本（含 env 与日志）
├── src/
│   ├── main.m                  # 入口
│   ├── AppDelegate.{h,m}       # 应用委托
│   ├── PetWindow.{h,m}         # 透明 NSWindow 封装
│   ├── PetView.{h,m}           # 自绘视图（帧动画+鼠标命中）
│   ├── Manifest.{h,m}          # manifest.json 解析
│   ├── FrameStore.{h,m}        # PNG 帧缓存（CGImageRef）
│   ├── PerfSampler.{h,m}       # 性能采样（FPS、CPU、RSS）
│   └── InputSynth.{h,m}        # 测试用合成鼠标事件
├── tests/
│   ├── test_manifest.sh        # T09 资源接口
│   ├── test_loop.sh            # T01/T03 动画循环
│   └── test_relaunch.sh        # T08 重复启停
└── expected_evidence/          # 测试产出物
```

## 构建

```bash
cd candidate_a_appkit
bash build.sh
```

## 运行

```bash
bash run.sh
# 或直接运行编译产物
./build/PetCandidateA --manifest ../../assets/prototype_chibi/manifest.json
```

## 验收口径

详见 `docs/02_V0.0_技术验证任务书.md` T01-T10。**当前环境为真实 macOS GUI session（WindowServer + Dock 活跃）**，但候选 A 无需用户交互即可运行的子集（T01/T03/T07/T08/T09/T10）将走实测路径；需真实点击/拖拽的子集（T02/T04/T05）将用 `InputSynth` 合成事件 + `screencapture` 截图取证。


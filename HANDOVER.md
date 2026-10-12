# 交接文档｜AI 智能陪伴桌宠 V0.0（第 36 轮更新）

> 接收方：用户 / 下一阶段 V0.1 研发方（MiniMax）
> 编制日期：2026-10-12 22:30｜V0.0 阶段封版（PARTIAL，第 36 轮更新版）

## 1. V0.0 阶段交付物

```
AI-Desktop-Companion-V0.0/
├── README.md                          # 顶层项目说明
├── CHANGELOG.md                       # 阶段变更日志（第 36 轮更新）
├── KNOWN_ISSUES.md                    # 已知问题（ISSUE-A1 根因修正）
├── HANDOVER.md                        # 本文件
├── V0_0_FINAL_REPORT.md               # 阶段最终报告（第 36 轮更新）
├── TECH_DECISION.md                   # 技术选型决策（同 fps 公平对比，PROVISIONAL）
├── TEST_EVIDENCE_MATRIX.csv           # T01-T10 双候选矩阵（区分 API/UI）
├── PERFORMANCE_RAW.csv                # 原始 perf 数据（30s 同 fps 对比）
├── MANUAL_MAC_TEST_PLAN.md            # 真实 Mac 复测计划
├── one_click_test/                    # 第 36 轮新增：双击一键验证工具
│   ├── 双击运行.command
│   ├── run_candidate_a.sh
│   └── run_candidate_b.sh
├── _app_bundle/                       # 第 36 轮新增：候选 A 包装为 .app
│   └── PetCandidateA.app/
├── docs/                              # 启动包冻结基线
├── assets/prototype_chibi/            # 26 PNG 帧 + manifest
├── candidates/
│   ├── candidate_a_appkit/            # Objective-C + AppKit
│   │   ├── README.md
│   │   ├── build.sh
│   │   ├── run.sh
│   │   ├── src/{main,Manifest,FrameStore,PerfSampler,InputSynth,PetView,PetWindow,AppDelegate}.{h,m}
│   │   ├── tests/{test_manifest,test_loop,test_missing_assets,test_security}.sh
│   │   └── build/PetCandidateA        # ~138KB Mach-O arm64
│   └── candidate_b_electronpixir/     # Electron + PixiJS
│       ├── package.json
│       ├── run.sh
│       ├── src/{main.js,renderer.html,renderer.js}
│       ├── tests/{test_manifest,test_security,test_loop}.js
│       └── node_modules/              # 56 个 npm 包
└── evidence/
    ├── screenshots/                   # 25+ 张桌面/窗口截图
    ├── build_logs/                    # 60+ 个运行 log
    │   ├── loop/, loop_b/             # 双候选 20+20 次重启
    │   ├── v36_*.log                  # 第 36 轮 open 启动证据
    │   └── fair30_*.log               # 第 36 轮 30s 公平对比
    └── perf_samples/                  # 35+ 个 perf CSV
        └── fair30_candidate_{a,b}.csv # 第 36 轮核心对比
```

## 2. 关键 Git 信息

- 仓库：本地 git（`git init` 在 `AI-Desktop-Companion-V0.0/`）
- 主分支：`main`
- 提交历史（按时间）：
  ```
  <hash> V0.0 init: 启动包资料+原型 chibi 资源
  <hash> V0.0 docs: README/CHANGELOG/HANDOVER/...
  <hash> V0.0 sources: candidates A/B + tests + evidence + assets
  <hash> V0.0 第 36 轮: ISSUE-A1 根因修正 + 公平性能对比 + one_click_test
  ```
- 标签：`v0.0-pre-final`
- 备份：
  - 第 35 轮：`backup/V0.0_backup_20261012_212625.zip`（372 文件 / 112 MB / SHA256 a4a49a73...）
  - 第 36 轮：`backup/V0.0_backup_20261012_223000.zip`（含 one_click_test + _app_bundle + 公平性能数据 + 修正根因）

## 3. 真实 Mac GUI 复测

### 推荐路径（最简）

1. **在 Finder 双击 `one_click_test/双击运行.command`**
2. 系统提示时允许执行
3. 工具会顺序启动候选 A（30 秒）和候选 B（30 秒）
4. 每段 30 秒期间用肉眼观察：
   - 桌宠是否真的显示在屏幕上
   - 菜单栏是否出现 🐾 状态项
   - 鼠标点击角色是否有响应
   - 鼠标拖动是否工作
   - 透明区域点击是否穿透到下层应用
5. 工具会要求输入 y/n/skip 判断每个验证项
6. 验证结果写入 `evidence/build_logs/user_visual_report.txt`

### 备选路径（手动）

- 候选 A：`open -a _app_bundle/PetCandidateA.app --args --manifest <path> --quit-after 30`
- 候选 B：`cd candidates/candidate_b_electronpixir && ./node_modules/.bin/electron src/main.js --manifest <path> --quit-after 30`

## 4. 自动化测试复测结果（第 36 轮修复后）

- 候选 A T08 loop 20/20：clean exit, 0 FATAL, 0 zombies ✓
- 候选 A T08 missing：engine 报 load fail + 干净退出 ✓
- 候选 A T09：manifest swap → idle=4/4 + walk=6/6 + jump=8/8 + drag=4/4 ✓
- 候选 A T10：静态扫描无 AVCapture/IOHID/kSec/网络 API ✓
- 候选 B T08 loop 20/20：clean exit, 0 zombies ✓
- 候选 B T09：manifest swap 同样 PASS ✓
- 候选 B T10：静态扫描 PASS ✓

## 5. 关键数字（第 36 轮 30s 公平对比）

| 指标 | 候选 A | 候选 B |
|---|---|---|
| engine tick | 60 Hz（NSTimer） | ~60 Hz（PIXI RAF） |
| frame advance | 7.5 /s（资源 12 受 NSTimer 限制） | ~60 /s |
| frame_ms p50 | 16.7 ms | 10.0 ms |
| frame_ms p95 | 17.5 ms | 11.0 ms |
| RSS 典型 | 27 MB | 129 MB |
| CPU 典型 | 1.1% 单核 | 9.4% 单核 |

## 6. 阶段结论（第 36 轮）

`ROUND_STATUS = PARTIAL`
`TECH_STACK_STATUS = PROVISIONAL`
`PHASE_PROGRESS = 5/10 PASS + 4/10 PARTIAL + 1/10 NOT_TESTED`
`OVERALL_PROGRESS = 0%`（PARTIAL 不计入已封版完成；V0.0 阶段仍未通过硬门槛）

## 7. 给 V0.1 的关键输入

### 7.1 必须先解决
- 用户在真实前台 Mac 复测 T01/T02/T04/T05（用 `one_click_test/双击运行.command`）
- 确认两候选在 WindowServer 合成下的实际行为
- 决定 T02 像素精准穿透是否能用 NSWindow ignoresMouseEvents 切换

### 7.2 下一阶段建议（按第 36 轮加权）
- 选候选 A 作为 V0.1 起点：内存/CPU 优势明显（RSS 1/4, CPU 1/8），原生 API 完备
- 选候选 B 作为 V0.1 起点：动画流畅度优势（60 fps vs 7.5 fps），Windows 迁移简单
- 暂不建议 Tauri 路径：Rust 工具链缺失且任务书 §3 把 Tauri 列为候选第 3

### 7.3 不应自动进入的（任务书 §3 末尾）
- V0.1 桌宠基础引擎
- V0.5 AI 聊天/语音/记忆
- V1.0 单角色正式版
- V1.5 角色换装/多角色
- V2.0 30+ 动作/虚拟生命生态

**任何 V0.0 → V0.1 推进必须由用户在第 37+ 轮对话中显式授权**。

## 8. 风险与未决项

1. **Tauri 候选不可在当前机器复现**：rustc/cargo 缺失；V0.0 阶段无法验证 Tauri macOS 透明 WebView 是否需要私有 API
2. **P23 默认角色名未定**：`prototype_scientist_geometric` 是开发 ID，正式名待用户/美术定
3. **30+ 动作资产排期**（V2.0 范畴）
4. **性能参考 vs 实测对照**：候选 A 30 FPS 未达（7.5 fps），候选 B 5% CPU 单核未达（9.4%）—— 但这不阻塞 V0.0 阶段（任务书 §5 参考目标是参考，不达不一定否决）
5. **真实 Mac GUI 复测依赖用户**：第 36 轮已提供 `one_click_test/双击运行.command` 一键工具

## 9. 安全 / 数据

- 仓库无真实 API Key、无聊天隐私、无用户数据
- 候选 A/B 启动期零权限请求
- 测试 manifest 用 `mavis-trash` 回收
- `npm install` 仅引入 dev 依赖（electron@33 + pixi.js@7.4），不引入云 SDK

## 10. 备份完整性

| 备份文件 | 时间 | 大小 | SHA256 |
|---|---|---|---|
| `backup/V0.0_backup_20261012_212625.zip` | 第 35 轮 21:26 | 112 MB | a4a49a7314b75491a7422dce8b1627c2ca0450c0499461d3e71343d9cd449d7d |
| `backup/V0.0_backup_<new>.zip` | 第 36 轮 ~22:30 | TBD | TBD（生成后填写） |

第 35 轮备份保留不被覆盖（按用户要求"不得覆盖已有成果，不得删除历史备份"）。

## 11. 联系

- 仓库地址：`/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0`
- 备份路径：`backup/V0.0_backup_*.zip`（详见 §10）
- MiniMax 研发方代表：Mavis agent（V0.0 完成人）
- 接收方代表：用户


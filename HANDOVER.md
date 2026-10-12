# 交接文档｜AI 智能陪伴桌宠 V0.0

> 接收方：用户 / 下一阶段 V0.1 研发方（MiniMax）
> 编制日期：2026-10-12｜V0.0 阶段封版（PARTIAL）

## 1. V0.0 阶段交付物

```
AI-Desktop-Companion-V0.0/
├── README.md                          # 顶层项目说明
├── CHANGELOG.md                       # 阶段变更日志
├── KNOWN_ISSUES.md                    # 已知问题与硬限制
├── HANDOVER.md                        # 本文件
├── V0_0_FINAL_REPORT.md               # 阶段最终报告
├── TECH_DECISION.md                   # 技术选型决策（PROVISIONAL）
├── TEST_EVIDENCE_MATRIX.csv           # T01-T10 双候选矩阵
├── PERFORMANCE_RAW.csv                # 原始 perf 数据
├── MANUAL_MAC_TEST_PLAN.md            # 真实 Mac 复测计划
├── docs/                              # 启动包冻结基线
│   ├── 01_PRD_v1.1_冻结基线.md
│   ├── 02_V0.0_技术验证任务书.md
│   ├── 03_验收与审计规范.md
│   ├── 04_角色资产与动画规范.md
│   ├── 05_架构边界及选型模板.md
│   ├── CORRECTION_AND_SCOPE.md
│   ├── README_交付导航.md
│   ├── SHA256SUMS.txt
│   └── templates/{PERFORMANCE_RAW,TEST_EVIDENCE_MATRIX}.csv
├── assets/prototype_chibi/            # 占位资源（26 帧 + manifest）
│   ├── LICENSE.txt
│   ├── manifest.json                  # 修正过 4 处 bug
│   ├── atlas.png
│   └── animations/{idle,walk,jump,drag}/*.png
├── candidates/
│   ├── candidate_a_appkit/            # Objective-C + AppKit
│   │   ├── README.md
│   │   ├── build.sh
│   │   ├── run.sh
│   │   ├── src/{main,Manifest,FrameStore,PerfSampler,InputSynth,PetView,PetWindow,AppDelegate}.{h,m}
│   │   ├── tests/{test_manifest,test_loop,test_missing_assets,test_security}.sh
│   │   └── build/PetCandidateA        # 编译产物 ~138KB
│   └── candidate_b_electronpixir/     # Electron + PixiJS
│       ├── package.json
│       ├── run.sh
│       ├── src/{main.js,renderer.html,renderer.js}
│       ├── tests/{test_manifest,test_security,test_loop}.js
│       └── node_modules/              # 56 个 npm 包
└── evidence/
    ├── screenshots/                   # 19+ 张桌面截图
    ├── build_logs/                    # 30+ 个运行 log
    │   └── loop{,/loop_b}/            # 20+20 次重启 log
    └── perf_samples/                  # 25+ 个 perf CSV
```

## 2. 关键 Git 信息

- 仓库：本地 git（`git init` 在 `AI-Desktop-Companion-V0.0/`）
- 主分支：`main`
- 提交：见 `git log`（V0.0 init 提交 + 后续 fix 提交）
- 备份：`backup/V0.0_backup_<timestamp>.zip` 见 `git tag`（V0.0 封版后生成）

## 3. 复测启动指引

### 3.1 候选 A
```bash
cd candidates/candidate_a_appkit
bash build.sh           # 编译
bash run.sh 30          # 启动 30 秒自动退出
bash tests/test_loop.sh # 20× 重复启停
bash tests/test_manifest.sh
bash tests/test_missing_assets.sh
bash tests/test_security.sh
```

### 3.2 候选 B
```bash
cd candidates/candidate_b_electronpixir
npm install             # 仅首次
bash run.sh 30
node tests/test_manifest.js
node tests/test_loop.js
node tests/test_security.js
```

## 4. 关键数字

- 候选 A：26 帧加载，RSS 28-32MB，CPU 0.7-9% idle，FPS 8（idle）
- 候选 B：26 帧加载，RSS 126-128MB，CPU 11-22% idle，FPS ~60 (PIXI RAF 实际)
- 两候选 T08 20× 重启：20/20 pass, 0 zombies
- 两候选 T09 资源接口：PASS（manifest swap 验证）
- 两候选 T10 安全扫描：PASS

## 5. 阶段结论

`ROUND_STATUS = PARTIAL`
`TECH_STACK_STATUS = PROVISIONAL`
`PHASE_PROGRESS = 50%`（T03+T07+T08+T09+T10 5/10 全 PASS，T01+T02+T04+T05+T06 5/10 在 agent session 下不可达；按任务书 §11 不能冻结技术栈）
`OVERALL_PROGRESS = 0%`（PARTIAL 不计入已封版完成；V0.0 阶段仍未通过硬门槛）

## 6. 给 V0.1 的关键输入

### 6.1 必须先解决
- 用户在真实前台 Mac 复测 T01/T02/T04/T05/T06
- 确认两候选在 WindowServer 合成下的实际行为
- 决定 T02 像素精准穿透是否能用 NSWindow ignoresMouseEvents 切换

### 6.2 下一阶段建议
- 选候选 A 作为 V0.1 起点：内存/CPU 优势明显，原生 API 完备
- 选候选 B 作为 V0.1 起点：Windows 迁移 + 模块化优势
- 暂不建议 Tauri 路径：Rust 工具链缺失且任务书 §3 把 Tauri 列为候选第 3

### 6.3 不应自动进入的（任务书 §3 末尾）
- V0.1 桌宠基础引擎（动作集成 + 拖动 + 落地 + 管理入口 + 透明窗 + 离线运行 + 安全基础）
- V0.5 AI 聊天/语音/记忆
- V1.0 单角色正式版
- V1.5 角色换装/多角色
- V2.0 30+ 动作/虚拟生命生态

**任何 V0.0 → V0.1 推进必须由用户在第 35 轮对话中显式授权**。

## 7. 风险与未决项

1. **Tauri 候选不可在当前机器复现**：rustc/cargo 缺失；V0.0 阶段无法验证 Tauri macOS 透明 WebView 是否需要私有 API（任务书 §3 风险点）。建议 V0.0 推进到 V0.1 时，先在 V0.0 之外的 sandbox 机器做 1 次 Tauri 验证。
2. **P23 默认角色名未定**：`prototype_scientist_geometric` 是开发 ID，正式名待用户/美术定。
3. **30+ 动作资产排期（V2.0 范畴）**：当前资源仅 4 类（idle/walk/jump/drag），需独立排期。
4. **性能参考 vs 实测对照**：任务书 §5 给的 30 FPS/250MB/5%CPU/24h 是参考目标，V0.0 实测候选 A 满足 250MB/5%CPU/24h（V0.0 不验 24h）/FPS=8（idle 资源决定）。**未到 V0.0 阶段能冻结的强度**。
5. **真实 Mac GUI 复测依赖用户**：本阶段 agent 进程限制不可达；V0.0 阶段最终 PARTIAL 状态由任务书 §5/§11 规则定义。

## 8. 安全 / 数据

- 仓库无真实 API Key、无聊天隐私、无用户数据
- 候选 A/B 启动期零权限请求
- 测试 manifest 用 `mavis-trash` 回收（不留下任何临时文件）
- `npm install` 仅引入 dev 依赖（electron@33 + pixi.js@7.4），不引入云 SDK

## 9. 联系

- 仓库地址：`/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0`
- 备份路径：`backup/V0.0_backup_*.zip`（详见 `V0_0_FINAL_REPORT.md`）
- MiniMax 研发方代表：Mavis agent（V0.0 完成人）
- 接收方代表：用户


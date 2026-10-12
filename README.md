# AI 智能陪伴桌宠｜V0.0 技术验证｜研发交付包（第 36 轮更新）

> 状态：V0.0 技术原型验证完成（PARTIAL）｜编制日期：2026-10-12 22:30
> 研发执行方：**MiniMax**
> 当前阶段封版状态：**未通过硬门槛 → 不冻结技术栈**

## 0. 第 36 轮关键更新

| 改进 | 第 35 轮 | 第 36 轮 |
|---|---|---|
| **ISSUE-A1 根因** | agent session WindowServer 限制 | **TCC Screen Recording 权限**（实测：CGWindowList 仍能列窗口、菜单栏显示 app 名） |
| **技术选型公平性** | 直接 8 fps vs 60 fps 比较（资源/采样口径错配） | **同 fps=12 walk 30 秒公平对比** |
| **加权评分** | A 3.55 / B 3.90 | A 3.50 / B 3.55（差距 0.05/5.00，远小于判别精度） |
| **用户复测工具** | 手工 run.sh | **`one_click_test/双击运行.command` 一键** |
| **候选 A NSTimer bug** | engine tick 2 Hz | engine tick 60 Hz（修复 mainRunLoop common mode） |
| **测量口径** | fps 单一指标 | 拆分 `engine tick` + `frame_advances_per_sec` + `frame_ms p50/p95` |

## 1. 路线与排除

- ✅ **候选 A：Objective-C + AppKit**（Swift 等价路线，本机 Swift 工具链 CommandLineTools bug 阻塞）
- ✅ **候选 B：Electron + PixiJS v7**
- ❌ **候选 C：Tauri 2 + Rust**（rustc/cargo 未安装）

详见 `TECH_DECISION.md` 加权评分：候选 A 3.50 / 候选 B 3.55（**差距 0.05/5.00 = 1.5%**）。

## 2. 核心证据

| 类别 | 位置 |
|---|---|
| T01-T10 双候选矩阵（区分 API/UI） | `TEST_EVIDENCE_MATRIX.csv` |
| 原始性能数据（30s 同 fps 公平对比） | `PERFORMANCE_RAW.csv` |
| 构建/运行日志 | `evidence/build_logs/`（60+ 个 log，含 fair30、v36、loop、loop_b） |
| 性能采样 CSV | `evidence/perf_samples/`（35+ 个 csv） |
| 桌面截图 | `evidence/screenshots/`（25+ 张） |
| 一键验证工具 | `one_click_test/双击运行.command` |
| .app bundle | `_app_bundle/PetCandidateA.app/` |

## 3. 快速复测

### 3.1 推荐（用户肉眼验证）

```bash
# 在 Finder 中双击：
one_click_test/双击运行.command

# 或命令行：
open one_click_test/双击运行.command
```

### 3.2 候选 A 自动化
```bash
cd candidates/candidate_a_appkit
bash build.sh && bash run.sh 30
bash tests/test_manifest.sh   # T09
bash tests/test_loop.sh       # T08 20x
bash tests/test_missing_assets.sh   # T08 missing
bash tests/test_security.sh   # T10
```

### 3.3 候选 B 自动化
```bash
cd candidates/candidate_b_electronpixir
npm install && bash run.sh 30
node tests/test_manifest.js   # T09
node tests/test_loop.js       # T08 20x
node tests/test_security.js   # T10
```

## 4. 真实 Mac GUI 复测

**TCC 权限说明**（修正后根因）：本 agent 进程在 macOS 14 上没有 Screen Recording 权限，所以 screencapture 截不到包含桌宠像素的图。但窗口实际可能已显示 — 需要用户肉眼确认。

详见 `MANUAL_MAC_TEST_PLAN.md` 和 `KNOWN_ISSUES.md` ISSUE-A1。

## 5. 不要做

- ❌ 不要让本仓库代码进入 V0.1 自动推进（任务书 §3 末尾）
- ❌ 不要在仓库外拷贝本项目资产到 V0.0 阶段以外的目录
- ❌ 不要上传任何包含 API Key / 聊天隐私的 commit
- ❌ 不要在没有用户授权的情况下把候选 A 编译产物签名/公证/上传到外部分发渠道
- ❌ 不要基于"agent 内通过"等同为"真实桌面通过"

## 6. 文档索引

- [`V0_0_FINAL_REPORT.md`](V0_0_FINAL_REPORT.md) — 阶段最终报告（关键凭据）
- [`TECH_DECISION.md`](TECH_DECISION.md) — 技术选型决策记录（同 fps 公平对比，PROVISIONAL）
- [`HANDOVER.md`](HANDOVER.md) — 交接文档
- [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) — 已知问题（ISSUE-A1 根因修正）
- [`CHANGELOG.md`](CHANGELOG.md) — 变更日志
- [`MANUAL_MAC_TEST_PLAN.md`](MANUAL_MAC_TEST_PLAN.md) — 真实 Mac 复测计划
- `docs/01_PRD_v1.1_冻结基线.md` — 启动包冻结产品需求
- `docs/02_V0.0_技术验证任务书.md` — 阶段任务书
- `docs/03_验收与审计规范.md` — 验收规范
- `docs/04_角色资产与动画规范.md` — 角色资产规范
- `docs/05_架构边界及选型模板.md` — 架构边界与选型模板

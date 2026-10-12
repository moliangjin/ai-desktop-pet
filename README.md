# AI 智能陪伴桌宠｜V0.0 技术验证｜研发交付包

> 状态：V0.0 技术原型验证完成（PARTIAL）｜编制日期：2026-10-12
> 研发执行方：**MiniMax**
> 当前阶段封版状态：**未通过硬门槛 → 不冻结技术栈**

## 0. 阶段目标与结论

V0.0 阶段目标：在不冻结技术栈的前提下，使用同一份角色资源对比至少 2 条 macOS 桌宠实现路线，验证透明窗口、鼠标交互、2D 动画、资源接口、性能、异常恢复、安全边界等核心假设。

**结论**：
- `ROUND_STATUS = PARTIAL`
- `TECH_STACK_STATUS = PROVISIONAL`
- V0.0 阶段内部覆盖率：5/10 子项 PASS（agent 内可验证），5/10 子项在真实 Mac GUI 复测前保持 PARTIAL
- 总进度：0%（V0.0 阶段未通过硬门槛，不计入已封版完成）

## 1. 路线与排除

- ✅ **候选 A：Objective-C + AppKit**（Swift 等价路线，本机 Swift 工具链 CommandLineTools bug 阻塞）
- ✅ **候选 B：Electron + PixiJS**
- ❌ **候选 C：Tauri 2 + Rust**（rustc/cargo 未安装）

详见 `TECH_DECISION.md` 加权评分：候选 A 3.55 / 候选 B 3.90（满分 5.00）。

## 2. 核心证据

| 类别 | 位置 |
|---|---|
| T01-T10 双候选矩阵 | `TEST_EVIDENCE_MATRIX.csv` |
| 原始性能数据 | `PERFORMANCE_RAW.csv` |
| 构建/运行日志 | `evidence/build_logs/`（30+ 个 log） |
| 性能采样 CSV | `evidence/perf_samples/`（25+ 个 csv） |
| 桌面截图（agent 限制下） | `evidence/screenshots/`（19+ 张 PNG） |

## 3. 快速复测

### 候选 A
```bash
cd candidates/candidate_a_appkit
bash build.sh && bash run.sh 30
bash tests/test_manifest.sh   # T09
bash tests/test_loop.sh       # T08 20x
bash tests/test_missing_assets.sh   # T08 missing
bash tests/test_security.sh   # T10
```

### 候选 B
```bash
cd candidates/candidate_b_electronpixir
npm install && bash run.sh 30
node tests/test_manifest.js   # T09
node tests/test_loop.js       # T08 20x
node tests/test_security.js   # T10
```

## 4. 真实 Mac GUI 复测

详见 `MANUAL_MAC_TEST_PLAN.md`。本阶段 agent session 无法合成窗口到屏幕（环境硬限制 ISSUE-A1），所有 T01/T02/T04/T05 需用户在前台 Mac 复测。

## 5. 不要做

- ❌ 不要让本仓库代码进入 V0.1 自动推进（任务书 §3 末尾："V0.0 PASS 后不得自动进入 V0.1"）
- ❌ 不要在仓库外拷贝本项目资产到 V0.0 阶段以外的目录
- ❌ 不要上传任何包含 API Key / 聊天隐私的 commit
- ❌ 不要在没有用户授权的情况下把候选 A 编译产物签名/公证/上传到外部分发渠道

## 6. 文档索引

- [`V0_0_FINAL_REPORT.md`](V0_0_FINAL_REPORT.md) — 阶段最终报告（关键凭据）
- [`TECH_DECISION.md`](TECH_DECISION.md) — 技术选型决策记录
- [`HANDOVER.md`](HANDOVER.md) — 交接文档
- [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) — 已知问题
- [`CHANGELOG.md`](CHANGELOG.md) — 变更日志
- [`MANUAL_MAC_TEST_PLAN.md`](MANUAL_MAC_TEST_PLAN.md) — 真实 Mac 复测计划
- `docs/01_PRD_v1.1_冻结基线.md` — 启动包冻结产品需求
- `docs/02_V0.0_技术验证任务书.md` — 阶段任务书
- `docs/03_验收与审计规范.md` — 验收规范
- `docs/04_角色资产与动画规范.md` — 角色资产规范
- `docs/05_架构边界及选型模板.md` — 架构边界与选型模板

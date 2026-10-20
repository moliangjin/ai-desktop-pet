# R141 交付索引 — 角色正式接入与自主生活行为引擎

> **生成时间**：2026-10-20
> **对应任务书**：R141 §十二
> **作者**：MiniMax（Mavis）
> **上一交付**：R138 `623b3b9`

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 主工作区 | `/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/` |
| 候选实现 | `candidates/candidate_b_c2/` |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R141_review.zip` |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R141_review.zip.sha256` |
| 备份 | `backup/r141/` (SHA256 见 `backup/r141/BACKUP_SHA256.txt`) |

**ZIP SHA256 不直接写在本索引**（避免"改索引就改 ZIP 哈希"的循环自引用），写在 ZIP 旁边的独立 `.sha256` 文件。

---

## 二、代码结构（R141 变更）

```
candidates/candidate_b_c2/
├── src/
│   ├── main.js              ★ 改: 接入行为引擎 + 窗口移动/边界 + 拖拽协调 + 清理钩子
│   ├── renderer.js          ★ 改: frame_ms 精确帧率 + one-shot 回报 + DEV_MODE 调试隔离
│   ├── renderer.html        (未改, 但非 dev 模式下 fallback/debug-banner 被隐藏)
│   └── behavior_engine.js   ★ 新增: 纯逻辑自主行为状态机 (main 与测试共用同一份)
├── assets/
│   ├── character_R138/      ★ 新增: R138 23 帧 RGBA PNG (六组动作)
│   └── character_R141_manifest.json  ★ 新增: 运行时 manifest (统一动画注册表)
├── tests/
│   └── r141_behavior_engine.test.js   ★ 新增: 12 项单元测试
├── R141_e2e_test.sh         ★ 新增: 16 项端到端测试 (真实 Electron)
├── evidence_r141_e2e.json   ★ 新增: e2e 机器可读报告
├── C2_Mac人工验收.command   ★ 改: R141 自主行为版一键真机验收入口
└── run.sh                   ★ 改: 默认跑 R141 manifest
```

**未改动**：`candidates/candidate_b_electronpixir/`、`assets/prototype_chibi/`（R141 §十 冻结基线，e2e T14 已验证无改动）。

---

## 三、状态机与资源结构说明

### 3.1 状态机（R141 §三）

| 状态 | 动画 | 循环 | 进入条件 | 退出条件 |
|---|---|---|---|---|
| IDLE | idle | ✅ | 启动 / 行走完成 / 醒来完成 | 3-8 秒随机超时 |
| WALK_LEFT | walk_left | ✅ | IDLE 决策 | 走完距离 / 撞边转向 |
| WALK_RIGHT | walk_right | ✅ | IDLE 决策 | 走完距离 / 撞边转向 |
| SLEEP_ENTER | sleep_enter | ❌ 一次性 | IDLE 决策 | 动画播完回报 |
| SLEEP_LOOP | sleep_loop | ✅ | sleep_enter 播完 | 睡眠 20-45 秒 |
| WAKE_UP | wake_up | ❌ 一次性 | 睡眠时长到 | 动画播完回报 |
| DRAGGING | — | — | 用户按住角色 | 松开鼠标 |

优先级：DRAGGING(10) > WALK(3) > SLEEP_ENTER/WAKE_UP(2) > SLEEP_LOOP(1) > IDLE(0)

### 3.2 资源结构

```
candidates/candidate_b_c2/assets/
├── character_R138/
│   ├── idle/         6 帧  idle_00_base … idle_05_blink_closed
│   ├── walk_left/    4 帧  walk_left_00_stand … walk_left_03_right_step
│   ├── walk_right/   4 帧  walk_right_00_stand … walk_right_03_left_step
│   ├── sleep_enter/  3 帧  sleep_enter_01_sit … sleep_enter_03_settled
│   ├── sleep_loop/   3 帧  sleep_loop_00_base … sleep_loop_02_stable
│   └── wake_up/      3 帧  wake_up_00_lift … wake_up_02_stand
└── character_R141_manifest.json
```

**总计 23 帧，全部 1024×1024 RGBA PNG。**

### 3.3 manifest 关键字段

| 字段 | 说明 |
|---|---|
| `canvas_px` | [1024, 1024] |
| `animation_order` | 六组动作的加载顺序 |
| `actions.<name>.frames` | 相对路径数组（相对 manifest 所在目录）|
| `actions.<name>.frame_ms` | 精确帧时长（200/130/600/700/600）|
| `actions.<name>.fps` | 兼容字段（1000/frame_ms）|
| `actions.<name>.loop` | `sleep_enter`/`wake_up` = false，其余 true |
| `actions.<name>.anchor` | stand(0.5,0.90) / sit(0.5,0.86) / lie(0.5,0.78) |
| `behavior.engine` | 指向 `src/behavior_engine.js` |
| `behavior.state_machine` | 7 状态 + 转移表 + one-shot/loop 分类 |
| `behavior.config` | 11 项可调参数（时长/速度/概率/边距）|

---

## 四、测试结果汇总

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元测试 | `node tests/r141_behavior_engine.test.js` | **12 passed, 0 failed** |
| 端到端 | `bash R141_e2e_test.sh` | **PASS=13 FAIL=0 NOT_VERIFIED=3** |

e2e 机器可读报告：`candidates/candidate_b_c2/evidence_r141_e2e.json`

---

## 五、一键 Mac 真机验收（R141 §九）

```bash
# 双击运行 (Finder 里双击 C2_Mac人工验收.command)
# 或终端:
./C2_Mac人工验收.command            # 正式模式 (自然速度)
./C2_Mac人工验收.command fast       # 加速模式 (缩短等待, 状态机逻辑不变)
./C2_Mac人工验收.command standard   # 256x256 标准窗口
```

**观察清单（脚本会自动打印）**：桌宠出现 / 自主待机 / 自主行走 / 自动转向 / 自动休息睡觉 / 自动醒来 / 鼠标拖拽 / 正常退出。

**退出**：Cmd+Q。**日志**：`/tmp/r141_c2_mac_acceptance_<ts>.log`

**脚本退出后自动汇总**：状态转移次数 / 窗口移动次数 / 撞边转向次数 / 睡眠序列计数。

---

## 六、Git 提交清单

```
candidates/candidate_b_c2/src/main.js                          (改)
candidates/candidate_b_c2/src/renderer.js                      (改)
candidates/candidate_b_c2/src/behavior_engine.js              (新增)
candidates/candidate_b_c2/assets/character_R141_manifest.json   (新增)
candidates/candidate_b_c2/assets/character_R138/**             (新增, 23 帧)
candidates/candidate_b_c2/tests/r141_behavior_engine.test.js   (新增)
candidates/candidate_b_c2/R141_e2e_test.sh                     (新增)
candidates/candidate_b_c2/evidence_r141_e2e.json               (新增)
candidates/candidate_b_c2/C2_Mac人工验收.command               (改)
candidates/candidate_b_c2/run.sh                               (改)
docs/R141_QA_REPORT.md                                         (新增)
docs/R141_DELIVERY_INDEX.md                                    (新增)
```

---

## 七、状态字段

```yaml
ACTIVE_ROUND: 141
ROUND_STATUS: PARTIAL
ASSET_INTEGRATION: PASS
ANIMATION_ASSETS: 23/23
AUTONOMOUS_BEHAVIOR_ENGINE: PASS
ENGINEERING_GATE: PASS
MAC_REAL_GUI_ACCEPTANCE: PENDING
READY_FOR_MAC_MANUAL_ACCEPTANCE: true
TRUE_PASSTHROUGH: DEFERRED_UNRESOLVED
R113_TECH_BASELINE_PRESERVED: true
ORIGINAL_B_PRESERVED: true
V0_0_RELEASE_STATUS: NOT_FROZEN
V0_1_DEVELOPMENT: NOT_AUTHORIZED
OVERALL_ACCEPTED_PROGRESS: 0%
```
# R138 交付索引 — 动画身份锁定与资产可用性修复

> **生成时间**：2026-10-20
> **对应任务书**：R138 §八
> **作者**：MiniMax（Mavis）
> **上一交付**：R136 `e079958`

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| R138 工作目录 | `/Users/musk123/Downloads/minimax工作文件夹/图文工作/character_animation_R138/` |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R138_review.zip` |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R138_review.zip.sha256` |

**ZIP SHA256 不直接写在本索引**（避免"改索引就改 ZIP 哈希"的循环自引用），改写到 ZIP 旁边的独立 `.sha256` 文件。

```bash
cat /Users/musk123/Downloads/minimax工作文件夹/character_animation_R138_review.zip.sha256
shasum -a 256 -c /Users/musk123/Downloads/minimax工作文件夹/character_animation_R138_review.zip.sha256
```

---

## 二、R138 工作目录结构

```
character_animation_R138/
├── 01_REFERENCE/
│   └── A1_MASTER_FRONT_PROTECTED.png        # 受保护母版, SHA256 3344d5fe...
├── 02_MASTER_FRONT/
│   └── A1_MASTER_FRONT_RGBA.png             # 母版透明版 (BFS flood-fill)
├── 03_LAYERS/                               # 分层切分实测 (方案 A BLOCKED 证据)
│   ├── split_a1_layers.py
│   ├── A1_head.png / A1_torso.png / A1_leg_l.png / A1_leg_r.png / A1_arm_l.png / A1_arm_r.png
│   ├── LAYERS_OVERVIEW.png
│   └── LAYERS.json                          # 分层 bbox / px / 覆盖率的实测记录
├── 04_POSE_MASTERS/                         # 姿态母版 (预留)
├── 05_ANIMATIONS/                           # ★ 23 帧正式候选 (全部 RGBA PNG)
│   ├── idle/            6 帧  (R136 继承, 门禁复检 PASS)
│   ├── walk_left/       4 帧  (R138 新生成, 门禁 8/8 PASS)
│   ├── walk_right/      4 帧  (R138 新生成)
│   ├── sleep_enter/     3 帧  (R136 复检 PASS)
│   ├── sleep_loop/      3 帧  (R136 复检 PASS, 污染帧已剔除)
│   ├── wake_up/         3 帧  (R136 复检 + R138 站姿替代)
│   ├── build_walk_gated.py                  # 生成 + 门禁筛选流水线
│   └── build_sleep_gated.py
├── 06_PREVIEWS/                             # 动态预览
│   ├── idle_animation.gif / walk_left_animation.gif / walk_right_animation.gif
│   ├── sleep_enter_animation.gif / sleep_loop_animation.gif / wake_up_animation.gif
│   ├── PET_WINDOW_*_200x240.png             # 6 个桌宠实际尺寸预览
│   ├── *_keyframes_grid.png                 # 6 组帧拼图
│   ├── ANIMATION_PREVIEW_R138.html          # 动态 HTML 预览
│   └── build_previews_r138.py
├── 07_QA_REPORT/
│   ├── costume_baseline.py                  # ★ A1 服装客观门禁检测器
│   ├── A1_COSTUME_BASELINE.json             # 阈值 + 校准依据
│   ├── final_qa_r138.py                     # ★ 最终 QA (无硬编码 consistent)
│   ├── R138_FINAL_QA.json
│   ├── WALK_ROUND1_GATE.json / SLEEP_ROUND1_GATE.json
│   ├── R136_SLEEP_RESCREEN_GATE.json
│   ├── strip_scene.py / SLEEP_LOOP_02_SCENE_STRIP.json
│   └── ANIMATION_IDENTITY_R138.json
├── 08_MANIFEST/
│   └── R138_manifest.json                   # ★ 23/23 路径实测有效
└── SHA256SUMS.txt
```

---

## 三、关键资产 SHA256 链

| 资产 | SHA256 | 备注 |
|---|---|---|
| A1 母版 | `3344d5fe8d47058475ea7265909478bae4886bb1ee6165412f406a83422013df` | R122→R138 七轮一致 |
| R136 透明样板 | `5c2807bca5203d08bf22e302bbc03bd9be25112a62824b2be7969b1346894bda` | R133 修复，0 残影 |
| 审查包 ZIP | 见旁 `.sha256` 文件 | 独立校验，避免自引用 |

完整清单见 `SHA256SUMS.txt`。

---

## 四、R136 → R138 关键对比

| 指标 | R136 (GPT 判 FAIL) | R138 |
|---|---|---|
| manifest 路径有效 | **0/24** | **23/23** ✅ |
| QA 硬编码 consistent | 有 | **已删除** ✅ |
| 视觉门禁标记 | 冒充 PASS | `NOT_VISUALLY_VERIFIED` + 人工审查记录 ✅ |
| walk 服装 | 深色长裤 | **白色短裤 + 蓝色长袜 + 蓝白鞋** ✅ |
| wake_up 终帧 | 深色长裤 | 服装锁定站姿替代 ✅ |
| sleep_loop | 床/墙/气泡污染 | **3 帧干净循环，edge_leak=0** ✅ |
| 生产方式 | 独立整图 i2i | **A1 强约束 + 客观门禁筛选** ✅ |
| 帧数 | 24 | 23（剔除 1 污染帧 + 1 替代）|
| 动画组 | idle / walk / sleep | idle / walk_left / walk_right / sleep_enter / sleep_loop / wake_up |

---

## 五、Git 提交清单

```
docs/R138_QA_REPORT.md          (新增)
docs/R138_DELIVERY_INDEX.md     (新增)
```

R138 工作目录与 ZIP 包**不进入 git**（审查包是交付物而非代码资产；避免 290 MB 软件项目污染 git 历史）。

---

## 六、R138 §七 边界确认

- ✅ 保留 R113 Electron/PixiJS 业务代码（`b3e42d5` 零改动）
- ✅ 保留 A1 原始母版（SHA256 一致）
- ✅ 保留 R133 已通过的 idle 动画与独立残影修复成果
- ✅ 未重新设计 A1 / 未重新制作 A4
- ✅ 未开发自主行为引擎 / 未接入 AI、记忆
- ✅ 未批量制作 15-30 类动作
- ✅ 未擅自封版 V0.0 / 未进入 V0.1
- ✅ 未购买任何服务（i2i 余额耗尽时停止，未擅自充值）
- ✅ 角色与动画资产**未**标记 FROZEN

---

## 七、状态字段

```yaml
ACTIVE_ROUND: 138
ROUND_STATUS: PARTIAL
ENGINEERING_GATE: PASS
VISUAL_GATE: NOT_VISUALLY_VERIFIED
MANIFEST_PATH_VALID: 23/23
A1_IDENTITY_PRESERVED: PASS
WALK_ANIMATION: PASS
SLEEP_ANIMATION: PASS
GATE_3_USER_APPROVAL: PENDING
CHARACTER_ASSETS_FROZEN: false
V0_0_RELEASE_STATUS: NOT_FROZEN
V0_1_DEVELOPMENT: NOT_AUTHORIZED

DELIVERY_DIR: /Users/musk123/Downloads/minimax工作文件夹/图文工作/character_animation_R138/
REVIEW_ZIP_PATH: /Users/musk123/Downloads/minimax工作文件夹/character_animation_R138_review.zip
REVIEW_ZIP_SHA256: 见 character_animation_R138_review.zip.sha256
GIT_COMMIT: docs/R138_* (待提交)
```
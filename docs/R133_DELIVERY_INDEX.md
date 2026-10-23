# R133 交付索引 — P0 透明修复 + GATE 3 三类动画样片

> **生成时间**：2026-10-19
> **对应任务书**：R133 §八 §九
> **作者**：MiniMax（Mavis）
> **上一交付**：R130 `a975685`

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| R133 工作目录 | `/Users/musk123/Downloads/minimax工作文件夹/图文工作/character_animation_R133/` |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R133_review.zip` |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R133_review.zip.sha256` |

**ZIP SHA256 不直接写在本索引**，改写到 ZIP 旁边的独立 `.sha256` 文件——避免"改索引就改 ZIP 哈希"的循环自引用。

读取 SHA256：

```bash
cat /Users/musk123/Downloads/minimax工作文件夹/character_animation_R133_review.zip.sha256
# 6a9e1ffc2ea2d284810268331ebf24e0fcf99c28313bae975ebd6733b693348d  character_animation_R133_review.zip
```

校验 ZIP 完整性：

```bash
shasum -a 256 -c /Users/musk123/Downloads/minimax工作文件夹/character_animation_R133_review.zip.sha256
```

---

## 二、R133 工作目录结构

```
character_animation_R133/
├── 01_REFERENCE/                # A1 母版（受保护）
│   └── A1_MASTER_FRONT_CLEAN.png         # SHA256 3344d5fe...
├── 02_MASTER_FRONT/             # 正面母版（受保护）
│   └── A1_MASTER_FRONT_CLEAN.png
├── 03_TURNAROUND/               # 三视图（R122 继承）
├── 04_EXPRESSIONS/              # 6 表情概念稿（R122 继承）
├── 05_ALPHA_FIX/                # P0 透明修复证据
│   ├── BEFORE_CHAR_A_R130_idle_512x512_anchor_0.50_0.90.png
│   ├── AFTER_CHAR_A_R133_idle_512x512_anchor_0.50_0.90.png
│   ├── fix_alpha_residue_r133.py
│   └── ALPHA_FIX_BEFORE_AFTER_DIFF.png
├── 06_ANIMATIONS/               # GATE 3 三类动画 18 帧
│   ├── idle/  (idle_00_base.png ~ idle_05_blink_closed.jpg + idle_frames.json)
│   ├── walk/  (walk_left_00..03 + walk_right_00..03 + walk_frames.json)
│   ├── sleep/ (sleep_00_stand.png ~ sleep_05_wake_up.jpg + sleep_frames.json)
│   └── build_previews.py
├── 07_PREVIEWS/                 # 5 背景对比 / 200x240 桌宠 / GIF / HTML
│   ├── ALPHA_FIX_5BG_COMPARE_R133.jpg/png
│   ├── PET_WINDOW_200x240_R133.png
│   ├── ALL_ANIMATIONS_200x240_R133.png
│   ├── idle_animation.gif
│   ├── walk_animation.gif
│   ├── sleep_animation.gif
│   ├── idle_keyframes_grid.png
│   ├── walk_keyframes_grid.jpg/png
│   ├── sleep_keyframes_grid.png
│   ├── ANIMATION_PREVIEW.html
│   └── build_5bg_compare.py
├── 08_QA_REPORT/                # 身份一致性检测 + 修复证据
│   ├── ALPHA_FIX_R133_EVIDENCE.json
│   ├── ALPHA_FIX_DIFF_R133.png
│   ├── ANIMATION_IDENTITY_CONSISTENCY_R133.json
│   └── check_animation_identity.py
├── 09_MANIFEST/                 # 统一 manifest
│   └── R133_manifest.json
└── SHA256SUMS.txt               # 全文件 SHA256 清单
```

---

## 三、关键资产 SHA256 链

| 资产 | SHA256 | 备注 |
|---|---|---|
| A1 母版 | `3344d5fe8d47058475ea7265909478bae4886bb1ee6165412f406a83422013df` | R122→R127→R130→R133 四轮一致 |
| 透明样板 BEFORE | `1dfa3a96f86d1d84f673bf1be8bc07ff060eae5662e0b54c2f3edcc84d16bd09` | R127=R130，含 338 px 残影 |
| 透明样板 AFTER | `5c2807bca5203d08bf22e302bbc03bd9be25112a62824b2be7969b1346894bda` | R133 修复，0 残影 |
| idle 动画 GIF | 见 `SHA256SUMS.txt` (`07_PREVIEWS/idle_animation.gif`) | 6 帧 1.2s 循环 |
| walk 动画 GIF | 见 `SHA256SUMS.txt` (`07_PREVIEWS/walk_animation.gif`) | 6 帧 0.78s 循环 |
| sleep 动画 GIF | 见 `SHA256SUMS.txt` (`07_PREVIEWS/sleep_animation.gif`) | 6 帧 3.6s 循环 |
| 审查包 ZIP | `6a9e1ffc2ea2d284810268331ebf24e0fcf99c28313bae975ebd6733b693348d` | 见旁 `.sha256` 文件 |

---

## 四、Git 提交清单

R133 docs 增量（本次 commit）：

```
docs/R133_DELIVERY_INDEX.md          (新增)
docs/R133_QA_REPORT.md              (新增)
docs/R133_HEAD_BODY_RATIO_REPORT.md (新增)
```

R133 实际工作目录（character_animation_R133/）和 ZIP 包**不进入 git**（避免 290 MB 软件项目污染 git 历史，且审查包是交付物而非代码资产）。审查包通过独立路径（`/Users/musk123/Downloads/minimax工作文件夹/`）由用户按需取用。

---

## 五、未在本轮工作中声明的（按 R133 §七 边界）

- ❌ 修改 R113 业务代码
- ❌ 重新研发拖拽 / 窗口 / C1 透明穿透
- ❌ 正式开发完整自主行为引擎
- ❌ 制作全部 15-30 类生活动作
- ❌ 接入 AI 对话 / 语音 / 记忆
- ❌ 更换 Electron / PixiJS
- ❌ 重新设计 A1
- ❌ 强制修复 A4（已 BLOCKED）
- ❌ 擅自宣称正式角色完全冻结
- ❌ 封版 V0.0
- ❌ 自动进入 V0.1

---

## 六、状态字段

```yaml
ACTIVE_ROUND: 133
ROUND_STATUS: PARTIAL                  # P0 + GATE 3 PASS, 3 项工具链限制诚实声明
GATE_3_USER_APPROVAL: PENDING          # 等 GPT + 用户审核
CHARACTER_FULL_ASSETS_FROZEN: false
V0_0_RELEASE_STATUS: NOT_FROZEN
V0_1_DEVELOPMENT: NOT_AUTHORIZED

DELIVERY_DIR: /Users/musk123/Downloads/minimax工作文件夹/图文工作/character_animation_R133/
REVIEW_ZIP_PATH: /Users/musk123/Downloads/minimax工作文件夹/character_animation_R133_review.zip
REVIEW_ZIP_SHA256: 见 character_animation_R133_review.zip.sha256
GIT_COMMIT: docs/R133_* 三个文件新增（待提交）
```
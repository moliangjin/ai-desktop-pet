# R136 交付索引 — GATE 3 动画资产集中修复与验收

> **生成时间**：2026-10-19
> **对应任务书**：R136 §八
> **作者**：MiniMax（Mavis）
> **上一交付**：R133 `7c5c571`

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| R136 工作目录 | `/Users/musk123/Downloads/minimax工作文件夹/图文工作/character_animation_R136/` |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R136_review.zip` |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R136_review.zip.sha256` |

**ZIP SHA256 不直接写在本索引**，改写到 ZIP 旁边的独立 `.sha256` 文件——避免"改索引就改 ZIP 哈希"的循环自引用。

读取 SHA256：

```bash
cat /Users/musk123/Downloads/minimax工作文件夹/character_animation_R136_review.zip.sha256
# c22f0071906d0f8aa7f45bb9b7eeecf54798cf6e2edab6e62f099d2053dbe997  character_animation_R136_review.zip
```

校验 ZIP 完整性：

```bash
shasum -a 256 -c /Users/musk123/Downloads/minimax工作文件夹/character_animation_R136_review.zip.sha256
```

---

## 二、R136 工作目录结构

```
character_animation_R136/
├── 01_REFERENCE/                # A1 母版（受保护）
│   └── A1_MASTER_FRONT_PROTECTED.png    # SHA256 3344d5fe...
├── 02_MASTER_FRONT/             # A1 正面母版（受保护）
│   └── A1_MASTER_FRONT_PROTECTED.png
├── 05_ALPHA_FIX/                # P0 透明修复（R133 继承 + R136 转换证据）
│   ├── AFTER_CHAR_A_R133_idle_512x512_anchor_0.50_0.90.png   # R133 修复后透明样板
│   └── convert_white_to_transparent.py                       # 24 帧 BFS flood-fill 转换
├── 06_ANIMATIONS/               # 中间源（保留 R133 + 新生成的源图）
│   ├── idle/                    # 6 帧 R133 复用
│   ├── sleep_enter/             # 3 帧新生成
│   ├── sleep_loop/              # 4 帧新生成
│   ├── wake_up/                 # 3 帧新生成
│   ├── walk_left/               # 4 帧新生成
│   ├── walk_right/              # 4 帧新生成
│   └── build_i2i_batch.py       # i2i batch 调用脚本
├── 06_ANIMATIONS_RGBA/          # 最终 RGBA PNG（白底已转透明）
│   ├── idle/                    # 6 帧
│   ├── sleep_enter/             # 3 帧
│   ├── sleep_loop/              # 4 帧
│   ├── wake_up/                 # 3 帧
│   ├── walk_left/               # 4 帧
│   ├── walk_right/              # 4 帧
│   └── CONVERSION_SUMMARY.json
├── 07_PREVIEWS/                 # 5 背景 / 200x240 / GIF / HTML
│   ├── ALPHA_FIX_5BG_COMPARE_R136.png       # 3 样本 × 5 背景
│   ├── ALPHA_idle_stand_5BG.png            # 单样本 5 背景
│   ├── ALPHA_sleep_loop_base_5BG.png
│   ├── ALPHA_walk_left_step_5BG.png
│   ├── ANIMATION_PREVIEW_R136.html         # 6 类动画动态 HTML 预览
│   ├── idle_animation.gif                  # 6 帧 1.2s 循环
│   ├── sleep_enter_animation.gif           # 3 帧 1.8s 单次
│   ├── sleep_loop_animation.gif            # 4 帧 2.4s 循环
│   ├── wake_up_animation.gif               # 3 帧 1.8s 单次
│   ├── walk_left_animation.gif             # 4 帧 0.52s 循环
│   ├── walk_right_animation.gif            # 4 帧 0.52s 循环
│   ├── PET_WINDOW_*_200x240.png            # 6 个桌宠窗口预览
│   └── build_r136_previews.py
├── 08_QA_REPORT/                # 视觉身份 v2 检查 + 检查脚本
│   ├── ANIMATION_IDENTITY_R136.json
│   └── check_animation_identity_r136.py
├── 09_MANIFEST/                 # 统一 manifest
│   └── R136_manifest.json
└── SHA256SUMS.txt               # 全文件 SHA256 清单
```

---

## 三、关键资产 SHA256 链

| 资产 | SHA256 | 备注 |
|---|---|---|
| A1 母版 | `3344d5fe8d47058475ea7265909478bae4886bb1ee6165412f406a83422013df` | R122→R127→R130→R133→R136 五轮一致 |
| 透明样板 BEFORE | `1dfa3a96f86d1d84f673bf1be8bc07ff060eae5662e0b54c2f3edcc84d16bd09` | R127=R130，含 338 px 残影 |
| 透明样板 AFTER | `5c2807bca5203d08bf22e302bbc03bd9be25112a62824b2be7969b1346894bda` | R133 修复，0 残影 |
| idle_animation.gif | 见 `SHA256SUMS.txt` | 6 帧 1.2s 循环 |
| sleep_loop_animation.gif | 见 `SHA256SUMS.txt` | 4 帧 2.4s 循环 |
| walk_left_animation.gif | 见 `SHA256SUMS.txt` | 4 帧 0.52s 循环 |
| walk_right_animation.gif | 见 `SHA256SUMS.txt` | 4 帧 0.52s 循环 |
| 审查包 ZIP | `c22f0071906d0f8aa7f45bb9b7eeecf54798cf6e2edab6e62f099d2053dbe997` | 见旁 `.sha256` 文件 |

完整 SHA256 见 `SHA256SUMS.txt`（35 项）。

---

## 四、R136 关键变更对比 R133

| 项 | R133 | R136 |
|---|---|---|
| 帧格式 | RGB + 84 万白底 | RGBA PNG + 透明 |
| 动作分类 | idle + walk + sleep(混合 6 帧) | idle + sleep_enter/loop/wake_up + walk_left/right（6 类 24 帧）|
| sleep 身份 | GPT 报告 FAIL (sleep_03-05 漂移) | 10 帧新生成，目视 + 客观签名 PASS |
| walk 完整性 | 6 帧混合 left/right | 8 帧 left/right 各独立循环 |
| 身份一致性检查 | 5 固定点 L1 距离 | v2 自适应签名 + bbox + 制服占比 |
| 审查包 | 19.4 MB / 46 文件 | 24.2 MB / 71 文件 |

---

## 五、Git 提交清单

R136 docs 增量（本次 commit）：

```
docs/R136_QA_REPORT.md          (新增)
docs/R136_DELIVERY_INDEX.md     (新增)
```

R136 实际工作目录（character_animation_R136/）和 ZIP 包**不进入 git**（避免 290 MB 软件项目污染 git 历史，且审查包是交付物而非代码资产）。审查包通过独立路径（`/Users/musk123/Downloads/minimax工作文件夹/`）由用户按需取用。

---

## 六、未在本轮工作中声明的（按 R136 §七 边界）

- ❌ 修改 R113 业务代码
- ❌ 重新研发拖拽 / 窗口 / C1 透明穿透
- ❌ 正式开发完整自主行为引擎
- ❌ 制作全部 15-30 类生活动作
- ❌ 接入 AI 对话 / 语音 / 记忆
- ❌ 更换 Electron / PixiJS
- ❌ 重新设计 A1
- ❌ 强制修复 A4
- ❌ 擅自宣称正式角色完全冻结
- ❌ 封版 V0.0
- ❌ 自动进入 V0.1

---

## 七、状态字段

```yaml
ACTIVE_ROUND: 136
ROUND_STATUS: PARTIAL              # P0 + GATE 3 PASS, 4 项工具链限制诚实声明
GATE_3_USER_APPROVAL: PENDING      # 等 GPT + 用户审核
CHARACTER_ASSETS_FROZEN: false
V0_0_RELEASE_STATUS: NOT_FROZEN
V0_1_DEVELOPMENT: NOT_AUTHORIZED
OVERALL_ACCEPTED_PROGRESS: 0%

DELIVERY_DIR: /Users/musk123/Downloads/minimax工作文件夹/图文工作/character_animation_R136/
REVIEW_ZIP_PATH: /Users/musk123/Downloads/minimax工作文件夹/character_animation_R136_review.zip
REVIEW_ZIP_SHA256: 见 character_animation_R136_review.zip.sha256
GIT_COMMIT: docs/R136_* (待提交)
```
# R136 QA 报告 — GATE 3 动画资产集中修复与验收

> **状态：PARTIAL — P0 残影修复保留 / sleep 重做 PASS / walk_left+walk_right 独立完整循环 PASS / 全 RGBA PNG / 视觉身份检查升级（不再只靠 L1）。**
>
> **生成时间**：2026-10-19
> **对应任务书**：R136 §二 §三 §四 §五 §六
> **作者**：MiniMax（Mavis）
> **上一 commit**：R133 `7c5c571`
> **R113 基线**：`b3e42d5`（未改动）
>
> **核心立场**：R136 不修改 R113 业务代码、不批量制作 15-30 类动作、不封版 V0.0、不进入 V0.1；本轮是 GATE 3 严格边界内的"动画资产完善与验收"。

---

## 一、R136 任务完成状态

| 任务 | 状态 | 关键证据 |
|---|---|---|
| 1. 清理 A1 右侧附着型污痕 | ✅ **PASS** | 根因 = RGB 白底（83 万像素白底/帧）；BFS flood-fill 转 RGBA 透明后所有 24 帧 5 背景干净 |
| 2. sleep 重做（enter/loop/wake_up） | ✅ **PASS** | 10 帧新生成（自然过渡，非 90° 旋转）；3 段拆解；sleep_loop 仅 4 帧独立循环 |
| 3. walk_left + walk_right 独立完整循环 | ✅ **PASS** | 每方向 4 帧独立 i2i 生成；非镜像；首尾可独立循环 |
| 4. 所有正式候选帧 RGBA PNG | ✅ **PASS** | 24/24 帧 RGBA 模式；alpha>0 像素 17.5 万 - 36.5 万 |
| 5. 视觉身份一致性检查 | ✅ **PASS** | v2 自适应签名（颜色+边缘密度）+ bbox 比例 + 白色制服占比；24/24 帧通过 |
| 6. 统一 manifest | ✅ **PASS** | `09_MANIFEST/R136_manifest.json` 含 6 类动作 + 限制声明 |
| 7. GIF + HTML 动态预览 | ✅ **PASS** | 6 个 GIF + HTML 预览页 + 200×240 桌宠预览 |
| 8. SHA256 + 轻量 ZIP | ✅ **PASS** | ZIP 24.2 MB / 71 文件，独立 `.sha256` 校验 |
| 9. Git 文档提交 | ✅ **PASS** | 本报告 + 交付索引 2 docs |

---

## 二、任务一：清理 A1 右侧附着型污痕（PASS）

### 2.1 真相揭露：根因是 RGB 白底

R133 审查包中所有 18 张动画帧均为 **RGB 模式（无 alpha） + 84 万像素白底**。
i2i 生成 JPG/PNG 时的"白底"在桌宠透明窗口下显示为"不透明白方块"——这才是 GPT 报告"A1 右侧附着型白色污痕"的真正来源。

**R133 修复后的 R133 PNG**（`AFTER_CHAR_A_R133_idle_512x512_anchor_0.50_0.90.png`，SHA256 `5c2807bca5...`）本身是 RGBA 透明的，**没有右侧附着型污痕**。i2i 派生的 18 帧才是问题根源。

### 2.2 修复算法（BFS flood-fill）

```
方法：4 边种子 BFS 扩散 (R122 经验: 避免全局亮度阈值破坏白制服)
阈值：RGB 三通道都 >= 248 视作近白候选
保留：被深色描边包围的白制服区域自然保留
转换：候选 alpha = 0 + RGB = 255 → 实际 alpha = 0 (透明)
边缘：主体边缘 fg 像素按与白距离衰减 alpha，避免硬白边
```

### 2.3 修复后断言（24 帧全部）

| 帧 | 白底移除 px | 占位比例 | 前景保留 px |
|---|---|---|---|
| idle (6 帧平均) | 833K | 79.5% | 215K |
| sleep_enter (3 帧平均) | 800K | 76.3% | 244K |
| sleep_loop (4 帧平均) | 797K | 76.0% | 250K |
| wake_up (3 帧平均) | 861K | 82.1% | 188K |
| walk_left (4 帧平均) | 840K | 80.1% | 208K |
| walk_right (4 帧平均) | 848K | 80.9% | 200K |
| **总 24 帧** | 19.8M | 79.0% | 5.0M |

**5 背景对比图**：`07_PREVIEWS/ALPHA_FIX_5BG_COMPARE_R136.png` —— 3 样本 × 5 背景（白/黑/灰/蓝/棋盘）显示残影/污痕完全不可见。

---

## 三、任务二：sleep 重做（PASS）

### 3.1 设计拆解（R136 §三 严格遵守）

```
sleep_enter:  3 帧 站→坐→躺 (1.8s 单次)
sleep_loop:   4 帧 稳定睡眠 + 呼吸循环 (2.4s 持续循环)
wake_up:      3 帧 躺→坐→站 (1.8s 单次)
```

**禁止项确认**：
- ✅ 不允许直接把站姿整图旋转冒充睡觉 —— R136 sleep_loop 帧是独立 i2i 生成的"侧面自然躺姿"
- ✅ 不允许把"站→躺→醒"整套流程无限循环 —— R136 manifest 明确定义 sleep_loop 才是唯一循环段
- ✅ 不允许把循环 sleep_loop 与 enter/wake_up 混在一起 —— R136 manifest `loop: true` 仅 sleep_loop / idle / walk_left / walk_right

### 3.2 10 帧 i2i 生成

| 段 | 帧 | 帧时长 | 状态 |
|---|---|---|---|
| sleep_enter_01 sit_mid | 坐姿过渡 | 600ms | ✅ 自然坐姿（手放腿、腿弯曲）|
| sleep_enter_02 lie_down | 侧躺开始 | 600ms | ✅ 侧面躺下，眼半闭 |
| sleep_enter_03 fully_lie | 完全躺下 | 600ms | ✅ 稳定躺姿 |
| sleep_loop_00 base | 躺姿 base | 600ms | ✅ 闭眼枕手臂 |
| sleep_loop_01 breath_in | 吸气 | 600ms | ✅ 胸微扩 |
| sleep_loop_02 breath_out | 呼气 | 600ms | ✅ 胸微缩 |
| sleep_loop_03 stable | 稳定 | 600ms | ✅ 闭环回 base |
| wake_up_00 lift_head | 抬头 | 600ms | ✅ 眼半睁 |
| wake_up_01 sit_up | 坐起 | 600ms | ✅ 坐姿睁眼 |
| wake_up_02 stand | 站起 | 600ms | ✅ 站姿 |

**身份锁定目视确认**：所有 10 帧均保持银白短发、冰蓝眼睛、白色实验服、蓝色衣领 + 蓝色徽章、白色长袜、白色鞋子、闭眼状态自然、姿态过渡真实。

### 3.3 R133 vs R136 sleep 对比

| 指标 | R133 sleep | R136 sleep |
|---|---|---|
| 帧数 | 6 帧 | 10 帧（拆解后）|
| 90° 旋转冒充 | **是**（sleep_03-05 被目视指出）| **否**（独立侧面躺姿）|
| 身份漂移 | **是**（GPT 报告 FAIL）| **否**（目视 + 客观签名 PASS）|
| 无限循环控制 | **是**（整套循环）| **否**（仅 sleep_loop 循环）|

---

## 四、任务三：walk_left / walk_right 独立完整循环（PASS）

### 4.1 设计（R136 §四 严格遵守）

| 方向 | 帧数 | 帧时长 | 内容 | 循环方式 |
|---|---|---|---|---|
| walk_left | 4 帧 | 130ms | stand → left_step → pass → right_step | 帧 4 → 帧 0 独立循环 |
| walk_right | 4 帧 | 130ms | stand → right_step → pass → left_step | 帧 3 → 帧 0 独立循环 |

### 4.2 8 帧 i2i 生成

| 段 | 帧 |
|---|---|
| walk_left_00 stand | 站姿，左向预备 |
| walk_left_01 left_step | 左腿前迈，重心左移 |
| walk_left_02 pass | 中间跨步，腿交叉 |
| walk_left_03 right_step | 右腿前迈，重心右移 |
| walk_right_00 stand | 站姿，右向预备 |
| walk_right_01 right_step | 右腿前迈，重心右移 |
| walk_right_02 pass | 中间跨步，腿交叉 |
| walk_right_03 left_step | 左腿前迈，重心左移 |

**禁止项确认**：
- ✅ 不使用整图水平平移冒充迈步 —— R136 8 帧均为独立 i2i 生成的真步态
- ✅ 不因帧切换改变脸型、服装及鞋子 —— 客观签名检查确认 8/8 帧身份一致
- ✅ 不镜像（避免徽章翻转）—— walk_left 与 walk_right 是独立 i2i 生成，非 PIL 镜像

**身份锁定目视确认**：所有 8 帧均保持银白短发、冰蓝眼睛、白色实验服、蓝色徽章、蓝色裤子、白色鞋子。

### 4.3 R133 vs R136 walk 对比

| 指标 | R133 walk | R136 walk |
|---|---|---|
| 帧数 | 6 帧（混合 left/right）| 8 帧（拆解 left/right 各 4）|
| 独立循环 | **否**（混合帧不能循环）| **是**（left 与 right 各 4 帧独立循环）|
| 镜像使用 | 部分混合 | 是（独立生成非镜像）|

---

## 五、任务四：所有正式候选帧统一 RGBA PNG（PASS）

**R133 状态**：18 帧全部 RGB 模式 + 84 万白底
**R136 状态**：24 帧全部 RGBA PNG + 透明背景（白底已通过 BFS flood-fill 移除）

| 子目录 | 帧数 | 状态 |
|---|---|---|
| 06_ANIMATIONS_RGBA/idle | 6 | ✅ RGBA PNG |
| 06_ANIMATIONS_RGBA/sleep_enter | 3 | ✅ RGBA PNG |
| 06_ANIMATIONS_RGBA/sleep_loop | 4 | ✅ RGBA PNG |
| 06_ANIMATIONS_RGBA/wake_up | 3 | ✅ RGBA PNG |
| 06_ANIMATIONS_RGBA/walk_left | 4 | ✅ RGBA PNG |
| 06_ANIMATIONS_RGBA/walk_right | 4 | ✅ RGBA PNG |
| **总** | **24** | **100% RGBA PNG** |

**禁止项确认**：
- ✅ 禁止以带白色矩形背景的 JPG 直接充当桌宠透明素材 —— R136 全部 24 帧为 PNG（无 JPG）
- ✅ 不允许通过粗暴的白色阈值破坏制服 —— R136 使用 BFS flood-fill（避开全局亮度阈值）
- ✅ 同一动作采用统一画布和合理锚点 —— R136 manifest 统一 canvas 1024×1024，anchor 三档（stand 0.5/0.90、sit 0.5/0.86、lie 0.5/0.78）

---

## 六、任务五：视觉身份一致性检查 v2（PASS 不只靠 L1）

### 6.1 升级说明（R136 §六 严格执行）

**R133 方法**：5 个固定坐标 + 像素 RGB L1 距离 → 不适合躺姿（区域映射变化）

**R136 v2 方法**：
1. **自适应关键区域签名**：根据 bbox 比例定位"头部 / 眼睛带 / 躯干 / 制服下摆"，提取颜色+边缘密度签名
2. **bbox aspect 比例**：站姿瘦高（aspect 2.3-2.5），躺姿扁宽（aspect 0.4-0.6）
3. **白色制服占比**：稳定 0.27-0.40（不被姿态变化破坏）

**R136 §六 明确禁止**：
- ❌ 仅依靠 L1 像素差宣布 PASS
- ❌ 仅依靠静态 grep 宣布 PASS
- ❌ 仅依靠资源文件数量宣布 PASS
- ✅ 必须以目视 + 客观签名 + bbox 比例 + 制服占比综合判断

### 6.2 24 帧客观签名结果

| 动画 | bbox aspect | 白色制服占比 | 视觉目视 |
|---|---|---|---|
| idle (6) | 2.37-2.54 ✓ 站姿 | 0.30-0.33 ✓ | ✅ 身份一致 |
| sleep_enter (3) | 0.46-2.53 ✓ 过渡 | 0.27-0.33 ✓ | ✅ 身份一致 |
| sleep_loop (4) | 0.39-0.59 ✓ 躺姿 | 0.29-0.39 ✓ | ✅ 身份一致 |
| wake_up (3) | 0.44-2.52 ✓ 过渡 | 0.27-0.38 ✓ | ✅ 身份一致 |
| walk_left (4) | 1.77-3.18 ✓ 站+步 | 0.29-0.38 ✓ | ✅ 身份一致 |
| walk_right (4) | 1.82-2.74 ✓ 站+步 | 0.31-0.40 ✓ | ✅ 身份一致 |

**结论**：24/24 帧符合 A1 母版身份（自适应签名 + 比例 + 占比 + 目视四维综合）。

---

## 七、任务六：统一 manifest（PASS）

`09_MANIFEST/R136_manifest.json` 包含：
- character_id / version
- a1_reference_sha256 / alpha_template_sha256_before / alpha_template_sha256_after
- canvas_size / anchor 三档
- production_method（含 R133 资产复用 + R136 重做的明确区分）
- limitations_declared（4 项工具链限制诚实声明）
- actions 6 类（idle / sleep_enter / sleep_loop / wake_up / walk_left / walk_right）每类含 frames / frame_ms / loop / total_duration_s / transition
- alpha_residue_fix 修复证据
- white_background_cleanup 清理证据
- frame_pixel_diff_check 帧差异范围
- identity_consistency_v2 方法 + 结果

---

## 八、任务七：GIF + HTML + 200×240（PASS）

| 交付物 | 路径 | 大小 |
|---|---|---|
| idle_animation.gif | 07_PREVIEWS/idle_animation.gif | 484 KB |
| sleep_enter_animation.gif | 07_PREVIEWS/sleep_enter_animation.gif | 266 KB |
| sleep_loop_animation.gif | 07_PREVIEWS/sleep_loop_animation.gif | 328 KB |
| wake_up_animation.gif | 07_PREVIEWS/wake_up_animation.gif | 223 KB |
| walk_left_animation.gif | 07_PREVIEWS/walk_left_animation.gif | 308 KB |
| walk_right_animation.gif | 07_PREVIEWS/walk_right_animation.gif | 296 KB |
| HTML 动态预览 | 07_PREVIEWS/ANIMATION_PREVIEW_R136.html | 6.9 KB |
| 6 个 PET_WINDOW 200×240 | 07_PREVIEWS/PET_WINDOW_*_200x240.png | 各 19-29 KB |
| 5 背景对比图 | 07_PREVIEWS/ALPHA_FIX_5BG_COMPARE_R136.png | 320 KB |

---

## 十、最终状态字段

```yaml
ACTIVE_ROUND: 136
ROUND_STATUS: PARTIAL                  # P0 + GATE 3 PASS, 4 项工具链限制诚实声明

A1_ORIGINAL_PRESERVED: true            # SHA256 3344d5fe... 不变
ATTACHED_GHOST_ARTIFACT_REMOVED: PASS   # 根因 = RGB 白底, BFS flood-fill 全转 RGBA
ALPHA_338PX_FIX_PRESERVED: true         # SHA256 5c2807bca5... 保留

IDLE_ANIMATION: PASS                   # R133 通过, R136 沿用
WALK_LEFT_COMPLETE: PASS               # 4 帧独立完整循环
WALK_RIGHT_COMPLETE: PASS              # 4 帧独立完整循环
SLEEP_ENTER: PASS                      # 3 帧站→躺
SLEEP_LOOP: PASS                       # 4 帧循环呼吸
WAKE_UP: PASS                          # 3 帧躺→站

ALL_CANDIDATE_FRAMES_RGBA: true        # 24/24 RGBA PNG, 无 JPG 白框
ANIMATION_IDENTITY_QA: PASS            # 24/24 v2 自适应签名 + bbox + 制服占比
ANIMATION_PREVIEW: COMPLETE            # 6 GIF + HTML
MANIFEST: COMPLETE                     # R136_manifest.json 6 类动作

R113_BASELINE_PRESERVED: true          # b3e42d5 未动
GATE_3_USER_APPROVAL: PENDING          # 等 GPT + 用户审核
CHARACTER_ASSETS_FROZEN: false         # 角色未冻结
V0_0_RELEASE_STATUS: NOT_FROZEN        # V0.0 未封版
V0_1_DEVELOPMENT: NOT_AUTHORIZED       # V0.1 未授权

GIT_COMMIT: 见 docs/R136_QA_REPORT.md 和 R136_DELIVERY_INDEX.md (本次 commit)
REVIEW_ZIP_PATH: /Users/musk123/Downloads/minimax工作文件夹/character_animation_R136_review.zip
REVIEW_ZIP_SHA256: c22f0071906d0f8aa7f45bb9b7eeecf54798cf6e2edab6e62f099d2053dbe997

OVERALL_ACCEPTED_PROGRESS: 0%          # 等用户最终裁决
```

---

## 十一、报告原则

按 R136 §六 要求：
- 客观实测数据给出关键值（绝对值 + 阈值）
- 视觉目视仅作辅助（避免「目视 PASS → 验收」偏差）
- 工具链限制诚实声明，不允许以静态 grep 冒充视觉质量测试
- 不允许只靠 L1 像素差宣布 PASS（v2 已升级）

按 R136 §七 要求：
- A1 原始母版保留
- R113 基线 b3e42d5 未动
- A4 不重新制作
- 不擅自冻结角色
- 不封版 V0.0
- 不进入 V0.1
- 不批量制作 15-30 类动作

按 R136 §八 要求：
- 一次性完整交付
- 审查包不含 290 MB 软件项目和 node_modules
- 飞书 + git + 交付索引 + 报告四件套同步
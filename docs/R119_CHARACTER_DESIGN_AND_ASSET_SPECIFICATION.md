# R119 — 正式角色设计与美术资源规范制定

> **状态：DRAFT — 候选设计阶段，等待用户 GATE 1 选择。**
>
> **轮次**：V0.0 第 119 轮
> **作者**：MiniMax（Mavis）
> **日期**：2026-10-19
> **R113 基线**：c0fb3bd（未改动）
> **R117 上游**：20d99ff（包含原始需求恢复 + 开源调研）

---

## 一、本轮目标

制定"银白科技研究员"角色的 3 套候选外观方案、统一的美术资源规范、首批 15 类动作规划、与 R113 技术基线的兼容性确认。

不修改任何产品代码、不替换现有角色素材、不进入 V0.1 功能开发。

完整交付位于独立目录 `图文工作/character_design_R119/`（不在产品代码仓库内）。本文件是产品仓库内的精简合并报告。

---

## 二、三套候选方案摘要

| 方案 | 方向 | 主色 | 关键特征 | 制作复杂度 |
|---|---|---|---|---|
| A 经典科技研究员 | 精致、聪明、亲切 | 银白 + 冰蓝 | 短直发 + 简洁立领 + 极简配饰 | ★★☆ |
| B 未来实验室研究员 | 科技感更强、专业 | 银白 + 实验室蓝 | 短碎发 + 多层立领 + 护目镜顶置 + 徽章 + 腰带 | ★★★ |
| C 灵动活力研究员 | 灵动、年轻、表情丰富 | 银白 + 暖粉蓝渐变 | 短翘发 + 翻领 + 小挂坠 | ★★☆ |

> **MiniMax 推荐**：方案 B（详见 `E_USER_SELECTION_GUIDE.md`）
> **最终决定权**：用户（王毅磊）

---

## 三、美术资源规范要点

### 3.1 尺寸与坐标

- **基础画布**：512×512 px（实际渲染前可降到 192×192 / 256×256）
- **画幅透明边界**：上下各 64 px 安全区，左右各 32 px 安全区
- **锚点位置**：(0.5, 0.9) — 脚底中心，PixiJS sprite.anchor.set(0.5, 0.9)
- **不同动作视觉位置保持**：以 anchor.y=0.9 为基准，所有动作的脚底必须在同一屏幕坐标（不论坐 / 站 / 躺）

### 3.2 图层结构（10 个标准图层）

```
LAYER_01 BG_SHADOW          # 角色脚下阴影（独立可选）
LAYER_02 LEGS               # 双腿（左 + 右）
LAYER_03 BODY               # 躯干（含制服主体）
LAYER_04 LEGS_FRONT         # 前腿（仅在跨步 / 坐姿使用）
LAYER_05 ARM_BACK           # 后手臂
LAYER_06 HEAD               # 头（含面部）
LAYER_07 EYES               # 眼睛（含高光 + 闭眼帧）
LAYER_08 HAIR               # 头发（含刘海 + 鬓角）
LAYER_09 ARM_FRONT          # 前手臂
LAYER_10 ACC                # 配饰层（护目镜 / 徽章 / 腰带 / 挂坠按方案选择性启用）
LAYER_11 EFFECT_OVERLAY     # 特效层（仅在睡觉气泡 / 跳跃星尘等使用）
```

### 3.3 动画实现方式选择

**决策**：A 方案 PNG 序列帧 + C 方案分层骨骼 = **混合方案**

- 简单动作（待机呼吸 / 眨眼 / 左右行走 / 停步 / 跳跃 / 坐下 / 躺下）：PNG 序列帧，每帧 4-12 张，192×192 px
- 复杂动作（转身 / 伸懒腰 / 睡醒起身 / 被拖动放下）：分层骨骼动画，使用 Spine / DragonBones 格式
- 表情系统：独立 EYE_LAYER 切换 4 帧（睁眼 / 半闭 / 闭眼 / 笑眯）

**理由**：PixiJS 7 已支持 Spine 4.x runtime，R0+ 19 实测 60fps 有余量；纯序列帧生产速度快、调试直观；分层骨骼用于真正复杂的形变。

### 3.4 美术风格统一

- **线条粗细**：1.5-2 px @ 512×512（缩到 192 时为 0.6-0.8 px）
- **明暗**：3 层（基色 / 中间色 / 高光），不使用更复杂的多层渲染
- **光影方向**：默认 45° 左上 → 右下（与桌面太阳光方向一致），方向不随动作变化
- **配色体系**：银白 #F5F8FA + 冰蓝 #A6D8E8 + 实验室蓝 #2A5C8A + 暖粉蓝（仅 C 方案）#FFB8C8
- **发丝画法**：2-3 像素宽的发束，避免单根发丝的细碎线条（缩略图不可读）
- **左右翻转**：所有左向素材按镜像生成，禁止使用 sprite.scale.x=-1（会反向高光和细节）

### 3.5 资产目录结构

```
assets/characters/default_scientist/
├── manifest.json                       # 全角色 manifest
├── base/                               # 基础立绘层（10 个图层 × 3 方案 = 30 个 PNG）
│   ├── A_classic/
│   ├── B_lab/
│   └── C_vivid/
├── actions/                            # 动作序列帧
│   ├── idle_breath/                    # 待机呼吸（循环）
│   ├── walk_left/                      # 左走（循环）
│   ├── walk_right/                     # 右走（循环，由 walk_left 镜像）
│   ├── run/                            # 小跑（循环）
│   ├── stop/                           # 停步（一次性）
│   ├── turn/                           # 转身（一次性）
│   ├── look_around/                    # 四处张望（一次性）
│   ├── blink/                          # 眨眼（一次性）
│   ├── stretch/                        # 伸懒腰（一次性）
│   ├── sit_down/                       # 坐下（一次性）
│   ├── sit_rest/                       # 坐姿休息（循环）
│   ├── lie_down/                       # 躺下睡觉（一次性）
│   ├── wake_up/                        # 睡醒起身（一次性）
│   ├── jump/                           # 跳跃（一次性）
│   ├── click_react/                    # 被点击反应（一次性）
│   └── drag_drop_react/                # 被拖动放下反应（一次性）
└── effects/                            # 特效层
    ├── sleep_bubble/                   # 睡觉气泡（循环）
    └── jump_dust/                      # 跳跃星尘（一次性）
```

---

## 四、首批 15 类动作清单

| # | 动作 | 类型 | 帧数 | 循环 | 方向需求 | 难度 |
|---|---|---|---|---|---|---|
| 1 | 待机呼吸 | 循环 | 6 | ✓ | 单一朝向 | 低 |
| 2 | 左走 | 循环 | 8 | ✓ | 左 | 中 |
| 3 | 右走 | 循环 | 8 | ✓ | 右（由左镜像） | 低 |
| 4 | 小跑 | 循环 | 8 | ✓ | 左/右 | 中 |
| 5 | 停步 | 一次性 | 4 | ✗ | 任意 | 低 |
| 6 | 转身 | 一次性 | 6 | ✗ | 左→右 / 右→左 | 中 |
| 7 | 四处张望 | 一次性 | 8 | ✗ | 任意 | 中 |
| 8 | 眨眼 | 一次性 | 3 | ✗ | 单一朝向 | 低 |
| 9 | 伸懒腰 | 一次性 | 8 | ✗ | 单一朝向 | 中 |
| 10 | 坐下 | 一次性 | 6 | ✗ | 任意 | 低 |
| 11 | 坐姿休息 | 循环 | 4 | ✓ | 任意 | 低 |
| 12 | 躺下睡觉 | 一次性 | 8 | ✗ | 任意 | 中 |
| 13 | 睡醒起身 | 一次性 | 6 | ✗ | 任意 | 中 |
| 14 | 跳跃 | 一次性 | 6 | ✗ | 任意 | 中 |
| 15 | 被点击反应 | 一次性 | 4 | ✗ | 任意 | 低 |
| 16 | 被拖动放下 | 一次性 | 4 | ✗ | 任意 | 低 |

> 实际为 16 类（含左走 + 右走分别），C_INITIAL_ACTION_PLAN.md 完整描述每类的优先级、资源需求与衔接规则。
> 未来扩展到 30 类以上动作的结构已规划（详见 `C_INITIAL_ACTION_PLAN.md` §五）。

---

## 六、与 R113 技术基线的兼容性

### 6.1 兼容性矩阵

| 层级 | R113 当前实现 | R119 新角色适配 | 改动需求 |
|---|---|---|---|
| Electron 主进程 | BrowserWindow + setInterval 60Hz 鼠标轮询 | 无需改动 | 0 |
| PixiJS 渲染器 | PixiJS 7.x Application | 无需改动 | 0 |
| 资源加载 | PIXI.Loader + resources | 适配新增 manifest.json 加载逻辑 | R0.5+ 改 1 处 |
| 拖拽跟随 | main 端 setInterval + screen.getCursorScreenPoint | 无需改动 | 0 |
| 坐标系 | screen 坐标 + BrowserWindow bounds | 无需改动 | 0 |
| 角色 sprite 渲染 | PIXI.Sprite + anchor | 适配 anchor (0.5, 0.9) 新标准 | R0.5+ 改 1 处 |
| 调试信息显示 | R104 preview 等开发文字 | R119 规范禁止常驻显示（仅 dev mode 显示） | R0.5+ 改 1 处 |
| 角色几何占位 | R0 阶段矩形 + 圆形 | R119 设计稿替换几何占位（仅在用户选定方案后） | R0.5+ 改 1 处 |

### 6.2 兼容性结论

**R0 + R113 完全兼容**，R119 仅产出 DRAFT 设计稿与规范文档。R0.5+ 阶段（用户选定方案后）需要修改的位置已明确标记（共 3 处，均在资源加载 / sprite anchor / 调试信息开关，不涉及 C2 拖拽底层）。

**R113 c0fb3bd 任何代码均未改动**。

---

## 七、4 阶段 GATE 机制

| GATE | 内容 | 状态 |
|---|---|---|
| GATE 1 | 用户从 3 套候选中选择方向 | ⏳ PENDING |
| GATE 2 | 立绘细化（发型 / 五官 / 制服 / 配色 / 比例） | 未启动 |
| GATE 3 | 5 个核心动作样片（待机 / 左走 / 右走 / 坐下 / 躺下） | 未启动 |
| GATE 4 | 用户确认后批量制作 15+ 类动作资源 | 未启动 |

**不得跳过 GATE 1 直接进入批量生产。**

任何未通过 GATE 的方案均标记为 DRAFT，不允许标记为 APPROVED 或 FROZEN。

---

## 八、交付清单（独立目录，不混入产品代码）

主交付目录：`/Users/musk123/Downloads/minimax工作文件夹/图文工作/character_design_R119/`

| # | 文件 | 类型 | 大小 |
|---|---|---|---|
| 1 | A_classic_front.jpg | 1024×1024 正面 | 486 KB |
| 2 | A_classic_desktop.png | 1024×576 桌面预览 | 1.2 MB |
| 3 | B_lab_front.png | 1024×1024 正面 | 902 KB |
| 4 | B_lab_desktop.png | 1024×576 桌面预览 | 1.5 MB |
| 5 | C_vivid_front.jpg | 1024×1024 正面 | 550 KB |
| 6 | C_vivid_desktop.png | 1024×576 桌面预览 | 1.1 MB |
| 7 | A_VISUAL_PREVIEW.md | Markdown | 8.1 KB |
| 8 | B_ART_ASSET_SPEC.md | Markdown | 12.1 KB |
| 9 | C_INITIAL_ACTION_PLAN.md | Markdown | 7.9 KB |
| 10 | D_TECH_COMPATIBILITY.md | Markdown | 9.0 KB |
| 11 | E_USER_SELECTION_GUIDE.md | Markdown | 7.6 KB |
| 12 | F_DELIVERY_INDEX.md | Markdown | 7.7 KB |

**总计**：12 个文件，约 6.2 MB。

---

## 九、阶段字段（最终状态）

```
ROUND_STATUS = COMPLETE
ACTIVE_ROUND = 119
TECH_STACK = ELECTRON_PIXIJS_CONFIRMED
CHARACTER_CONCEPTS = 3
VISUAL_PREVIEWS = 6
ASSET_SPECIFICATION = COMPLETE
INITIAL_ACTION_PLAN = 15
USER_CHARACTER_APPROVAL = PENDING
CHARACTER_ASSETS_FROZEN = false
R113_TECH_BASELINE_PRESERVED = true
FORMAL_FEATURE_CODE_CHANGED = false
AUTONOMOUS_BEHAVIOR_DEVELOPMENT = NOT_STARTED
AI_DEVELOPMENT = NOT_STARTED
V0_0_RELEASE_STATUS = NOT_FROZEN
OVERALL_ACCEPTED_PROGRESS = 0%
GIT_COMMIT = (本文件 commit 后回填)
REVIEW_PACKAGE_PATH = /Users/musk123/Downloads/minimax工作文件夹/图文工作/character_design_R119_review.zip
REVIEW_PACKAGE_SHA256 = (zip 生成后回填)
CURRENT_PHASE = CHARACTER_DESIGN_GATE_1
```

---

## 十、等待用户 GATE_1_DECISION

用户需按 `E_USER_SELECTION_GUIDE.md` §四 格式回复决策，Mavis 进入 R120 GATE 2 立绘细化。

R119 阶段结束，等待用户选择外观。
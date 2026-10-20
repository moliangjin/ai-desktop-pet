# R147 质量报告 — Mac 真机验收首轮交互与动画质量修复

> **生成时间**：2026-10-20
> **对应任务书**：R147（`ACTIVE_TASK = MAC_GUI_FEEDBACK_FIX`）
> **执行**：MiniMax（Mavis）
> **上一交付**：R144 `3634d83`
> **基线**：R144（工程门禁 PASS / Mac 真机验收 FAILED_PARTIAL）

---

## 〇、结论先说

用户 Mac 真机验收提出的三个问题，**全部做了实修**，并用**真实 Electron 运行采集的像素**做了客观量化验证（不是靠测试日志或文件名判定）：

| 用户反馈 | 修复 | 真实运行量化证据 |
|---|---|---|
| ① 左右转身腿没转向，像倒着走 | 保留左右各自的迈步帧，**对整帧施加反向整体倾斜**（身体连同腿一起朝移动方向倾，纹理不镜像） | 左移：上半身相对下半身 **-13.04px**，26/26 帧一致偏左；右移 **+12.23px**，0/26 帧偏左 → 方向明确且左右对称 |
| ② 点击角色毫无反馈 | 区分 CLICK / DRAG，CLICK 触发**眨眼 + 轻微弹跳**；睡眠中点击走完整 `wake_up` 过渡 | 真实 pointer 事件 → `kind=CLICK elapsed=95ms dist=0.0px` → 弹跳 **9px** 离地 + texture 变化；睡眠点击 → `DRAGGING -> WAKE_UP (user-click-wake)` → `animation-finished wake_up` → 回 IDLE |
| ③ 待机时胸部剧烈膨胀 | 播放序列改为**稳定站姿 + 自然眨眼**，胸腔膨胀帧（`idle_01`）与回落帧（`idle_02/03`）**不再进入播放序列** | 90 帧真实采集：胸部最大轮廓宽度 **波动 0px**（旧帧为 +26px 源像素外扩）；6.3s 内眨眼 3 次，间隔 2440ms / 2200ms（随机，非 1.2s 机械循环） |

同步修复了 GPT 在 R144 独立审查里记录的老问题：**切换动作时 `Sprite.texture` 未立即更新** → 现在 `applyAction()` 在切换的同一时刻就换好首帧并同步地面线与倾斜（运行时自检逐动作核对通过）。

**三件套**：git commit + 轻量审查包 ZIP + SHA256 + 飞书通知，均在本轮完成。

---

## 一、素材实测：根因到底在哪

用户说"倒着走"，可能是**帧方向标错**、**映射错**、**重复姿态**，也可能是**躯干朝向与移动方向完全无关**。这一层必须先查清，否则只能靠改名糊弄。

### 1.1 左右两组素材不是同一套帧（排除"改名"）

`12_R147_gait_analysis.py` / `13_R147_step_direction.py` 实测：

- 交叉像素差异矩阵：`walk_left` 任一帧 vs `walk_right` 任一帧，差异 **68k~152k 像素**（占不透明像素 30%~65%），**不是镜像、不是副本**。
- `walk_left_01` 踩地那只靴子的**鞋尖朝左**（迈左步）；`walk_right_01` 踩地那只鞋的**鞋尖朝右**（迈右步）。
- **结论：两组素材各自的迈步方向本来就是对的**，所以本轮**没有替换帧来源**（避免"只改文件名就宣称通过"）。

### 1.2 真正的根因：躯干朝向没有绑定移动方向

| 实测项 | walk_left | walk_right |
|---|---|---|
| 原始帧上半身−下半身水平偏移（无错切） | −11.6px | −7.9px |
| 原始帧躯干轴倾角（`12_...` 肩−胯） | −1.5（基本正直） | +1.6（基本正直） |

两组素材的角色都是**正面朝镜头**的 3/4 姿态，躯干朝向基本正直且**不与行进方向绑定**。窗口往左移动时，画面里没有任何"朝左"的姿态线索，只有脚下在动 —— 这正是用户看到的"倒着走"。

### 1.3 镜像方案为什么被否决

- 头部/发型左右不对称明显，镜像会翻转发型与服装配件 → 角色身份不一致。
- 任务书明确要求"必须检查服装徽章、头发、鞋子等非对称细节"，实测结论是**镜像不可接受**。

### 1.4 采用的方案：整体朝向处理（任务书授权路径）

> "优先使用已有资源，通过正确映射、关键帧顺序调整、**整体朝向处理**和必要的局部资产修复解决。"

对整帧做**水平错切（shear）**，让身体连同腿一起朝行进方向倾：

- `walk_left`：`skew_x = +0.085`（PixiJS 语义 k>0 → 上半身向左偏移）
- `walk_right`：`skew_x = -0.11`（k<0 → 向右偏移）

错切作用在**顶点层**，**纹理本身不镜像** → 角色身份 / 服装 / 发型 / 徽章完全不变。

---

## 二、三项修复的实现

### 2.1 P0 行走方向

**代码**：
- `src/sprite_layout.js`：新增错切感知。缩放核算纳入错切后的水平占位（否则倾斜会把角色推出画布）；新增 `skewCosFactor()` / `skewAngleX()` / `frameScreenRect()`。
- `src/renderer.js`：`buildLayoutFor()` 从 manifest 读 `lean.skew_x`；`applyFramePosition()` 施加 `sprite.skew.x = skewAngleX(k)`。
- `assets/character_R141_manifest.json`：`walk_left.lean = {skew_x: +0.085, direction: -1}`、`walk_right.lean = {skew_x: -0.11, direction: +1}`。

**关键实现细节（踩过的坑）**：
PixiJS 7.4.3 的错切语义**不是** `tan(skew.x)`，读源码确认（`@pixi/math/lib/Transform.js`）：

```
_cx = cos(rot+skew.y),  _sx = sin(rot+skew.y)
_cy = -sin(rot-skew.x),  _sy = cos(rot-skew.x)
lt.a = _cx*scale.x,  lt.b = _sx*scale.x,  lt.c = _cy*scale.y,  lt.d = _sy*scale.y
→ screen_x = tx + s*(lx + sin(skew.x)*ly)
→ screen_y = ty + s*cos(skew.x)*ly
```

即 **k = sin(skew.x)**（不是 tan），且**竖直方向同时被 cosθ 压缩**。
本轮新增 `tests/r147_layout_pixi_parity.test.js`，用**真实 `@pixi/math` Transform**（renderer 用的同一个库）逐点比对 `contentRectToScreen` 与 PixiJS 顶点矩阵，**误差 < 1e-9**。

### 2.2 P0 鼠标单击反馈

**新增生产模块 `src/click_policy.js`（纯逻辑，renderer 与测试共用同一份代码）**：

| 结束原因 | 累计位移 | 按住时长 | 判定 |
|---|---|---|---|
| 抬起 | < 3px | ≤ 400ms | **CLICK** → 触发可见反馈 |
| 抬起 | ≥ 3px | 任意 | **DRAG** → 窗口拖拽，不触发点击反馈 |
| 抬起 | < 3px | > 400ms | **HOLD** → 安全松开，无点击反馈 |
| 已进入窗口拖拽 | 任意 | 任意 | **DRAG** |
| 取消 / 离开角色区域 | 任意 | 任意 | **CANCEL** → 安全清理 |

- **幂等守卫**：`finishPress()` 开头 `if (!dragging) return;` → sprite 与 canvas 两层 `pointerup` 只会生效一次（**同一次操作不可能既触发点击反馈又触发拖拽结束**）。
- **可见反馈**：复用 `idle` 的 `blink_half` / `blink_closed` 两帧 + 轻微弹跳（峰值 9 屏幕像素），总时长 620ms。**不改身份与服装，不新增动作资源**。
- **自主行为协调**：点击走独立 IPC `character-click` → 主进程 `engine.onUserClick()` → `holdBriefly(700ms)` 暂缓自主计时器；**行走中点击会暂停位移计时器但保留剩余距离**，反馈结束后继续走完。
- **睡眠点击唤醒**：`sleep_loop / sleep_enter` 被点击 → `DRAGGING -> WAKE_UP (user-click-wake)` → 播 `wake_up` 一次性动画 → 播完回 IDLE。**不跳过醒来过渡、不瞬移成站姿**（运行时日志实证）。

### 2.3 P1 自然待机

- **新增生产模块 `src/idle_director.js`（纯逻辑）**：稳定站姿（`base_index=0`）+ 自然眨眼（`blink_sequence=[4,5]`，半闭 90ms / 全闭 110ms，间隔 **1600~3400ms 随机**）。
- manifest `idle.director.excluded_frames = [1,2,3]` → **胸腔膨胀帧与回落帧永不进入播放序列**，但 6 帧仍全部加载（资产完整性 23/23 不变）。
- 眨眼与"呼吸"节奏不同：眨眼是一次性短促动作（实测 < 400ms），站姿保持 1.6~3.4s。

### 2.4 动作首帧同步（同步修复项）

新增 `applyAction(action)` 统一入口，所有切换路径（`set-action` IPC / 拖拽结束 / 模式重建 / 资源加载完成 / dev 快捷键）都走它：

```
currentAction = action; frameIdx = 0;
animClock_.setAction(...)            // 旧完成事件作废
sprite_.texture = meta.frames[0]     // ★ 首帧立即显示, 不等下一次 ticker
applyFramePosition(action, 0)        // ★ 地面线 + 方向倾斜同步
```

运行时自检逐动作核对 `texture === frames[0]` / `sprite.y === 布局值` / `sprite.skew.x === skewAngleX(k)`，**6 组动作全部 issues=0**。

---

## 三、测试与证据

### 3.1 单元测试：66 项全通过（R144 的 38 项零回归 + R147 新增 28 项）

| 套件 | 项数 | 结果 |
|---|---|---|
| `r141_behavior_engine.test.js` | 12 | 12 PASS（未改） |
| `r144_layout.test.js` | 8 | 8 PASS（输入改为与生产一致，含方向倾斜；断言未削弱） |
| `r144_oneshot.test.js` | 9 | 9 PASS（未改） |
| `r144_assets_gate.test.js` | 9 | 9 PASS（未改） |
| `r147_layout_pixi_parity.test.js` | 5 | **新增**：与真实 PixiJS 顶点矩阵逐点一致 |
| `r147_interaction.test.js` | 23 | **新增**：点击判定 / 引擎点击与唤醒 / 自然待机 / 步态方向 / 资产完整性 |

### 3.2 端到端：真实启动 Electron（生产代码）

| 套件 | 结果 |
|---|---|
| `R144_e2e_test.sh` | PASS=22 FAIL=0 NOT_VERIFIED=4（B9 撞边本轮随机未触发，属环境项） |
| `R141_e2e_test.sh` | PASS=12 FAIL=0 NOT_VERIFIED=4（T8 撞边同上） |
| `R147_e2e_test.sh` | **PASS=18 FAIL=0 NOT_VERIFIED=0**（真实采集帧量化 + 运行时自检 + 真实撞边反向） |

### 3.3 真实运行预览（可直接观看）

采集方式：`electron src/main.js --preview <dir>` → `webContents.capturePage()` 逐帧截图 + 记录窗口**真实 x 位移** → `14_R147_preview_gif.py` 合成 GIF。

> 诚实说明：GIF 里的角色像素是**真实运行时截图**，未做任何重绘；行走场景里角色在画布上的横向位置 = 该帧窗口的**真实**位移（`dx`），"往哪边走"是运行时真实发生的事。

| 预览 | 文件 | 内容 |
|---|---|---|
| 向左行走 | `evidence_r147_preview/R147_walk_left.gif` | 26 帧，窗口真实左移 60px，walk_left + 向左倾斜 |
| 向右行走 | `evidence_r147_preview/R147_walk_right.gif` | 26 帧，窗口真实右移 60px，walk_right + 向右倾斜 |
| 自然待机 | `evidence_r147_preview/R147_idle.gif` | 90 帧 / 6.3s，稳定站姿 + 3 次随机眨眼，无胸腔膨胀 |
| 单击反馈 | `evidence_r147_preview/R147_click.gif` | 26 帧，眨眼 + 9px 弹跳 |
| 睡眠唤醒 | `evidence_r147_preview/R147_wake.gif` | 34 帧，sleep_loop → wake_up → idle |
| 汇总图 | `evidence_r147_preview/R147_preview_summary.png` | 五场景并排 |

### 3.4 真实采集帧的客观量化（`15_R147_preview_verify.py`）

| 指标 | 实测 | 判定 |
|---|---|---|
| 待机胸部最大轮廓宽度波动 | **0px**（90 帧） | 无胸腔膨胀 |
| 待机角色底边（地面线）波动 | **0px** | 地面接触稳定 |
| 待机出现过的姿态 | 仅 0 / 4 / 5 | 膨胀帧 1/2/3 从未出现 |
| 单击弹跳幅度 | **9px 离地** + texture 变化 | 肉眼可见 |
| 左移上半身偏移 | **-13.04px**，26/26 帧为负 | 方向正确 |
| 右移上半身偏移 | **+12.23px**，0/26 帧为负 | 方向正确，左右对称 |
| 睡眠唤醒姿态数 | 3 段（躺 → 坐 → 站） | 完整过渡 |

---

## 四、报告字段

```
ACTIVE_ROUND = 147
ROUND_STATUS = COMPLETE

WALK_LEFT_VISUAL_DIRECTION = PASS
WALK_RIGHT_VISUAL_DIRECTION = PASS
EDGE_TURN_VISUAL = PASS

CLICK_RESPONSE = PASS
CLICK_DRAG_DISAMBIGUATION = PASS
CLICK_WAKE_UP = PASS

IDLE_BREATHING = PASS
IDLE_BLINK_TIMING = PASS

ACTION_FIRST_FRAME_SYNC = PASS
AUTONOMOUS_BEHAVIOR_REGRESSION = PASS
R113_DRAG_CORE_PRESERVED = true

ENGINEERING_GATE = PASS
VISUAL_GATE = PASS
MAC_REAL_GUI_ACCEPTANCE = PENDING

V0_0_RELEASE_STATUS = NOT_FROZEN
V0_1_DEVELOPMENT = NOT_AUTHORIZED

GIT_COMMIT = 7ec7a3bcd9c2cde6bdf741cb2abd426ff9c34888
REVIEW_ZIP_PATH = /Users/musk123/Downloads/minimax工作文件夹/character_animation_R147_review.zip
REVIEW_ZIP_SHA256 = 见 ZIP 同目录的 character_animation_R147_review.zip.sha256
                       (刻意不内嵌: 内嵌会造成"改报告就改 ZIP 哈希"的循环自引用)
```

字段口径说明：

- `WALK_*_VISUAL_DIRECTION = PASS` —— 依据是**真实运行时采集帧的像素测量**（左 -13.04px / 26 帧一致；右 +12.23px / 0 帧相反），不是文件名、不是日志。
- `EDGE_TURN_VISUAL = PASS` —— 真实把窗口放到屏幕左缘（`--x 40`）向左走，**真的撞到屏幕边界**并触发 `WALK_LEFT -> WALK_RIGHT (edge-turn)`，且转向后窗口 x 由减转增（真实掉头）。
- `VISUAL_GATE = PASS` —— 已交付可直接观看的真实运行 GIF + 真实帧量化指标；**用户主观观感确认仍在 `MAC_REAL_GUI_ACCEPTANCE` 里等真机**。
- `MAC_REAL_GUI_ACCEPTANCE = PENDING` —— 沙箱内**无法完成真实物理鼠标**操作（点击手感、拖拽手感），一律不冒充通过。

---

## 五、残余限制（如实记录，不粉饰）

1. **左移仍有约 20px/s 的脚步滑动**（资产固有，不是代码缺陷）
   实测：窗口以 30px/s 左移时，`walk_left` 源帧内部双脚只漂移约 10px/s（`walk_right` 是 28px/s，与窗口速度基本匹配）。
   → 落地脚相对地面约有 20px/s 的滑移，约合角色身高的 7%/秒。
   **为什么不在代码里补**：用逐帧横向偏移补偿会在循环回卷处产生约 10px 的整体跳变，比滑移更刺眼；用加速/减速播放补偿会让腿部动作变成 3 倍快放的碎步。两者观感都更差。
   **根因在素材**：`walk_left` 四帧是"刚性同向漂移"步态，双脚间距单调变化（132→154→184→204px），本身就不是闭合跨步循环（接缝/帧内变化比 1.55，`walk_right` 为 1.03）。
   **要根治需要重画 walk_left 四帧**，而 i2i 当前余额为 0 且本轮禁止充值 → 列为待补素材项。

2. **左右两组步态不是严格对称**
   `walk_left` 四帧循环接缝比 `walk_right` 明显（1.55 vs 1.03），肉眼在慢速时可察觉一次"回到站姿"的衔接。

3. **方向靠整体倾斜表达，不是真正的侧视**
   R138 行走素材本身是正面 3/4 姿态，没有侧视帧；本轮用**整体错切**让身体朝行进方向倾，这是不重画素材前提下能做到的最强方向表达。纹理未镜像，身份/服装/发型/徽章完全未变。

4. **真实物理鼠标操作未验证**
   点击/拖拽判定走的是**真实 pointer 事件路径**（PixiJS 命中测试 → `finishPress` → CLICK/DRAG），e2e 里已实证 `kind=CLICK` 与"点击不触发 `window-drag-start`"，但**真实鼠标的手感**（点击阈值 3px / 400ms 是否贴合用户习惯）仍需用户真机确认。

5. **R113 拖拽核心逐字未改** —— `tools/r144_drag_core_diff.py` 对比 `6e35231`：9/9 区块逐字未改。

---

## 六、变更清单

```
candidates/candidate_b_c2/
├── src/
│   ├── main.js                ★ 改: character-click IPC 处理 / --preview 采集模式 / 行为引擎预览钩子
│   ├── renderer.js            ★ 改: applyAction 首帧同步 / 方向倾斜 / 待机导演 / 点击判定与反馈
│   │                                 / finishPress 幂等守卫 / preview-command 真实 pointer 采集
│   │                                 / R147 运行时自检
│   ├── behavior_engine.js     ★ 改: onUserClick / holdBriefly / wakeUpByUser / setAutonomousPaused
│   │                                 / startWalk(dir, distance) / setDragging 醒来态保护 / 移动暂停
│   ├── sprite_layout.js       ★ 改: 错切感知缩放 + cosθ 竖直修正 + skewAngleX + frameScreenRect
│   ├── idle_director.js       ★ 新增: 自然待机导演 (稳定站姿 + 自然眨眼) — 生产与测试共用
│   └── click_policy.js        ★ 新增: 点击/拖拽判定 — 生产与测试共用
├── assets/
│   ├── character_R138/        (未改 — 23 帧 SHA256 与 R138 交付清单 47/47 校验一致)
│   └── character_R141_manifest.json  ★ 改: walk_left/walk_right 的 lean 段 + idle 的 director 段
│                                         (帧路径未改, 仍是 23 个不同文件)
├── tests/
│   ├── r147_layout_pixi_parity.test.js  ★ 新增: 5 项 (与真实 PixiJS 顶点矩阵一致)
│   ├── r147_interaction.test.js          ★ 新增: 23 项 (点击/拖拽/唤醒/待机/步态/资产)
│   └── r144_layout.test.js                ★ 改: 布局输入改为与生产一致 (含倾斜), 断言未削弱
├── 11_R147_manifest_update.py  ★ 新增: manifest 修订器 (幂等, 可重放)
├── 12_R147_gait_analysis.py    ★ 新增: 步态/躯干轴定量分析
├── 13_R147_step_direction.py   ★ 新增: 迈步方向判定 (鞋底前后脚分离)
├── 14_R147_preview_gif.py      ★ 新增: 真实帧 → GIF 合成器
├── 15_R147_preview_verify.py   ★ 新增: 真实帧客观量化校验
├── R147_e2e_test.sh            ★ 新增: 端到端 (真实 Electron, 含真实采集帧量化)
├── evidence_r147_e2e.json      ★ 新增: e2e 机器可读报告
└── evidence_r147_preview/      ★ 新增: 5 个可观看 GIF + 采集元数据 + 量化结果
```

---

## 七、待用户真机确认（一次性）

双击运行：`candidates/candidate_b_c2/C2_Mac人工验收.command`

需要人工确认的三点（沙箱内无法替代）：
1. **左右走动的观感**：身体是否明显朝行进方向倾、腿是否不"倒着走"；
2. **点击手感**：单击是否有反应、拖拽会不会被误判成点击；
3. **待机观感**：是否已无胸部膨胀、眨眼是否自然。

---

*本报告由 MiniMax（Mavis）生成。所有结论均来自真实运行的像素测量与生产代码调用，无任何凭文件存在或颜色统计的判定。*

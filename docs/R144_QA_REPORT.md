# R144 QA 报告 — R141 运行时阻断修复（裁切 / 单次动画 / 资源握手 / 窗口坐标）

> **状态：ENGINEERING_GATE = PASS / MAC_REAL_GUI_ACCEPTANCE = PENDING**
>
> **生成时间**：2026-10-20
> **对应任务书**：R144 §二 §三 §四 §五 §七 §八
> **作者**：MiniMax（Mavis）
> **上一 commit**：R141 `47a7d87`
> **R113 基线**：`b3e42d5`（未改动）｜**A1 母版**：`3344d5fe…22013df`（未改动）
>
> **核心立场**：本轮**只修运行时工程阻断，不动资产、不加功能**。GPT 独立审查指出的 4 项阻断全部属实，本轮用**同一份生产代码**修复，并用**真实 Electron + 真实 PixiJS 变换矩阵**验证，而不是换一套预览算法自证。

---

## 一、结论总表（R144 §八 要求字段）

| 字段 | 结果 |
|---|---|
| `ACTIVE_ROUND` | 144 |
| `ROUND_STATUS` | **COMPLETE** |
| `ANIMATION_RENDER_BOUNDS` | **PASS** |
| `COMPACT_200X240_NO_CLIPPING` | **PASS**（23/23 帧，越界 0px） |
| `STANDARD_256X256_NO_CLIPPING` | **PASS**（23/23 帧，越界 0px） |
| `ONESHOT_LAST_FRAME_HOLD` | **PASS**（实测 600~610ms，规格 600ms） |
| `ONESHOT_FINISH_IPC_ONCE` | **PASS**（sleep_enter 2/2、wake_up 1/1，与状态进入次数严格相等） |
| `ASSET_READY_HANDSHAKE` | **PASS** |
| `ASSET_LOAD` | **23 / 23** |
| `AUTONOMOUS_BEHAVIOR_ENGINE` | **PASS**（12/12 单元 + e2e 状态流转全绿） |
| `WINDOW_BOUNDS_ACTUAL_MOVEMENT` | **PASS**（17 次 setBounds，位移与日志 0 偏差） |
| `DRAG_COMPATIBILITY` | **NOT_GUI_VERIFIED**（R113 拖拽核心 9/9 区块逐字未改；真实鼠标需 Mac 真机） |
| `DEBUG_OVERLAY_REMOVED` | **true** |
| `ORIGINAL_B_PRESERVED` | **true** |
| `R113_DRAG_CORE_PRESERVED` | **true**（逐字 diff 证明） |
| `ENGINEERING_GATE` | **PASS** |
| `READY_FOR_MAC_MANUAL_ACCEPTANCE` | **true** |
| `MAC_REAL_GUI_ACCEPTANCE` | **PENDING** |
| `V0_0_RELEASE_STATUS` | **NOT_FROZEN** |
| `V0_1_DEVELOPMENT` | **NOT_AUTHORIZED** |

---

## 二、P0-1 角色裁切与缩放

### 2.1 先复现 GPT 的裁切数据（不是先改代码）

`08_R144_layout_builder.py` 用**真实 PNG** + **真实运行时几何公式**复现 R141 遗留算法的裁切：

| 动作 | GPT 报告 | 本轮实测（遗留算法） | 判定 |
|---|---|---|---|
| idle（compact） | 4.7%~5.1% | **4.70%~5.05%** | 属实 |
| walk_left / walk_right | 3.7%~4.9% | **3.74%~4.91% / 3.94%~4.90%** | 属实 |
| sleep_enter 坐姿 | 6.7% | **6.73%** | 属实 |
| standard 256×256 | 缩放倍率取 1.0 | **sc=1.0 → 78.15%~99.31% 被裁** | 比报告更严重 |

遗留算法 = `anchor.set(0.5,0.9)` + `sprite.y = h` + `sc = compact ? w/1024 : 1.0`。
根因：**R138 素材是 1024×1024 且角色只占画布一部分**，把"画布"当成"角色"直接缩放/贴底，必然溢出。

### 2.2 修复算法（`src/sprite_layout.js`，生产与测试共用同一份）

三条硬约束：

1. **全局统一缩放**：`scale = min over 23 帧 of fit`，所有帧共用同一个倍率 —— 禁止逐帧改人物大小来规避裁切。
2. **地面接触线**：每帧内容**底边**都落在同一条屏幕线 `canvasH - margin(4)`，姿态切换时脚底/地面接触点不跳动。
3. **水平参考线**：纹理中心固定落在画布正中，角色不左右漂移。

关键洞察（来自实测）：卧姿帧宽达 **970px**（站姿仅 434px），二者是**同一物理尺寸**（人躺下的长度 ≈ 站立身高 950px）。
因此**必须统一缩放**（缩到能放下最宽的卧姿帧），再按底边对齐地面；卧姿自然显得比站姿"矮"，这正是物理真实。

| 模式 | 画布 | 统一缩放 | 地面线 | 裁切帧 |
|---|---|---|---|---|
| compact | 200×240 | **0.196319** | 236 | **0 / 23** |
| standard | 256×256 | **0.253579** | 252 | **0 / 23** |

### 2.3 三重独立验证（都调生产代码）

| 验证层 | 手段 | 结果 |
|---|---|---|
| L1 素材层 | 自写纯 Node PNG 解码器（zlib，无依赖）解 23 张真实 PNG，逐帧量非透明 bbox | bbox 与 manifest 记录**逐帧一致** |
| L2 算法层 | `tests/r144_layout.test.js` 调 `src/sprite_layout.js` | 23 帧 × 2 尺寸全部在留白内；缩放倍率**唯一**；底边**同一水平线**；缩放取到**最紧可行值** |
| L3 运行时层 | 真实 Electron 内 renderer 自检：用**真实 `PIXI.Sprite.worldTransform`** 把每帧内容 bbox 四角映射到屏幕 | `frames=46 clipped=0 issues=0`，`groundErr=0`（46/46） |

L3 抽样实测（与手算逐位一致）：

```
compact idle[0]        screen=(64.07,49.50)-(137.69,236.00)  inside=true  groundErr=0.0000
compact sleep_enter[1] screen=(4.00,148.44)-(194.43,236.00)  inside=true  groundErr=0.0000   ← 卧姿左边界正好压在 4px 留白
standard idle[0]       screen=(81.60,11.10)-(176.69,252.00)  inside=true  groundErr=0.0000
```

### 2.4 踩坑记录（重要，PixiJS 7.4.3 语义）

- `Matrix.apply` 的入参是 **Point 对象**，不是 `(x, y)`；传数字会报 `Cannot create property 'x' on number`。
- 游离 DisplayObject 调 `updateTransform()` 前必须 `enableTempParent()` / 之后 `disableTempParent()`，否则 `this.parent.transform` 空指针（PixiJS 自己的 `ObjectRendererSystem.render` 就是这么做的）。
- **anchor 作用在顶点层**（`Sprite._calculateVertices` 用 `w1 = -anchor.x * orig.width` 平移四角），**不在 worldTransform 里**。
  故"纹理像素 → 屏幕"必须先减 anchor 偏移：`local = (u - ax*W, v - ay*H)`；`sprite_layout.js` 的公式与之一致。

---

## 三、P0-2 一次性动画结束机制

### 3.1 缺陷

R141 用取模推进帧：`frameIdx = (frameIdx + 1) % meta.frames.length`。
对 `loop=false` 的 `sleep_enter` / `wake_up`，播到末帧后会**跳回首帧**（闪一下第一帧）。

### 3.2 修复（`src/anim_clock.js`，生产与测试共用同一份）

- `loop=true`：正常回卷（循环动画本就该回卷）。
- `loop=false`：**逐帧推进到末帧后停住**，绝不回卷；末帧保持**恰好一个 `frame_ms`** 后回报一次 `animation-finished`。
- **epoch 机制**：切换动作 / 拖拽打断都会让 epoch 自增，旧的完成事件在发出前被校验丢弃 → 过期事件发不出去。

### 3.3 验证

| 验证 | 手段 | 结果 |
|---|---|---|
| 单元 | `tests/r144_oneshot.test.js`（9 项，连续时间推进驱动生产时钟） | 9/9 PASS：末帧停住 / 只报一次 / 保持恰好 600ms / 切走丢弃 / 打断丢弃 / 不越界 |
| 运行时 | 真实 Electron 睡眠场景 | 完成事件次数 **sleep_enter 2/2、wake_up 1/1**（与状态进入次数严格相等） |
| 运行时 | 真实日志时间戳 | 末帧保持 **600~610ms**（规格 600ms，ticker 16ms 精度内），**回卷 0 次** |

---

## 四、P0-3 资源就绪握手

### 4.1 缺陷

R141 在 `did-finish-load` 立刻启动 BehaviorEngine，而 renderer 还在异步加载 23 帧 → 状态机可能在资源就绪前要求切动作。

### 4.2 修复协议

```
renderer: 加载 6 组 23 帧 → 构建布局 → 建 sprite → 发 assets-ready {total, loaded, failed, actions{...}}
main:     收到 assets-ready → asset_gate.evaluateAssetReadiness() 判定
          ├─ 通过 → 启动 BehaviorEngine
          └─ 不通过 → 打印 R144 ASSETS_ERROR 明确报错, 拒绝启动 (拒绝虚假 PASS)
```

- `src/asset_gate.js` 为纯逻辑判定模块，main 与测试调用同一份。
- 重复 `assets-ready` → main 打印 `ASSETS_READY_DUPLICATE` 并忽略，**引擎只启动一次**。
- 20s 看门狗：renderer 迟迟不上报 → `R144 ASSETS_TIMEOUT` 明确报错，不静默等待。

### 4.3 验证

| 场景 | 手段 | 结果 |
|---|---|---|
| 正常 | e2e 真实 Electron | `ASSETS_READY loaded=23/23`（日志行 34）**先于** `behavior engine started`（日志行 37） |
| 缺帧 | e2e 用坏 manifest（路径指向不存在目录） | `R144 ASSETS_ERROR` 已报，**引擎未启动** |
| 慢速加载 | e2e 设 `PET_R144_ASSET_DELAY_MS=5000` | 引擎在资源就绪**之后**才启动，且后续自动切换 2 次（**首次行为切换未丢失**） |
| 重复 ready | e2e 设 `PET_R144_DUP_READY=1` | `ASSETS_READY_DUPLICATE` 被忽略，引擎**只启动 1 次** |
| 单元 | `tests/r144_assets_gate.test.js`（9 项） | 9/9 PASS：缺组 / 0 帧 / 部分失败 / 帧数不符 / 空报告 全部拒绝并给出明确错误 |

---

## 五、P1 真实窗口移动坐标复核

### 5.1 两个真实缺陷

1. **小数位移被系统取整吃掉**：引擎给的是 `30px/s × 33ms ≈ 0.99px/次`，R141 直接 `setBounds(小数)` → 系统取整 → 窗口几乎不动（低速丢步）。
2. **日志记录的是目标坐标而非真实坐标**：R141 的 MOVE 日志写的是 `clamped.x/y`，无法证明窗口真的移动了。

### 5.2 修复

- **小数累计**：`moveRemainder_` 累加小数位移，凑够 1px 才 `setBounds`（Electron 需要整数坐标），余量留到下一拍 → 位移不丢。
- **setBounds 后立即 `getBounds()` 复核**，日志与边界判定全部改用**真实**坐标：
  `R144 MOVE x=<真实x> y=<真实y> target=(..) actual=(..) moved=(..) step=(..) dx=.. blocked=.. state=..`
- **边界判定基于实际窗口位置**：`actualBlocked = (实际位移 == 0)` —— 真正动不了才算撞边。
  （顺带修掉一个 R141 遗留小 bug：起点在屏幕工作区外时，第一步行走会被误判成撞边，导致开局莫名掉头。）
- **初始位置先夹进工作区**，避免上述误判。
- 行为引擎改为按**主进程复核后的真实位移**扣减剩余行走距离（`onMove` 返回 `moved` 时优先采用）。

### 5.3 验证（真实 Electron，17 次 setBounds）

```
MOVE 复核: OK|17|0|0|0|105|0
  17 次 setBounds | actual≠target 0 次 | 真实位移≠请求步长 0 次 | 零步长 0 次 | x 跨度 105px
```

同时观测到 **1 次 edge-turn**（边界判定基于真实位置的直接证据）。
R113 拖拽核心 9 个区块**逐字未改**（`tools/r144_drag_core_diff.py` 对比 `47a7d87`）。

---

## 六、测试汇总

### 6.1 单元测试（38/38 全绿，全部直接 require 生产代码）

| 文件 | 项数 | 结果 | 生产代码 |
|---|---|---|---|
| `tests/r141_behavior_engine.test.js` | 12 | 12 PASS | `src/behavior_engine.js` |
| `tests/r144_layout.test.js` | 8 | 8 PASS | `src/sprite_layout.js` |
| `tests/r144_oneshot.test.js` | 9 | 9 PASS | `src/anim_clock.js` |
| `tests/r144_assets_gate.test.js` | 9 | 9 PASS | `src/asset_gate.js` |

### 6.2 端到端测试（真实启动 Electron，`R144_e2e_test.sh`）

```
R144 e2e 结果: PASS=23 FAIL=0 NOT_VERIFIED=3
```

| ID | 测试项 | 结果 | 证据 |
|---|---|---|---|
| TA1 | 23/23 动画帧路径真实有效 + 6 组动作 | PASS | manifest 逐项实际验证 23/23 |
| TA2 | R138 23 帧角色资产逐字节未变 | PASS | 与 R138 交付清单 SHA256 比对 **23/23 一致** |
| TA3 | A1 母版 SHA256 未变 | PASS | `3344d5fe…22013df` |
| TA4 | R113 拖拽核心代码逐字未改 | PASS | 9/9 区块 diff（对比 `47a7d87`） |
| TA5 | 原候选 B 冻结基线未改变 | PASS | 无已跟踪文件改动 |
| TA6 | 正式运行无调试文字 | PASS | DEV_MODE 默认关闭 + fallback/debug-banner 隐藏 |
| TB0 | Electron 真实启动并产生日志 | PASS | 119 行 |
| TB1 | 六组动画全部加载成功 | PASS | 6 组 loaded，合计 23 帧，failed=0 |
| TB2 | 资源就绪握手顺序 | PASS | ready@行34 < engine@行37 |
| TB3 | **真实 PixiJS 变换矩阵下 23 帧 × 2 尺寸零裁切** | PASS | `frames=46 clipped=0 issues=0` |
| TB4 | 全部帧底边贴同一地面接触线 | PASS | 46/46 帧 `groundErr=0` |
| TB5 | idle 能自动切换 | PASS | 2 次自动切出 |
| TB6 | walk_left / walk_right 状态有效 | PASS | 2 次进入行走状态 |
| TB8 | **窗口坐标复核** | PASS | 17 次 setBounds，0 不一致，0 位移偏差，x 跨度 105px |
| TB9 | 到屏幕边缘自动转向 | PASS | 1 次 edge-turn |
| TB10 | 退出后无定时器/进程残留 | PASS | 引擎已 stop，残留 0 |
| TC1 | 缺帧时明确报错且拒绝启动 | PASS | `ASSETS_ERROR` 已报，引擎未启动 |
| TC2 | 缺帧时 renderer 仍上报事实 | PASS | assets-ready 带错误信息上报 |
| TD1 | 慢速加载：引擎等资源就绪，首次切换不丢 | PASS | ready@行35 < engine@行37，后续切换 2 次 |
| TE1 | 重复 assets-ready 被忽略 | PASS | 引擎只启动 1 次 |
| TF1 | sleep_enter → sleep_loop → wake_up 顺序 | PASS | `SLEEP_ENTER,SLEEP_LOOP,WAKE_UP` |
| TF2 | 一次性动画完成事件每次只发一次 | PASS | sleep_enter 2/2、wake_up 1/1 |
| TF3 | **末帧保持时长符合 frame_ms 且未回卷** | PASS | 3 个样本，保持 600~610ms，回卷 0 次 |
| TG1~TG3 | 真实鼠标拖拽三项 | NOT_GUI_VERIFIED | 需 Mac 真机；引擎层已由单元测试覆盖，R113 核心逐字未改 |

### 6.3 R141 旧套件回归

`R141_e2e_test.sh` 同步更新（MOVE 日志格式随 R144 升级，解析规则由 `R141 MOVE` 放宽为 `R14[14] MOVE`，**产品行为无回归**），结果见 §八。

### 6.4 本轮自查出的"测试脚本自身缺陷"（与产品缺陷分开记录）

| 编号 | 现象 | 判定 | 处理 |
|---|---|---|---|
| S1 | SHA256 比对报 23 帧"缺失" | **测试脚本缺陷**（按 basename 找文件，未走 action 子目录） | 改为遍历目录树 |
| S2 | renderer 自检无输出 | **测试脚本缺陷**（`updateTransform` 未走 temp-parent、anchor 偏移漏算） | 按 PixiJS 7.4.3 真实语义修正 |
| S3 | wake_up 完成事件 0 次 | **测试脚本缺陷**（观测到 WAKE_UP 即杀进程，动画还没播完） | 等待 6s 让一次性动画自然结束 |
| S4 | MOVE 复核 NOLOG | **测试脚本缺陷**（随机行为下该次恰好连睡两次没走） | 加 `--sleep-probability` 开关，行走/睡眠拆成两个确定性场景 |

以上 4 项均为**验收脚本自身**的问题，**产品代码未因此放宽任何断言**。

---

## 七、代码变更清单

| 文件 | 变更 | 说明 |
|---|---|---|
| `src/sprite_layout.js` | **新增** | 布局算法（统一缩放 + 地面线对齐），生产与测试共用 |
| `src/anim_clock.js` | **新增** | 帧推进时钟（末帧停住 / epoch 作废），生产与测试共用 |
| `src/asset_gate.js` | **新增** | 资源就绪判定，生产与测试共用 |
| `src/renderer.js` | 改 | 布局应用、逐帧地面线对齐、one-shot 走 anim_clock、assets-ready 上报、R144 边界自检 |
| `src/main.js` | 改 | 握手门控（引擎延后到 assets-ready）、setBounds 后 getBounds 复核、小数累计、边界按真实位置判定、初始位置夹紧、`--sleep-probability` 开关 |
| `src/behavior_engine.js` | 改 | 按主进程复核后的**真实位移**扣减剩余距离（仅在 `onMove` 返回 `moved` 时生效，不影响既有 12 项单测） |
| `assets/character_R141_manifest.json` | 改 | 新增 `layout` 段（逐帧 bbox / 留白 / 规则说明），**23 帧路径一字未改** |
| `tests/*` | 新增 | 3 个 R144 测试 + 1 个纯 Node PNG 解码器 |
| `tools/*` | 新增 | 布局探针、拖拽核心 diff 器 |
| `08_R144_layout_builder.py` | 新增 | 布局构建器 + 遗留算法复现器 |
| `R144_e2e_test.sh` | 新增 | 23 项端到端测试 |
| `R141_e2e_test.sh` | 改 | MOVE 解析随日志格式同步 |
| `C2_Mac人工验收.command` | 改 | R144 版真机验收入口（新增渲染完整性观察项） |

**未改动**：R138 的 23 张 PNG（SHA256 23/23 一致）、A1 母版、R113 拖拽核心（9/9 区块逐字一致）、原候选 B 冻结基线。

---

## 八、交付与验收

- Git commit：见 `docs/R144_DELIVERY_INDEX.md`
- 轻量审查包：`character_animation_R144_review.zip`（SHA256 见同名 `.sha256` 文件）
- 备份：`backup/V0.0_backup_<ts>_r144.zip`
- **Mac 真机验收入口**：`candidates/candidate_b_c2/C2_Mac人工验收.command`（双击即用；`fast` 参数加速）

### 仍需 Mac 真机确认的 3 项（`NOT_GUI_VERIFIED`）

1. 用户拖拽期间自动行为暂停（真实鼠标）
2. 松开拖拽后自主行为恢复（真实鼠标）
3. 真实鼠标拖拽窗口跟随（R113 已由用户验证；本轮核心代码逐字未改，但未重测）

### 建议真机观察重点（R144 新增）

- 角色**完整显示**：脚底不被窗口边缘切掉，睡觉躺下时整段身体在窗口内。
- 姿态切换时**角色不跳**：站 → 坐 → 躺 → 起，脚底始终贴在同一条地面线上。
- 一次性动画**不闪回首帧**：入睡/醒来动画播完后停在末帧，不会突然闪回第一帧。
- 行走时桌面位置**平滑移动**（低速不再原地踏步）。

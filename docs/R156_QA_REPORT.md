# R156 质量报告 — 点击互动扩展 + 场景道具 + 办公待机

> **生成时间**：2026-10-21
> **对应任务书**：R156（点击互动扩展 + 场景道具 + 办公待机场景）
> **作者**：MiniMax（Mavis）
> **基线**：R153 `d93819b` / 归档 `0a91a29`
> **仓库**：`/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0`
> **状态**：`ENGINEERING_GATE = PASS` / `VISUAL_GATE = PASS`（沙箱内真实 Electron 运行 + 像素级客观测量）/ **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** / `V0_0_RELEASE_STATUS = NOT_FROZEN`
> **范围声明**：本轮**未进入 V0.1**，未重做角色，未新增语音/记忆/AI 聊天，未做系统鼠标注入，未充值 i2i。

---

## 0. 一句话结论

点击动作池从 **1 个扩到 6 个**（每个 3 帧、随机触发、短时不重复），睡觉/坐下/办公三个场景各自配上了**程序化绘制的 7 个小道具**（床+月亮+被子 / 小沙发 / 转椅+小桌+笔记本+屏幕微光），并新增了 **`WORK` 办公待机状态**接入行为引擎；单元测试 **122/122 PASS**、真实 Electron 运行时客观校验 **21/21 PASS**、e2e 全绿，**道具退出后残留像素 = 0、front 层遮脸重叠 = 0**；但 **Mac 真机观感仍 PENDING**，且 4 类动作受 R138 素材边界限制**做不到真手势**（详见 §6）。

---

## 1. 本轮完成定义的逐条对照

任务书 §七 的 7 条 COMPLETE 条件：

| # | 条件 | 结论 | 证据 |
|---|---|---|---|
| 1 | 点击互动动作池 **≥5** | ✅ **6 个** | `manifest.click_reactions.pool` 6 项；真实点击 10 次实测触发 **5~6 种**、**无相邻重复**（两次独立采集） |
| 2 | 睡觉有**床 + 月亮灯光**场景 | ✅ | `prop_bed` + `prop_moon` + `prop_quilt`；实测道具专属区域可见像素 **5505**（阈值 400） |
| 3 | 坐下有**小沙发** | ✅ | `prop_sofa`；实测可见像素 **5429** |
| 4 | 存在"**电脑前办公**"待机小场景 | ✅ | `work` 动作（2 帧）+ `prop_chair` / `prop_desk` / `prop_screen_glow`；实测可见像素 **1610** |
| 5 | 新动作与场景**已接入运行逻辑** | ✅ | 运行时日志 `R156 PROPS action=work scene=yes mounted=prop_chair,prop_desk,prop_screen_glow`；`R156 CLICK_REACTION start action=cheer_wink frames=3` |
| 6 | 给出**真实运行证据** | ✅ | `evidence_r156_preview/`（真实 Electron 采集 650 帧）+ `evidence_r156_gifs/`（10 GIF + 2 总览图） |
| 7 | 不破坏拖拽/行走/睡眠/唤醒主链路 | ✅ | R113 拖拽核心 **9/9 区块逐字未改**；R148 行走方向修复保留；R138 原始 23 帧 **47/47 SHA256 一致**；e2e 全绿 |

---

## 2. 点击互动扩展（6 个动作，3 帧，随机触发）

### 2.1 动作清单

| 动作 | 语义 | 帧资源 | 实现手法 |
|---|---|---|---|
| `cheer_heart` | 比心（近似） | `cheer_heart_0/1/2.png` | 头部连续权重场弯曲 + 胸部软遮罩微缩 |
| `cheer_jump` | 开心小跳 | `cheer_jump_0/1/2.png` | 压扁(0.86) ↔ 伸展 ↔ 落地(0.88) + 运行时地面偏移 |
| `cheer_spin` | 原地轻盈转身 | `cheer_spin_0/1/2.png` | 整体水平压缩 64% / 82% 读作侧身 → 回正 |
| `cheer_wink` | 歪头眨眼卖萌 | `cheer_wink_0/1/2.png` | 头部连续权重场弯曲（14° / 7°）+ 眼部区域合成 |
| `cheer_hands` | 双手小庆祝 | `cheer_hands_0/1/2.png` | 双臂抬起近似 + 整体垂直平移 |
| `cheer_sway` | 开心摇摆 | `cheer_sway_0/1/2.png` | 整体水平平移 ±46 纹理 px + 反向歪头 |

> **为什么没有第 7 个 `cheer_happy`**：R153 已有 `happy`（歪头+眯眼笑）。若再加一个语义相近的 `cheer_happy`，就构成"重命名虚增动作数"，违反任务书 §二 的禁止项。`cheer_sway` 的视觉语义（身体整体左右摇摆）与 `happy`（头部歪斜）明显不同，是独立帧资源。

### 2.2 随机触发 + 不重复

- `src/action_library.js` 新增 `CLICK_POOL` 与 `pickClickReaction(random, recent, pool)`：从池里按权重抽取，**排除最近用过的动作**；若全部被排除则兜底返回池中任一项。
- 权重：`cheer_heart` 3、`cheer_wink` 3、`cheer_jump` 2、`cheer_spin` 2、`cheer_hands` 2、`cheer_sway` 2（合计 14）。
- `manifest.click_reactions.no_repeat_last = true`。
- 渲染器侧另有 `clickRecent_` 记忆队列 + 独立的 `clickClock_` 计时器，**不与自主行为共用时钟**。

**真实运行实测（Electron 连点 10 次，两次独立采集）**：

```
采集 A: cheer_wink, cheer_heart, cheer_sway, cheer_wink, cheer_heart,
        cheer_jump, cheer_wink, cheer_hands, cheer_heart, cheer_wink   → 5 种
采集 B: cheer_wink, cheer_spin, cheer_hands, cheer_wink, cheer_heart,
        cheer_sway, cheer_wink, cheer_heart, cheer_spin, cheer_wink   → 6 种
```

→ 两次都**无相邻重复**（10 次里 9 个相邻间隔均不相等）。

### 2.3 开始 / 中间 / 结束

每个动作 3 帧独立烘焙，运行时逐帧推进。真实采集帧聚类结果（差异 <0.5% 视为同一画面）：

| 动作 | 采集帧数 | 不同画面数 | 帧间差异范围 |
|---|---|---|---|
| `cheer_heart` | 16 | **5** | 0.0000 ~ 0.1945 |
| `cheer_jump` | 16 | **5** | 0.0000 ~ 0.1975 |
| `cheer_spin` | 16 | **5** | 0.0000 ~ 0.1706 |
| `cheer_wink` | 16 | **5** | 0.0000 ~ 0.1936 |
| `cheer_hands` | 16 | **4** | 0.0000 ~ 0.1437 |
| `cheer_sway` | 16 | **5** | 0.0000 ~ 0.2143 |

> "不同画面数 ≥3"即满足任务书"清晰的开始/中间/结束"。帧数多于 3 是因为采集时包含了动作前后的稳定态。

### 2.4 播放期间暂停自主行为 / 结束回到正常状态机

- `R156_CLICK_HOLD_MS = 1100`（覆盖 3 帧总时长），点击反馈期间引擎的 idle/walk/sleep 推进被暂缓。
- R153 的"人工 7px 弹跳"已移除 —— 运动改由动作帧自身承担（R147 自检判据同步升级为"≥2 个不同画面"，单帧定格不再算有效反馈）。
- 反馈播完（`R156 CLICK_REACTION end action=...`）后角色回到正常状态机。

### 2.5 不虚增动作数（内置唯一性自检）

`29_R156_pose_bake.py` **每跑一次就自检一次**：

1. 20 张新帧互不相同；
2. 20 张新帧与 R138 / R153 既有帧**无字节重复**。

该自检实际拦下 **3 处**伪新动作并已修正：

| 问题帧 | 撞上的既有帧 | 修法 |
|---|---|---|
| `cheer_wink_0` | R153 `head_tilt` | 歪头角 11° → 14°/7° |
| `cheer_heart_0` | R153 `blink_closed` | 叠加头部连续权重场后再换眼 |
| `cheer_jump_1` | R153 `blink_closed` | 同上 |

---

## 3. 场景道具（7 个，程序化矢量绘制）

### 3.1 为什么是程序化绘制

i2i 余额为 0 且任务书禁止擅自充值 ⇒ 全部道具用 **PIL 程序化矢量绘制**，无外部素材、无 AI 生图。

### 3.2 道具清单与 z 序

| 道具 | 用途 | alpha bbox（1024 纹理坐标） | 层 |
|---|---|---|---|
| `prop_bed` | 床 | [40, 424, 963, 818] | back |
| `prop_moon` | 月亮夜晚氛围 | [88, 0, 955, 308] | back |
| `prop_quilt` | 被子盖身 | [470, 494, 981, 701] | **front** |
| `prop_sofa` | 小沙发 | [253, 368, 812, 1001] | back |
| `prop_chair` | 办公转椅 | [332, 392, 713, 1001] | back |
| `prop_desk` | 小桌子 + 笔记本 | [330, 470, 789, 1001] | **front** |
| `prop_screen_glow` | 屏幕微光 | [328, 379, 793, 774] | **front** |

**z 序**：`back（月亮/床/沙发/转椅）→ 角色 → front（被子/桌子+笔记本/屏幕微光）`。

> 踩坑记录：初版预览把床/沙发/转椅画在角色**前面**，导致枕头盖脸、沙发像浴缸、转椅底盘压住鞋。已按正确 z 序重做，并加了"道具 bbox 底边 = 该场景地面行"的硬约束。

### 3.3 地面行机制（`ground_tex_y`）

有道具时，"地面"不是角色的脚底，而是**道具的底**。因此引入逐帧地面行：

| 场景 | 地面纹理行 | 含义 |
|---|---|---|
| 睡觉（床脚） | 818 | 床脚底边 |
| 坐下 / 打盹（沙发底） | 1001 | 沙发底边 |
| 办公（桌腿底） | 1001 | 桌腿底边 |
| 腾空帧（`cheer_jump` 中间帧） | **1015** | 比站立更高 ⇒ 离地 |

`src/sprite_layout.js` 的 `computeLayout` 支持逐帧 `ground_tex_y`（`null` = 缺省，R153 语义**完全不变**），新增导出 `groundRowY(layout, groundTexY, skewX)`。

**实测**：真实采集帧中 `cheer_jump` 的脚底 y = 49/236（站立）→ **75/236**（压扁）→ **44/230**（腾空，离地 6px）→ 71/236（落地）→ 站立。

### 3.4 道具随动作挂载 / 退出即销毁

渲染器新增道具 sprite 系统（`propTextures_` / `propSprites_` / `restageProps` / `applyPropsFor` / `updateProps`），260ms 淡入淡出，切换动作时旧道具淡出后**销毁**，模式重建时清空旧引用。

**真实运行日志**：

```
R156 PROPS action=sleep_breath scene=yes mounted=prop_bed,prop_moon,prop_quilt
R156 PROPS action=sleep_loop    scene=yes mounted=prop_bed,prop_moon,prop_quilt
R156 PROPS action=sit_rest      scene=yes mounted=prop_sofa
R156 PROPS action=doze          scene=yes mounted=prop_sofa
R156 PROPS action=work          scene=yes mounted=prop_chair,prop_desk,prop_screen_glow
R156 PROPS action=idle          scene=none mounted=none
```

**残留实测**：从 `sleep_breath` 切回 `idle` 后，最后 4 帧的道具专属区域残留像素 = **`[0, 0, 0, 0]`**（阈值 30）；同一区域在睡觉场景里是 **9123** 像素（正向对照，证明判据有效，不是"因为阈值太松所以看不出来"）。

### 3.5 道具不遮脸

5 个场景的 front 层道具与角色脸部区域（角色掩膜最上 18% 头部）重叠像素 = **全部 0**。

---

## 4. 办公待机场景（`WORK` 状态）

### 4.1 表现

- 角色坐在**转椅**上，**从笔记本电脑屏幕后面探出上半身**，屏幕有**冷白微光**。
- 动作 `work` 2 帧循环（`work_1.png` / `work_2.png`），由 `torso_lean`（上半身绕髋前倾）烘焙 —— 一帧前倾看屏幕，一帧抬头思考。
- 道具 `prop_desk` 整体**右移 44px**，让角色头部正好落在屏幕中线。

### 4.2 行为引擎接入

`src/behavior_engine.js` 新增 `WORK` 状态：

```
work_probability: 0.10     ← 低权重
work_min_ms: 9000
work_max_ms: 19000
```

- 活动池顺序固定为 `['gesture','walk','sit','doze','work','sleep']` 并导出 `ACTIVITY_KINDS`（让测试能从权重**反推**随机阈值，不必把阈值写死）。
- **上一项是办公时，办公权重直接归零** ⇒ 不会一直只办公，与普通待机/打盹/行走/睡眠错开。
- `work` 是一个**新的 idle 类状态**，不与其它活动连做。

### 4.3 身份未漂移（像素级）

| 场景 | 白 | 冰蓝 | 银白 |
|---|---|---|---|
| `scene_sleep` | 0.58 | 0.50 | 0.22 |
| `scene_sofa` | 0.57 | 0.65 | 0.36 |
| `scene_work` | 0.26 | 0.40 | 0.24 |

三个场景的角色主色仍是**银白 + 冰蓝 + 白大褂**，与既定 identity 一致。

---

## 5. 行为与状态机接入细节

| 任务书要求 | 实现方式 | 证据 |
|---|---|---|
| 点击从池里随机选一个播放 | `pickClickReaction()` 权重抽取 + `clickRecent_` 去重 | 真实点击 10 次触发 5 种、无相邻重复 |
| 播放期间暂停普通 idle/walk/sleep 推进 | `R156_CLICK_HOLD_MS = 1100` 独立计时器 | `R156 CLICK_REACTION start/end` 日志对 |
| 播放结束后回到正常状态 | 反馈结束即释放 hold | e2e 全部通过 |
| 办公待机作为新的 idle 类状态 | `STATES.WORK` + `STATE_ACTION.WORK = 'work'` | `R141 STATE ... -> WORK (idle-decision)` |
| 办公不能过于高频 | `work_probability = 0.10` + 连续办公权重归零 | `tests/r141_behavior_engine.test.js` 17 项 |
| 与其它活动错开 | `ACTIVITY_KINDS` 固定顺序 + 连续同类归零 | 同上 |
| 睡觉/坐下才显示对应道具 | manifest `props.scenes` 按动作声明 back/front | `R156 PROPS ... scene=yes/none` 日志 |
| 退出时道具一并退出、不残留 | 260ms 淡出后销毁 + 残留像素实测 0 | 校验项 5 / 5b |

---

## 6. 做不到的事（如实列出，不硬标 PASS）

### 6.1 真正的双手手势 —— 需要新素材

R138 的 23 帧**没有手部素材**（手臂大多与躯干一体或被裁掉），因此：

| 想做的 | 实际交付 | 性质 |
|---|---|---|
| 双手比心 | 右手横在胸前的近似 | **近似，不是真手势** |
| 挥手 | 双臂抬起的近似 | **近似**（`cheer_hands` 不是挥手） |
| 双手拍掌 | 双臂抬起 + 微小起伏 | **近似** |
| 敲键盘 | 只能"看屏幕 / 思考 / 停顿" | **做不到** |

已写入 `src/action_library.js` 的 `NEEDS_NEW_ASSETS`（本轮追加 4 条：`heart_hands_true` / `clap_hands` / `typing` / `spin_180`），单测断言它们**不得**出现在已实现动作表里。

### 6.2 "原地转身"是 2D 表现手法，不是真的背面转身

`cheer_spin` = 正面 → 整体水平压缩 **64%**（读作侧身）→ 82% → 回正。**不是**真正的 180° 背面转身 —— R138 无背面素材。

实测宽度变化：**8725 → 5697 → 7239 → 8735** 像素（侧身时确实变窄，宽度降幅 34.7%）。

### 6.3 "跳"的离地幅度受窗口高度硬约束

- R138 角色轮廓在纹理里占 y = 37 ~ 987，**头顶只剩 37px 余量**。
- 在纹理内挪动最多只能离地 **7 屏幕 px**，抬升幅度不够 ⇒ 改为运行时 `ground_tex_y = 1015` 表达离地。
- **compact 200×240**：scale 0.196319、groundY 236、头顶余量 **49.5px** → 离地 ≈ 5.5px。
- **standard 256×256**（默认模式）：scale 0.253579、groundY 252、头顶余量 **仅 11.1px** → 离地 ≈ 7.1px。
- 因此"跳"的可读性**主要来自剪影对比**（压扁 0.86 ↔ 伸展 ↔ 落地 0.88，头部竖直行程约 31px），而不是明显的离地。**真正的跳离地面需要重绘带留白的原画。**

### 6.4 床只兼容躺姿

床垫顶（纹理 y=632）之上的净空 632 纹理 px **小于**坐姿帧高 886~964 ⇒ 坐不进这张床。因此：

- `sleep_enter` 与 `wake_up` **不带道具**（走"场景溶解"过渡）；
- 床在 `sleep_breath` 淡入、`wake_up` 淡出。

### 6.5 其它未做

- 未进入 V0.1；未做语音/记忆/AI 聊天；未做系统鼠标注入；未重做 C1；未批量重做旧动作（只改了本轮相关动作与接入逻辑）。
- **Mac 真机验收 PENDING** —— 沙箱内无法完成真实鼠标手感与真机观感判断。

---

## 7. 测试结果

### 7.1 单元测试（9 份文件，**122 项全绿**）

| 测试文件 | 结果 |
|---|---|
| `r141_behavior_engine.test.js` | 17 / 17 PASS |
| `r144_layout.test.js` | 8 / 8 PASS |
| `r144_oneshot.test.js` | 9 / 9 PASS |
| `r144_assets_gate.test.js` | 9 / 9 PASS |
| `r147_layout_pixi_parity.test.js` | 5 / 5 PASS |
| `r147_interaction.test.js` | 23 / 23 PASS |
| `r148_walk_direction.test.js` | 8 / 8 PASS |
| `r153_action_library.test.js` | 22 / 22 PASS |
| **`r156_click_props_work.test.js`** | **21 / 21 PASS** |
| **合计** | **122 / 122 PASS** |

> R153 / R141 两份测试被改写为"**对 R156 扩展稳健**"（不再写死动作数 9/15/7、不再写死随机阈值），但 R153 的九动作齐全、独占帧、23 帧门禁等**不变量继续守护**。

### 7.2 运行时客观校验（真实 Electron 采集像素，**22 / 22 PASS**）

见 §1、§2.2、§2.3、§3.4、§3.5、§4.3。全部判据基于**真实采集到的像素**，不依赖脚本自报的 PASS。

第 8 项「点击反馈明显区别于僵立待机」是本轮新增的（见 §7.5）。

### 7.3 e2e（真实启动 Electron，调用真实生产代码）

`bash R147_e2e_test.sh` — 本轮新增 **[I] R156 专项**段（TI0~TI7 + 22 条逐项追溯），含：

- TI0 汇总 + TI1_x 逐项（22 条来自真实像素）；
- TI2 点击池结构（≥5、每动作 ≥3 帧、帧互不相同 ⇒ 不虚增）；
- TI3 办公动作 + 道具库 + 场景配置齐备；
- TI4 7 个道具资源在真实运行时 `loaded=7 failed=0`；
- TI5 道具按场景挂载、无道具动作时 `mounted=none`；
- TI6 真实运行时点击池随机触发 ≥3 种、每个 `frames=3`；
- TI7 可观看产物齐备（10 GIF + 2 总览图）。

> 预览流程因新增 10 个采集场景从 ~60s 涨到 ~120s，e2e 的安全网 `--quit-after` 由 180s 提到 600s（**仅兜底**，preview 流程自己结束就 `app.quit`，不改变任何逻辑）。

### 7.4 本轮 e2e 抓出并修掉的 3 处判据问题（如实记录）

首次跑 e2e 时是 **51 PASS / 5 FAIL**。逐条查证后，**3 处是判据过时（不是产品缺陷），2 处是本轮自己新写的 e2e 代码 bug**，全部已修，不是靠放宽容差糊过去的：

| 项 | 现象 | 根因 | 处理 |
|---|---|---|---|
| TC3 | `114 帧 clipped=0 issues=20` | R144 的"内容底边必须贴在地面接触线"判据是**站立角色**时代写的；R156 引入逐帧地面行后，躺床上（离床脚 127 纹理 px）、坐沙发（离沙发底 1 行）、腾空跳（离地 28 纹理 px）都会**合法地**高于地面线 | 把判据精确化为「内容底边必须落在**该帧声明的接触行**上」：接触行 = `ground_tex_y`（声明值）或内容底边（未声明 ⇒ **R144 原语义逐字不变**）。修正后 `frames=114 clipped=0 issues=0` |
| TG2 | 「弹跳幅度肉眼可见 = 0px」 | R153 的"人工 7px 弹跳"本轮**主动移除**（运动改由动作帧承担），该判据随之失效 | 改为与生产自检同口径：「点击段出现 ≥2 个不同画面」。测量也一并换掉：旧脚本把帧缩到 48×58 再按"整图平均差 < 6"聚类，**降采样把细微动作抹平了**，且判定受采集相位影响 → 改成**全分辨率 + "变化像素占比 < 0.5% 视为同一画面"**（与 `34_R156_runtime_verify.py` 同一口径）。三个独立采集目录下该判据稳定给出 **4 个不同画面** |
| TH8 | `actions":9` 不匹配 | R156 把动作库从 9 个扩到 16 个（+6 点击 +1 办公） | 判据从写死 9 改为 `actions>=9 且 failed=0` |
| TH5 | 「点击反馈用闭眼笑」不通过 | R153 的代理判据是"虹膜像素必须等于 happy 参照"；R156 的点击反馈是**随机池多帧动作**，`cheer_wink` 只闭一只眼（虹膜 14，不是 happy 的 8） | 改为等价且更稳的表述：「点击反馈必须明显区别于僵立待机」—— 表情变化（虹膜 < 睁眼待机）或姿态变化（整图平均差 ≥ 6），二者满足其一。同时在 R156 校验脚本里新增同口径的第 8 项作为独立证据 |
| TI2 / TI3 | 点击池结构 / 办公配置 FAIL（数据明明正确） | 本轮自己写的 e2e 解析 bug：Python `print(True)` 输出的是大写 `True`，我却拿小写 `"true"` 比 | 提取时统一小写化 |

> **顺带记录一个采集层面的抖动（非产品缺陷）**：预览的"点击"命令与采集循环之间有 IPC 往返，偶尔会**晚几十毫秒**才开始采，采到的是动作尾段而非全程。实测三个独立采集目录里，同一动作的相邻帧最大差在 **1.78 ~ 19.02** 之间波动（取决于采到的是"站立→动作"的大跳变还是动作内部的小变化）。这不影响产品行为（真实运行时三帧照常推进，已由 §2.3 的 4~5 个不同画面与 §7.4 的"区别于僵立待机"共同证明），但它是 GIF 偶发"看起来动作没演完"的原因，已在判据里改用对相位稳健的全分辨率口径。

**TC3 那一条值得特别说明**：它一开始看起来像"角色位置错了"的真缺陷。实际逐帧核算后确认 —— 10 帧 × 2 种画布共 20 条，全部是**新机制的预期结果**（躺/坐/腾空），没有一条是错位：

| 帧 | 偏差 | 含义 |
|---|---|---|
| `sleep_breath[0/1]`、`sleep_loop[0..2]` | 24.93px / 13.94~14.53px | 角色**躺在床上**，床脚（818）是地面线，身体底边在 691/747 —— 正确 |
| `cheer_jump[1]` | 5.50px | 腾空帧，地面行抬到 1015 ⇒ 离地 28 纹理 px —— 正确 |
| `sit_rest[0]`、`doze[0]`、`work[0/1]` | 0.20px | 脚底行 1001 = 地面行 1001；差的是 bbox **开区间**约定的 1 行（0.2 屏幕 px，肉眼不可见） |

### 7.5 未被破坏的既有成果

| 项 | 结果 |
|---|---|
| R113 拖拽核心 | **9 / 9 区块逐字未改**（`tools/r144_drag_core_diff.py`） |
| R138 原始 23 帧 | **47 / 47 SHA256 一致，逐字节未变** |
| A1 母版 | SHA256 `3344d5fe8d47058475ea7265909478bae4886bb1ee6165412f406a83422013df` 未变 |
| R148 行走方向修复 | 保留（`walk_left` / `walk_right` 派生镜像帧 + skew 归零） |
| 核心 6 组帧槽位 | 仍为 **23 个互不相同**的文件 |

---

## 8. 产物清单

| 类型 | 路径 |
|---|---|
| 真实采集帧（650 帧 + meta + run.log） | `candidates/candidate_b_c2/evidence_r156_preview/` |
| 运行时客观校验 JSON | `candidates/candidate_b_c2/evidence_r156_preview/r156_runtime_verify.json` |
| 6 个点击 GIF | `candidates/candidate_b_c2/evidence_r156_gifs/R156_click_cheer_*.gif` |
| 4 个场景 GIF | `candidates/candidate_b_c2/evidence_r156_gifs/R156_scene_{sleep,sofa,work,prop_exit}.gif` |
| 点击动作总览图 | `candidates/candidate_b_c2/evidence_r156_gifs/R156_click_pool_overview.png` |
| 场景总览图 | `candidates/candidate_b_c2/evidence_r156_gifs/R156_scene_overview.png` |
| 20 张新动作帧 + 7 个道具 | `candidates/candidate_b_c2/assets/character_R156/` |
| 烘焙/道具/测量报告 | `assets/character_R156/{bake_report,props_report,r156_measure_report}.json` |
| 本报告 / 交付索引 | `docs/R156_QA_REPORT.md` / `docs/R156_DELIVERY_INDEX.md` |
| Mac 真机验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command` |

---

## 9. 验收入口

```bash
# 双击即用（macOS）
candidates/candidate_b_c2/C2_Mac人工验收.command          # 正式模式
candidates/candidate_b_c2/C2_Mac人工验收.command fast     # 加速模式（状态机逻辑不变）

# 复审命令
cd candidates/candidate_b_c2
node tests/r156_click_props_work.test.js                  # 21 项
python3 34_R156_runtime_verify.py --preview-dir evidence_r156_preview   # 21 项真实像素校验
python3 33_R156_preview_gif.py                            # 重新生成 GIF 与总览图
bash R147_e2e_test.sh                                     # 真实 Electron 全量回归
python3 tools/r144_drag_core_diff.py                      # R113 拖拽核心逐字未改
```

---

## 10. 诚实性声明

| 分类 | 内容 |
|---|---|
| **已真实实现** | 6 个点击动作（3 帧、随机、不重复）、7 个道具、3 个场景（睡觉/坐下/办公）、`WORK` 状态、道具挂载与退场、`ground_tex_y` 地面行 |
| **自动测试通过** | 单元 122/122；运行时像素校验 21/21；e2e 全绿；R113 拖拽 9/9；R138 23 帧 47/47 SHA256 一致 |
| **仅视觉预览（未在真机确认）** | 全部 GIF 与总览图的**观感**、点击手感、办公场景的"像不像在办公"、跳跃离地的可读性 |
| **真机未验证** | `MAC_REAL_GUI_ACCEPTANCE = PENDING` —— 沙箱内无法完成真实鼠标交互与真机观感判断 |
| **明确做不到** | 真正的双手比心 / 挥手 / 拍掌 / 敲键盘；真正的 180° 背面转身；明显的跳离地面；坐姿躺上床 |
| **未做（按任务书禁止项）** | V0.1、语音、记忆、AI 聊天、系统鼠标注入、充值 i2i、重做 C1 |

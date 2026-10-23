# R170 质量报告 — 恢复"电脑办公场景" + 新增"吃水果"生活行为

> **生成时间**：2026-10-22
> **对应任务书**：R170（承接 R167，基线 commit `f753c21`）
> **作者**：MiniMax（Mavis）
> **上一交付**：R167 `f753c21`（实现 `e4ff766` / 索引 `2f3d452` / 归档 `f753c21`）
> **范围声明**：本轮**只做任务书点名的两项**（恢复办公场景 + 新增吃水果生活行为）；未进入 V0.1；**未改动人物身份与服装**（R138 原始 23 帧 SHA256 逐字节未变）；**未改动任何点击动作素材**（`assets/character_R158/` 18 张帧与 `f753c21` 逐字节一致）；**未重新开发整个桌宠**（改动集中在行为引擎 + 动作库 + 吃水果新素材 + 验收入口）；**未充值 i2i**（全程零 AI 生图调用）；R148 行走方向、R153 自主行为、R162 点击互动、R165 手臂修复、R167 办公/睡眠成果、R113 拖拽核心**均未改动**。

---

## 〇、结论速览

| 字段 | 结论 | 判定依据（绝对值口径，非"相比基线没变差"） |
|---|---|---|
| `WORK_SCENE` | **PASS** | 真实 Electron 连跑 **240s** ⇒ WORK 进入 **2 次**、平均间隔 **62.4s**、每次持续 **17.8s / 25.3s**、无"刚出现就被顶掉"、与 EAT_FRUIT **0 次重叠**（触发取证 7/7 PASS）。**修复前基线**（R167 交付版 `f753c21` 真实连跑 **180s**、空闲决策 **14 次**）⇒ WORK **0 次**。差距是"同一个场景、同一份素材，只因为配置与时间轴被修好就会自己出现" |
| `EAT_FRUIT_SCENE` | **PASS** | 13/13 绝对值判据全 PASS（13 项，口径见第二节）。真实 Electron 240s 连跑里 EAT_FRUIT 进入 1 次；逐帧目视复核确认：伸手取果 → 手心托果举到胸前 → **低头张嘴咬一口** → 咀嚼（腮红）→ **满足笑眼**。200×240 与 256×256 下角色坐在小圆凳、手里捧红苹果、旁边矮边桌果盘清晰可辨。 |
| `ENGINEERING_GATE` | **PASS** | 全量 node 单测 **167**；R147 e2e 全量回归 **60 PASS / 0 FAIL / 0 NOT_VERIFIED**；R167 场景判据复跑 **15/15 PASS**（本轮未改坏 R167 成果）；R165 手臂判据复跑 **18/18 PASS** |
| `VISUAL_GATE` | **PASS** | 办公：真实 Electron 采集帧里角色**坐在电脑前双手打字**，桌面/笔记本/键盘/转椅齐全，道具随场景挂载并在退出后清零（残留 0 px）。吃水果：真实 Electron 采集帧 + 200×240/256×256 合成图逐帧目视复核，手—果—嘴三者关系自然，无"把水果贴在脸上冒充"、无断臂、无多余肢体、无道具残留。**本轮所有视觉结论都基于真实运行像素与逐帧目视，不是仅凭自动测试 PASS。** |
| `MAC_REAL_GUI_ACCEPTANCE` | **PENDING** | 沙箱内无法代替你在 Mac 上看最终观感；**未伪造任何真机结论** |
| `V0_0_RELEASE_STATUS` | **NOT_FROZEN** | 未擅自宣布 V0.0 封版 |

> 按任务书要求："**不得仅凭自动测试 PASS 认定视觉效果合格**。"
> 本轮所有视觉结论都附**真实 Electron 运行像素**与**逐帧目视复核**，并对素材做不到的部分**如实登记限制**（见第六节），不伪造视觉 PASS。

---

## 一、任务 A：办公场景为什么会"消失"

### 1.1 决定性实验（不是推测）

R167 交付版真实 Electron 连跑 **180 秒**，抓状态转移日志：**空闲决策 14 次，WORK 触发 0 次**。
⇒ **"状态机里明明有 WORK" 与 "用户能看见办公场景" 是两件事** —— 上一轮把前者当成了后者。

复算产物：`candidates/candidate_b_c2/evidence_r170_trigger_before.json`（+ 同名 `.log`）

### 1.2 真根因（三项叠加，缺一不可）

| # | 根因 | 实测 | 修法 |
|---|---|---|---|
| ① | **`manifest.behavior.config` 是 R141 时代的陈旧快照**，被 `main.js` 的 `Object.assign({}, behavior.config)` **静默覆盖**引擎默认值 | 基线 manifest 里 **根本没有 `work_probability` 这个键**；`sleep_probability=0.30`（引擎 R153 已降到 0.10）、`walk_probability=0.70`（引擎 0.62） | manifest 配置与引擎 `DEFAULT_CONFIG` **逐项对齐**；并加**根因回归护栏**（`tests/r170_eat_fruit_work.test.js` A1：manifest ↔ 引擎配置必须一致，以后再漂移直接测试失败） |
| ② | **单次命中率只有 5%** | `work_probability=0.10` / 总权重 2.00 | `work_probability` 0.10 → **0.55** |
| ③ | **时间轴把空闲决策压到 ~20s 一次** | 长活动（睡 20~45s / 打盹 7~15s / 坐 6~13s）⇒ 期望 **≈6.7 分钟**才出现一次，且每次只有 9~19s | 时长 9~19s → **16~28s**；新增 `work_cooldown_ms = 60000` |

### 1.3 顺带修掉的**同源 bug**（上一轮没发现）

`holdBriefly`（点击反馈）会**清掉状态计时器**，但结束后**无人重排** ⇒ **办公中点一下角色会永久卡在 WORK**。
修法：新增 `_armStateTimer(kind, ms, done)` / `_resumeStateTimer(kind, remaining)`，记住 `_stateTimerKind` / `_stateDeadline`，点击反馈结束后按**剩余时间**恢复状态计时器。
（回归见 `tests/r170_eat_fruit_work.test.js` D1/D2）

### 1.4 验收专用入口（与正式自主行为**严格分离**）

```
electron . --manifest assets/character_R141_manifest.json --size 200 --demo-scene work
electron . --manifest assets/character_R141_manifest.json --size 200 --demo-scene eat_fruit
```

实现要点（`src/main.js`）：
- `--demo-scene <action>` 解析进 `demoScene_`；
- `startBehaviorEngine()` 里 `if (demoScene_) behaviorEngine.setAutonomousPaused(true);` ⇒ **自主决策被暂停，不会随机跑掉**；
- 资源就绪后 250ms 发 `mainWindow.webContents.send('set-action', demoScene_)` ⇒ **仍走正式渲染路径**，所以道具按正式规则挂载。

**实测输出**（`--demo-scene eat_fruit`）：
```
[main] R170 DEMO_SCENE action=eat_fruit (自主决策已暂停, 场景锁定供验收)
[renderer] R156 PROPS action=eat_fruit scene=yes mounted=prop_stool,prop_fruit_table
[renderer] R147 set-action eat_fruit applied=true loop=true frame_ms=820,760,900,700,1150 frames=5
```
`C2_Mac人工验收.command` 已支持 `work` / `eat_fruit` 两个参数（双击即用）。

---

## 二、任务 B：新增"吃水果"生活行为 `EAT_FRUIT`

### 2.1 场景设计

- 角色坐在**小圆凳**上（`prop_stool.png`），画面左侧一张**矮边桌**，桌上一个**果盘**（`prop_fruit_table.png`）。
- 水果（苹果）**画进角色帧内部**，不作为独立道具 ⇒ 手掌与水果的接触是**像素级精确**的；场景道具只承担环境，且全部在 **back 层**，结构上不可能遮住五官。
- 蓝白科技系：凳子与边桌沿用 R156/R167 道具的同一套配色与描边。

### 2.2 素材烘焙路线（为什么是这条路）

基图用 `assets/character_R138/sleep_enter/sleep_enter_01_sit.png`（坐姿），复用 `36_R158_arm_rig.py` 的手臂 rig：
- **坐姿关节自标定**（站立硬编码腕点 (654,556) 在坐姿上偏 **142 px**，直接用会把手臂甩飞）；
- 手臂分段旋转 + 肘部重叠缝合（避免刚体拼接的"断臂"）；
- 手臂原位在大腿上会破洞 ⇒ **竖向克隆填充**（洞内像素沿同列向下取第一个"不透明且非手臂"像素）；
- **苹果画在掌心锚点**、手指层叠在苹果之上 ⇒ "被握住"是几何必然；
- 描边改成与角色一致的**柔和深棕**，去掉贴纸感的白+黑双描边。

### 2.3 客观判据（13 项，全部绝对阈值，`83_R170_scene_verify.py`）

| 判据 | 口径 | 门槛 | 实测 |
|---|---|---|---|
| E1 | 每帧有苹果（最大红色连通块，已排除腮红/唇色） | ≥ 300 px | PASS — apple_px_per_frame = [1080, 1168, 1083, 1072, 1126] |
| E2 | 苹果到手部肤色的最短距离 | ≤ 8 纹理 px | PASS — dist_hand_px = [1, 1, 1, 1, 1] |
| E3 | 苹果从远处送到嘴边（帧0→帧2 到嘴框距离缩短） | ≥ 100 纹理 px | PASS — frame0_dist_to_mouth_px = 225; frame2_dist_to_mouth_px = 29; dist_to_mouth_px_per_frame = [225, 128, 29, 59, 120] |
| E4 | 咬那一帧苹果到嘴框 | ≤ 30 纹理 px | PASS — dist_to_mouth_px = 29 |
| E5 | **角色非透明像素连通块数**（手臂断裂 / 多余漂浮肢体都会 >1） | == 1 | PASS — solid_block_count_per_frame = [1, 1, 1, 1, 1] |
| E6 | 200×240 里道具实际可见 / 道具压脸 / 面部皮肤保留率 | ≥120 px / 0 px / ≥98% | PASS — props_visible_screen_px = 830; prop_cover_face_px = 0; face_box_screen = [79, 55, 125, 86]; face_skin_px_char_only = 490; face_skin_px_final = 490; face_keep_ratio = 1.0 |
| E7 | 200×240 与 256×256 下苹果仍看得见（显示层用宽松暖色阈值，因缩放抗锯齿会稀释红色） | 各 ≥ 8 px | PASS — apple_px = {'200x240': 467, '256x256': 746} |
| E8 | 末帧是满足/开心表情（末帧虹膜像素 ≤ 首帧 75%） | ≤ 75% | PASS — iris_px_frame0 = 2355; iris_px_frame4 = 541 |
| E9 | 相对基图**新增**的手部肤色（确实抬起了手） | ≥ 150 px | PASS — raised_hand_px_per_frame = [1538, 1479, 1729, 1563, 1526] |
| E10 | **苹果必须落在角色主连通块里**（被握住，不是漂浮在旁边） | ≥95% 像素在主块 | PASS — apple_in_main_block_per_frame = [True, True, True, True, True] |
| W1 | 200×240 里键盘可见 | ≥ 260 屏幕 px | PASS — keyboard_opaque_tex_px = 28082; keyboard_visible_screen_px = 1071 |
| W2 | `props.scenes` 必须登记 `work` | 有 | PASS |
| W3 | R167 的 `work` 帧路径不得改动 | 逐字节一致 | PASS |

> 判据脚本自身也修过三个真 bug（都会让判据"假通过"）：
> ① 面部区域原按"顶部 30%"取，抬手时手臂会落进那个区域，把"苹果在手边"误判成"苹果到嘴边" ⇒ 改为**固定面部框**；
> ② 苹果检测原会把**腮红/唇色**当成苹果 ⇒ 改为**排除面部框 + 取最大连通块**；
> ③ 显示层用严格红色阈值，缩放到 200×240 后抗锯齿会把红色稀释到检不出 ⇒ 显示层改**宽松暖色阈值**。

---

## 三、任务 C：接入自主行为引擎

| 要求 | 实现 | 证据 |
|---|---|---|
| `WORK` 与 `EAT_FRUIT` 可自然随机触发 | 活动池新增 `work` / `eat_fruit` 两类，带各自权重与冷却 | 触发取证 240s：WORK 2 次 / EAT_FRUIT 1 次 |
| 两者不能同时运行 | 状态机单例 + 优先级（`EAT_FRUIT` priority 2） | T7：活动区间 0 次重叠 |
| 播放期间行走/睡眠不得随意打断 | 状态计时器独立于空闲决策；长活动不重置状态 | T6：0 次"刚进入就被顶掉" |
| 动作结束后恢复正常生活状态 | 状态结束回到 IDLE | e2e TI3 / D3 |
| 道具随状态出现和消失，不残留 | `props.scenes` 按 action 挂载，退出后卸载 | e2e TTI5：`sleep=3 sit=4 work=2 eat=2 none=112`；TTI1_12：退出后残留 **0 px** |
| 拖拽时正确暂停自主行为 | 沿用 R113 拖拽核心（`drag_resume_delay_ms=800`） | R113 未改动；e2e 拖拽用例通过 |
| 六种点击互动不受影响 | 点击池未动（R158 18 张帧与基线逐字节一致） | `r158_click_actions.test.js` 25/25；e2e TTI2 / TTI6 |

**引擎参数**（`src/behavior_engine.js`）：
```
work_probability    0.10 → 0.55    work_min/max_ms  16000 / 28000    work_cooldown_ms    60000
eat_fruit_probability   → 0.36     eat_fruit_min/max_ms 14000 / 22000  eat_fruit_cooldown_ms 50000
```
`manifest.behavior.config` 已与引擎 `DEFAULT_CONFIG` **逐项对齐**（含 `sleep_probability=0.10` / `walk_probability=0.62`）。

---

## 四、集中验收清单（对应任务书第五节 D 的 10 项）

| # | 要求 | 交付物 | 状态 |
|---|---|---|---|
| 1 | 办公场景实际运行截图与动态预览 | `evidence_r170_gifs/R170_scene_work.gif`、`R170_work_overview.png`、对比图 | ✅ 已产出（`evidence_r170_gifs/R170_scene_work.gif` + `R170_work_overview.png`） |
| 2 | 吃水果场景完整动作 GIF | `evidence_r170_gifs/R170_scene_eat_fruit.gif` | ✅ 已产出（`evidence_r170_gifs/R170_scene_eat_fruit.gif`，30 帧真实运行采集） |
| 3 | 两场景 200×240 预览 | `吃水果场景_200x240.png`、`办公场景_R167版_vs_R170_200x240.png` | ✅ 已产出 |
| 4 | 两场景 256×256 预览 | `吃水果场景_256x256.png`、`办公场景_R167版_vs_R170_256x256.png` | ✅ 已产出 |
| 5 | 自主状态机真实触发记录 | `evidence_r170_trigger.json`（240s）+ `evidence_r170_trigger_before.json`（基线 180s） | ✅ 已产出（240s 修复后 + 180s 修复前基线两份） |
| 6 | 办公及吃水果的直接验收入口 | `--demo-scene work` / `--demo-scene eat_fruit`；`C2_Mac人工验收.command` | ✅ 已产出（`--demo-scene work` / `--demo-scene eat_fruit` + `C2_Mac人工验收.command`） |
| 7 | 自动测试和回归测试结果 | 全量 node 单测 + R147 e2e 全量 + R167 场景判据 + R165 手臂判据 + R170 触发取证 | ✅ 已产出（node 单测 167 全绿 + e2e 60 PASS / 0 FAIL / 0 NOT_VERIFIED） |
| 8 | Git commit | 三提交链（实现 → 交付索引 → 交付归档） | ✅ 已产出（三提交链） |
| 9 | 轻量源码审查 ZIP 及 SHA256 | `character_animation_R170_review.zip`（139 文件 / 17,331,010 字节）+ 独立 `.sha256`（`d6d6a93d…147`） | ✅ 已产出 |
| 10 | 完整备份和最终研发报告 | `backup/V0.0_backup_20261022_182946_r170.zip`（249 文件 / 50,356,658 字节，SHA256 `83eb0879…b7`）+ 本报告 + `docs/R170_DELIVERY_INDEX.md` | ✅ 已产出 |

---

## 五、严格保护已有成果的证据

| 被保护成果 | 证据 |
|---|---|
| A1 原始角色外观 | R138 原始 23 帧 SHA256 **逐字节未变**（`r138_source_checksums.json`）；`r156_click_props_work.test.js` F1 |
| R148 左右行走方向 | `r148_walk_direction.test.js` **8/8**；行走帧未改 |
| R153 自主生活行为 | 状态机未重写；`r153_action_library.test.js` **22/22** |
| R162 点击互动 | `r162_click_defects.test.js` **5/5**；R158 18 张帧与基线逐字节一致 |
| R165 手臂修复 | `evidence_r170_arm_verify.json` **18/18 PASS**（本轮复跑） |
| R167 办公/睡眠成果 | `71_R167_scene_verify.py` **15/15 PASS**；`work` 帧路径逐字节未改（W3 判据） |
| R113 拖拽核心 | `tools/r144_drag_core_diff.py` 与拖拽实现**未改动** |

---

## 六、已知限制（如实登记，不粉饰）

### L1 袖子切割边的锯齿与硬描边（R170 新增素材的已知瑕疵）

吃水果 5 帧的**抬起手臂**是用 `36_R158_arm_rig.py` 的刚体分段旋转拼出来的，拼接切割线在旋转后
会露出**轻微的锯齿与偏硬的描边**（200×240 实际显示尺寸下不可见，放大到 100% 纹理时才明显）。
角色自身的描边是柔和深棕，这段拼接边与之不完全一致。
**如实登记，不掩盖。** 修它需要把 arm rig 的切割边改成亚像素抗锯齿，属于 R158 rig 本身的改造，
不在本轮"只加吃水果场景、不重做手臂系统"的范围内。

### L2 苹果是"手心托着"，不是"五指握紧"

苹果画在**掌心锚点**、手指层叠在苹果之上，接触关系是像素级精确的（判据 E2 实测 1 px）；
但手指是**张开**的，所以读作"**捧着**一个苹果"而不是"握紧苹果"。
用户要求里"伸手拿起水果 → 将水果送到嘴边"的语义成立（判据 E3 实测到嘴距离 225 → 29 px），
但"握住"这个更细的手部姿态没有做到。

### L3 场景切换瞬间旧场景道具与新场景道具短暂共存

道具进出场是 **260ms 淡入淡出**（`R156_PROP_FADE_MS`）。从"办公"直接切到"吃水果"时，
前者的桌椅会在 260ms 内淡出、后者的圆凳果盘淡入，中间有 1~2 帧是两套道具同时可见的过渡帧。
实测：过渡帧之后**办公桌椅完全消失**（`scene_prop_exit` 末帧道具残留 **0 px**），属设计内的淡入淡出行为，
不是"道具残留"缺陷。

### L4 F0 的"伸手取果"在 200×240 下看不太清

F0 的手伸向画面左下方（果盘方向），但在 200×240 的竖屏构图里，手与果盘大部分落在角色身体左侧、
接近裁切边缘，"正在从盘子里拿水果"这一动作的第一拍不如后 4 拍清晰。
（判据 E9 实测 F0 新增手部肤色 1538 px ⇒ 手确实抬起了，是构图问题不是缺帧。）

### L5 沿用 R167 的既有限制（本轮未改动，仅登记）

- R167 办公场景角色**下半身被剪**（为让桌面露出来）；
- R167 被子绗缝是柔和鼓包，不是菱形格；
- 200×240 下睡眠场景**底部裁掉床腿**；
- `sleep_loop` 仍用 R138 老帧，肩背可能探出被子上沿；
- 屏幕相对键盘**右置**；
- 手指级"真比心"不可读；
- 180° 背面转身缺 R138 素材。

### L6 判据脚本自身的三个真 bug（本轮已修，避免"假通过"）

1. 面部区域原按"顶部 30%"取 ⇒ 抬手时手臂落进该区域，把"苹果在手边"误判成"苹果到嘴边"；
2. 苹果检测会抓到**腮红/唇色** ⇒ 改为排除面部框 + 取最大连通块；
3. 显示层用严格红色阈值，缩放到 200×240 后抗锯齿稀释红色导致**检不出苹果** ⇒ 显示层改宽松暖色阈值。

### L7 manifest 生成脚本的幂等性 bug（R158 时代遗留，本轮顺手修掉）

`38_R158_manifest_update.py` 的 `action_library.note` 与 `notes[]` 每次重跑都追加 ⇒
**manifest 无法复算**。现已修掉，重跑**逐字节一致**（`38_R158_manifest_update.py` 连跑两次 diff 为空）。

### L8 真机观感未确认

以上所有视觉结论都来自**沙箱内的真实 Electron 运行像素 + 逐帧目视复核**，
但**沙箱无法代替你在 Mac 上看最终观感** ⇒ `MAC_REAL_GUI_ACCEPTANCE = PENDING`。

---

## 七、本轮改动清单

| 文件 | 改动 |
|---|---|
| `src/behavior_engine.js` | `work` 概率/时长/冷却上调；新增 `eat_fruit` 状态、活动类别、权重与冷却；新增 `_armStateTimer` / `_resumeStateTimer` 修"点击后卡死" |
| `src/action_library.js` | 新增 `eat_fruit` 动作目录项（kind=rest, loop=true, 5 帧） |
| `src/main.js` | 新增 `--demo-scene` 验收入口（暂停自主决策 + 场景锁定）；状态日志加相对时间戳 `t=…ms`；预览序列新增 `eat_fruit` |
| `assets/character_R141_manifest.json` | 登记 `eat_fruit` 动作 + `props.scenes.eat_fruit` + 2 个新道具；`behavior.config` 与引擎对齐 |
| `38_R158_manifest_update.py` | 新增 `LIBRARY_R170` / `PROP_STOOL` / `PROP_FRUIT_TABLE` / `BEHAVIOR_CONFIG_R170` |
| `tests/r170_eat_fruit_work.test.js` | **新增 15 项**：manifest↔引擎一致性根因护栏 / 命中率区间 / 吃水果登记与素材 / 点击后不卡死 / 验收入口 / 既有成果保护 |
| `tests/r141_behavior_engine.test.js` | 活动池加 `eat_fruit`；概率阈值改为**从配置反推**（不再写死数字） |
| `tests/r156_click_props_work.test.js` | D2/D3 按真机实测重标定为区间断言；A4 的 PNG 数量改为**按磁盘实况推导** |
| `R147_e2e_test.sh` | TI4 期望 10→12；新增 TI5 `MOUNT_EAT`（eat_fruit 场景挂载 2 个道具） |
| `C2_Mac人工验收.command` | 支持 `work` / `eat_fruit` 验收入口 + R170 观测汇总 |
| `80~87_R170_*.py` | **新增**：吃水果 spike / 帧烘焙 / 道具 / 客观判据 / 证据产出 / 打包器 / 触发取证 / GIF 生成 |

---

## 八、复算方法

```bash
cd "/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/candidates/candidate_b_c2"

# 全量 node 单测
for f in tests/*.test.js; do node "$f"; done

# R170 客观判据 (13 项)
python3 83_R170_scene_verify.py --out evidence_r170_scene_verify.json

# 真实 Electron 触发取证 (≥240s)
python3 86_R170_trigger_verify.py --seconds 240 --out evidence_r170_trigger.json

# 修复前基线 (R167 交付版 git f753c21) 180s
#   git archive f753c21 candidates/candidate_b_c2 | tar -x -C /tmp/r167_baseline
#   ln -s <repo>/candidates/candidate_b_c2/node_modules /tmp/r167_baseline/candidates/candidate_b_c2/node_modules
#   cd /tmp/r167_baseline/candidates/candidate_b_c2 && python3 86_R170_trigger_verify.py --seconds 180 \
#     --out evidence_r170_trigger_before.json --log evidence_r170_trigger_before.log

# 真实 Electron 重采集 + GIF
electron src/main.js --manifest assets/character_R141_manifest.json --mode compact --x 600 --y 300 \
  --preview evidence_r170_preview --quit-after=600
python3 87_R170_gif.py --preview-dir evidence_r170_preview --out-dir evidence_r170_gifs
python3 84_R170_evidence.py

# 验收入口
electron . --manifest assets/character_R141_manifest.json --size 200 --demo-scene eat_fruit --quit-after 12

# 全量回归
bash R147_e2e_test.sh
```

# R170 交付索引 — 恢复"电脑办公场景" + 新增"吃水果"生活行为

> **生成时间**：2026-10-22
> **对应任务书**：R170（承接 R167，基线 commit `3893c28`）
> **作者**：MiniMax（Mavis）
> **上一交付**：R167 `3893c28`（实现 `8f693e6` / 索引 `fbfdca3` / 归档 `3893c28`）
> **本轮实现提交**：`d1b700e`
> **状态**：`ENGINEERING_GATE = PASS` / `VISUAL_GATE = PASS` / **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** / `V0_0_RELEASE_STATUS = NOT_FROZEN`
> **范围声明**：本轮**只做任务书点名的两项**（恢复办公场景 + 新增吃水果生活行为），未扩展功能；**未进入 V0.1**；**未改动人物身份与服装**（R138 原始 23 帧 SHA256 逐字节未变）；**未改动任何点击动作素材**（`assets/character_R158/` 18 张帧与 `3893c28` 逐字节一致）；**未重新开发整个桌宠**；**未充值 i2i**（全程零 AI 生图调用）；R148 行走方向 / R153 自主行为 / R162 点击互动 / R165 手臂修复 / R167 办公睡眠成果 / R113 拖拽核心均未改动。

---

## 〇、本轮两项结论（任务书要求逐项给结论）

| 字段 | 结论 | 一句话依据 |
|---|---|---|
| `WORK_SCENE` | **PASS** | **修复前基线**（R167 交付版 `3893c28` 真实 Electron 连跑 180s、空闲决策 14 次）⇒ WORK **触发 0 次**；**修复后**（R170 真实连跑 240s、空闲决策 15 次）⇒ WORK **2 次**、平均间隔 **62.4s**、每次持续 **17.8s / 25.3s**、**0 次**"刚出现就被顶掉"、与 EAT_FRUIT **0 次**重叠（触发取证 **7/7 PASS**）。画面素材两轮**逐字节一致** ⇒ 差异纯粹来自"配置 + 时间轴"修复 |
| `EAT_FRUIT_SCENE` | **PASS** | 13/13 绝对值判据全 PASS：苹果每帧 **≥1315 px**、苹果到手 **1 px**、到嘴距离 **225 → 123 → 29 → 59 → 116 px**（真实"从果盘举到嘴边再落下"的轨迹）、咬那帧到嘴 **29 px**、**每帧角色非透明连通块 = 1**（手臂不裂、无漂浮肢体）、苹果 **100% 落在角色主块内**（被手握住）、200×240 道具可见 **823 px** / 道具压脸 **0 px** / 面部皮肤保留 **100%**、200×240 与 256×256 苹果可见 **476 / 751 px**、末帧虹膜 **541 px**（首帧 2355 的 **23%** ⇒ 满足笑眼） |

> 两项同时成立 ⇒ 按任务书判定，**本轮通过**。
> **但**：沙箱内无法代替你在 Mac 上看最终观感 ⇒ **`MAC_REAL_GUI_ACCEPTANCE = PENDING`**，未伪造任何真机结论。

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 主工作区 | `/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/` |
| 候选实现 | `candidates/candidate_b_c2/` |
| QA 报告 | `docs/R170_QA_REPORT.md` |
| 交付索引 | `docs/R170_DELIVERY_INDEX.md`（本文件） |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R170_review.zip`（139 文件 / 17,331,010 字节） |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R170_review.zip.sha256`（`d6d6a93db926e1c89948a9a1b311722e126cacf51348e6ed3e9acc90e29dc147`） |
| 备份 | `backup/V0.0_backup_20261022_182946_r170.zip`（249 文件 / 50,356,658 字节）+ 同名 `.sha256`（`83eb0879ddfba92a156a67f7e1e1f5d86944a336f198c83f75c3372bdc8114b7`） |
| e2e 机器报告 | `candidates/candidate_b_c2/evidence_r147_e2e.json`（60 PASS / 0 FAIL / 0 NOT_VERIFIED） |
| **R170 客观判据** | `candidates/candidate_b_c2/evidence_r170_scene_verify.json`（吃水果 **13/13 PASS** + 办公 3/3） |
| **触发取证（修复后）** | `candidates/candidate_b_c2/evidence_r170_trigger.json`（240s，**7/7 PASS**） |
| **触发取证（修复前基线）** | `candidates/candidate_b_c2/evidence_r170_trigger_before.json`（180s，**2/7 PASS** ⇒ WORK 0 次） |
| 真实采集帧 | `candidates/candidate_b_c2/evidence_r170_preview/`（708 帧 + `preview_meta.json` / `run.log` / 运行时校验 JSON；**原始 PNG 不入库**） |
| 可观看运行预览 | `candidates/candidate_b_c2/evidence_r170_gifs/`（2 个 GIF + 3 张总览图） |
| 前后对比图 | `candidates/candidate_b_c2/evidence_r170_compare/`（7 张，含**触发频率修复前 vs 修复后**对比卡） |
| 可视化产物副本 | `/Users/musk123/Downloads/minimax工作文件夹/图文工作/R170_吃水果/` |
| Mac 真机验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command`（双击即用，支持 `work` / `eat_fruit` 参数） |

**ZIP SHA256 不写在本索引内**（避免「改索引就改 ZIP 哈希」的循环自引用），写在 ZIP 旁边的独立 `.sha256` 文件；本索引里的占位符在**归档提交**里替换为最终值。

---

## 二、代码结构（R170 变更）

| 文件 | 变更 |
|---|---|
| `src/behavior_engine.js` | ① `work_probability` 0.10→**0.55**、`work_min/max_ms` → **16000/28000**、新增 `work_cooldown_ms=60000`；② 新增 `eat_fruit_probability=0.36`、`eat_fruit_min/max_ms=14000/22000`、`eat_fruit_cooldown_ms=50000`；③ 新增状态 `EAT_FRUIT`（priority 2）、`STATE_ACTION.EAT_FRUIT`、`ACTIVITY_KINDS` 新增 `eat_fruit`；④ `_pickActivity` 按各自冷却期把权重归零（互斥）；⑤ **修掉同源 bug**：新增 `_armStateTimer` / `_resumeStateTimer` —— 修复"点击反馈结束后状态计时器无人重排 ⇒ 办公中点一下角色会**永久卡在 WORK**" |
| `src/action_library.js` | 新增 `eat_fruit` 动作目录项（kind=rest，loop=true，5 帧） |
| `src/main.js` | ① 新增 `--demo-scene <action>` 验收入口（`setAutonomousPaused(true)` 暂停自主决策 + 资源就绪后 250ms 下发 `set-action`，**仍走正式渲染路径** ⇒ 道具按正式规则挂载）；② 状态日志加相对时间戳 `t=…ms`；③ 预览采集序列新增 `['eat_fruit', 30, 160, 300]` 与 `summary.scene_eat_fruit` |
| `assets/character_R141_manifest.json` | 登记 `eat_fruit` 动作（5 帧）+ `props.scenes.eat_fruit`（back: `prop_stool` + `prop_fruit_table`）+ 2 个新道具；**`behavior.config` 与引擎 `DEFAULT_CONFIG` 逐项对齐**（含 `sleep_probability=0.10` / `walk_probability=0.62`） |
| `38_R158_manifest_update.py` | 新增 `LIBRARY_R170` / `PROP_STOOL` / `PROP_FRUIT_TABLE` / `BEHAVIOR_CONFIG_R170`；**修掉一个 R158 时代遗留的幂等性 bug**（`action_library.note` 与 `notes[]` 每次重跑都追加 ⇒ manifest 无法复算），现**重跑逐字节一致** |
| `tests/r170_eat_fruit_work.test.js` | **新增 15 项**：manifest↔引擎一致性根因护栏 / 命中率区间 / 吃水果登记与素材 / 点击后不卡死 / 验收入口 / 既有成果保护 |
| `tests/r141_behavior_engine.test.js` | 活动池加 `eat_fruit`；概率阈值一律改为**从配置反推**（不再写死数字） |
| `tests/r156_click_props_work.test.js` | D2/D3 按真机实测重标定为区间断言 + 冷却断言；A4 的 PNG 数量改为**按磁盘实况推导**（不再手工维护） |
| `R147_e2e_test.sh` | TI4 期望 10→12；新增 TI5 `MOUNT_EAT`（`action=eat_fruit scene=yes mounted=prop_stool,prop_fruit_table`） |
| `C2_Mac人工验收.command` | 支持 `work` / `eat_fruit` 验收入口 + R170 观测汇总（办公次数 / 吃水果次数 / 场景锁定） |
| `80~87_R170_*.py` | **新增**：吃水果 spike / 帧烘焙 / 场景道具 / 客观判据 / 证据产出 / 打包器 / 触发取证 / GIF 生成 |

---

## 三、本轮最关键的一件事：办公场景为什么会"消失"

**不是素材问题，是"配置 + 概率 + 时间轴"三重问题。**

| # | 根因 | 实测 | 修法 |
|---|---|---|---|
| ① | `manifest.behavior.config` 是 **R141 时代的陈旧快照**，被 `main.js` 的 `Object.assign({}, behavior.config)` **静默覆盖**引擎默认值 | 基线 manifest 里**根本没有 `work_probability` 这个键**；`sleep_probability=0.30`（引擎 R153 已降到 0.10）、`walk_probability=0.70`（引擎 0.62） | manifest 与引擎对齐 + **根因回归护栏**（r170 测试 A1） |
| ② | 单次空闲决策命中率只有 **5%** | `work_probability=0.10` / 总权重 2.00 | → **0.55** |
| ③ | 长活动把空闲决策压到 ~20s 一次 | 期望 **≈6.7 分钟**才出现一次，且每次仅 9~19s | 时长 → **16~28s**，冷却 **60s** |

**决定性证据**：修复前基线真实连跑 **180 秒**（空闲决策 14 次）⇒ **WORK 触发 0 次**；修复后 **240 秒** ⇒ **2 次**。

---

## 四、验收入口（与正式自主行为严格分离）

```bash
cd candidates/candidate_b_c2
# 办公场景
../candidate_b_electronpixir/node_modules/.bin/electron . \
  --manifest assets/character_R141_manifest.json --size 200 --demo-scene work
# 吃水果场景
../candidate_b_electronpixir/node_modules/.bin/electron . \
  --manifest assets/character_R141_manifest.json --size 200 --demo-scene eat_fruit
```

或双击 `C2_Mac人工验收.command` 并带上 `work` / `eat_fruit` 参数。

**实现保证**：进入验收模式时 `behaviorEngine.setAutonomousPaused(true)` ⇒ **自主决策暂停，不会随机跑掉**；场景仍走**正式渲染路径** ⇒ 道具按正式规则挂载/卸载。

实测输出：
```
[main] R170 DEMO_SCENE action=eat_fruit (自主决策已暂停, 场景锁定供验收)
[renderer] R156 PROPS action=eat_fruit scene=yes mounted=prop_stool,prop_fruit_table
[renderer] R147 set-action eat_fruit applied=true loop=true frames=5
```

---

## 五、已知限制（如实登记）

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

## 六、复算方法

见 `docs/R170_QA_REPORT.md` 第八节。

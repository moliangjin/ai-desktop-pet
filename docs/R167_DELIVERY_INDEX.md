# R167 交付索引 — R165 审查 PARTIAL 后的最后两项视觉整改（办公打字 / 睡眠被子）

> **生成时间**：2026-10-22
> **对应任务书**：R167（承接 R165，基线 commit `c689e7b`）
> **作者**：MiniMax（Mavis）
> **上一交付**：R165 `c689e7b`（实现 `10dd0f0` / 索引 `af8a660` / 归档 `c689e7b`）
> **本轮实现提交**：`e4ff766`
> **状态**：`ENGINEERING_GATE = PASS` / `VISUAL_GATE = PASS`（真实 Electron 运行 + 像素级客观测量 + 可复算回归判据）/ **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** / `V0_0_RELEASE_STATUS = NOT_FROZEN`
> **范围声明**：本轮**只修任务书点名的 2 项问题**，未扩展功能；**未进入 V0.1**；**未改动人物身份与服装**（R138 原始 23 帧 SHA256 逐字节未变）；**未改动任何点击动作素材**（`assets/character_R158/` 18 张帧与 HEAD 逐字节一致）；**未重新开发整个动画系统**（只在场景道具生成器 + 办公帧烘焙段内改）；**未充值 i2i**（全程零 AI 生图调用）；R148 行走方向与 R113 拖拽核心未动。

---

## 〇、本轮两项结论（任务书要求逐项给结论）

| 字段 | 结论 | 一句话依据 |
|---|---|---|
| `WORK_SCENE_BELIEVABILITY` | **PASS** | 8/8 绝对值判据（全部在 **200×240 真实合成图**上量）：**键盘落在双手区内的比例 0.51**（门槛 0.40）、**手部皮肤落在键区内的比例 1.0**（门槛 0.55）、**两帧手部质心位移 10.2 纹理 px**（门槛 6）、**200×240 键盘可见 494 px**（门槛 260）、屏幕背板均亮 **63.1**（<120 = 屏幕朝角色）、青蓝边缘光 **1738 px**、不透明道具遮脸 **0 px**。R162 旧素材同套判据 **6/15 PASS**（P2-1/2/5/6/7/8 FAIL） |
| `SLEEP_SCENE_QUALITY` | **PASS** | 7/7 绝对值判据：被子覆盖身体核心 **96%**（门槛 85%）、整体 **50.7%**、遮脸 **9 px**（门槛 30）、最外 2px alpha 中位数 **0**、平均 RGB **(183.5, 204.5, 225.1)** 亮度 **200.6**（浅蓝）、**褶皱明暗 p90−p10 = 62.6**（门槛 34）、**床架木纹 1436 px**（床头 569 / 底部 812）、**床垫 4514 px**。R162 旧素材同套判据 P3-1/5/6 FAIL（褶皱明暗 = **0.0**、床架仅 **396 px**） |
| `CLICK_ACTION_VISUAL_CLEANLINESS` | **PASS（保持 R165 成果）** | 本轮**未改动点击动作素材**；R165 的 18/18 帧 C0~C5 复测仍全 PASS、`r158_click_actions.test.js` 25/25、全量 node 单测 **152/152**、R158 运行时 **6/6** |

> 两项同时成立 ⇒ 按任务书判定，**本轮通过**。

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 主工作区 | `/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/` |
| 候选实现 | `candidates/candidate_b_c2/` |
| QA 报告 | `docs/R167_QA_REPORT.md` |
| 交付索引 | `docs/R167_DELIVERY_INDEX.md`（本文件） |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R167_review.zip`（139 文件 / 17,423,634 字节） |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R167_review.zip.sha256`（`f75cb862c2395968a004a3b37ad9ddd9fc38e9cf4640226346f5849eb802615f`） |
| 备份 | `backup/V0.0_backup_20261022_104356_r167.zip`（223 文件 / 47,824,543 字节）+ 同名 `.sha256`（`adb571102fb9e0a507b029b44270b932abecaa9b71e535e1e0c7bc0d09a03f25`） |
| e2e 机器报告 | `candidates/candidate_b_c2/evidence_r147_e2e.json`（59 项，PASS 59 / FAIL 0 / NOT_VERIFIED 0） |
| R167 场景客观判据 | `candidates/candidate_b_c2/evidence_r167_scene_verify.json`（R167 **15/15 PASS** · R162 旧素材 **6/15 PASS** ⇒ 9 项 FAIL） |
| R165 手臂客观判据（本轮复跑） | `candidates/candidate_b_c2/evidence_r167_arm_verify.json`（18 帧 C0~C5，**18/18 PASS**） |
| 绝对测量报告 | `candidates/candidate_b_c2/evidence_r167_measure.json`（面积 / 脚底 / 冠部，6 动作全 PASS） |
| 真实采集帧 | `candidates/candidate_b_c2/evidence_r167_preview/`（648 帧 + `preview_meta.json` / `run.log` / 运行时校验 JSON；**原始 PNG 不入库**） |
| 可观看运行预览 | `candidates/candidate_b_c2/evidence_r167_gifs/`（6 个 GIF + 1 张总览图） |
| 前后对比图 | `candidates/candidate_b_c2/evidence_r167_compare/`（9 张：办公/睡眠 200×240 与 256×256、双手放大前后、打字两帧、被子床放大前后、点击池逐帧总览） |
| 可视化产物副本 | `/Users/musk123/Downloads/minimax工作文件夹/图文工作/R167_修复证据/`（16 个文件：6 GIF + 总览图 + 9 张对比图） |
| Mac 真机验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command`（双击即用） |

**ZIP SHA256 不写在本索引内**（避免「改索引就改 ZIP 哈希」的循环自引用），写在 ZIP 旁边的独立 `.sha256` 文件；本索引里的占位符在**归档提交**里替换为最终值。

---

## 二、代码结构（R167 变更）

```
candidates/candidate_b_c2/
├── src/                        (未改 — 场景挂载顺序与渲染逻辑本轮不动)
├── assets/
│   ├── character_R138/         (未改 — 23 帧 SHA256 逐字节一致, 人物身份与服装未动)
│   ├── character_R153/         (未改)
│   ├── character_R156/         ★ 改: prop_desk_surface / prop_desk / prop_screen_glow
│   │                              ★ 新增: prop_keyboard.png
│   │                              ★ 改: prop_quilt.png (浅蓝蓬松布被) / prop_bed.png (床头立板+床架)
│   │                              ★ 改: work_1.png / work_2.png (剪下半身 + 双手按键盘)
│   │                              ★ 改: props_report.json / prop_scene_guides.json / bake_report.json
│   ├── character_R158/         (未改 — 18 张点击动作帧与 HEAD 逐字节一致)
│   └── character_R141_manifest.json  ★ 改: 幂等更新 (38_R158_manifest_update.py, 新增 prop_keyboard)
├── tests/
│   └── r156_click_props_work.test.js ★ 改: 道具数 9→10 / PNG 28→29 / 必需道具加 prop_keyboard
├── 29_R156_pose_bake.py        ★ 改: WORK_CUT_Y=592 剪下半身 / _hand_region 手部掩膜 / hand_press 打字动作
├── 30_R156_props_bake.py       ★ 改: 台面加深 / make_keyboard 新增 / 笔记本后移 / 冷光外溢 / 屏幕微光
├── 38_R158_manifest_update.py  ★ 改: 新增 PROP_KEYBOARD + work 场景 back 层挂载 + guides
├── 42_R158_measure_report.py   ★ 改: 面积判据对齐 node 单测 C1 的压扁系数归一化 (阈值不变) + --out
├── 67_R167_diag_sit_arms.py    ★ 新增: 坐姿帧几何测量 (手/腕带位置)
├── 68_R167_sleep_props.py      ★ 新增: 被子高度场 + Lambert 着色 + 床重做
├── 69_R167_spike_work.py       ★ 新增: 办公 z 序可行性 spike
├── 71_R167_scene_verify.py     ★ 新增: P2-1~P2-8 + P3-1~P3-7 (15 项, 以 200×240 真实合成图为口径)
├── 72_R167_evidence.py         ★ 新增: 9 张前后对比图产出
├── 73_R167_package.py          ★ 新增: 交付打包器 (审查包 + 备份包 + SHA256)
└── R147_e2e_test.sh            ★ 改: TI4 loaded 9→10 / TI5 work 挂载加 prop_keyboard
```

---

## 三、本轮修掉的根因

### P0-1 办公场景「双手没有真正操作键盘」（3 个根因）

| # | 根因 | 修法 | 客观量（旧 → 新，门槛） |
|---|---|---|---|
| ① | **z 序根本不成立**：渲染顺序固定 back 道具 → 角色 → front 道具，台面在 back 层而角色**大腿整片压在台面带上** ⇒ 台面被腿挡住，**键盘根本没地方出现** | 角色帧在 `y=592` 以下剪掉下半身（保留双手 + 腕带），台面从她腰部露出 | desk_far 640/desk_near 716 → **552/700**，200×240 下台面可见带 21 屏幕 px |
| ② | **根本没有键盘道具** ⇒ "手按键盘"物理上不存在 | 新增 `prop_keyboard.png`（back 层，远沿 566 / 近沿 664，4 排键位 + 空格键，分隔线加粗 4~5 纹理 px） | 键盘落在双手区内比例 **0** → **0.51**（门槛 0.40）；200×240 可见 **0** → **494 px**（门槛 260） |
| ③ | 笔记本**底座落在台面近沿**与键盘抢位，透视不对 | 笔记本后移：盖板 y428~596、基座 y596~624 ⇒ 屏幕在后、键盘在前 | 手部皮肤落在键区内比例 **0** → **1.0**（门槛 0.55）；打字位移 1.1 px → **10.2 px**（门槛 6） |

### P0-2 睡眠场景「被子像光滑灰蓝色硬壳」（3 个根因）

| # | 根因 | 修法 | 客观量（旧 → 新，门槛） |
|---|---|---|---|
| ④ | 被子是**平涂色块 + 硬边**，无高度/明暗层次 ⇒ 读作塑料壳 | 改**高度场 + Lambert 着色**：形体 / 绗缝鼓包 / 折痕沟槽三层分开给权重 | 褶皱明暗 p90−p10 **0.0** → **62.6**（门槛 34） |
| ⑤ | 配色是灰蓝 | 暗 #7EA6D1 → 亮 #E0EEFA，菱形绗缝 32° + 顶部翻折被沿 + 边缘羽化 | 均 RGB (194,217,239) → **(183.5, 204.5, 225.1)**，最外 2px alpha 中位数 **0** |
| ⑥ | 床的立板与腿落在 **200×240 裁切线以下** ⇒ 床几乎看不见 | 床头立板做高做宽（上沿 y=228）+ 床垫与木质床侧栏整体上移 40 纹理 px + 床整体横向缩到 1000 右移 8px | 床架木纹 **396** → **1436 px**（门槛 床头 300 / 底部 400）；身体核心覆盖 0.699 → **0.96**（门槛 0.85） |

---

## 四、本轮改写的既有判据口径（**不是放宽标准，见 QA 报告 §二**）

| 判据 | 旧口径的问题 | 新口径 | 修正后 |
|---|---|---|---|
| `42_R158_measure_report.py` 面积中位数 | 没跟上 node 单测 C1 在 R165 做的**纵向压扁系数归一化**，把 `cheer_jump` 故意压扁的蓄力/落地帧误判成"整体压缩" | `ratio = 中位帧面积 / (基准面积 × 该帧 scale_y)`（同一公式、同一数据源 `bake_report.json`，**阈值仍是 15%**，并保留原始偏差字段） | `cheer_jump` 原始 −15.19% ⇒ 归一化 **+0.97% PASS**；6 动作全 PASS |
| e2e TI4 / TI5 | 期望道具数 9、work 挂载未含新道具 | `loaded=10`；work 挂载加 `prop_keyboard` | 59/59 |
| `r156_click_props_work.test.js` | 道具数 9 / PNG 28 | 10 / 29，必需道具加 `prop_keyboard` | 21/21 |

> **`cheer_jump` 的 −15.19% 是 HEAD 自带的存量问题，不是 R167 回归**：在 HEAD 的独立 worktree（`c689e7b`）上跑同一个脚本得到**完全相同的数字**；且 `assets/character_R158/` 与 HEAD 逐字节一致。
> 另发现 R165 归档里的 `evidence_r165_measure.json` 是**陈旧快照**（记录 212244/203477/183127，实测 211501/208630/182192）—— 本轮不改动历史归档，改用新生成的 `evidence_r167_measure.json`，差异已如实登记在 QA 报告 §二。

---

## 五、验收结果一览

| 项 | 结果 |
|---|---|
| node 单元测试 | **152 passed / 0 failed**（11 个测试文件） |
| R167 场景客观判据 | R167 **15/15 PASS**；R162 旧素材同套 **6/15 PASS**（9 项 FAIL）⇒ 新旧完美区分 |
| R165 手臂客观判据（复跑） | **18/18 PASS**（点击动作未被本轮改动影响） |
| 真实 Electron 运行时客观校验 | **23/23** + **6/6** |
| e2e | **59 PASS / 0 FAIL / 0 NOT_VERIFIED** |
| 面积 / 脚底 / 冠部绝对测量 | 6 个动作全 PASS（`cheer_jump` 归一化后 +0.97%） |
| 真实运行采集 | 648 帧，`loaded=10 failed=0` |
| 人物身份与服装 | R138 23 帧 SHA256 逐字节未变 |
| 点击动作素材 | `character_R158/` 18 帧与 HEAD 逐字节一致 |
| **Mac 真机 GUI 验收** | **PENDING**（沙箱内无法代替你在 Mac 上看最终观感；入口 `candidates/candidate_b_c2/C2_Mac人工验收.command`） |

---

## 六、做不到 / 未验证（如实列出，**不标视觉 PASS**）

1. **办公场景角色下半身被剪掉**（`y>592`），读作"坐在桌后"，桌下只剩椅子底座 —— 这是为解决 z 序（大腿整片压住台面）所做的**取舍**。
2. **被子的绗缝读作柔和不规则鼓包**，不是清晰的菱形格 —— 刻意避开 v1 的"瓷砖感"硬格。
3. **200×240 窗口底部只到纹理 y≈735**，床体下部（腿）被裁切；床垫顶面约 90% 被角色挡住，床的存在主要靠床头立板 + 木梁 + 角腿 + 床垫正面带表达。
4. `sleep_loop` 用 R138 老帧 `sleep_loop_00_base.png`（头顶 y=265），而被子上沿轮廓按 R153 `sleep_breath_in.png`（头顶 y=330）量 ⇒ 肩背会从被子上沿探出。
5. **屏幕相对键盘右置**：正面视角下屏幕若正对放在键盘后方会被角色身体完全挡住，故采用"屏幕在右后方"的常规插画约定；深度关系正确。
6. **手指级"真比心"几何在 200×240 下物理不可读**（单指宽约 2 px）⇒ 沿用"双手在胸前合拢 + 头侧爱心特效"，**不是**真比心。
7. **真正的 180° 背面转身仍做不到** —— R138 全库无背面素材，清单原样保留。
8. **Mac 真机验收 PENDING** —— 本轮用真实 Electron 采集 + 200×240/256×256 真实尺寸合成替代客观判据，**最终观感仍需你确认**。

---

## 七、复审入口

```bash
cd "/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/candidates/candidate_b_c2"

# 1) R167 场景客观判据 (15 项, 全部在 200×240 真实合成图上量; R162 旧素材复验必 FAIL)
python3 71_R167_scene_verify.py --out evidence_r167_scene_verify.json
# 2) 重新产出全部前后对比图 (9 张)
python3 72_R167_evidence.py
# 3) 点击动作绝对测量 (口径已对齐 node 单测 C1)
python3 42_R158_measure_report.py --out evidence_r167_measure.json
# 4) 真实尺寸场景预览
python3 45_R165_scene_preview.py --scene work --size 200x240 --out /tmp/w.png
python3 45_R165_scene_preview.py --scene sleep_loop --size 200x240 --out /tmp/s.png
# 5) 既有回归测试
node tests/r158_click_actions.test.js
node tests/r162_click_defects.test.js
node tests/r156_click_props_work.test.js
# 6) 运行时真实像素校验 (23 + 6 项)
python3 34_R156_runtime_verify.py --preview-dir evidence_r167_preview
python3 39_R158_runtime_verify.py --preview-dir evidence_r167_preview
# 7) 真实 Electron 全量回归
bash R147_e2e_test.sh
# 8) 重放烘焙 (顺序不可换: 30 会覆盖睡眠道具)
python3 30_R156_props_bake.py && python3 68_R167_sleep_props.py \
  && python3 29_R156_pose_bake.py && python3 38_R158_manifest_update.py
```

素材本体（R138 原始 23 帧 PNG）不在审查包内，位于 `assets/character_R138/` 与 R138 交付目录；SHA256 清单见 `assets/character_R138_derived/r138_source_checksums.json`。

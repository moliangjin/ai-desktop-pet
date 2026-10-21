# R165 交付索引 — 真机验收失败后的精准修复（点击多手 / 办公场景 / 睡眠场景）

> **生成时间**：2026-10-22
> **对应任务书**：R165（承接 R162，基线 commit `2cdb6c7`）
> **作者**：MiniMax（Mavis）
> **上一交付**：R162 `2cdb6c7`（实现 `e60931e` / 索引 `273f104` / 证据 `5b8c676` / 归档 `2cdb6c7`）
> **本轮实现提交**：`969ee86`
> **状态**：`ENGINEERING_GATE = PASS` / `VISUAL_GATE = PASS`（真实 Electron 运行 + 像素级客观测量 + 可复算回归判据）/ **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** / `V0_0_RELEASE_STATUS = NOT_FROZEN`
> **范围声明**：本轮**只修任务书点名的 3 类问题**，未扩展功能；**未进入 V0.1**；**未改动人物身份与服装**（R138 原始 23 帧 SHA256 逐字节未变）；**未重新开发整个动画系统**（只在 `arm_rig` 的 5 处切层/接缝/外缘/回填/端面描边 + 场景道具生成器内改）；**未充值 i2i**（全程零 AI 生图调用）；6 个点击动作与三类生活场景原样保留；R148 行走方向与 R113 拖拽核心未动。

---

## 〇、本轮三项结论（任务书要求逐项给结论）

| 字段 | 结论 | 一句话依据 |
|---|---|---|
| `CLICK_ACTION_VISUAL_CLEANLINESS` | **PASS** | 18/18 帧 C0~C5 全 PASS，C1/C2/C3/C5 全为 0；R162 旧素材同套判据 15/18 FAIL（旧 `cheer_jump_0/2` 手部块数 = **6**） |
| `WORK_SCENE_BELIEVABILITY` | **PASS** | 屏幕背板均亮 **62.3**（<120 = 屏幕朝角色）、青蓝边缘光 **921 px**、双手压在台面带（desk_far 556 / desk_near 668）、不透明道具遮脸 **0 px**、白大褂 0.414 / 银白发 0.360 |
| `SLEEP_SCENE_QUALITY` | **PASS** | 被子覆盖身体核心区 **95.8%**（门槛 85%）、整体 50.6%（门槛 45%）、遮脸 **9 px**（门槛 30）、最外 2px alpha 中位数 **0** |

> 三项同时成立 ⇒ 按任务书判定，**本轮通过**。

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 主工作区 | `/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/` |
| 候选实现 | `candidates/candidate_b_c2/` |
| QA 报告 | `docs/R165_QA_REPORT.md` |
| 交付索引 | `docs/R165_DELIVERY_INDEX.md`（本文件） |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R165_review.zip`（__ZIP_FILES__ 文件 / __ZIP_BYTES__ 字节） |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R165_review.zip.sha256`（`__ZIP_SHA256__`） |
| 备份 | `backup/V0.0_backup_20261022_r165.zip`（__BAK_FILES__ 文件 / __BAK_BYTES__ 字节）+ 同名 `.sha256`（`__BAK_SHA256__`） |
| e2e 机器报告 | `candidates/candidate_b_c2/evidence_r147_e2e.json`（59 项，PASS 59 / FAIL 0） |
| R165 手臂客观判据 | `candidates/candidate_b_c2/evidence_r165_arm_verify.json`（18 帧 C0~C5） |
| R165 场景客观判据 | `candidates/candidate_b_c2/evidence_r165_scene_verify.json`（R165 7/7 · R162 3 FAIL） |
| 绝对测量报告 | `candidates/candidate_b_c2/evidence_r165_measure.json`（面积 / 脚底 / 冠部） |
| 真实采集帧 | `candidates/candidate_b_c2/evidence_r165_preview/`（648 帧 + `preview_meta.json` / `run.log` / 运行时校验 JSON；**原始 PNG 不入库**） |
| 可观看运行预览 | `candidates/candidate_b_c2/evidence_r165_gifs/`（6 个 GIF + 1 张总览图） |
| 前后对比图 | `candidates/candidate_b_c2/evidence_r165_compare/`（12 张：办公/睡眠 200×240 与 256×256、6 动作前后、点击池逐帧总览新/旧） |
| 可视化产物副本 | `/Users/musk123/Downloads/minimax工作文件夹/图文工作/R165_修复证据/`（19 个文件：6 GIF + 总览图 + 12 张对比图） |
| Mac 真机验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command`（双击即用） |

**ZIP SHA256 不写在本索引内**（避免「改索引就改 ZIP 哈希」的循环自引用），写在 ZIP 旁边的独立 `.sha256` 文件；本索引里的占位符在**归档提交**里替换为最终值。

---

## 二、代码结构（R165 变更）

```
candidates/candidate_b_c2/
├── src/                        ★ renderer.js: 场景挂载顺序 (back 层台面 / front 层桌+笔记本)
├── assets/
│   ├── character_R138/         (未改 — 23 帧 SHA256 逐字节一致, 人物身份与服装未动)
│   ├── character_R153/         (未改)
│   ├── character_R156/         ★ 改: 6 个场景道具重做 + 新增 prop_desk_surface.png
│   │                              + prop_scene_guides.json + work_1/work_2 + reports
│   ├── character_R158/         ★ 改: 18 张动作帧全部重烘焙
│   └── character_R141_manifest.json  ★ 改: 幂等更新 (38_R158_manifest_update.py)
├── tests/
│   ├── r158_click_actions.test.js  ★ 改: C1 面积比除压扁系数 / G1 底图自检 / handGap 盒放宽
│   ├── r162_click_defects.test.js  ★ 改: chestHandGroups 放宽 + R2-5 改质心高度变化幅度
│   └── r156_click_props_work.test.js ★ 改: 场景道具测试
├── 36_R158_arm_rig.py          ★★ 手臂 rig 5 处根因修复 (接缝线归衣身 / 外缘取剪影边 /
│                                  肩区回填半径 46 / fore 段端面 2px 描边 / 静态肩球)
├── 37_R158_action_bake.py      ★ 改: 姿态按 200×240 真实尺寸重标定 + 烘焙顺序
├── 30_R156_props_bake.py       ★ 改: 场景道具重做 (床/被子/月亮/桌+台面/屏幕光)
├── 29_R156_pose_bake.py        ★ 改: 场景帧姿态 (办公坐姿 / 睡眠卧姿)
├── 34_R156_runtime_verify.py   ★ 改: 运行时校验适配新道具
├── 38_R158_manifest_update.py  ★ 改: 新增 prop_desk_surface
├── R147_e2e_test.sh            ★ 改: TI4 loaded 8→9 / TI5 work 挂载加 prop_desk_surface
├── 45_R165_scene_preview.py    ★ 新增: 真实尺寸场景预览
├── 46_R165_arm_verify.py      ★ 新增: C0~C5 客观判据 (旧素材复验必 FAIL)
├── 47_R165_evidence.py        ★ 新增: 12 张前后对比图产出
├── 48_R165_package.py         ★ 新增: 交付打包器
├── 49_R165_scene_verify.py    ★ 新增: P2-1~P3-3 场景绝对值判据
├── 50_R165_pose_sweep.py      ★ 新增: 姿态参数扫描
└── 51~66_R165_diag_*.py       ★ 新增: 16 个诊断脚本 (弧线/分层/溯源/接缝/缝隙/肩区/边缘/接触表…)
```

---

## 三、本轮修掉的 11 个独立根因

### P0-1 点击动作"多出来一双手"（5 个根因）

| # | 根因 | 修法 | 客观量（旧 → 新，门槛） |
|---|---|---|---|
| ① | 手臂掩膜不是手臂（洪水填充被青色饰条暗描边截断 + `cuff_box` 坐标错） | 掩膜改几何重建 + 袖子连腕带整块抹掉 + 静态肩关节球 + 肩区回填 + 两侧手臂都必须参与 | 上臂入掩膜 854 px → 全段 |
| ② | 衣身接缝线被切进手臂旋转层 → 髋部游离虚线 | 接缝线归衣身，不进手臂层（L 侧到 `band[0]-1`，R 侧从 `band[1]+1`） | 反变换落点实测 = 底图 (586,430) 正是 R 侧接缝线 ⇒ 进手臂层 0 px |
| ③ | 手臂掩膜外缘切在描边中间 → 衣身点状残线 | 外缘直接取底图剪影边缘（最右不透明像素） | y440 掩膜到 x628、真实黑轮廓 x631~634 ⇒ 缺口归零 |
| ④ | 肩区过度回填 → 衣身白边 | 回填限定在肩关节半径 `SHOULDER_FILL_R = 46` | 无描边白边 41 行 → 0 行 |
| ⑤ | 前臂段二分线切边暴露成无描边白边 | fore 段切边补 2 px `OUTLINE_RGB=(10,14,34)` 描边 | 端面描边 0 px → 2 px（补上，不是残留） |

### P0-2 办公场景（3 个根因）

| # | 根因 | 修法 | 客观量 |
|---|---|---|---|
| ⑥ | 整张桌子在 front 层 ⇒ 双手完全落在桌板上方 | 桌子拆两层：`prop_desk_surface`（back 台面）+ `prop_desk`（front 前沿/桌腿/笔记本） | desk_far 556 / desk_near 668；hand_l [348,567,425,638]、hand_r [439,571,535,641] |
| ⑦ | 屏幕朝观众 = 角色坐在屏幕背后 | 笔记本背板朝观众、屏幕朝角色，放角色右侧 | 盖板均亮 120.9 → **62.3**（<120 = 看到石墨背板） |
| ⑧ | 头部不朝笔记本 | `head_transform` 转向 | 青蓝边缘光 6542 → 921 px（背板边缘，不是正面发光面） |

### P0-3 睡眠场景（3 个根因）

| # | 根因 | 修法 | 客观量 |
|---|---|---|---|
| ⑨ | 被子上沿是一条拍脑袋画的直线，不跟身体轮廓 | 沿角色**实测轮廓**逐列 alpha 测量起伏 | 身体核心覆盖率 0.699 → **0.958** |
| ⑩ | 被子边缘硬切 + 无褶皱 ⇒ 材质粗糙 | 4 长 3 短羽化弧形褶皱 + 17 px 翻折亮边 + 左缘翻折带与横向渐变淡出 | 最外 2px alpha 中位数 0（完全渐隐）；遮脸 9 px ≤ 30 |
| ⑪ | 床 / 月亮抢戏 | 床与月亮重做，月亮只做氛围 | 整体覆盖 0.369 → 0.506 |

---

## 四、本轮改写的既有判据口径（**不是放宽标准，见 QA 报告 §2**）

| 判据 | 旧口径的问题 | 新口径 | 修正后 |
|---|---|---|---|
| r158 C1 肤色面积比 | 未除该动作纵向压扁系数（跳跃帧 scale_y 0.84） | 先除压扁系数再比 | 25/25 |
| r158 G1 元检查 | 检源码字符串是否还在 | 改成拿底图当已知坏样本自检（1044 px） | 25/25 |
| r158 `handGap` 测量盒 | 盒太窄，脸/脖被当成手 | 放宽盒 + 排除 y0<400 的脸/脖块 | 25/25 |
| r162 `chestHandGroups` | 同上 | 同上 | 5/5 |
| r162 R2-5 中帧手势跨度 | 固定像素阈值 | 改三帧手部质心高度变化幅度（比心 22 px vs 鼓掌 96 px，差 74 ≥ 40） | 5/5 |
| e2e TI4 / TI5 | 期望道具数 8、work 挂载未含新道具 | `loaded=9`；work 挂载加 `prop_desk_surface` | 59/59 |

---

## 五、验收结果一览

| 项 | 结果 |
|---|---|
| node 单元测试 | **152 passed / 0 failed**（11 个测试文件） |
| R165 手臂客观判据 | 新素材 **18/18 PASS**；R162 旧素材 **15/18 FAIL**（复验成立） |
| R165 场景客观判据 | R165 **7/7 PASS**；R162 旧素材 **3 FAIL**（P2-1 / P2-2 / P3-1）⇒ 新旧完美区分 |
| 真实 Electron 运行时客观校验 | **23/23** + **6/6** |
| e2e | **59 PASS / 0 FAIL / 0 NOT_VERIFIED** |
| 面积 / 脚底 / 冠部绝对测量 | 6 个动作全 PASS |
| 真实运行采集 | 648 帧，`loaded=9 failed=0` |
| 人物身份与服装 | R138 23 帧 SHA256 逐字节未变 |
| **Mac 真机 GUI 验收** | **PENDING**（沙箱内无法代替你在 Mac 上看最终观感；入口 `candidates/candidate_b_c2/C2_Mac人工验收.command`） |

---

## 六、做不到 / 未验证（如实列出，**不标视觉 PASS**）

1. **手指级"真比心"几何在 200×240 下物理不可读**（单指宽约 2 px）⇒ 沿用"双手在胸前合拢 + 头侧爱心特效"，**不是**真比心。
2. **真正的 180° 背面转身仍做不到** —— R138 全库无背面素材，需新素材，清单原样保留。
3. **抬手类动作（wave / hands_up / clap）肩部有一小块平涂衣身色** —— 2D 切割动画固有代价；A/B 对照（平涂 R46 / 原图 R46 / 平涂 R32）在 200×240 下均读作大褂肩线，**不构成额外肢体**。
4. **手臂摆动本质是剪影式切割动画** —— 在实测的 6 组角度内不可见切割感，超出范围仍可能看出切割痕迹。
5. **Mac 真机验收 PENDING** —— 本轮用真实 Electron 采集 + 200×240/256×256 真实尺寸合成替代客观判据，**最终观感仍需你确认**。

---

## 七、复审入口

```bash
cd "/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/candidates/candidate_b_c2"

# 1) R165 手臂客观判据 (18 项) —— 把 assets/character_R158/ 换回 R162 旧素材会 15/18 FAIL
python3 46_R165_arm_verify.py --dir assets/character_R158 --out evidence_r165_arm_verify.json
# 2) R165 场景客观判据 (7 项, 新旧同套口径)
python3 49_R165_scene_verify.py
# 3) 重新产出全部对比图
python3 47_R165_evidence.py
# 4) 既有回归测试
node tests/r158_click_actions.test.js
node tests/r162_click_defects.test.js
node tests/r156_click_props_work.test.js
# 5) 运行时真实像素校验 (23 + 6 项)
python3 34_R156_runtime_verify.py --preview-dir evidence_r165_preview
python3 39_R158_runtime_verify.py --preview-dir evidence_r165_preview
# 6) 重放烘焙 / manifest (可复算)
python3 37_R158_action_bake.py
python3 30_R156_props_bake.py
python3 38_R158_manifest_update.py
# 7) 真实 Electron 全量回归
bash R147_e2e_test.sh
```

素材本体（R138 原始 23 帧 PNG）不在审查包内，位于 `assets/character_R138/` 与 R138 交付目录；SHA256 清单见 `assets/character_R138_derived/r138_source_checksums.json`。

# R162 交付索引 — 修复点击动作视觉缺陷（残影 / 断线 / 头顶破损 / 手势清晰度）

> **生成时间**：2026-10-21
> **对应任务书**：R162（修复点击动作视觉缺陷，承接 R158）
> **作者**：MiniMax（Mavis）
> **上一交付**：R158 `03fe4d9`（实现 `b740070` / 索引 `4b3793f` / 归档 `03fe4d9`）
> **本轮实现提交**：`e60931e`
> **状态**：`ENGINEERING_GATE = PASS` / `VISUAL_GATE = PASS`（沙箱内真实 Electron 运行 + 像素级客观测量 + 独立可复算的缺陷回归测试）/ **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** / `V0_0_RELEASE_STATUS = NOT_FROZEN`
> **范围声明**：本轮未进入 V0.1；**未改动人物身份与服装**；**未重新开发整个动画系统**（只在 `arm_rig` 的切层/关节/衣身还原 + 烘焙顺序两层修）；**未充值 i2i**（全程无 AI 生图调用）；6 个点击动作与三类生活场景原样保留；R148 行走方向与 R113 拖拽核心未动。

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 主工作区 | `/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/` |
| 候选实现 | `candidates/candidate_b_c2/` |
| QA 报告 | `docs/R162_QA_REPORT.md` |
| 交付索引 | `docs/R162_DELIVERY_INDEX.md`（本文件） |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R162_review.zip`（98 文件 / 11,421,943 B） |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R162_review.zip.sha256`（`d278cb1b083e596c349c72fa8afb1c0ffcb4a69f232f7079bb5f5361ccdc3836`） |
| 备份 | `backup/V0.0_backup_20261021_180542_r162.zip`（184 文件 / 47,481,093 B）+ 同名 `.sha256`（`e17e35a28ff14f13990a6c672bb25af1c817fc68232292ae99602bd1b13689eb`） |
| e2e 机器报告 | `candidates/candidate_b_c2/evidence_r147_e2e.json`（59 项） |
| 运行时客观量化 | `candidates/candidate_b_c2/evidence_r162_preview/r156_runtime_verify.json`（23 项）+ `r158_runtime_verify.json`（6 项） |
| rig 层缺陷验证 | `candidates/candidate_b_c2/evidence_r162_rig_verify.json` |
| 绝对测量报告 | `candidates/candidate_b_c2/evidence_r162_measure.json`（面积 / 脚底 / 冠部） |
| 可观看运行预览 | `candidates/candidate_b_c2/evidence_r162_gifs/`（6 个 GIF + 1 张总览图） |
| 真实采集帧 | `candidates/candidate_b_c2/evidence_r162_preview/`（648 帧；仅 `preview_meta.json` / `run.log` / 校验 JSON 入库） |
| 可视化产物副本 | `/Users/musk123/Downloads/minimax工作文件夹/图文工作/R162_点击动作修复/`（6 GIF + 总览图 + 爱心特效 PNG） |
| Mac 真机验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command`（双击即用） |

**ZIP SHA256 不写在本索引内**（避免「改索引就改 ZIP 哈希」的循环自引用），写在 ZIP 旁边的独立 `.sha256` 文件；本索引里的占位符在**归档提交**里替换为最终值。

---

## 二、代码结构（R162 变更）

```
candidates/candidate_b_c2/
├── src/                        (未改 —— 未重做动画系统)
├── assets/
│   ├── character_R138/         (未改 — 23 帧 SHA256 逐字节一致, 人物身份与服装未动)
│   ├── character_R153/         (未改)
│   ├── character_R156/         (未改 — 7 个道具 + 5 个场景原样保留)
│   ├── character_R158/         ★ 改: 18 张动作帧全部重烘焙 + prop_heart.png 移到头侧
│   └── character_R141_manifest.json  ★ 改: 幂等更新 (38_R158_manifest_update.py)
├── tests/
│   ├── r158_click_actions.test.js  ★ 改: C4/C6/G2 三条判据按新几何与新机制改写
│   └── r162_click_defects.test.js  ★ 新增: 5 条缺陷回归判据 (旧素材必 FAIL, 已复验)
├── 36_R158_arm_rig.py          ★ 改: 接缝线封顶 / 剪影外扩 / 双线性旋转 / 衣身重建 + 阴影迁移
├── 37_R158_action_bake.py      ★ 改: 烘焙顺序 (表情先贴) + 比心/鼓掌姿态重标定 + 爱心特效位置
├── 38_R158_manifest_update.py  (未改 — 幂等, 本轮重跑)
├── 39_R158_runtime_verify.py   ★ 改: 爱心特效取样区改为由 prop_heart 包围盒换算 (不再写死)
├── 40_R158_preview_gif.py      (未改 — 本轮换用 evidence_r162_preview/gifs 目录)
├── 42_R158_measure_report.py   (未改)
├── 43_R162_defect_verify.py    ★ 新增: rig 层缺陷验证 (衣身外缘连续性 / 接缝越界 / 青色残留)
└── 44_R162_package.py          ★ 新增: 交付打包器
```

---

## 三、本轮修掉的 4 条独立根因（详见 QA 报告 §2）

| # | 根因 | 修法 | 客观量（旧 → 新，门槛） |
|---|---|---|---|
| ① | 重建大褂外缘时，描边颜色取自描边**外侧**的透明区 ⇒ 整条边成**虚线** | 保留底图剪影描边带原像素；描边色只从底图接缝线取 | 衣身外缘**最长断开行数** 45~62 → **0~31**（门槛 38）；重建后衣身外缘**连续 236/236 行** |
| ② | 洪水填充从**肩膀上方**绕进大褂胸口 ⇒ 手臂一转衣身跟着飞 ⇒ **白色残块** | 按底图实测接缝线 `SEAM_L` 给手臂掩膜内侧封顶 | 越过接缝线 **544 px → 0 行** |
| ③ | 袖子外侧**青色高光带**留在掩膜外 ⇒ 原地一条**青色虚线** | 沿不透明像素一路走到真正的剪影，整段并入掩膜 | 外侧青色残留 **176~243 px → 0 px** |
| ④ | 烘焙顺序「变换→压扁→贴五官」⇒ 五官贴进已压扁的头顶 | 改为「手臂→贴五官→头部变换→整体压扁」 | `cheer_jump_0` 头部 y<260 肤色 **2605 → 0**（阈值 0） |

附带：旋转改**预乘 alpha 双线性**（最近邻把斜描边重采样成 1px 阶梯）；删除旧几何遗留的 `x>412` 硬裁剪（会腰斩袖子）；衣身平涂改为「干净白 + 18px 柔和边缘阴影」（原来是一块灰板）。

---

## 四、本轮改写的 3 条 R158 既有判据（不是放宽标准，见 QA 报告 §7）

| 判据 | 旧口径 | 新口径 | 理由 |
|---|---|---|---|
| C4 双手举高 | 固定矩形的实心像素 >150 | 两翼 y<300 的**肤色**像素 >300 | 手臂重标定后外移十几个像素，固定矩形只擦到边缘 ⇒ 假失败；新判据与坐标无关，且基准帧同区域为 0 |
| C6 鼓掌 | 张开帧**剪影宽度**比合拢帧大 60px | 两掌**间距**张开 ≥40、合拢 ≤张开−25 | 旧口径对应的是旧参数「双臂平举」；新口径直接用「鼓掌」的定义 |
| G2 修复落在 arm_rig | 源码含 `大褂外缘之外`/`edge_by_row` | 源码含 `SEAM_L`/`seam_x` 与 `OUT_KEEP` | 衣身还原机制整体重写；「不得手工改图」这条要求不变 |

---

## 五、验收结果一览

| 项 | 结果 |
|---|---|
| 单元测试 | **152 passed / 0 failed**（11 个测试文件；R158 时代为 147，本轮新增 5 条缺陷回归） |
| R162 缺陷回归判据（旧素材复验） | 旧素材 **0 passed / 5 failed** → 新素材 **5 passed / 0 failed** |
| 真实 Electron 运行时客观校验 | **23/23**（`34_R156_runtime_verify.py`）+ **6/6**（`39_R158_runtime_verify.py`） |
| rig 层缺陷验证 | 全项通过（连续 236/236、越界 0 行、青色 0 px） |
| e2e | **59 PASS / 0 FAIL / 0 NOT_VERIFIED** |
| 面积 / 脚底 / 冠部绝对测量 | 6 个动作全 PASS：面积偏差 −10.00%~+8.52%（门槛 15%）、脚底中心位移 ≤0.16 px（门槛 24）、冠部行宽差 5.07%~12.32%（门槛 15%） |
| 唯一性自检 | 19 张新帧互不相同，且与 R138/R153/R156 无字节重复 |
| 人物身份与服装 | R138 23 帧 SHA256 逐字节未变；R156 道具与场景逐字节保留 |
| **Mac 真机 GUI 验收** | **PENDING**（沙箱内无法完成真机观感与鼠标手感判断） |

---

## 六、做不到 / 未验证（如实列出，**不标视觉 PASS**）

1. **手指级几何「真比心」在 200×240 下物理不可读** —— 缩放 0.196319，整只开口约 12×16 屏幕 px，单指宽约 2 px。比心用「双手在下颌前合成心形 + 头侧大爱心特效」，动作描述里如实写明**不是**真比心。
2. **真正的 180° 背面转身仍做不到** —— R158 已下架 `cheer_spin` 并给出精确新素材需求清单，本轮不涉及，清单原样保留。
3. **比心帧两腕之间的小青色竖条是袖口腕带本身**（结构真实存在），不是残留；「无额外青色残影」已用客观判据证明。
4. **手臂摆动本质是剪影式切割动画** —— 本轮不重做动画系统；在实测的 6 组角度内肉眼不可见切割感，超出该角度范围仍可能看出切割痕迹。
5. **Mac 真机验收 PENDING** —— 入口 `candidates/candidate_b_c2/C2_Mac人工验收.command`。

---

## 七、复审入口

```bash
cd "/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/candidates/candidate_b_c2"

# 1) R162 缺陷回归 (5 项) —— 把 assets/character_R158/ 换回 R158 旧素材会 0/5 FAIL
node tests/r162_click_defects.test.js
# 2) R158 点击互动质量 (25 项)
node tests/r158_click_actions.test.js
# 3) rig 层缺陷验证
python3 43_R162_defect_verify.py
# 4) 运行时真实像素校验 (6 + 23 项)
python3 39_R158_runtime_verify.py --preview-dir evidence_r162_preview
python3 34_R156_runtime_verify.py --preview-dir evidence_r162_preview
# 5) 重放烘焙 / manifest / GIF (可复算)
python3 37_R158_action_bake.py
python3 38_R158_manifest_update.py
python3 40_R158_preview_gif.py --preview-dir evidence_r162_preview --out-dir evidence_r162_gifs
# 6) 真实 Electron 全量回归
bash R147_e2e_test.sh
```

素材本体（R138 原始 23 帧 PNG）不在审查包内，位于 `assets/character_R138/` 与 R138 交付目录；SHA256 清单见 `assets/character_R138_derived/r138_source_checksums.json`。

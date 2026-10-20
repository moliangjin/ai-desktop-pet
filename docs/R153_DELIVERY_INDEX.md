# R153 交付索引 — 动作自然度与自主生活丰富度升级

> **生成时间**：2026-10-20
> **对应任务书**：R153（动作自然度与自主生活丰富度升级）
> **作者**：MiniMax（Mavis）
> **上一交付**：R148 `3928e7c`（索引 `b70eff5`，归档 `3984bd2`）
> **本轮实现提交**：`664abac366d5b7379adc9c25ecef9dbcae5740c6`
> **状态**：ENGINEERING_GATE = PASS / VISUAL_GATE = PASS（沙箱内真实运行 + 像素级客观测量）/ **MAC_REAL_GUI_ACCEPTANCE = PENDING** / V0_0_RELEASE_STATUS = NOT_FROZEN

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 主工作区 | `/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/` |
| 候选实现 | `candidates/candidate_b_c2/` |
| QA 报告 | `docs/R153_QA_REPORT.md` |
| 交付索引 | `docs/R153_DELIVERY_INDEX.md`（本文件） |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R153_review.zip` |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R153_review.zip.sha256` |
| 备份 | `backup/V0.0_backup_<时间戳>_r153.zip`（仓库内） |
| e2e 机器报告 | `candidates/candidate_b_c2/evidence_r147_e2e.json` |
| 运行时客观量化 | `candidates/candidate_b_c2/evidence_r153_runtime.json`（6 项）、`evidence_r153_posture.json`（行走姿态） |
| 可观看运行预览 | `candidates/candidate_b_c2/evidence_r153_gifs/`（16 个 GIF + 动作总览图 + 坐躺过渡帧条） |
| 真实采集帧 | `candidates/candidate_b_c2/evidence_r153_preview/`（456 帧，仅 `preview_meta.json` 入库） |
| 烘焙帧复核图 | `candidates/candidate_b_c2/evidence_r153_baked/`（接触表 + 头部放大） |
| 可视化产物副本 | `/Users/musk123/Downloads/minimax工作文件夹/图文工作/R153_*` |
| Mac 真机验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command`（双击即用） |

**ZIP SHA256 不写在本索引内**（避免"改索引就改 ZIP 哈希"的循环自引用），写在 ZIP 旁边的独立 `.sha256` 文件。

---

## 二、代码结构（R153 变更）

```
candidates/candidate_b_c2/
├── src/
│   ├── action_library.js      ★ 新增: 动作目录(15) / 小动作池 / 过渡策略 / NEEDS_NEW_ASSETS(5) / 动作计数
│   ├── renderer.js            ★ 改: 动作库独立加载与上报 + 动作级交叉溶解 + 帧级交叉溶解
│   │                              + 点击反馈改"歪头+眯眼笑"(happy) + 轻微弹跳
│   ├── behavior_engine.js     ★ 改: 5 类加权活动池 + 重复折扣 + 醒后冷却 + GESTURE/SIT/DOZE 三态
│   │                              + 打盹/长睡分层 + 睡眠呼吸主循环 + 睡眠姿态微调 + 醒来伸懒腰
│   ├── anim_clock.js          ★ 改: period() 支持"每帧时长数组"(修致命 bug: 帧永不推进)
│   ├── main.js                ★ 改: 预览采集新增 9 个库动作场景 + 坐躺过渡 + 坐下打盹
│   ├── sprite_layout.js       (未改)
│   ├── idle_director.js       (未改 — manifest 侧改 blink_sequence 即可生效)
│   ├── click_policy.js        (未改)
│   └── asset_gate.js          (未改)
├── assets/
│   ├── character_R138/        (未改 — 23 帧 SHA256 47/47 一致, 逐字节未变)
│   ├── character_R138_derived/ (未改 — R148 派生镜像帧 + 基线清单)
│   ├── character_R153/        ★ 新增: 12 张局部烘焙帧 + bake_report.json
│   └── character_R141_manifest.json  ★ 改: walk_*.lean.skew_x=0 + idle.director(blink=[5]/excluded=[1,2,3,4])
│                                      + action_library(9 动作) + frame_blend_ms + 逐帧实测 bbox
├── tests/
│   ├── r153_action_library.test.js  ★ 新增: 22 项 (动作库/不虚增/局部烘焙诚实性/帧级溶解/anim_clock 回归)
│   ├── r153_png.js                 ★ 新增: 共享 PNG 像素解码 + 姿态测量助手
│   ├── r141_behavior_engine.test.js ★ 改: T2~T9 按新活动池模型重写 + 新增 T13~T17
│   ├── r147_interaction.test.js    ★ 改: B3(醒来伸懒腰) / C1(排除帧4) / D1(错切归零) / D2(像素级偏心)
│   └── r148_walk_direction.test.js ★ 改: T6 改为"错切归零 + 像素级偏心相反"
├── 22_R153_pose_bake.py        ★ 新增: 局部烘焙器 (眼部合成 / 头部连续权重场弯曲 / 胸口软遮罩微缩)
├── 23_R153_manifest_update.py  ★ 新增: manifest 修订器 (幂等, 可重放)
├── 24_R153_package.py          ★ 新增: 交付打包器 (审查包 + 备份 + SHA256)
├── 25_R153_walk_posture_verify.py ★ 新增: 行走姿态像素级客观测量 + 三态渲染对比图
├── 26_R153_baked_contact_sheet.py ★ 新增: 烘焙帧接触表 + 头部放大复核图
├── 27_R153_runtime_verify.py   ★ 新增: 运行时 6 项客观量化
├── 28_R153_preview_gif.py      ★ 新增: 16 个动作 GIF + 总览图 + 坐躺过渡帧条
└── R147_e2e_test.sh            ★ 改: TD1(错切归零) / TD5(眨眼帧5) / TC2(合法帧集合) + 新增 TH0~TH9
```

---

## 三、动作清单（15 个 = 6 核心 + 9 新增）

| # | 动作 | 帧资源 | 来源 |
|---|---|---|---|
| 1–6 | `idle` / `walk_left` / `walk_right` / `sleep_enter` / `sleep_loop` / `wake_up` | 23 个互不相同文件 | R138 + R148 派生 |
| 7 | `look_around` 左右张望 | 2 | ★ R153 烘焙 |
| 8 | `tilt_head` 歪头观察 | 2 | ★ R153 烘焙 |
| 9 | `head_nod` 点头回应 | 2 | ★ R153 烘焙 |
| 10 | `happy` 开心反馈 | 1 | ★ R153 烘焙 |
| 11 | `blink_soft` 柔和眨眼 | 2 | ★ R153 烘焙 |
| 12 | `stretch` 伸懒腰 | 1 | R138 `idle_01`（复用） |
| 13 | `sit_rest` 坐下休息 | 1 | R138 坐姿（复用） |
| 14 | `doze` 困倦打盹 | 1 | ★ R153 烘焙 |
| 15 | `sleep_breath` 躺姿呼吸 | 2 | ★ R153 烘焙 |

**需新素材（如实列出，未伪报完成）**：原地转身 / 后退走 / 奔跑 / 挥手打招呼 / 进食喝水 —— 清单见 `src/action_library.js` 的 `NEEDS_NEW_ASSETS`，单测 `F1` 断言它们不得出现在已实现动作表里。

---

## 四、四条反馈的结论

| 反馈 | 结论 | 关键证据 |
|---|---|---|
| 启动/点击莫名抬手、手放胸前 | **已解决** | 眨眼序列 `[5]`，`idle_04` 运行时出现 **0 次**；点击段头部虹膜像素 min=9 vs 待机 min=90 |
| 坐下瞬间躺姿 | **已解决** | 坐→躺之间实测 **7~8 帧**渐变中间态（`d_sit` 21.6→44.5，`d_lie` 78.6→30.8）；运行时日志 `FRAME_BLEND sleep_enter 0 -> 1 (320ms)` |
| 行走前倾像摔倒 | **已解决** | 躯干偏心 0.0933 身高(5.33°) → **0.0166 身高(0.95°)**，保留 17.8%；运行时 walk_left −0.0123 / walk_right +0.0123，最大绝对 0.0169 < 3% 门槛 |
| 动作太少、行为重复 | **已解决** | 6 → **15 个动作**；5 类加权活动池 + 重复折扣 + 醒后冷却 + 打盹/长睡分层 |

---

## 五、测试结果

| 类别 | 结果 |
|---|---|
| 单元测试（8 份） | **101 / 101 PASS**（r141 17 · r144 8+9+9 · r147 5+23 · r148 8 · r153 22） |
| e2e（真实 Electron） | **28 / 28 PASS**（静态基线 4 · 单测 1 · 运行时自检 3 · 交互 5 · 撞边 1 · 客观量化 4 · R153 专项 10） |
| R113 拖拽核心 | **9 / 9 区块逐字未改**（对比 `6e35231`） |
| R138 原始 23 帧 | **47 / 47 SHA256 一致，逐字节未变** |
| A1 母版 | SHA256 `3344d5fe8d47058475ea7265909478bae4886bb1ee6165412f406a83422013df` 未变 |
| 核心 6 组帧槽位 | 仍为 **23 个互不相同**的文件（资产门禁口径不变） |
| Mac 真机验收 | **PENDING**（沙箱无法完成真实鼠标手感 / 真机观感） |

---

## 六、仍需用户确认（真机）

1. 左右行走观感（错切归零后重心是否真的"端正"，而不是"太正"）
2. 点击"歪头眯眼笑"的手感与清晰度
3. 坐→躺溶解过渡在真机上的观感是否自然
4. 9 个新动作在真机上的可辨识度
5. 自主行为的"无聊感"是否真的下降（建议连续观察 5~10 分钟）
6. R148 遗留：左右行走方向、点击手感、待机观感

---

## 七、复审命令

```bash
cd candidates/candidate_b_c2
node tests/r153_action_library.test.js      # 22 项
node tests/r141_behavior_engine.test.js     # 17 项
node tests/r147_interaction.test.js         # 23 项
node tests/r148_walk_direction.test.js      # 8 项
python3 25_R153_walk_posture_verify.py      # 行走姿态像素级测量
python3 27_R153_runtime_verify.py --preview-dir evidence_r153_preview
bash R147_e2e_test.sh                       # 真实 Electron 全量回归
python3 tools/r144_drag_core_diff.py        # R113 拖拽核心逐字未改
```

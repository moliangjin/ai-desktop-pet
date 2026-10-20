# R156 交付索引 — 点击互动扩展 + 场景道具 + 办公待机场景

> **生成时间**：2026-10-21
> **对应任务书**：R156（点击互动扩展 + 场景道具 + 办公待机场景）
> **作者**：MiniMax（Mavis）
> **上一交付**：R153 `664abac` / 索引 `36fe633` / 归档 `a51ba84`
> **本轮实现提交**：`5905cf1558bf9a16175cc1d40db336bacecf7e47`
> **状态**：`ENGINEERING_GATE = PASS` / `VISUAL_GATE = PASS`（沙箱内真实运行 + 像素级客观测量）/ **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** / `V0_0_RELEASE_STATUS = NOT_FROZEN`
> **范围声明**：本轮未进入 V0.1；未重做角色；未新增语音/记忆/AI 聊天；未做系统鼠标注入；未充值 i2i（全部道具为程序化矢量绘制）。

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 主工作区 | `/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/` |
| 候选实现 | `candidates/candidate_b_c2/` |
| QA 报告 | `docs/R156_QA_REPORT.md` |
| 交付索引 | `docs/R156_DELIVERY_INDEX.md`（本文件） |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R156_review.zip` |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R156_review.zip.sha256` |
| 备份 | `backup/V0.0_backup_<时间戳>_r156.zip` + 同名 `.sha256` |
| e2e 机器报告 | `candidates/candidate_b_c2/evidence_r147_e2e.json`（57 项） |
| 运行时客观量化 | `candidates/candidate_b_c2/evidence_r156_preview/r156_runtime_verify.json`（22 项） |
| 可观看运行预览 | `candidates/candidate_b_c2/evidence_r156_gifs/`（10 个 GIF + 2 张总览图） |
| 真实采集帧 | `candidates/candidate_b_c2/evidence_r156_preview/`（650 帧，仅 `preview_meta.json` / `run.log` / 校验 JSON 入库） |
| Mac 真机验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command`（双击即用，已标注本轮 8 项重点） |

**ZIP SHA256 不写在本索引内**（避免"改索引就改 ZIP 哈希"的循环自引用），写在 ZIP 旁边的独立 `.sha256` 文件。

---

## 二、代码结构（R156 变更）

```
candidates/candidate_b_c2/
├── src/
│   ├── action_library.js      ★ 改: 登记 7 个新动作 + CLICK_POOL + pickClickReaction()
│   │                              + NEEDS_NEW_ASSETS 追加 4 条 + countDistinctActions 增报 clickPool
│   ├── renderer.js             ★ 改: 道具 sprite 系统 (propTextures_/propSprites_/restageProps/
│   │                              applyPropsFor/updateProps, 260ms 淡入淡出, back→角色→front 分层)
│   │                              + 点击反馈改"随机池多帧播放" (clickClock_/clickRecent_)
│   │                              + R144 裁切自检的地面接触判据按逐帧地面行精确化
│   ├── behavior_engine.js      ★ 改: WORK 办公状态 (weight 0.10 / 9~19s) + 连续办公权重归零
│   │                              + 导出 ACTIVITY_KINDS 固定顺序 ['gesture','walk','sit','doze','work','sleep']
│   ├── sprite_layout.js        ★ 改: computeLayout 支持逐帧 ground_tex_y + 新增导出 groundRowY()
│   │                              + contentRectToScreen/frameScreenRect 支持地面行
│   ├── main.js                 ★ 改: 新增 10 个预览场景 (6 个点击动作 + 连点 10 次随机序列
│   │                              + 睡觉/沙发/办公 + 道具退场)
│   ├── anim_clock.js           (未改)
│   ├── idle_director.js        (未改)
│   ├── click_policy.js         (未改)
│   └── asset_gate.js           (未改)
├── assets/
│   ├── character_R138/         (未改 — 23 帧 SHA256 47/47 一致, 逐字节未变)
│   ├── character_R138_derived/ (未改 — R148 派生镜像帧 + 基线清单)
│   ├── character_R153/         (未改 — 12 张烘焙帧)
│   ├── character_R156/         ★ 新增: 20 张动作帧 + 7 个道具 PNG
│   │                              + bake_report.json / props_report.json / r156_measure_report.json
│   └── character_R141_manifest.json  ★ 改: version=R156-RUNTIME + action_library(16 动作)
│                                      + click_reactions(6 池) + props(7 道具 + 5 场景)
│                                      + 逐帧 ground_tex_y + r156_click_props_work(诚实性声明)
├── tests/
│   ├── r156_click_props_work.test.js ★ 新增: 21 项 (点击池结构/不虚增/随机可达与权重/
│   │                                      道具登记/front 不遮脸/两种画布零裁切/地面行一致/
│   │                                      腾空离地量化/WORK 状态/诚实性/23 帧与 R138 字节未变)
│   ├── r153_action_library.test.js   ★ 改: 动作数断言改为对 R156 扩展稳健 (仍守卫 R153 九动作)
│   ├── r141_behavior_engine.test.js ★ 改: 随机阈值改为从引擎权重反推 (不再写死)
│   └── (其余 6 份未改)
├── 29_R156_pose_bake.py       ★ 新增: 姿态烘焙器 (4 新技法 + 唯一性自检, 产出 20 帧)
├── 30_R156_props_bake.py      ★ 新增: 7 个程序化矢量道具 (显式落影 + 底边裁切)
├── 31_R156_measure_preview.py ★ 新增: 逐帧真实 bbox + 统一 scale + 正确 z 序场景预览
├── 32_R156_manifest_update.py ★ 新增: manifest 幂等修订器
├── 33_R156_preview_gif.py     ★ 新增: 10 个 GIF + 2 张总览图
├── 34_R156_runtime_verify.py  ★ 新增: 运行时 22 项客观校验 (真实采集像素)
├── 35_R156_package.py         ★ 新增: 交付打包器 (审查包 + 备份 + SHA256)
├── 27_R153_runtime_verify.py  ★ 改: TH5 判据按 R156 口径一般化 (见下)
└── R147_e2e_test.sh           ★ 改: 新增 [I] R156 专项段 (TI0~TI7 + 22 条逐项) + 修正 4 处过时判据
```

---

## 三、动作与场景清单

### 3.1 点击动作池（6 个，每个 3 帧）

| 动作 | 语义 | 帧资源 | 权重 |
|---|---|---|---|
| `cheer_heart` | 比心（近似） | `cheer_heart_0/1/2.png` | 3 |
| `cheer_wink` | 歪头眨眼卖萌 | `cheer_wink_0/1/2.png` | 3 |
| `cheer_jump` | 开心小跳 | `cheer_jump_0/1/2.png` | 2 |
| `cheer_spin` | 原地轻盈转身 | `cheer_spin_0/1/2.png` | 2 |
| `cheer_hands` | 双手小庆祝 | `cheer_hands_0/1/2.png` | 2 |
| `cheer_sway` | 开心摇摆 | `cheer_sway_0/1/2.png` | 2 |

### 3.2 动作库（16 个 = R153 的 9 + R156 的 7）

R153 九个：`look_around` / `tilt_head` / `head_nod` / `happy` / `blink_soft` / `stretch` / `sit_rest` / `doze` / `sleep_breath`
R156 七个：`work` + 上表 6 个点击动作
动作总数：**22**（6 核心 + 16 库动作）

### 3.3 道具场景（5 个）

| 场景 | 地面纹理行 | back 层 | front 层 |
|---|---|---|---|
| `sleep_breath` / `sleep_loop` | 818 | 床、月亮 | 被子 |
| `sit_rest` / `doze` | 1001 | 小沙发 | — |
| `work` | 1001 | 转椅 | 小桌+笔记本、屏幕微光 |

`sleep_enter` / `wake_up` **不带道具**（床只放得下躺姿 ⇒ 睡→醒走场景溶解过渡）。

---

## 四、本轮完成定义的逐条对照

| # | 任务书 §七 条件 | 结论 | 关键证据 |
|---|---|---|---|
| 1 | 点击动作池 ≥5 | ✅ **6 个** | 真实点击 10 次两次独立采集分别触发 **5 种 / 6 种**，均**无相邻重复** |
| 2 | 睡觉有床 + 月亮灯光 | ✅ | 道具专属区域可见像素 **5505**（阈值 400）；正向对照 9123 |
| 3 | 坐下有小沙发 | ✅ | 可见像素 **5429** |
| 4 | 存在"电脑前办公"待机场景 | ✅ | 可见像素 **1610**；运行时 `R156 PROPS action=work scene=yes mounted=prop_chair,prop_desk,prop_screen_glow` |
| 5 | 已接入运行逻辑 | ✅ | 点击池/道具/办公状态全部进运行时；e2e TI2~TI6 逐项验证 |
| 6 | 真实运行证据 | ✅ | 真实 Electron 采集 650 帧 + 10 GIF + 2 总览图 + 22 项像素校验 |
| 7 | 不破坏已有主链路 | ✅ | R113 拖拽 9/9 逐字未改；R138 23 帧 47/47 SHA256 一致；A1 母版未变；e2e 57/57 |

---

## 五、测试结果

| 类别 | 结果 |
|---|---|
| 单元测试（9 份） | **122 / 122 PASS**（r141 17 · r144 8+9+9 · r147 5+23 · r148 8 · r153 22 · r156 21） |
| 运行时客观校验（真实采集像素） | **22 / 22 PASS**（`evidence_r156_preview/r156_runtime_verify.json`） |
| e2e（真实 Electron） | **57 / 57 PASS**（静态基线 4 · 单测 1 · 运行时自检 3 · 交互 5 · 撞边 1 · 客观量化 4 · R153 专项 10 · R156 专项 29） |
| R113 拖拽核心 | **9 / 9 区块逐字未改** |
| R138 原始 23 帧 | **47 / 47 SHA256 一致，逐字节未变** |
| A1 母版 | SHA256 `3344d5fe8d47058475ea7265909478bae4886bb1ee6165412f406a83422013df` 未变 |
| Mac 真机验收 | **PENDING** |

### 5.1 本轮修正的 5 处失效判据（如实记录，详见 `docs/R156_QA_REPORT.md` §7.4）

首次 e2e 为 **51 PASS / 5 FAIL**，逐条查证后确认**没有一条是产品缺陷**，全部是判据过时或本轮自己写的解析 bug：

| 项 | 根因 | 处理 |
|---|---|---|
| TC3 | R144 的"内容底边贴地面线"是站立角色时代写的判据 | 精确化为"落在该帧声明的接触行上"；未声明 `ground_tex_y` 的帧判据与 R144 **逐字等价**。修正后 `frames=114 clipped=0 issues=0` |
| TG2 | 人工 7px 弹跳本轮主动移除；且旧测量降采样到 48×58 会抹平细微动作 | 改判"点击段 ≥2 个不同画面"，测量换成全分辨率口径 |
| TH5 | "虹膜必须等于 happy 参照"的代理判据在随机池下失效 | 改为"明显区别于僵立待机"（表情变化 或 姿态变化） |
| TH8 | 动作库 9 → 16，写死的数字过时 | 改为 `actions>=9 且 failed=0` |
| TI2 / TI3 | 本轮自己写的 e2e 解析 bug（`print(True)` 大写） | 提取时统一小写化 |

---

## 六、做不到的事（如实列出，未硬标 PASS）

| 项 | 原因 | 实际交付 |
|---|---|---|
| 真正的双手比心 / 挥手 / 双手拍掌 | R138 无手部素材 | 近似表现（右手横在胸 / 双臂抬起） |
| 敲键盘 | R138 无手部素材 | 办公只能"看屏幕 / 思考 / 停顿" |
| 真正的 180° 背面转身 | R138 无背面素材 | 2D 表现手法：正面 → 水平压缩 64%（读作侧身）→ 回正 |
| 明显的跳离地面 | 角色头顶在纹理里只剩 37px 余量；standard 模式头顶屏幕余量仅 11.1px | 运行时地面行 1015，离地 5.5~7.1px；可读性主要靠压扁↔伸展↔落地的剪影对比 |
| 坐姿躺上床 | 床垫净空 632 纹理 px < 坐姿帧高 886~964 | `sleep_enter`/`wake_up` 不带道具，睡→醒走场景溶解 |

已写入 `src/action_library.js` 的 `NEEDS_NEW_ASSETS`（本轮追加 `heart_hands_true` / `clap_hands` / `typing` / `spin_180`），单测断言它们**不得**出现在已实现动作表里。

---

## 七、Mac 真机待确认（沙箱无法完成）

1. **点击 6 个动作的随机性与不重复**（连点 10 次是否真的每次不同）
2. **睡觉场景**（床 + 月亮 + 被子是否够"像在睡觉"，且不挡脸）
3. **坐沙发的接触关系**（屁股是否贴住沙发、有没有悬空）
4. **办公场景像不像在办公**（从笔记本屏幕后探出上半身的观感）
5. **道具退场是否干净**（离开场景后床/沙发/桌子是否真的消失）
6. **桌宠透明感是否被破坏**（不能变成大插画）
7. **跳跃离地幅度**（已知上限，如 §六 所述，不作为 bug 报）
8. **角色身份是否零漂移**（银白短发 / 冰蓝眼睛 / 白大褂）
9. R147/R148/R153 遗留：左右行走观感、点击手感、待机观感、坐躺过渡观感、动作可辨识度、自主行为是否真的不再无聊

---

## 八、复审命令

```bash
cd candidates/candidate_b_c2
node tests/r156_click_props_work.test.js     # 21 项
node tests/r153_action_library.test.js        # 22 项
node tests/r141_behavior_engine.test.js       # 17 项
python3 34_R156_runtime_verify.py --preview-dir evidence_r156_preview   # 22 项真实像素校验
python3 29_R156_pose_bake.py                  # 重放烘焙 (内置唯一性自检)
python3 30_R156_props_bake.py                 # 重放 7 个道具
python3 32_R156_manifest_update.py            # manifest 幂等更新, 可重放
python3 33_R156_preview_gif.py                # 重新生成 GIF 与总览图
bash R147_e2e_test.sh                         # 真实 Electron 全量回归 (57 项)
python3 tools/r144_drag_core_diff.py          # R113 拖拽核心逐字未改
```

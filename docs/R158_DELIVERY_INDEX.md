# R158 交付索引 — 修复点击互动视觉质量（真手势 / 反伪动作）

> **生成时间**：2026-10-21
> **对应任务书**：R158（修复点击互动视觉质量，承接 R156）
> **作者**：MiniMax（Mavis）
> **上一交付**：R156 `59851cd` / 索引 `75114f8` / 实现 `5905cf1`
> **本轮实现提交**：`947396fab68487b4d97cc1855b5442f9e0e0ba14`
> **状态**：`ENGINEERING_GATE = PASS` / `VISUAL_GATE = PASS`（沙箱内真实 Electron 运行 + 像素级客观测量）/ **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** / `V0_0_RELEASE_STATUS = NOT_FROZEN`
> **范围声明**：本轮未进入 V0.1；未重做角色/C1；未新增语音/记忆/AI 聊天；未做系统鼠标注入；**未充值 i2i**；未做 180° 转身的伪实现；未批量重做旧动作。R156 的床/月亮/被子、小沙发、办公场景**原样保留未重做**。

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 主工作区 | `/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/` |
| 候选实现 | `candidates/candidate_b_c2/` |
| QA 报告 | `docs/R158_QA_REPORT.md` |
| 交付索引 | `docs/R158_DELIVERY_INDEX.md`（本文件） |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R158_review.zip`（89 文件 / 11,148,951 B） |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R158_review.zip.sha256`（`b400c62be1e6d2c3a92ce04cbed00a8ea642f95c2a274c17d9a35c7d8f99cd7a`） |
| 备份 | `backup/V0.0_backup_20261021_061729_r158.zip`（179 文件 / 47,273,554 B）+ 同名 `.sha256`（`9f4b80fbb985926290686b336eccabdb8ba7b857f3a51f77278c0e445cc9eec8`） |
| e2e 机器报告 | `candidates/candidate_b_c2/evidence_r147_e2e.json`（59 项） |
| 运行时客观量化 | `candidates/candidate_b_c2/evidence_r158_preview/r156_runtime_verify.json`（23 项）+ `r158_runtime_verify.json`（6 项） |
| 可观看运行预览 | `candidates/candidate_b_c2/evidence_r158_gifs/`（6 个 GIF + 1 张总览图） |
| 真实采集帧 | `candidates/candidate_b_c2/evidence_r158_preview/`（648 帧，仅 `preview_meta.json` / `run.log` / 校验 JSON 入库） |
| 可视化产物副本 | `/Users/musk123/Downloads/minimax工作文件夹/图文工作/R158_点击互动/`（6 GIF + 总览图 + 爱心特效 PNG） |
| Mac 真机验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command`（双击即用，已换成 R158 的 8 项重点） |

**ZIP SHA256 不写在本索引内**（避免"改索引就改 ZIP 哈希"的循环自引用），写在 ZIP 旁边的独立 `.sha256` 文件。

---

## 二、代码结构（R158 变更）

```
candidates/candidate_b_c2/
├── src/
│   ├── action_library.js      ★ 改: ACTION_CATALOG 换新 6 个 R158 动作 (下架 cheer_spin/
│   │                              cheer_wink/cheer_hands/cheer_sway) + CLICK_POOL 换新 6 项
│   │                              + NEEDS_NEW_ASSETS 删除已实现的 wave_hand/clap_hands,
│   │                              spin_180 改为"缺背面素材"并指向需求清单
│   ├── renderer.js            ★ 改: 修复关键 bug —— 点击反馈路径从不调用 applyPropsFor
│   │                              ⇒ 爱心特效从未挂载。startClickReaction 末尾加
│   │                              applyPropsFor(action), updateClickReaction 的 finished
│   │                              分支加 applyPropsFor(currentAction) (道具随点击退场)
│   ├── main.js                ★ 改: 预览采集 CLICK_ACTIONS 换新 6 个
│   ├── behavior_engine.js     (未改)
│   ├── sprite_layout.js       (未改)
│   ├── idle_director.js       (未改)
│   ├── click_policy.js        (未改)
│   ├── anim_clock.js          (未改)
│   └── asset_gate.js          (未改)
├── assets/
│   ├── character_R138/        (未改 — 23 帧 SHA256 47/47 一致, 逐字节未变)
│   ├── character_R138_derived/(未改 — R148 派生镜像帧 + 基线清单)
│   ├── character_R153/        (未改 — 12 张烘焙帧)
│   ├── character_R156/        (未改 — 20 张动作帧 + 7 个道具 PNG, R156 场景原样保留)
│   ├── character_R158/        ★ 新增: 18 张动作帧 (6 动作 × 3 帧) + prop_heart.png
│   │                              + bake_report.json (含每帧姿态参数与唯一性自检)
│   └── character_R141_manifest.json  ★ 改: version=R158-RUNTIME + action_library(16 动作)
│                                      + click_reactions(6 池) + props(8 道具 + 6 场景)
│                                      + 新增 r158_click_actions (可行性/诚实边界/新素材需求)
├── tests/
│   ├── r158_click_actions.test.js ★ 新增: 25 项 (A 池结构 / B 帧唯一性 / C 反"压缩·平移"
│   │                                      客观像素判据 C1·C2·C2b·C3~C8 / D 双画布零裁切与
│   │                                      腾空量 / E 爱心道具 / F 诚实性 / G 反"髋部虚线鬼影")
│   ├── r156_click_props_work.test.js ★ 改: 道具 7→8、E1 移除已实现的 wave_hand/clap_hands、
│   │                                      E2 改写为"诚实标注做不到项"、F2 允许 character_R158/、
│   │                                      C1 允许纯 front 层特效场景
│   ├── r153_action_library.test.js   ★ 改: F1 移除 wave_hand
│   └── (其余 7 份未改)
├── 36_R158_arm_rig.py        ★ 新增: 三关节手臂骨架 (切层 + 圆形咬口 + 两骨 IK + 衣身还原)
│                              + 髋部虚线鬼影修复 (大褂外缘整段清透明 + 紧贴手部皮肤5px内的
│                                原手轮廓清理; 见 QA 报告 §3.1)
├── 36b_R158_pose_preview.py  ★ 新增: 姿态预览工具
├── 37_R158_action_bake.py    ★ 新增: 6 动作 × 3 帧烘焙 (内置唯一性自检)
├── 38_R158_manifest_update.py★ 新增: manifest 幂等修订器
├── 39_R158_runtime_verify.py ★ 新增: R158 专项 6 项真实像素校验
├── 40_R158_preview_gif.py    ★ 新增: 6 个 GIF + 1 张总览图
├── 41_R158_package.py        ★ 新增: 交付打包器 (审查包 + 备份 + SHA256)
├── 42_R158_measure_report.py ★ 新增: 绝对数值测量 (报告 §5.2 的数据来源)
├── 34_R156_runtime_verify.py ★ 改: 点击场景列表改为 6 个新动作
├── R147_e2e_test.sh          ★ 改: TI4 loaded=7→8 (新增 prop_heart) + TB1 测试清单加入
│                                 r158_click_actions (9→10 份) + 新增 TI8 (R158 可观看产物齐备)
└── C2_Mac人工验收.command    ★ 改: R156 的 8 项重点看项换成 R158 的 8 项
```

---

## 三、动作清单

### 3.1 点击动作池（R158，6 个，每个 3 帧）

| 动作 | 语义 | 帧资源 | 手臂骨架姿态（肩/肘/腕，°） | 权重 |
|---|---|---|---|---|
| `cheer_wave` | **真挥手**（单臂抬起 + 手腕摆动） | `cheer_wave_0/1/2` | R (130,0,0)→(133,−14,30)→(126,−7,−30) | 3 |
| `cheer_hands_up` | **双臂高举欢呼** | `cheer_hands_up_0/1/2` | L ∓118/126/112，R ±118/126/112 | 3 |
| `cheer_heart` | **比心**（双手胸前合拢 + 爱心特效） | `cheer_heart_0/1/2` | L (−6,116,−18)/(−6,140,0)/(−6,132,−8) | 3 |
| `cheer_tilt` | **歪头眨眼卖萌**（头转 17°/17°/12°） | `cheer_tilt_0/1/2` | 双臂自然下垂 | 3 |
| `cheer_clap` | **鼓掌**（张开→合拢→张开） | `cheer_clap_0/1/2` | L (−30,−34,0)/(−6,142,0)/(−32,−30,0) | 2 |
| `cheer_jump` | **开心跳跃**（双臂上扬 + 离地） | `cheer_jump_0/1/2` | 双臂上扬 ∓124 | 2 |

### 3.2 已下架的 R156 动作（4 个，全部为几何形变冒充）

| 下架动作 | R156 的做法 | 为什么下架 |
|---|---|---|
| `cheer_spin` | 整体水平压缩到 **64%** 读作侧身 | 面积 −36%，是压缩不是转身；且真转身无背面素材 |
| `cheer_sway` | 整体水平平移 **±46 纹理 px** | 是平移不是摇摆 |
| `cheer_wink` | 头部权重场 14°/7° | 与 R158 的 `cheer_tilt`（17°/17°/12°）语义重叠，属重命名虚增 |
| `cheer_hands` | 复用 idle_04「右手横在胸前」 | 用户已明确不喜欢这一手 |

### 3.3 动作库（16 个 = R153 的 9 + R156 的 1 + R158 的 6）

R153 九个：`look_around` / `tilt_head` / `head_nod` / `happy` / `blink_soft` / `stretch` / `sit_rest` / `doze` / `sleep_breath`
R156 一个：`work`（办公待机）
R158 六个：上表 6 个点击动作

### 3.4 道具场景（6 个，R156 的 5 个原样保留 + 新增 1 个）

| 场景 | 地面纹理行 | back 层 | front 层 |
|---|---|---|---|
| `sleep_breath` / `sleep_loop` | 818 | 床、月亮 | 被子 |
| `sit_rest` / `doze` | 1001 | 小沙发 | — |
| `work` | 1001 | 转椅 | 小桌+笔记本、屏幕微光 |
| **`cheer_heart`**（★新增） | 987 | — | **prop_heart 爱心特效** |

---

## 四、本轮任务书逐条对照

| # | R158 要求 | 结论 | 关键证据 |
|---|---|---|---|
| 1 | ≥5 种视觉上明确、动作含义清晰的点击互动 | ✅ **6 种** | 真实点击 10 次两次独立采集分别触发 **6 种 / 5 种**，均**无相邻重复** |
| 2 | 优先真比心 / 开心跳跃 / 优美转身 / 挥手庆祝 / 歪头眨眼 | ⚠️ **4 达成 + 1 明确做不到** | 挥手 ✅ 跳跃 ✅ 挥手庆祝 ✅ 歪头眨眼 ✅ 比心 = 双手合拢+爱心特效（手指级不可读，如实标注）转身 ❌ 已下架 |
| 3 | 禁止用压缩/平移/重命名冒充新动作 | ✅ | 4 个旧动作下架；客观像素判据 C1/C2/C2b/C3~C8 逐条否证，6/6 全 PASS |
| 4 | 先评估素材可行性 | ✅ **推翻了前两轮结论** | `idle_00_base.png` 两只手都张开带描边；切层脚本漏切左臂；全库无背面素材 |
| 5 | 不可行则列新素材需求、停止伪修复 | ✅ | `manifest.r158_click_actions.new_asset_requests` 2 条（含帧数/姿态/视角/分辨率/验收口径/失败史） |
| 6 | 不得虚报 PASS | ✅ | 真比心与真转身**未**标 PASS；`MAC_REAL_GUI_ACCEPTANCE = PENDING` |
| 7 | 不得擅自充值 | ✅ | 全程无 i2i、无付费调用 |
| 8 | 保留 R156 场景 | ✅ | 7 原道具 + 5 原场景逐字节保留；e2e TTI3/TTI5/TTI7 全绿 |
| 9 | 保留 R148 行走方向 | ✅ | e2e TTD1：`walk_left skew=0, walk_right skew=0` |
| 10 | 保留原拖拽功能 | ✅ | e2e TTA4：R113 拖拽核心 **9/9 区块逐字未改**（对比 `6e35231`） |
| 11 | 不进入 V0.1 | ✅ | 全部改动在 V0.0 范围内 |

---

## 五、测试结果

| 类别 | 结果 |
|---|---|
| 单元测试（10 份） | **147 / 147 PASS**（r141 17 · r144 8+9+9 · r147 5+23 · r148 8 · r153 22 · r156 21 · **r158 25**） |
| 运行时客观校验（真实采集像素） | **23 / 23 PASS**（R156 通用）+ **6 / 6 PASS**（R158 专项） |
| e2e（真实 Electron） | **59 / 59 PASS，0 FAIL，0 NOT_VERIFIED** |
| R113 拖拽核心 | **9 / 9 区块逐字未改** |
| R138 原始 23 帧 | **47 / 47 SHA256 一致，逐字节未变** |
| A1 母版 | SHA256 `3344d5fe8d47058475ea7265909478bae4886bb1ee6165412f406a83422013df` 未变 |
| Mac 真机验收 | **PENDING** |

**反鬼影回归测试（G 组）**：以底图里「手部皮肤外沿 5 纹理 px 以内」为手的描边位置，逐帧逐侧统计新帧里该带**仍为暗色不透明**的像素 ⇒ 原手轮廓残留。门槛 **≤60 px/帧**（干净基线 **11 px**，修复前 **83 px**）。已用「换回修复前的帧」验证该测试确实会 FAIL。

### 5.1 反伪动作的客观判据（绝对值 + 绝对门槛 + 门槛出处）

基准帧 `character_R138/idle/idle_00_base.png`：实心面积 **214814 px**、脚底中心 x **522.3**、冠部行宽 **138 px**。

| 动作 | 面积中位数 | 面积偏差 | 门槛 15% | 脚底位移 | 门槛 24px | 冠部偏差 | 门槛 15% |
|---|---|---|---|---|---|---|---|
| `cheer_wave` | 221300 | **+3.02%** | ✅ | **0.00 px** | ✅ | 5.07% | ✅ |
| `cheer_hands_up` | 226968 | **+5.66%** | ✅ | **0.00 px** | ✅ | 10.87% | ✅ |
| `cheer_heart` | 213870 | **−0.44%** | ✅ | **0.00 px** | ✅ | 12.32% | ✅ |
| `cheer_clap` | 224805 | **+4.65%** | ✅ | **0.00 px** | ✅ | 5.07% | ✅ |
| `cheer_jump` | 187561 | **−12.69%** | ✅ | **0.16 px** | ✅ | 10.14% | ✅ |
| `cheer_tilt` | 213930 | **−0.41%** | ✅ | **0.00 px** | ✅ | 9.42% | ✅ |

**门槛出处**：R156 的 `cheer_spin` 中位帧面积只有基准的 **64%（= −36%）** ⇒ 整体压缩门限定 15%；R156 的 `cheer_sway` 实测平移 **46 px** ⇒ 整体平移门限定 24 px。

### 5.2 本轮对 e2e 脚本的 3 处改动（判据随资产变更同步更新，非放宽）

| 项 | 改动 | 原因 |
|---|---|---|
| TI4 | `loaded=7` → `loaded=8` | R158 新增 `prop_heart` 道具 |
| TB1 | 测试清单加 `r158_click_actions`（9→10 份） | 新增 1 份单元测试 |
| TI8 | **新增** R158 可观看产物齐备校验 | 新增 6 GIF + 1 总览图 |

---

## 六、做不到的事（如实列出，未硬标 PASS）

| 项 | 原因 | 实际交付 / 后续 |
|---|---|---|
| **真正的 180° 背面转身** | R138 全库只有正面素材；程序化"合成背面"需重画后脑勺 + 实验服背面，属重画角色；i2i 三/四视角 R130 已连续三次失败；本轮禁止充值 | **已下架 `cheer_spin`，不做伪实现**；需求清单见 `manifest.r158_click_actions.new_asset_requests`（4~6 张 1024×1024 正面→3/4→背面→3/4→正面，验收口径写明） |
| **手指级比心（拇指+食指围心形）** | compact 200×240 窗口 scale 0.196，整只开口仅约 **12×16 屏幕 px**，单指宽约 **2 px**，围出的心形不可读 | 比心用**双手胸前合拢 + 爱心特效**；动作描述 / `NEEDS_NEW_ASSETS` / manifest / 单测**四处如实标注**；需求清单已列 |
| 敲键盘手部动作 | R138 无键盘手部素材 | 办公场景仍只能"看屏幕 / 思考 / 停顿"；保留在 `NEEDS_NEW_ASSETS` |
| 大幅跳跃离地 | standard 256×256 头顶只剩 **11 px** 余量 ⇒ 离地 ≤ 7 屏幕 px | `ground_tex_y` 已顶到 **1015**（R156 同值，**已是上限**）；改用**双臂上扬 + 更深蓄力/落地压缩**的剪影对比 |

---

## 七、Mac 真机待确认（沙箱无法完成）

1. **真挥手** —— 是不是单臂抬起 + 手腕摆动，不是整体变形
2. **双臂高举欢呼** —— 是不是两条手臂都真的举高
3. **比心 + 爱心特效** —— 胸前有没有粉红爱心（R158 修的 bug 就是这个），双手是否确实在胸前
4. **鼓掌** —— 手是不是真的张开又合拢（剪影宽度变化肉眼可见）
5. **跳跃** —— 有没有真的离地 + 双臂上扬
6. **歪头** —— 头是不是真的歪了（17°，明显）
7. **大褂边缘** —— 抬手/举臂处有没有鬼影 / 锯齿 / 灰色块
8. **道具退场** —— 点完动作结束，爱心特效有没有退干净，不残留到待机

**建议连点 10~15 次**，覆盖 6 个动作各至少 2 次。

R147/R148/R153 遗留：左右行走观感、点击手感、待机观感、坐躺过渡观感、新动作可辨识度、自主行为是否真的不再无聊。

---

## 八、复审命令

```bash
cd candidates/candidate_b_c2
node   tests/r158_click_actions.test.js     # 25 项 (含反"压缩/平移"与反"鬼影"客观判据)
node   tests/r156_click_props_work.test.js  # 21 项
python3 39_R158_runtime_verify.py --preview-dir evidence_r158_preview   # 6 项 R158 专项
python3 34_R156_runtime_verify.py --preview-dir evidence_r158_preview   # 23 项通用
python3 37_R158_action_bake.py              # 重放烘焙 (内置唯一性自检)
python3 38_R158_manifest_update.py         # manifest 幂等更新, 可重放
python3 40_R158_preview_gif.py --preview-dir evidence_r158_preview --out-dir evidence_r158_gifs
python3 42_R158_measure_report.py          # 绝对数值测量 (报告 §5.1 的数据来源)
bash   R147_e2e_test.sh                     # 真实 Electron 全量回归 (59 项)
python3 tools/r144_drag_core_diff.py        # R113 拖拽核心逐字未改
```

素材本体（R138 原始 23 帧 PNG）不在审查包内，位于产品目录 `assets/character_R138/` 与 R138 交付目录，SHA256 清单见 `assets/character_R138_derived/r138_source_checksums.json`。

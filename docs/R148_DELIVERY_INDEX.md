# R148 交付索引 — 左右行走倒退问题（walk_right）精准修复

> **生成时间**：2026-10-20
> **对应任务书**：R148（walk_right 倒退步态补充验收）
> **作者**：MiniMax（Mavis）
> **上一交付**：R147 `7ec7a3b`（归档 `d102d84`，索引修正 `02cc4ee`）
> **本轮实现提交**：`3928e7c406ff00e3e66d144a1de8c2345494cec5`
> **状态**：ENGINEERING_GATE = PASS / VISUAL_GATE = PASS / MAC_REAL_GUI_ACCEPTANCE = PENDING / V0_0_RELEASE_STATUS = NOT_FROZEN

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 主工作区 | `/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/` |
| 候选实现 | `candidates/candidate_b_c2/` |
| QA 报告 | `docs/R148_QA_REPORT.md` |
| 交付索引 | `docs/R148_DELIVERY_INDEX.md`（本文件） |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R148_review.zip` |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R148_review.zip.sha256` |
| 备份 | `backup/V0.0_backup_20261020_182920_r148.zip`（106 文件 / 20,133,049 B）+ 同名 `.sha256` |
| e2e 机器报告 | `candidates/candidate_b_c2/evidence_r147_e2e.json`、`evidence_r144_e2e.json`、`evidence_r141_e2e.json` |
| 方向几何测量 | `candidates/candidate_b_c2/evidence_r148_direction.json` |
| 可观看运行预览 | `candidates/candidate_b_c2/evidence_r148_preview/`（6 个 GIF + 汇总图 + x 轨迹图 + 采集元数据） |
| 可视化产物副本 | `/Users/musk123/Downloads/minimax工作文件夹/图文工作/R148_*.gif`、`R148_*.png` |
| Mac 真机验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command`（双击即用） |

**ZIP SHA256 不写在本索引内**（避免"改索引就改 ZIP 哈希"的循环自引用），写在 ZIP 旁边的独立 `.sha256` 文件。

---

## 二、代码结构（R148 变更）

```
candidates/candidate_b_c2/
├── src/
│   ├── main.js              ★ 改: 预览采集新增"撞边转向"场景 + 行走场景帧数 26→32
│   ├── renderer.js          (未改)
│   ├── behavior_engine.js   (未改)
│   ├── sprite_layout.js     (未改)
│   ├── idle_director.js     (未改)
│   ├── click_policy.js      (未改)
│   ├── anim_clock.js        (未改)
│   └── asset_gate.js        (未改)
├── assets/
│   ├── character_R138/      (未改 — 23 帧 SHA256 47/47 校验一致, 逐字节未变)
│   ├── character_R138_derived/            ★ 新增
│   │   ├── walk_right_mirror/walk_right_m_0{0..3}.png   ★ 派生镜像帧 (4 张, 1024×1024 RGBA)
│   │   ├── walk_right_mirror/derive_report.json         ★ 派生元数据 (源/派生路径/徽章框/NCC/bbox/SHA256)
│   │   └── r138_source_checksums.json                   ★ R138 23 帧 SHA256 基线 (供回归核对)
│   └── character_R141_manifest.json  ★ 改: walk_right 指向派生帧 + 逐帧实测 bbox
│                                         + r148_walk_direction_fix 根因段 + notes
├── tests/
│   ├── r148_walk_direction.test.js   ★ 新增: 8 项 (镜像严格性/徽章未镜像/方向语义/资产字节/框一致)
│   ├── r147_interaction.test.js      ★ 改: D1 断言更新到 R148 新设计 (原断言要求"必须用原始帧")
│   └── 其余 5 个测试文件              (未改 — 66/66 零回归)
├── 17_R148_mirror_derive.py     ★ 新增: 派生镜像帧 (整体水平镜像 + 徽章就地修补 + 羽化归位)
├── 18_R148_direction_verify.py  ★ 新增: 鞋尖几何客观测量 + 镜像严格性逐像素校验
├── 19_R148_manifest_update.py   ★ 新增: manifest 修订器 (幂等, 可重放)
├── 20_R148_preview_gif.py       ★ 新增: R148 版 GIF 合成 (含撞边 x 轨迹图)
├── 21_R148_package.py           ★ 新增: 交付打包器 (轻量审查包 + 完整备份 + SHA256)
├── evidence_r148_direction.json ★ 新增: 方向测量结果
├── evidence_r148_preview/       ★ 新增: 6 个可观看 GIF + 汇总图 + x 轨迹图 + preview_meta.json
└── R141/R144/R147_e2e_test.sh   (未改 — 本轮全部重跑通过)
```

---

## 三、本轮修的问题（一句话版）

| 编号 | 问题 | 修复 | 真实运行证据 |
|---|---|---|---|
| P0 | 窗口向右移动时人物却向左迈步（用户真机截图确认 `WALK_RIGHT_VISUAL_DIRECTION = FAIL`） | 以**已确认方向正确**的 `walk_left` 4 帧为源做**整体水平镜像**派生 `walk_right`；胸口烧瓶徽章**原样归位**回角色左胸（不镜像） | 鞋尖几何：旧 `walk_right` = `[-1,-1,-1]`（落脚侧全左）**FAIL** → R148 = `[+1,+1,+1]`（落脚侧全右）**PASS**；派生帧在徽章区外与镜像**逐像素差 = 0**（4 帧 × 4,175,904 字节全中）→ 证明是整体镜像而非只翻腿 |

**同时更正 R147 报告 §1.1 的错误结论**：R147 写"`walk_right_01` 踩地那只鞋的鞋尖朝右（迈右步）"，与本轮可复现测量**相反**（实测朝左），与用户截图描述一致。本轮以可复现脚本取代主观判断。

---

## 四、测试与门禁

| 项 | 结果 |
|---|---|
| 单元测试 | **74/74 PASS**（原有 66 项零回归 + R148 新增 8 项） |
| R147 e2e（真实 Electron + 真实采集帧量化） | PASS=18 FAIL=0 NOT_VERIFIED=0 |
| R144 e2e（真实 Electron） | PASS=23 FAIL=0 NOT_VERIFIED=3（3 项为"需真实物理鼠标"，与基线一致） |
| R141 e2e（真实 Electron） | PASS=13 FAIL=0 NOT_VERIFIED=3（同上） |
| R113 拖拽核心逐字未改 | 9/9 区块（对比 `6e35231`） |
| R138 23 帧资产 SHA256 | 47/47 校验一致（逐字节未变） |
| A1 母版 SHA256 | `3344d5fe8d47058475ea7265909478bae4886bb1ee6165412f406a83422013df` 未变 |
| 200×240 / 256×256 零裁切 | 真实 PixiJS 矩阵下 46 帧 clipped=0 issues=0 |
| 真实撞边 | `WALK_LEFT -> WALK_RIGHT (edge-turn)`；窗口 x 轨迹 100→8（边缘）→85 |
| 真实行走帧倾斜方向 | 左 −13.02px（32/32 帧为负）/ 右 +16.29px（0/32 帧为负） |

---

## 五、可观看的运行预览（`evidence_r148_preview/`）

| 文件 | 内容 |
|---|---|
| `R148_walk_left.gif` | 32 帧 / 2.08s = **4.00 个完整步态循环**，窗口真实左移 75px |
| `R148_walk_right.gif` | 32 帧 / 2.08s = **4.00 个完整步态循环**，窗口真实右移 77px（R148 修复后） |
| `R148_edge_turn.gif` | 90 帧 / 4.95s，撞边转向（含转向点标注），**转向在第 45 帧** |
| `R148_edge_turn_trail.png` | 撞边场景窗口真实 x 轨迹图 |
| `R148_idle.gif` | 90 帧 / 6.3s，稳定站姿 + 自然眨眼，无胸腔膨胀 |
| `R148_click.gif` | 26 帧，眨眼 + 9px 弹跳 |
| `R148_wake.gif` | 34 帧，sleep_loop → wake_up → idle |
| `R148_preview_summary.png` | 六场景并排汇总 |
| `preview_meta.json` | 每帧的窗口真实 x 位移 |

> GIF 里的角色像素是**真实运行时 `capturePage` 截图**，未做任何重绘；
> 行走场景中角色在画布上的横向位置 = 该帧窗口的**真实**位移。

---

## 六、残余限制（详见 `docs/R148_QA_REPORT.md` §五）

1. **原 R138 的 `walk_right` 4 帧不再被运行时使用**（保留在 `character_R138/walk_right/`，字节未变，SHA256 可验）。运行时实际加载 23 帧 = 19 张 R138 原帧 + 4 张派生帧，仍是 23 个互不相同的文件（资产门禁口径不变）。
2. **`walk_right` 现为 `walk_left` 的镜像** → 接缝比随 `walk_left`（1.55），此前左右不一致的接缝现在左右一致。属取舍。
3. **左移仍有约 20px/s 脚步滑动**（R138 源素材是"刚性同向漂移"步态，资产固有）。根治需重画 `walk_left` 四帧（i2i 余额 0 且本轮禁止充值）。
4. **方向仍靠正面 3/4 立绘 + 倾斜表达**，R138 无侧视帧、无背视帧 —— 素材固有限制。
5. **徽章修复是像素级修补**，纹理级放大可见极轻微痕迹，**运行时分辨率下不可见**（屏幕上约 10×11px）。
6. **真实物理鼠标手感未验证** → `MAC_REAL_GUI_ACCEPTANCE = PENDING`。
7. **未另起 `R148_e2e.sh`**：复用 R147/R144/R141 三套 e2e 脚本，R148 新断言落在 `tests/r148_walk_direction.test.js` 与 `18_R148_direction_verify.py`。

---

## 七、待用户真机确认（一次性）

双击 `candidates/candidate_b_c2/C2_Mac人工验收.command`，重点看这几点：

1. **向右走时人物是朝右迈步**（鞋尖朝右、落脚脚在画面右侧）—— 本轮核心验收点；
2. **向左走时人物是朝左迈步**（上一轮已确认，本轮未改 `walk_left`）；
3. **撞到屏幕边缘掉头时，朝向与步态同步切换**，不出现"头朝一边、腿朝另一边"；
4. 转身瞬间胸口烧瓶徽章**仍在角色左胸**、不左右跳变；
5. 左右走动的**服装/腿袜一致**（转身不换装）；
6. R147 遗留：点击手感、待机观感。

---

*本索引由 MiniMax（Mavis）生成。ZIP 的 SHA256 见同名 `.sha256` 文件（刻意不内嵌，避免自引用）。*

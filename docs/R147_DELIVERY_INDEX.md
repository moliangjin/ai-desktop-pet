# R147 交付索引 — Mac 真机验收首轮交互与动画质量修复

> **生成时间**：2026-10-20
> **对应任务书**：R147 §八
> **作者**：MiniMax（Mavis）
> **上一交付**：R144 `3634d83`
> **状态**：ENGINEERING_GATE = PASS / VISUAL_GATE = PASS / MAC_REAL_GUI_ACCEPTANCE = PENDING / V0_0_RELEASE_STATUS = NOT_FROZEN

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 主工作区 | `/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/` |
| 候选实现 | `candidates/candidate_b_c2/` |
| QA 报告 | `docs/R147_QA_REPORT.md` |
| 交付索引 | `docs/R147_DELIVERY_INDEX.md`（本文件） |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R147_review.zip` |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R147_review.zip.sha256` |
| 备份 | `backup/V0.0_backup_<ts>_r147.zip` + 同名 `.sha256` |
| e2e 机器报告 | `candidates/candidate_b_c2/evidence_r147_e2e.json` |
| 可观看运行预览 | `candidates/candidate_b_c2/evidence_r147_preview/`（5 个 GIF + 汇总图 + 采集元数据 + 量化结果） |
| Mac 真机验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command`（双击即用） |

**ZIP SHA256 不写在本索引内**（避免"改索引就改 ZIP 哈希"的循环自引用），写在 ZIP 旁边的独立 `.sha256` 文件。

---

## 二、代码结构（R147 变更）

```
candidates/candidate_b_c2/
├── src/
│   ├── main.js              ★ 改: character-click IPC / --preview 真实采集模式 / 行为引擎预览钩子
│   ├── renderer.js          ★ 改: applyAction 首帧同步 / 方向倾斜 / 待机导演 / 点击判定与反馈
│   │                             / finishPress 幂等守卫 / preview-command 真实 pointer 采集
│   │                             / R147 运行时自检
│   ├── behavior_engine.js   ★ 改: onUserClick / holdBriefly / wakeUpByUser / startWalk / 移动暂停
│   ├── sprite_layout.js     ★ 改: 错切感知缩放 + cosθ 竖直修正 + skewAngleX + frameScreenRect
│   ├── idle_director.js     ★ 新增: 自然待机导演 (稳定站姿 + 自然眨眼) — 生产与测试共用
│   ├── click_policy.js      ★ 新增: 点击/拖拽判定 — 生产与测试共用
│   ├── anim_clock.js        (未改)
│   ├── asset_gate.js        (未改)
│   └── renderer.html        (未改)
├── assets/
│   ├── character_R138/      (未改 — 23 帧 SHA256 与 R138 交付清单校验 47/47 一致)
│   └── character_R141_manifest.json  ★ 改: walk_left/walk_right 的 lean 段 + idle 的 director 段
│                                         (帧路径未改, 仍是 23 个不同文件)
├── tests/
│   ├── r141_behavior_engine.test.js   (未改 — 12/12 PASS)
│   ├── r144_layout.test.js            ★ 改: 布局输入改为与生产一致 (含方向倾斜), 断言未削弱, 8/8 PASS
│   ├── r144_oneshot.test.js           (未改 — 9/9 PASS)
│   ├── r144_assets_gate.test.js       (未改 — 9/9 PASS)
│   ├── r147_layout_pixi_parity.test.js ★ 新增: 5 项 (与真实 @pixi/math 顶点矩阵逐点一致)
│   ├── r147_interaction.test.js        ★ 新增: 23 项 (点击/拖拽/唤醒/待机/步态/资产)
│   └── lib/png_reader.js              (未改)
├── tools/
│   ├── r144_layout_probe.js           (未改)
│   └── r144_drag_core_diff.py         (未改 — 9/9 区块逐字未改)
├── 11_R147_manifest_update.py   ★ 新增: manifest 修订器 (幂等, 可重放)
├── 12_R147_gait_analysis.py     ★ 新增: 步态/躯干轴/循环接缝定量分析
├── 13_R147_step_direction.py    ★ 新增: 迈步方向判定 (鞋底前后脚分离)
├── 14_R147_preview_gif.py       ★ 新增: 真实采集帧 → GIF 合成器
├── 15_R147_preview_verify.py    ★ 新增: 真实采集帧客观量化校验
├── R147_e2e_test.sh             ★ 新增: 端到端 (真实 Electron + 真实采集帧量化 + 撞边反向)
├── evidence_r147_e2e.json       ★ 新增: e2e 机器可读报告
├── evidence_r147_preview/       ★ 新增: 5 个可观看 GIF + 汇总图 + preview_meta.json + preview_verify.json
├── C2_Mac人工验收.command       (未改)
└── run.sh                       (未改)
```

---

## 三、本轮修复的 3 个问题 + 1 个同步项（一句话版）

| 编号 | 问题 | 修复 | 真实运行证据 |
|---|---|---|---|
| P0-1 | 左右转身腿没转向，像倒着走 | 保留左右各自迈步帧（素材本身方向正确），对整帧施加**反向整体倾斜**（身体连同腿一起朝移动方向倾，纹理不镜像） | 左移上半身偏移 **-13.00px（26/26 帧）**；右移 **+12.23px（0/26 帧）** |
| P0-2 | 点击毫无反馈 | 新增 `click_policy.js` 判定 CLICK/DRAG/HOLD/CANCEL；CLICK → 眨眼 + 9px 弹跳；睡眠点击 → `wake_up` 过渡 | `kind=CLICK elapsed=92ms dist=0.0px` → 弹跳 9px；`DRAGGING -> WAKE_UP (user-click-wake)` → 播完回 IDLE |
| P1 | 待机胸部剧烈膨胀 | `idle_director.js`：稳定站姿 + 自然眨眼（1.6~3.4s 随机），膨胀帧 1/回落帧 2/3 不再进入播放序列 | 胸部轮廓宽度波动 **0px**；6.3s 内眨眼 3 次，间隔 1830ms / 2580ms |
| 同步 | 切动作时 texture 未立即更新 | 统一入口 `applyAction()`：切换同一时刻换好首帧 + 地面线 + 倾斜 | 运行时自检 6 组动作 **issues=0** |

---

## 四、测试与门禁

| 项 | 结果 |
|---|---|
| 单元测试 | **66/66 PASS**（R144 的 38 项零回归 + R147 新增 28 项） |
| R144 e2e（真实 Electron） | PASS=22 FAIL=0 NOT_VERIFIED=4（B9 撞边本轮随机未触发，环境项） |
| R141 e2e（真实 Electron） | PASS=12 FAIL=0 NOT_VERIFIED=4（T8 撞边同上） |
| R147 e2e（真实 Electron + 真实采集帧量化） | PASS=18 FAIL=0 NOT_VERIFIED=0 |
| R113 拖拽核心逐字未改 | 9/9 区块（对比 `6e35231`） |
| R138 23 帧资产 SHA256 | 47/47 校验一致 |
| A1 母版 SHA256 | `3344d5fe8d47058475ea7265909478bae4886bb1ee6165412f406a83422013df` 未变 |
| 200×240 / 256×256 零裁切 | 真实 PixiJS 矩阵下 46 帧 clipped=0 issues=0 |

---

## 五、可观看的运行预览（`evidence_r147_preview/`）

| 文件 | 内容 |
|---|---|
| `R147_walk_left.gif` | 26 帧，窗口真实左移 60px，walk_left + 向左倾斜 |
| `R147_walk_right.gif` | 26 帧，窗口真实右移 60px，walk_right + 向右倾斜 |
| `R147_idle.gif` | 90 帧 / 6.3s，稳定站姿 + 3 次随机眨眼，无胸腔膨胀 |
| `R147_click.gif` | 26 帧，眨眼 + 9px 弹跳 |
| `R147_wake.gif` | 34 帧，sleep_loop → wake_up → idle |
| `R147_preview_summary.png` | 五场景并排汇总 |
| `preview_meta.json` | 每帧的窗口真实 x 位移 |
| `preview_verify.json` | 量化结果（胸宽波动 / 弹跳 / 左右倾斜） |

> GIF 里的角色像素是**真实运行时 `capturePage` 截图**，未做任何重绘；
> 行走场景中角色在画布上的横向位置 = 该帧窗口的**真实**位移。

---

## 六、残余限制（详见 `docs/R147_QA_REPORT.md` §五）

1. 左移仍有约 20px/s 脚步滑动（`walk_left` 源素材是"刚性同向漂移"步态，循环接缝比 1.55；`walk_right` 为 1.03）。代码补偿会带来更刺眼的跳变，**根治需重画 walk_left 四帧**（i2i 余额 0 且本轮禁止充值）。
2. 左右两组步态不对称（同上）。
3. 方向靠整体倾斜表达，不是真正侧视帧（R138 素材本身是正面 3/4 姿态）。
4. 真实物理鼠标手感未验证 → `MAC_REAL_GUI_ACCEPTANCE = PENDING`。

---

## 七、待用户真机确认（一次性）

双击 `candidates/candidate_b_c2/C2_Mac人工验收.command`，确认三点：

1. **左右走动观感**：身体是否明显朝行进方向倾、腿是否不再"倒着走"；
2. **点击手感**：单击有反应、拖拽不被误判为点击；
3. **待机观感**：已无胸部膨胀、眨眼自然。

---

*本索引由 MiniMax（Mavis）生成。ZIP 的 SHA256 见同名 `.sha256` 文件（刻意不内嵌，避免自引用）。*

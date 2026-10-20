# R144 交付索引 — R141 运行时阻断修复

> **生成时间**：2026-10-20
> **对应任务书**：R144 §八
> **作者**：MiniMax（Mavis）
> **上一交付**：R141 `6e35231`
> **状态**：ENGINEERING_GATE = PASS / MAC_REAL_GUI_ACCEPTANCE = PENDING / V0_0_RELEASE_STATUS = NOT_FROZEN

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 主工作区 | `/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/` |
| 候选实现 | `candidates/candidate_b_c2/` |
| QA 报告 | `docs/R144_QA_REPORT.md` |
| 交付索引 | `docs/R144_DELIVERY_INDEX.md`（本文件） |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R144_review.zip` |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R144_review.zip.sha256` |
| 备份 | `backup/V0.0_backup_<ts>_r144.zip` + 同名 `.sha256` |
| e2e 机器报告 | `candidates/candidate_b_c2/evidence_r144_e2e.json` |
| 渲染边界证据 | `candidates/candidate_b_c2/evidence_r144/render_bounds_r144.json` |
| 23 帧 SHA256 清单 | `candidates/candidate_b_c2/evidence_r144/character_R138_frames_SHA256.txt` |
| Mac 真机验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command`（双击即用） |

**ZIP SHA256 不写在本索引内**（避免"改索引就改 ZIP 哈希"的循环自引用），写在 ZIP 旁边的独立 `.sha256` 文件。

---

## 二、代码结构（R144 变更）

```
candidates/candidate_b_c2/
├── src/
│   ├── main.js              ★ 改: 资源握手门控 / setBounds 后 getBounds 复核 / 小数位移累计
│   │                             / 边界按真实位置判定 / 初始位置夹紧 / --sleep-probability 开关
│   ├── renderer.js          ★ 改: 统一缩放+地面线布局 / 逐帧地面线对齐 / one-shot 走 anim_clock
│   │                             / assets-ready 上报 / R144 真实 PixiJS 边界自检
│   ├── behavior_engine.js   ★ 改: 按主进程复核后的真实位移扣减剩余行走距离
│   ├── sprite_layout.js     ★ 新增: 布局算法 (统一缩放 + 地面接触线) — 生产与测试共用
│   ├── anim_clock.js        ★ 新增: 帧推进时钟 (末帧停住 + epoch 作废) — 生产与测试共用
│   ├── asset_gate.js        ★ 新增: 资源就绪判定 (拒绝虚假 PASS) — 生产与测试共用
│   └── renderer.html        (未改)
├── assets/
│   ├── character_R138/      (未改 — 23 帧 SHA256 与 R138 交付清单 23/23 一致)
│   └── character_R141_manifest.json  ★ 改: 新增 layout 段 (逐帧 bbox / 留白 / 规则), 帧路径未改
├── tests/
│   ├── r141_behavior_engine.test.js   (未改 — 12/12 PASS)
│   ├── r144_layout.test.js            ★ 新增: 8 项 (真实 PNG 解码 + 布局核算)
│   ├── r144_oneshot.test.js           ★ 新增: 9 项 (一次性动画时钟)
│   ├── r144_assets_gate.test.js       ★ 新增: 9 项 (资源就绪判定)
│   └── lib/png_reader.js              ★ 新增: 纯 Node PNG 解码器 (zlib, 无第三方依赖)
├── tools/
│   ├── r144_layout_probe.js           ★ 新增: 布局探针 (进程边界适配, 算法只来自生产模块)
│   └── r144_drag_core_diff.py         ★ 新增: R113 拖拽核心逐字 diff 器
├── 08_R144_layout_builder.py   ★ 新增: 布局构建器 + R141 遗留算法复现器
├── R144_e2e_test.sh            ★ 新增: 23 项端到端测试 (真实 Electron, 6 个场景)
├── R141_e2e_test.sh            ★ 改: MOVE 日志解析随 R144 日志格式同步 (产品无回归, 13/13 PASS)
├── evidence_r144_e2e.json      ★ 新增: e2e 机器可读报告
├── evidence_r144/              ★ 新增: 渲染边界证据 + 23 帧 SHA256 清单
├── C2_Mac人工验收.command      ★ 改: R144 版一键真机验收入口 (新增渲染完整性观察项)
└── run.sh                      (未改)
```

---

## 三、本轮修复的 4 项阻断（一句话版）

| 编号 | 阻断 | 修复 | 验证 |
|---|---|---|---|
| P0-1 | 角色被裁切（compact 3.7%~6.7%，standard 82%~99%） | 基于素材**真实非透明 bbox** 的**统一缩放** + **逐帧底边对齐地面线** | 真实 PixiJS 矩阵下 46 帧（23×2 尺寸）**零裁切**，groundErr 全 0 |
| P0-2 | 一次性动画结束跳回首帧 | 末帧停住 + 保持一个 `frame_ms` + 只报一次 + epoch 作废过期事件 | 运行时末帧保持 **600~610ms**（规格 600），完成事件 **2/2、1/1** |
| P0-3 | 引擎早于资源就绪启动 | renderer 上报 `assets-ready` → main 经 `asset_gate` 判定后才启动 | 握手顺序 ready@34 < engine@37；缺帧/慢加载/重复 ready 三场景均验证 |
| P1 | 窗口坐标只记目标值、小数位移被取整吞掉 | `setBounds` 后 `getBounds()` 复核 + 小数累计 + 边界按真实位置判定 | 17 次 setBounds，位移与日志 **0 偏差**，x 跨度 105px |

---

## 四、测试复现命令

```bash
cd candidates/candidate_b_c2

# 单元测试 (38 项, 全部直接 require 生产代码)
node tests/r141_behavior_engine.test.js   # 12/12
node tests/r144_layout.test.js            # 8/8
node tests/r144_oneshot.test.js           # 9/9
node tests/r144_assets_gate.test.js       # 9/9

# 端到端 (真实 Electron, 23 项)
bash R144_e2e_test.sh                     # PASS=23 FAIL=0 NOT_VERIFIED=3

# R141 旧套件回归
bash R141_e2e_test.sh                     # PASS=13 FAIL=0 NOT_VERIFIED=3

# 重建 manifest 的 layout 段 (从真实 PNG 重新量 bbox)
python3 08_R144_layout_builder.py
python3 08_R144_layout_builder.py --check # 只核算, 不改 manifest

# 证明 R113 拖拽核心逐字未改
python3 tools/r144_drag_core_diff.py

# Mac 真机验收 (双击也行)
./C2_Mac人工验收.command          # 正式模式
./C2_Mac人工验收.command fast     # 加速模式
```

---

## 五、交付边界声明

- **未重新生成角色素材**：R138 的 23 张 PNG 逐字节未变（SHA256 23/23 一致），A1 母版 `3344d5fe…22013df` 未变。
- **未使用 i2i / 未充值**：本轮零生成式调用，全部为代码修复。
- **未扩展动作种类**：仍是 6 组动作 / 7 状态机。
- **未重做窗口拖拽架构**：R113 拖拽核心 9/9 区块逐字未改。
- **未重新研发 C1 透明穿透**：本轮完全未触碰。
- **未进入 V0.1，未擅自封版 V0.0**：`V0_0_RELEASE_STATUS = NOT_FROZEN`。
- **正式界面无调试文字**：R144 边界自检只写日志，不在窗口显示任何文字。
- **角色资产与 A1 外观未经用户审核前不标记 FROZEN**。

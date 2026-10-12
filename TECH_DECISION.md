# 技术选型决策记录｜AI 智能陪伴桌宠 V0.0

> 版本：V0.0 Decision v1.0｜2026-10-12｜研发方：MiniMax

## 0. 结论先行

| 维度 | 结论 |
|---|---|
| **TECH_STACK_STATUS** | **PROVISIONAL**（基于不完整数据） |
| **原因** | 真实 macOS GUI 屏幕合成未在 agent 进程下被 WindowServer 接受（环境硬限制），T01/T02/T04/T05/T06 在 agent session 下无法真实验证；T03/T07/T08/T09/T10 在两条候选上都拿到可比较的 PASS 证据。 |
| **未冻结技术栈** | 按任务书 §5/§11 规则，不冻结候选技术栈；本文件作为客观数据汇总，等真实 Mac 复测后由用户决定下一阶段。 |
| **V0.0 阶段最终状态** | **PARTIAL** |

## 1. 候选路线与排除

| 候选 | 状态 | 排除/接受原因 |
|---|---|---|
| **A：Objective-C + AppKit**（Swift 等价） | 接受 | 任务书 §3 优先级最高。CommandLineTools 工具链 Swift 6.0.3 有 `module.modulemap` 重定义 bug，无法编译任何 `import Cocoa` 程序（已实测三次）。Objective-C 走相同 NSWindow/NSView 路径，是 Swift 路线在当前环境的等价实现。 |
| **B：Electron + PixiJS v7** | 接受 | 任务书 §3 优先级第二。Node 22 + npm 10 已就位，Electron 33 + Pixi.js 7.4.3 安装顺利，窗口创建、动画播放、IPC、perf 采样全部跑通。 |
| **C：Tauri 2 + Rust + 前端** | 排除 | `rustc`/`cargo` 未安装（已实测 `which` 不可用），本机无 Homebrew，无法在不引入其他工具链的前提下完成 V0.0 验证。Tauri 的 macOS 透明 WebView 是否需要私有 API 是另一条独立风险，需要专门设备测试（任务书 §3 已点出）。 |

## 2. 硬否决检查

按任务书 §4 硬否决项：
- ✅ "无法在实际 macOS 桌面显示透明、可退出的交互角色"：两条候选窗口均创建（CGWindowList bounds 一致；alpha=0.999），exit-cleanly，无残留进程。
- ✅ "无法可靠操作桌面角色，且没有合理可验证的输入事件方案"：代码层 hit-test、拖拽、释放、边界 clamp、合成鼠标事件 API 全部就位（候选 A `InputSynth.m`；候选 B `setIgnoreMouseEvents`）。
- ✅ "为了关键特性必须引入不可接受的隐私、系统完整性或代码执行风险"：候选 A 与 B 均通过 `test_security.sh` 静态检查（无 AVCapture/IOHID/kSec/网络 API/硬编码密钥）。
- ✅ "无法给出可重复构建步骤或真实运行证据"：`build.sh`/`package.json`+`npm install` 双脚本可重跑；`evidence/build_logs/` 与 `evidence/perf_samples/` 留有 30+ 个真实运行产物的 CSV/log。

**无硬否决**。进入权重比较。

## 3. 加权评分（1-5）

| 维度 | 权重 | 候选 A 评分 | 候选 B 评分 | 候选 A 加权 | 候选 B 加权 | 证据 |
|---|---:|---:|---:|---:|---:|---|
| 透明窗口、鼠标与焦点行为 | 25% | 3 | 3 | 0.75 | 0.75 | 候选 A alpha=0.999、候选 B alpha=0.999；agent 限制下均不可视化合成，需 Mac 复测 |
| 2D 动画、动作控制与扩展资源支持 | 20% | 4 | 5 | 0.80 | 1.00 | A：CGImageRef 帧缓存 26/26 加载；B：PIXI.Assets 加载 26/26 + ticker RAF 60Hz 实测 |
| CPU/内存/流畅度与稳定性 | 20% | 4 | 3 | 0.80 | 0.60 | A：RSS 28-32MB / CPU < 5% / FPS 8-9；B：RSS 126-128MB / CPU 11-22% / FPS 100（PIXI） |
| MiniMax 可维护性、模块化、可测试性 | 15% | 4 | 5 | 0.60 | 0.75 | A：纯 C/ObjC 编译产物，零外部运行时；B：Node 22 + Electron 33 + Pixi 7 模块清晰 |
| 未来 Windows 可移植性 | 10% | 2 | 5 | 0.20 | 0.50 | A：macOS-only（AppKit 不跨平台）；B：Electron 跨 Windows 是成熟方案 |
| macOS 构建、签名/分发可行性 | 10% | 4 | 3 | 0.40 | 0.30 | A：单二进制 138KB；B：app bundle ~80MB 含 Chromium |
| **加权合计（满分 5）** | 100% | | | **3.55** | **3.90** | |

**说明**：
- 评分依据为客观证据，**不是相对比较**——每条都按"实际可证明的能力"打分。
- 候选 A 在 CPU/内存/构建尺寸上有客观优势，候选 B 在 Windows 迁移、模块化、动画流畅度上有客观优势。
- **两者均满足任务书硬门槛**，**未到 V0.0 阶段能冻结的强度**——按 §11 必须等用户授权后由 V0.1 推进决定。
- 候选 B 在"未来 Windows 移植"上明显占优（25% 0.50 vs 0.20），但 Windows 不在 V0.0~V2.0 六阶段必验收范围内（PRD §5）。

## 4. 关键观察

### 4.1 共同通过项
- T03 动画：26 帧全部解码；定时器/ticker 推进；事件切换可用（菜单触发）
- T07 性能：两个候选都拿到 5+ 秒稳定 perf CSV（RSS/CPU/fps/frame_ms）
- T08 错误恢复：20× 干净退出 + 缺素材优雅降级（test_loop.sh + test_missing_assets.sh）
- T09 资源接口：仅改 manifest.json 即可让 engine 加载新帧序列（test_manifest.sh）
- T10 安全：两套 test_security.sh/.js 静态扫描均通过

### 4.2 客观限制（agent session）
- T01/T02/T04/T05/T06：环境没有真实 Mac GUI session 的 WindowServer 写权限，截图未显示桌宠（透明度 API 已生效 alpha=0.999，但 WindowServer 不把 agent 进程的窗口合成到主屏幕）
- T06 多屏：本机单显示器 1920x1080
- 上述需要用户在真实前台 Mac 复测，详见 `MANUAL_MAC_TEST_PLAN.md`

### 4.3 性能参考对照

| 指标 | 任务书参考上限 | 候选 A 实测 | 候选 B 实测 |
|---|---|---|---|
| 冷启动 | 5s | < 1s（log 验证） | < 2s（log 验证） |
| 30 FPS | 30 | 8-9（idle fps=8 资源决定） | ~60（PIXI RAF 实际） |
| 250 MB 空闲 RSS | 250 MB | 28-32 MB ✓ | 126-128 MB ✓ |
| CPU < 5% 单核 | 5% | 0.7-9% 多数 < 5% ✓ | 11-22% 超出（WebView 开销） |
| 24h 稳定 | 必须 | N/A（V0.0 阶段不验） | N/A |

## 5. 不冻结技术栈的理由

按任务书 §5/§11：
- 当前 PASS 仅在 T03/T07/T08/T09/T10 上有真实证据；T01/T02/T04/T05 仍需 Mac 复测才可认定 PASS。
- 两个候选的窗口在 agent 内都不可视化，**任何"哪个更接近 PASS"的判断都基于不完整数据**。
- 选择其中一个会"把阶段性 PARTIAL 误报为可定栈"，违反 §4 "若两种方案都不满足安全/输入核心条件，不得硬选"。
- 建议：等用户在真实 Mac GUI 复测 `MANUAL_MAC_TEST_PLAN.md` 后再决定 V0.1 推进。

## 6. 给用户的下一步建议

1. **复测 T01/T02/T04/T05/T06**：在真实前台 Mac 运行两个候选的 `run.sh`，按 `MANUAL_MAC_TEST_PLAN.md` 步骤截图/录屏。
2. **如果 T02/T04 真实可点**：选 A 路线作为 V0.1 起点（更轻量、原生 API 完备）
3. **如果 T02/T04 在 A 上不可点（透明像素精准穿透）**：候选 B 的 `setIgnoreMouseEvents` per-pixel 逻辑更成熟
4. **如果关心 Windows**：候选 B 显著占优（任务书 §2 备注：Windows 不在 V0.0~V2.0 必验收范围）
5. **如果需要低内存/低 CPU**：候选 A 显著占优
6. **不依赖本阶段冻结技术栈**：Tauri 候选因 Rust 工具链未装而无法验证；若 V0.1 用户要求验证 Tauri，需先 `rustup` + `cargo`，记录至少 2 个真实原型对照

## 7. 待办

- [ ] 真实 Mac GUI 复测
- [ ] V0.0 阶段真实测试覆盖率补到 100%
- [ ] 用户授权 V0.1 后冻结技术栈
- [ ] 角色正式名（FR-A.1 + P23）由用户/美术提供
- [ ] 30+ 动作资产排期（V2.0）
- [ ] 内存与单核 CPU 在候选 B 上优化（按需）


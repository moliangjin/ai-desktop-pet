#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R158 交付打包器 — 生成轻量审查包 + 完整备份 + SHA256。

两份包:
  1) 轻量审查包 (供独立复审):
     源码 / 测试 / 脚本 / manifest / 证据 JSON /
     **R158 新烘焙的 18 张动作帧** (6 个点击动作 × 3 帧) + **1 个爱心特效 PNG** /
     **6 个可直接观看的运行预览 GIF** + 1 张总览图 /
     报告与索引
     —— 不含 R138 的 23 张原始 PNG (素材本体可从 R138 交付包取, 另有 SHA256 清单核对)
  2) 完整备份: 候选实现的全部内容 (含 R138 23 帧 + 派生 4 帧 + R153 12 帧 + R156 20 帧 + R158 19 张)
     + 本轮文档

SHA256 写在 ZIP **旁边的独立 .sha256 文件** (不内嵌), 避免"改索引就改哈希"的循环自引用。

用法: python3 41_R158_package.py <commit>
"""
import hashlib
import os
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))    # 仓库根 (HERE=candidates/candidate_b_c2)
CAND = HERE
OUT_DIR = "/Users/musk123/Downloads/minimax工作文件夹"

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R158_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r158.zip" % time.strftime("%Y%m%d_%H%M%S"))

R158_FRAMES = [
    "cheer_wave_0.png", "cheer_wave_1.png", "cheer_wave_2.png",
    "cheer_hands_up_0.png", "cheer_hands_up_1.png", "cheer_hands_up_2.png",
    "cheer_heart_0.png", "cheer_heart_1.png", "cheer_heart_2.png",
    "cheer_clap_0.png", "cheer_clap_1.png", "cheer_clap_2.png",
    "cheer_jump_0.png", "cheer_jump_1.png", "cheer_jump_2.png",
    "cheer_tilt_0.png", "cheer_tilt_1.png", "cheer_tilt_2.png",
]
R158_PROPS = ["prop_heart.png"]

REVIEW_FILES = [
    ("src/main.js", "candidate_b_c2/src/main.js"),
    ("src/renderer.js", "candidate_b_c2/src/renderer.js"),
    ("src/behavior_engine.js", "candidate_b_c2/src/behavior_engine.js"),
    ("src/action_library.js", "candidate_b_c2/src/action_library.js"),
    ("src/sprite_layout.js", "candidate_b_c2/src/sprite_layout.js"),
    ("src/idle_director.js", "candidate_b_c2/src/idle_director.js"),
    ("src/click_policy.js", "candidate_b_c2/src/click_policy.js"),
    ("src/anim_clock.js", "candidate_b_c2/src/anim_clock.js"),
    ("src/asset_gate.js", "candidate_b_c2/src/asset_gate.js"),
    ("src/renderer.html", "candidate_b_c2/src/renderer.html"),
    ("package.json", "candidate_b_c2/package.json"),
    ("assets/character_R141_manifest.json", "candidate_b_c2/assets/character_R141_manifest.json"),
    # ---- 测试 ----
    ("tests/r141_behavior_engine.test.js", "candidate_b_c2/tests/r141_behavior_engine.test.js"),
    ("tests/r144_layout.test.js", "candidate_b_c2/tests/r144_layout.test.js"),
    ("tests/r144_oneshot.test.js", "candidate_b_c2/tests/r144_oneshot.test.js"),
    ("tests/r144_assets_gate.test.js", "candidate_b_c2/tests/r144_assets_gate.test.js"),
    ("tests/r147_layout_pixi_parity.test.js", "candidate_b_c2/tests/r147_layout_pixi_parity.test.js"),
    ("tests/r147_interaction.test.js", "candidate_b_c2/tests/r147_interaction.test.js"),
    ("tests/r148_walk_direction.test.js", "candidate_b_c2/tests/r148_walk_direction.test.js"),
    ("tests/r153_action_library.test.js", "candidate_b_c2/tests/r153_action_library.test.js"),
    ("tests/r153_png.js", "candidate_b_c2/tests/r153_png.js"),
    ("tests/r156_click_props_work.test.js", "candidate_b_c2/tests/r156_click_props_work.test.js"),
    ("tests/r158_click_actions.test.js", "candidate_b_c2/tests/r158_click_actions.test.js"),
    ("tests/lib/png_reader.js", "candidate_b_c2/tests/lib/png_reader.js"),
    # ---- 工具 ----
    ("tools/r144_drag_core_diff.py", "candidate_b_c2/tools/r144_drag_core_diff.py"),
    ("tools/r144_layout_probe.js", "candidate_b_c2/tools/r144_layout_probe.js"),
    # ---- R158 新增脚本 ----
    ("36_R158_arm_rig.py", "candidate_b_c2/36_R158_arm_rig.py"),
    ("36b_R158_pose_preview.py", "candidate_b_c2/36b_R158_pose_preview.py"),
    ("37_R158_action_bake.py", "candidate_b_c2/37_R158_action_bake.py"),
    ("38_R158_manifest_update.py", "candidate_b_c2/38_R158_manifest_update.py"),
    ("39_R158_runtime_verify.py", "candidate_b_c2/39_R158_runtime_verify.py"),
    ("40_R158_preview_gif.py", "candidate_b_c2/40_R158_preview_gif.py"),
    ("41_R158_package.py", "candidate_b_c2/41_R158_package.py"),
    ("42_R158_measure_report.py", "candidate_b_c2/42_R158_measure_report.py"),
    # ---- 前序轮次脚本 (便于复算) ----
    ("29_R156_pose_bake.py", "candidate_b_c2/29_R156_pose_bake.py"),
    ("30_R156_props_bake.py", "candidate_b_c2/30_R156_props_bake.py"),
    ("32_R156_manifest_update.py", "candidate_b_c2/32_R156_manifest_update.py"),
    ("33_R156_preview_gif.py", "candidate_b_c2/33_R156_preview_gif.py"),
    ("34_R156_runtime_verify.py", "candidate_b_c2/34_R156_runtime_verify.py"),
    ("35_R156_package.py", "candidate_b_c2/35_R156_package.py"),
    ("22_R153_pose_bake.py", "candidate_b_c2/22_R153_pose_bake.py"),
    ("23_R153_manifest_update.py", "candidate_b_c2/23_R153_manifest_update.py"),
    ("08_R144_layout_builder.py", "candidate_b_c2/08_R144_layout_builder.py"),
    ("15_R147_preview_verify.py", "candidate_b_c2/15_R147_preview_verify.py"),
    ("17_R148_mirror_derive.py", "candidate_b_c2/17_R148_mirror_derive.py"),
    ("19_R148_manifest_update.py", "candidate_b_c2/19_R148_manifest_update.py"),
    ("R141_e2e_test.sh", "candidate_b_c2/R141_e2e_test.sh"),
    ("R144_e2e_test.sh", "candidate_b_c2/R144_e2e_test.sh"),
    ("R147_e2e_test.sh", "candidate_b_c2/R147_e2e_test.sh"),
    ("run.sh", "candidate_b_c2/run.sh"),
    ("C2_Mac人工验收.command", "candidate_b_c2/C2_Mac人工验收.command"),
    # ---- 证据 ----
    ("evidence_r147_e2e.json", "candidate_b_c2/evidence_r147_e2e.json"),
    ("evidence_r153_runtime.json", "candidate_b_c2/evidence_r153_runtime.json"),
    ("evidence_r158_preview/r156_runtime_verify.json",
     "candidate_b_c2/evidence_r158_preview/r156_runtime_verify.json"),
    ("evidence_r158_preview/r158_runtime_verify.json",
     "candidate_b_c2/evidence_r158_preview/r158_runtime_verify.json"),
    ("evidence_r158_preview/preview_meta.json",
     "candidate_b_c2/evidence_r158_preview/preview_meta.json"),
    ("evidence_r158_preview/run.log", "candidate_b_c2/evidence_r158_preview/run.log"),
    ("assets/character_R158/bake_report.json", "candidate_b_c2/assets/character_R158/bake_report.json"),
    ("assets/character_R138_derived/r138_source_checksums.json",
     "candidate_b_c2/assets/character_R138_derived/r138_source_checksums.json"),
    ("assets/character_R138_derived/walk_right_mirror/derive_report.json",
     "candidate_b_c2/assets/character_R138_derived/walk_right_mirror/derive_report.json"),
]

for _f in R158_FRAMES + R158_PROPS:
    REVIEW_FILES.append((f"assets/character_R158/{_f}", f"candidate_b_c2/assets/character_R158/{_f}"))

_GIFS = [
    "R158_click_cheer_wave.gif", "R158_click_cheer_hands_up.gif",
    "R158_click_cheer_heart.gif", "R158_click_cheer_clap.gif",
    "R158_click_cheer_jump.gif", "R158_click_cheer_tilt.gif",
]
PREVIEW_FILES = [(f"evidence_r158_gifs/{g}", f"preview/{g}") for g in _GIFS]
PREVIEW_FILES += [
    ("evidence_r158_gifs/R158_click_pool_overview.png", "preview/R158_click_pool_overview.png"),
]

DOC_FILES = [
    ("docs/R158_QA_REPORT.md", "docs/R158_QA_REPORT.md"),
    ("docs/R158_DELIVERY_INDEX.md", "docs/R158_DELIVERY_INDEX.md"),
]

README = """R158 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: __GENERATED_AT__
提交:     __COMMIT__

本轮主题: 修复点击互动的视觉质量 (承接 R156) —— 素材可行性评估 + 手臂骨架真手势

candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
                  + assets/character_R158/  ★ R158 新增:
                     - 18 张局部烘焙动作帧 (6 个点击动作 × 3 帧)
                     - 1 个程序化矢量爱心特效 PNG
                     - bake_report.json (含每帧的姿态参数与唯一性自检)
preview/          ★ 真实运行预览 (可直接观看, 6 个 GIF + 1 张总览图)
                   - R158_click_cheer_wave.gif      真挥手 (手臂骨架抬手 + 手腕摆动)
                   - R158_click_cheer_hands_up.gif  双臂高举欢呼
                   - R158_click_cheer_heart.gif     比心 (双手合拢 + 爱心特效)
                   - R158_click_cheer_clap.gif      鼓掌 (张开 → 合拢 → 张开)
                   - R158_click_cheer_jump.gif      开心跳跃 (双臂上扬 + 离地)
                   - R158_click_cheer_tilt.gif      歪头眨眼卖萌
                   - R158_click_pool_overview.png   6 个点击动作总览
evidence/         运行时客观量化 (r156_runtime_verify.json + r158_runtime_verify.json)
                   + e2e 机器报告 + 真实采集元数据 + 真实运行日志
docs/             R158 质量报告 + 交付索引

本轮完成定义 → 证据
--------------------------------
1. 素材可行性评估 (本轮第一交付物)
   · R153/R156 的"R138 无手部素材"结论**是错的**: idle_00_base.png 里两只手都是张开的、
     5 指带描边; R138 自己的切层脚本 (03_LAYERS/split_a1_layers.py) 漏切了画面左臂,
     LAYERS.json 只登记了 head/torso/leg_r/arm_r (arm_r = 胸前的拳头)。
   · R156 的 cheer_heart 根因: 29_R156_pose_bake.py 里 HAND_CHEST = idle_04_blink_half.png,
     而 idle_04 正是"右手横在胸前"的姿势 ⇒ 必然还是用户已经不喜欢的那一手。
   · 全仓库逐目录核查: 只有**正面**素材, 无任何侧身/背面视图。
   证据: manifest.r158_click_actions.asset_feasibility + docs/R158_QA_REPORT.md §2。

2. ≥5 种视觉上明确、动作含义清晰的点击互动 (实际 6 种)
   cheer_wave(真挥手) / cheer_hands_up(双臂欢呼) / cheer_heart(比心+爱心特效)
   / cheer_clap(鼓掌) / cheer_jump(开心跳跃) / cheer_tilt(歪头眨眼)
   每个 3 帧 (开始/中间/结束), 全部独立烘焙帧。
   证据: preview/R158_click_pool_overview.png + 6 个 GIF。

3. 禁止用压缩/平移/重命名冒充新动作
   · R156 的 4 个几何形变动作已全部下架: cheer_spin(水平压缩 64% 冒充转身) /
     cheer_sway(整体水平平移 ±46px) / cheer_heart(复用 idle_04 手放胸前) /
     cheer_wink / cheer_hands。
   · 反伪判据是**客观像素测量** (tests/r158_click_actions.test.js C1/C2):
     每个动作 3 帧的实心面积中位数与基准偏差 <15% (整体压缩会 -36%),
     且任一帧的脚底中心位移 <24 纹理 px (整体平移会 46px)。
   · 另有 C3/C4/C5 用像素级测量证明"手真的抬起来了/真的到胸前了"。

4. 真正的比心 / 跳跃 / 挥手 / 歪头眨眼
   · 手臂骨架 (36_R158_arm_rig.py): 描边阻隔洪水填充切出漏切的开张手,
     肩/肘/腕三个圆形咬口旋转 (近端关节完整圆盘 ⇒ 接缝永不出现),
     摘袖后按行重建大褂边缘 (描边 + 白大褂面料) ⇒ 不留鬼影。
   · 跳跃: 腾空帧加**双臂上扬 + 仰头**, 蓄力压扁 20% / 落地压缩 16%,
     离地由运行时 ground_tex_y=1015 实现 (standard 模式窗口高度允许的上限)。
   证据: tests/r158_click_actions.test.js C3~C8 + 39_R158_runtime_verify.py 第 11/12/12b 项。

做不到的事 (如实列出, 未硬标 PASS)
--------------------------------
- **真正的 180° 背面转身做不到** —— R138 全库只有正面素材。程序化"合成背面"需要重画
  后脑勺 + 实验服背面 (去掉前襟/胸牌/纽扣), 属于重画角色且质量不可控 ⇒ 本轮**不做**,
  已把 cheer_spin 下架, 并给出精确的新素材需求 (帧数/姿态/视角/分辨率/验收口径),
  见 manifest.r158_click_actions.new_asset_requests 与 docs/R158_QA_REPORT.md §7。
- **手指级比心几何在桌宠实际显示尺寸下不可读** —— compact 200x240 窗口缩放 0.196,
  整只开口只有约 12x16 屏幕 px, 单根手指宽约 2px, 拇指+食指围出的心形读不出来
  ⇒ 比心采用"双手在胸前合拢 + 爱心特效(prop_heart)"的可读性方案, 已在动作描述里如实写明。
- 跳跃离地上限受**窗口高度**硬约束 (standard 256x256 头顶只剩 11px 余量 ⇒ 离地 ≤7 屏幕 px),
  已顶到上限; 再大必须改窗口尺寸或重绘带留白的原画。
- 办公场景仍然只能做"看屏幕/思考/停顿", 做不到"敲键盘"手部动作 (R138 无键盘手部素材)。
- Mac 真机验收 = PENDING (沙箱无法完成真实鼠标手感与真机观感判断)。

复审要点
--------
1. node  candidates/candidate_b_c2/tests/r158_click_actions.test.js     (23 项, 含反"压缩/平移"客观判据)
2. node  candidates/candidate_b_c2/tests/r156_click_props_work.test.js  (21 项)
3. python3 candidates/candidate_b_c2/39_R158_runtime_verify.py --preview-dir candidates/candidate_b_c2/evidence_r158_preview
                                                                              (6 项 R158 专项真实像素校验)
4. python3 candidates/candidate_b_c2/34_R156_runtime_verify.py --preview-dir candidates/candidate_b_c2/evidence_r158_preview
                                                                              (23 项通用真实像素校验)
5. python3 candidates/candidate_b_c2/37_R158_action_bake.py             (重放烘焙, 内置唯一性自检, 可复算)
6. python3 candidates/candidate_b_c2/38_R158_manifest_update.py          (manifest 幂等更新, 可重放)
7. python3 candidates/candidate_b_c2/40_R158_preview_gif.py             (重放 GIF/总览合成)
8. bash   candidates/candidate_b_c2/R147_e2e_test.sh                    (真实 Electron 全量回归)
9. python3 candidates/candidate_b_c2/tools/r144_drag_core_diff.py       (R113 拖拽核心逐字未改)

素材本体 (R138 原始 23 帧 PNG) 不在本包内, 位于产品目录 assets/character_R138/ 与 R138 交付目录,
SHA256 清单见 candidate_b_c2/assets/character_R138_derived/r138_source_checksums.json。
"""


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def add(zf, src, arc):
    if not os.path.exists(src):
        print("  ⚠️  缺失, 跳过: %s" % src)
        return False
    zf.write(src, arc)
    return True


def build_review(commit):
    os.makedirs(OUT_DIR, exist_ok=True)
    n = 0
    with zipfile.ZipFile(REVIEW_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel, arc in REVIEW_FILES + PREVIEW_FILES:
            if add(zf, os.path.join(CAND, rel), arc):
                n += 1
        for rel, arc in DOC_FILES:
            if add(zf, os.path.join(ROOT, rel), arc):
                n += 1
        readme = README.replace("__GENERATED_AT__", time.strftime("%Y-%m-%d %H:%M:%S")) \
                         .replace("__COMMIT__", commit)
        zf.writestr("evidence/README_R158_review.txt", readme)
        n += 1
    return n


def build_backup():
    os.makedirs(os.path.dirname(BACKUP_ZIP), exist_ok=True)
    n = 0
    with zipfile.ZipFile(BACKUP_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for base, arcbase in (('src', 'candidate_b_c2/src'),
                              ('tests', 'candidate_b_c2/tests'),
                              ('tools', 'candidate_b_c2/tools'),
                              ('assets', 'candidate_b_c2/assets')):
            b = os.path.join(CAND, base)
            if not os.path.isdir(b):
                continue
            for root, dirs, files in os.walk(b):
                dirs[:] = [d for d in dirs if d not in ('__pycache__', 'node_modules')]
                for fn in files:
                    p = os.path.join(root, fn)
                    arc = os.path.join(arcbase, os.path.relpath(p, b))
                    if add(zf, p, arc):
                        n += 1
        for fn in sorted(os.listdir(CAND)):
            if fn.endswith(('.py', '.sh', '.command', '.json', '.md')):
                if add(zf, os.path.join(CAND, fn), f"candidate_b_c2/{fn}"):
                    n += 1
        for rel, arc in DOC_FILES:
            if add(zf, os.path.join(ROOT, rel), arc):
                n += 1
    return n


def main():
    commit = sys.argv[1] if len(sys.argv) > 1 else 'HEAD'
    print("R158 打包:")
    n = build_review(commit)
    print(f"  ✅ 审查包: {REVIEW_ZIP}  ({n} 个文件, {os.path.getsize(REVIEW_ZIP)} 字节)")
    h = sha256_file(REVIEW_ZIP)
    with open(REVIEW_ZIP + '.sha256', 'w', encoding='utf-8') as f:
        f.write(f"{h}  {os.path.basename(REVIEW_ZIP)}\n")
    print(f"     SHA256: {h}")
    n = build_backup()
    print(f"  ✅ 备份包: {BACKUP_ZIP}  ({n} 个文件, {os.path.getsize(BACKUP_ZIP)} 字节)")
    h2 = sha256_file(BACKUP_ZIP)
    with open(BACKUP_ZIP + '.sha256', 'w', encoding='utf-8') as f:
        f.write(f"{h2}  {os.path.basename(BACKUP_ZIP)}\n")
    print(f"     SHA256: {h2}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

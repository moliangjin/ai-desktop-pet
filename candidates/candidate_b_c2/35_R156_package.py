#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R156 交付打包器 — 生成轻量审查包 + 完整备份 + SHA256。

两份包:
  1) 轻量审查包 (供独立复审):
     源码 / 测试 / 脚本 / manifest / 证据 JSON /
     **R156 新烘焙的 20 张动作帧** (6 点击动作 × 3 帧 + 办公 2 帧) /
     **7 个程序化道具 PNG** /
     **10 个可直接观看的运行预览 GIF** + 2 张总览图 /
     报告与索引
     —— 不含 R138 的 23 张原始 PNG (素材本体可从 R138 交付包取, 另有 SHA256 清单核对)
  2) 完整备份: 候选实现的全部内容 (含 R138 23 帧 + 派生 4 帧 + R153 12 帧 + R156 20 帧 + 7 道具)
     + 本轮文档

SHA256 写在 ZIP **旁边的独立 .sha256 文件** (不内嵌), 避免"改索引就改哈希"的循环自引用。

用法: python3 35_R156_package.py <commit>
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

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R156_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r156.zip" % time.strftime("%Y%m%d_%H%M%S"))

# R156 新烘焙的 20 张动作帧 + 7 个道具 (含在包内, 便于复审者自行验证"局部烘焙"与"程序化道具"性质)
R156_FRAMES = [
    "cheer_heart_0.png", "cheer_heart_1.png", "cheer_heart_2.png",
    "cheer_jump_0.png", "cheer_jump_1.png", "cheer_jump_2.png",
    "cheer_spin_0.png", "cheer_spin_1.png", "cheer_spin_2.png",
    "cheer_wink_0.png", "cheer_wink_1.png", "cheer_wink_2.png",
    "cheer_hands_0.png", "cheer_hands_1.png", "cheer_hands_2.png",
    "cheer_sway_0.png", "cheer_sway_1.png", "cheer_sway_2.png",
    "work_1.png", "work_2.png",
]
R156_PROPS = [
    "prop_bed.png", "prop_quilt.png", "prop_moon.png",
    "prop_sofa.png", "prop_chair.png", "prop_desk.png", "prop_screen_glow.png",
]

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
    ("tests/lib/png_reader.js", "candidate_b_c2/tests/lib/png_reader.js"),
    # ---- 工具 ----
    ("tools/r144_drag_core_diff.py", "candidate_b_c2/tools/r144_drag_core_diff.py"),
    ("tools/r144_layout_probe.js", "candidate_b_c2/tools/r144_layout_probe.js"),
    # ---- R156 新增脚本 ----
    ("29_R156_pose_bake.py", "candidate_b_c2/29_R156_pose_bake.py"),
    ("30_R156_props_bake.py", "candidate_b_c2/30_R156_props_bake.py"),
    ("31_R156_measure_preview.py", "candidate_b_c2/31_R156_measure_preview.py"),
    ("32_R156_manifest_update.py", "candidate_b_c2/32_R156_manifest_update.py"),
    ("33_R156_preview_gif.py", "candidate_b_c2/33_R156_preview_gif.py"),
    ("34_R156_runtime_verify.py", "candidate_b_c2/34_R156_runtime_verify.py"),
    # ---- 前序轮次脚本 (便于复算) ----
    ("22_R153_pose_bake.py", "candidate_b_c2/22_R153_pose_bake.py"),
    ("23_R153_manifest_update.py", "candidate_b_c2/23_R153_manifest_update.py"),
    ("24_R153_package.py", "candidate_b_c2/24_R153_package.py"),
    ("25_R153_walk_posture_verify.py", "candidate_b_c2/25_R153_walk_posture_verify.py"),
    ("26_R153_baked_contact_sheet.py", "candidate_b_c2/26_R153_baked_contact_sheet.py"),
    ("27_R153_runtime_verify.py", "candidate_b_c2/27_R153_runtime_verify.py"),
    ("28_R153_preview_gif.py", "candidate_b_c2/28_R153_preview_gif.py"),
    ("08_R144_layout_builder.py", "candidate_b_c2/08_R144_layout_builder.py"),
    ("15_R147_preview_verify.py", "candidate_b_c2/15_R147_preview_verify.py"),
    ("17_R148_mirror_derive.py", "candidate_b_c2/17_R148_mirror_derive.py"),
    ("18_R148_direction_verify.py", "candidate_b_c2/18_R148_direction_verify.py"),
    ("19_R148_manifest_update.py", "candidate_b_c2/19_R148_manifest_update.py"),
    ("20_R148_preview_gif.py", "candidate_b_c2/20_R148_preview_gif.py"),
    ("R141_e2e_test.sh", "candidate_b_c2/R141_e2e_test.sh"),
    ("R144_e2e_test.sh", "candidate_b_c2/R144_e2e_test.sh"),
    ("R147_e2e_test.sh", "candidate_b_c2/R147_e2e_test.sh"),
    ("run.sh", "candidate_b_c2/run.sh"),
    ("C2_Mac人工验收.command", "candidate_b_c2/C2_Mac人工验收.command"),
    # ---- 证据 ----
    ("evidence_r147_e2e.json", "candidate_b_c2/evidence_r147_e2e.json"),
    ("evidence_r153_runtime.json", "candidate_b_c2/evidence_r153_runtime.json"),
    ("evidence_r156_preview/r156_runtime_verify.json",
     "candidate_b_c2/evidence_r156_preview/r156_runtime_verify.json"),
    ("evidence_r156_preview/preview_meta.json",
     "candidate_b_c2/evidence_r156_preview/preview_meta.json"),
    ("evidence_r156_preview/run.log", "candidate_b_c2/evidence_r156_preview/run.log"),
    ("assets/character_R156/bake_report.json", "candidate_b_c2/assets/character_R156/bake_report.json"),
    ("assets/character_R156/props_report.json", "candidate_b_c2/assets/character_R156/props_report.json"),
    ("assets/character_R156/r156_measure_report.json",
     "candidate_b_c2/assets/character_R156/r156_measure_report.json"),
    ("assets/character_R138_derived/r138_source_checksums.json",
     "candidate_b_c2/assets/character_R138_derived/r138_source_checksums.json"),
    ("assets/character_R138_derived/walk_right_mirror/derive_report.json",
     "candidate_b_c2/assets/character_R138_derived/walk_right_mirror/derive_report.json"),
]

for _f in R156_FRAMES:
    REVIEW_FILES.append((f"assets/character_R156/{_f}", f"candidate_b_c2/assets/character_R156/{_f}"))
for _f in R156_PROPS:
    REVIEW_FILES.append((f"assets/character_R156/{_f}", f"candidate_b_c2/assets/character_R156/{_f}"))

# 预览 GIF (真实运行采集, 可直接观看)
_GIFS = [
    "R156_click_cheer_heart.gif", "R156_click_cheer_jump.gif", "R156_click_cheer_spin.gif",
    "R156_click_cheer_wink.gif", "R156_click_cheer_hands.gif", "R156_click_cheer_sway.gif",
    "R156_scene_sleep.gif", "R156_scene_sofa.gif", "R156_scene_work.gif", "R156_scene_prop_exit.gif",
]
PREVIEW_FILES = [(f"evidence_r156_gifs/{g}", f"preview/{g}") for g in _GIFS]
PREVIEW_FILES += [
    ("evidence_r156_gifs/R156_click_pool_overview.png", "preview/R156_click_pool_overview.png"),
    ("evidence_r156_gifs/R156_scene_overview.png", "preview/R156_scene_overview.png"),
]

DOC_FILES = [
    ("docs/R156_QA_REPORT.md", "docs/R156_QA_REPORT.md"),
    ("docs/R156_DELIVERY_INDEX.md", "docs/R156_DELIVERY_INDEX.md"),
]

README = """R156 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: __GENERATED_AT__
提交:     __COMMIT__

本轮主题: 点击互动扩展 + 场景道具 + 办公待机场景 (承接 R153)

candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
                  + assets/character_R156/  ★ R156 新增:
                     - 20 张局部烘焙动作帧 (6 个点击动作 × 3 帧 + 办公 2 帧)
                     - 7 个程序化矢量道具 PNG (床/被子/月亮/沙发/转椅/桌+笔记本/屏幕微光)
                     - bake_report.json / props_report.json / r156_measure_report.json
preview/          ★ 真实运行预览 (可直接观看, 10 个 GIF + 2 张总览图)
                   - R156_click_cheer_*.gif (6 个)  6 个点击动作, 每个能看清开始/中间/结束
                   - R156_scene_sleep.gif      睡觉场景 (床 + 月亮 + 被子)
                   - R156_scene_sofa.gif       坐下场景 (小沙发)
                   - R156_scene_work.gif       办公待机 (转椅 + 小桌 + 笔记本 + 屏幕微光)
                   - R156_scene_prop_exit.gif  道具退场验证 (床与月亮必须一起退出)
                   - R156_click_pool_overview.png  6 个点击动作总览
                   - R156_scene_overview.png      3 个场景总览
evidence/         运行时客观量化 (r156_runtime_verify.json, 21 项真实像素校验)
                   + e2e 机器报告 + 真实采集元数据 + 真实运行日志
docs/             R156 质量报告 + 交付索引

本轮完成定义 → 证据
--------------------------------
1. 点击动作池 ≥5
   实际 6 个: cheer_heart(比心近似) / cheer_jump(开心小跳) / cheer_spin(原地轻盈转身)
             / cheer_wink(歪头眨眼) / cheer_hands(双手小庆祝) / cheer_sway(开心摇摆)
   每个 3 帧 (开始/中间/结束), 全部独立烘焙帧, 互相不重命名、不重复播放。
   随机触发: 真实 Electron 连点 10 次 → 触发 5 种, 无相邻重复。
   证据: preview/R156_click_pool_overview.png + evidence/r156_runtime_verify.json 第 1/1b/2 项。

2. 睡觉 = 床 + 月亮夜晚氛围
   证据: 道具专属区域可见像素 5505 (阈值 400); preview/R156_scene_sleep.gif。

3. 坐下 = 小沙发
   证据: 可见像素 5429; preview/R156_scene_sofa.gif。

4. 办公待机场景
   证据: 可见像素 1610; preview/R156_scene_work.gif;
         运行时日志 "R156 PROPS action=work scene=yes mounted=prop_chair,prop_desk,prop_screen_glow"。

5. 已接入运行逻辑 (不是只交静态图)
   - 点击: 渲染器 pickClickReaction 随机池 + clickRecent_ 去重 + 1100ms 暂缓自主行为
   - 道具: 渲染器 back/front 分层 sprite 系统, 260ms 淡入淡出, 退出即销毁
   - 办公: 行为引擎 WORK 状态, work_probability=0.10, 连续办公权重归零
   证据: 运行时日志 R156 PROPS / R156 CLICK_REACTION start|end。

6. 真实运行证据
   evidence/ 目录 = 真实 Electron 采集 650 帧 + meta + run.log + 21 项像素级校验。

7. 不破坏已有主链路
   R113 拖拽核心 9/9 逐字未改 / R138 23 帧 47/47 SHA256 一致 / A1 母版 SHA256 未变 /
   R148 行走方向修复保留 / e2e 全绿。

做不到的事 (如实列出, 未硬标 PASS)
--------------------------------
- R138 无手部素材 ⇒ 真正的双手比心 / 挥手 / 拍掌 / 敲键盘 做不到 (用近似表现代替)
- "原地转身"是 2D 表现手法 (水平压缩 64% 读作侧身), 不是真的 180° 背面转身
- "跳"的离地幅度受窗口高度硬约束 (standard 模式头顶只剩 11.1px 余量),
  可读性主要来自压扁↔伸展↔落地的剪影对比
- 这张床只放得下躺姿 ⇒ sleep_enter / wake_up 不带道具, 睡→醒走场景溶解过渡
- Mac 真机验收 = PENDING (沙箱无法完成真实鼠标手感与真机观感判断)

复审要点
--------
1. node  candidates/candidate_b_c2/tests/r156_click_props_work.test.js   (21 项)
2. python3 candidates/candidate_b_c2/34_R156_runtime_verify.py --preview-dir candidates/candidate_b_c2/evidence_r156_preview
                                                                              (21 项真实像素校验)
3. python3 candidates/candidate_b_c2/29_R156_pose_bake.py                 (重放烘焙, 内置唯一性自检, 可复算)
4. python3 candidates/candidate_b_c2/30_R156_props_bake.py                 (重放 7 个道具)
5. python3 candidates/candidate_b_c2/32_R156_manifest_update.py           (manifest 幂等更新, 可重放)
6. bash   candidates/candidate_b_c2/R147_e2e_test.sh                      (真实 Electron 全量回归, 含 R156 段)
7. python3 candidates/candidate_b_c2/tools/r144_drag_core_diff.py         (R113 拖拽核心逐字未改)

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
        zf.writestr("evidence/README_R156_review.txt", readme)
        n += 1
    return n


def build_backup():
    os.makedirs(os.path.dirname(BACKUP_ZIP), exist_ok=True)
    n = 0
    with zipfile.ZipFile(BACKUP_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for base, _dirs, files in os.walk(CAND):
            if "__pycache__" in base:
                continue
            for f in files:
                if f.endswith(".pyc") or f == ".DS_Store":
                    continue
                src = os.path.join(base, f)
                arc = os.path.relpath(src, ROOT)
                zf.write(src, arc)
                n += 1
        for rel, arc in DOC_FILES + [("docs/R153_QA_REPORT.md", "docs/R153_QA_REPORT.md"),
                                     ("docs/R153_DELIVERY_INDEX.md", "docs/R153_DELIVERY_INDEX.md")]:
            if add(zf, os.path.join(ROOT, rel), arc):
                n += 1
    return n


def main():
    commit = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print("R156 打包:")
    cnt = build_review(commit)
    h = sha256_file(REVIEW_ZIP)
    with open(REVIEW_ZIP + ".sha256", "w", encoding="utf-8") as f:
        f.write("%s  %s\n" % (h, os.path.basename(REVIEW_ZIP)))
    print("  ✅ 审查包: %s" % REVIEW_ZIP)
    print("     文件数=%d  大小=%d B  SHA256=%s" % (cnt, os.path.getsize(REVIEW_ZIP), h))

    cnt2 = build_backup()
    h2 = sha256_file(BACKUP_ZIP)
    with open(BACKUP_ZIP + ".sha256", "w", encoding="utf-8") as f:
        f.write("%s  %s\n" % (h2, os.path.basename(BACKUP_ZIP)))
    print("  ✅ 备份: %s" % BACKUP_ZIP)
    print("     文件数=%d  大小=%d B  SHA256=%s" % (cnt2, os.path.getsize(BACKUP_ZIP), h2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

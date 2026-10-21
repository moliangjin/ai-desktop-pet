#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 交付打包器 — 生成轻量审查包 + 完整备份 + SHA256。

与 R162 的差别:
  · 新增 R165 的 4 个脚本 (45 场景预览 / 46 客观判据 / 47 证据产出 / 48 打包)
  · 新增 R165 的证据 (真实 Electron 重采集 + 运行时校验 + 客观判据 + GIF + 总览图)
  · 新增/更新的场景道具 PNG (prop_desk_surface 等 5 个) 一并入包
  · R158 的 18 张动作帧照旧入包 (本轮重新烘焙过, 内容已变)

SHA256 写在 ZIP **旁边的独立 .sha256 文件** (不内嵌), 避免"改索引就改哈希"的循环自引用。

用法: python3 48_R165_package.py <commit>
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

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R165_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r165.zip" % time.strftime("%Y%m%d_%H%M%S"))

R165_FRAMES = [
    "cheer_wave_0.png", "cheer_wave_1.png", "cheer_wave_2.png",
    "cheer_hands_up_0.png", "cheer_hands_up_1.png", "cheer_hands_up_2.png",
    "cheer_heart_0.png", "cheer_heart_1.png", "cheer_heart_2.png",
    "cheer_clap_0.png", "cheer_clap_1.png", "cheer_clap_2.png",
    "cheer_jump_0.png", "cheer_jump_1.png", "cheer_jump_2.png",
    "cheer_tilt_0.png", "cheer_tilt_1.png", "cheer_tilt_2.png",
]
R165_PROPS = ["prop_heart.png"]
# R165 重做/新增的场景道具 (进包, 供复审直接对比)
R165_SCENE_PROPS = ["prop_bed.png", "prop_quilt.png", "prop_moon.png",
                    "prop_desk.png", "prop_desk_surface.png", "prop_screen_glow.png",
                    "prop_chair.png"]

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
    ("tests/r162_click_defects.test.js", "candidate_b_c2/tests/r162_click_defects.test.js"),
    ("tests/lib/png_reader.js", "candidate_b_c2/tests/lib/png_reader.js"),
    # ---- 工具 ----
    ("tools/r144_drag_core_diff.py", "candidate_b_c2/tools/r144_drag_core_diff.py"),
    ("tools/r144_layout_probe.js", "candidate_b_c2/tools/r144_layout_probe.js"),
    # ---- R158 脚本 ----
    ("36_R158_arm_rig.py", "candidate_b_c2/36_R158_arm_rig.py"),
    ("36b_R158_pose_preview.py", "candidate_b_c2/36b_R158_pose_preview.py"),
    ("37_R158_action_bake.py", "candidate_b_c2/37_R158_action_bake.py"),
    ("38_R158_manifest_update.py", "candidate_b_c2/38_R158_manifest_update.py"),
    ("39_R158_runtime_verify.py", "candidate_b_c2/39_R158_runtime_verify.py"),
    ("40_R158_preview_gif.py", "candidate_b_c2/40_R158_preview_gif.py"),
    ("41_R158_package.py", "candidate_b_c2/41_R158_package.py"),
    ("42_R158_measure_report.py", "candidate_b_c2/42_R158_measure_report.py"),
    # ---- R162 脚本 ----
    ("43_R162_defect_verify.py", "candidate_b_c2/43_R162_defect_verify.py"),
    ("44_R162_package.py", "candidate_b_c2/44_R162_package.py"),
    # ---- R165 新增脚本 ----
    ("45_R165_scene_preview.py", "candidate_b_c2/45_R165_scene_preview.py"),
    ("46_R165_arm_verify.py", "candidate_b_c2/46_R165_arm_verify.py"),
    ("47_R165_evidence.py", "candidate_b_c2/47_R165_evidence.py"),
    ("48_R165_package.py", "candidate_b_c2/48_R165_package.py"),
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
    # ---- R165 证据 ----
    ("evidence_r165_preview/preview_meta.json",
     "candidate_b_c2/evidence_r165_preview/preview_meta.json"),
    ("evidence_r165_preview/run.log",
     "candidate_b_c2/evidence_r165_preview/run.log"),
    ("evidence_r165_preview/r156_runtime_verify.json",
     "candidate_b_c2/evidence_r165_preview/r156_runtime_verify.json"),
    ("evidence_r165_preview/r158_runtime_verify.json",
     "candidate_b_c2/evidence_r165_preview/r158_runtime_verify.json"),
    ("evidence_r165_arm_verify.json",
     "candidate_b_c2/evidence_r165_arm_verify.json"),
    ("evidence_r165_scene_verify.json",
     "candidate_b_c2/evidence_r165_scene_verify.json"),
    ("evidence_r147_e2e.json",
     "candidate_b_c2/evidence_r147_e2e.json"),
    ("evidence_r165_measure.json",
     "candidate_b_c2/evidence_r165_measure.json"),
    ("assets/character_R158/bake_report.json",
     "candidate_b_c2/assets/character_R158/bake_report.json"),
    ("assets/character_R156/props_report.json",
     "candidate_b_c2/assets/character_R156/props_report.json"),
    ("assets/character_R156/prop_scene_guides.json",
     "candidate_b_c2/assets/character_R156/prop_scene_guides.json"),
    ("assets/character_R138_derived/r138_source_checksums.json",
     "candidate_b_c2/assets/character_R138_derived/r138_source_checksums.json"),
    ("assets/character_R138_derived/walk_right_mirror/derive_report.json",
     "candidate_b_c2/assets/character_R138_derived/walk_right_mirror/derive_report.json"),
]

for _f in R165_FRAMES + R165_PROPS:
    REVIEW_FILES.append((f"assets/character_R158/{_f}", f"candidate_b_c2/assets/character_R158/{_f}"))
for _f in R165_SCENE_PROPS:
    REVIEW_FILES.append((f"assets/character_R156/{_f}", f"candidate_b_c2/assets/character_R156/{_f}"))

_GIFS = [
    "R158_click_cheer_wave.gif", "R158_click_cheer_hands_up.gif",
    "R158_click_cheer_heart.gif", "R158_click_cheer_clap.gif",
    "R158_click_cheer_jump.gif", "R158_click_cheer_tilt.gif",
]
PREVIEW_FILES = [(f"evidence_r165_gifs/{g}", f"preview/{g}") for g in _GIFS]
PREVIEW_FILES += [
    ("evidence_r165_gifs/R158_click_pool_overview.png", "preview/R158_click_pool_overview.png"),
]

# R165 的场景前后对比图 (真实显示尺寸)
_SCENE_CMP = [
    "办公场景_修复前后_200x240.png", "办公场景_修复前后_256x256.png",
    "睡眠场景_修复前后_200x240.png", "睡眠场景_修复前后_256x256.png",
    "点击动作池_逐帧总览_新素材_200x240.png",
    "点击动作池_逐帧总览_R162旧素材_200x240.png",
    # 6 个点击动作的修复前后对比 (200x240 真实显示尺寸)
    "点击动作_cheer_wave_修复前后_200x240.png",
    "点击动作_cheer_hands_up_修复前后_200x240.png",
    "点击动作_cheer_heart_修复前后_200x240.png",
    "点击动作_cheer_clap_修复前后_200x240.png",
    "点击动作_cheer_jump_修复前后_200x240.png",
    "点击动作_cheer_tilt_修复前后_200x240.png",
]
for _f in _SCENE_CMP:
    PREVIEW_FILES.append((f"evidence_r165_compare/{_f}",
                          "preview/场景对比/" + _f))

DOC_FILES = [
    ("docs/R165_QA_REPORT.md", "docs/R165_QA_REPORT.md"),
    ("docs/R165_DELIVERY_INDEX.md", "docs/R165_DELIVERY_INDEX.md"),
]

README = """R165 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: __GENERATED_AT__
提交:     __COMMIT__

本轮主题: R162 真机验收失败后的精准修复 —— 点击动作"多出来一双手" / 办公场景不成立 /
          睡眠场景质量不足 (只修这 3 类, 不扩展功能)

candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
                  + assets/character_R158/  ★ R165 重烘焙的 18 张动作帧
                  + assets/character_R156/  ★ R165 重做的场景道具 (床/被子/月亮/桌+笔记本/屏幕光)
                  + prop_desk_surface.png   ★ R165 新增 (办公桌台面, back 层)
preview/          ★ 真实运行预览 GIF (6 个) + 总览图 + 场景前后对比图
evidence/         真实 Electron 重采集元数据 + 运行日志 + 运行时客观校验
                   + R165 客观判据报告 (C1~C4)
docs/             R165 质量报告 + 交付索引

R165 三项修复的证据链
--------------------------------
1. P0-1 点击动作"多出来一双手"
   真根因 (R165 才定位到, 之前四轮都误判成"手部数量问题"):
     · 手臂掩膜**根本不是手臂** —— 靠洪水填充切, 而袖子中段的青色饰条暗描边
       把填充拦腰截断 ⇒ 肩→肘的上臂整段没进掩膜 (实测仅 854 px);
     · `cuff_box` 坐标写错 (写 340~408, 底图真正的青色腕带在 x407~436)
       ⇒ 腕带种子落空, 腕带整条留在身体上;
     · 摘袖子后用"平涂衣身色"补 ⇒ 平涂区盖住上臂 + 保留袖子外轮廓描边
       ⇒ 身体上留一只"空袖子", 肘一折前臂+手横穿胸口 = 用户看到的"多出来一双手";
     · `bisect()` 的方向向量左右相反 ⇒ R 侧三段分配符号反转。
   修法: 掩膜改**几何重建** (逐行 [剪影外缘, 实测接缝线]); 袖子连腕带整块抹掉并把
         底图接缝线贴回当大褂外缘; 新增**静态肩关节球** + **肩区回填**;
         两条手臂**都必须参与** (不动的一侧走"摘→原位摆回")。
   客观判据: 46_R165_arm_verify.py (C1 胸前漂浮肢体 / C2 未解释的肤色 /
             C3 原手位残留 / C4 幽灵袖描边), 旧素材复验必 FAIL。

2. P0-2 办公场景
   真根因: 整张桌子放在 front 层 ⇒ 角色 sprite 里的双手 (y567~641) 完全落在桌板**上方**,
             一根手指都碰不到桌面 ⇒ 用户看到"双手搭在腿上"; 且屏幕朝观众 = 角色在
             屏幕背后坐, 物理不成立。
   修法: 桌子**拆成两层** (prop_desk_surface = back 层台面; prop_desk = front 层
         前沿+桌腿+笔记本) ⇒ 双手完整压在台面上; 笔记本背板朝观众、屏幕朝角色,
         放在角色右侧; 头部转向笔记本。

3. P0-3 睡眠场景
   修法: 被子上沿沿角色身体**实测轮廓** (逐列 alpha 测量) 起伏; 4 长 3 短羽化弧形褶皱;
         17px 翻折亮边; 左缘加翻折带 + 横向渐变淡出 (消除贴脸的硬直边);
         床/月亮重做, 月亮只做氛围不喧宾夺主。

复审要点
--------
1. python3 candidates/candidate_b_c2/46_R165_arm_verify.py --dir candidates/candidate_b_c2/assets/character_R158
2. python3 candidates/candidate_b_c2/47_R165_evidence.py            (重新产���全部对比图)
3. python3 candidates/candidate_b_c2/45_R165_scene_preview.py --all (真实尺寸场景预览)
4. node  candidates/candidate_b_c2/tests/r162_click_defects.test.js
5. node  candidates/candidate_b_c2/tests/r158_click_actions.test.js
6. python3 candidates/candidate_b_c2/43_R162_defect_verify.py
7. python3 candidates/candidate_b_c2/39_R158_runtime_verify.py --preview-dir candidates/candidate_b_c2/evidence_r165_preview
8. python3 candidates/candidate_b_c2/34_R156_runtime_verify.py --preview-dir candidates/candidate_b_c2/evidence_r165_preview
9. python3 candidates/candidate_b_c2/37_R158_action_bake.py           (重放烘焙, 内置唯一性自检)
10. bash   candidates/candidate_b_c2/R147_e2e_test.sh                (真实 Electron 全量回归)

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
        zf.writestr("evidence/README_R165_review.txt", readme)
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
    print("R165 打包:")
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

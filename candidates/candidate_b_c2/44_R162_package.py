#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R162 交付打包器 — 生成轻量审查包 + 完整备份 + SHA256。

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

用法: python3 44_R162_package.py <commit>
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

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R162_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r162.zip" % time.strftime("%Y%m%d_%H%M%S"))

R162_FRAMES = [
    "cheer_wave_0.png", "cheer_wave_1.png", "cheer_wave_2.png",
    "cheer_hands_up_0.png", "cheer_hands_up_1.png", "cheer_hands_up_2.png",
    "cheer_heart_0.png", "cheer_heart_1.png", "cheer_heart_2.png",
    "cheer_clap_0.png", "cheer_clap_1.png", "cheer_clap_2.png",
    "cheer_jump_0.png", "cheer_jump_1.png", "cheer_jump_2.png",
    "cheer_tilt_0.png", "cheer_tilt_1.png", "cheer_tilt_2.png",
]
R162_PROPS = ["prop_heart.png"]

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
    # ---- R158 新增脚本 ----
    ("36_R158_arm_rig.py", "candidate_b_c2/36_R158_arm_rig.py"),
    ("36b_R158_pose_preview.py", "candidate_b_c2/36b_R158_pose_preview.py"),
    ("37_R158_action_bake.py", "candidate_b_c2/37_R158_action_bake.py"),
    ("38_R158_manifest_update.py", "candidate_b_c2/38_R158_manifest_update.py"),
    ("39_R158_runtime_verify.py", "candidate_b_c2/39_R158_runtime_verify.py"),
    ("40_R158_preview_gif.py", "candidate_b_c2/40_R158_preview_gif.py"),
    ("41_R158_package.py", "candidate_b_c2/41_R158_package.py"),
    ("42_R158_measure_report.py", "candidate_b_c2/42_R158_measure_report.py"),
    # ---- R162 新增脚本 ----
    ("43_R162_defect_verify.py", "candidate_b_c2/43_R162_defect_verify.py"),
    ("44_R162_package.py", "candidate_b_c2/44_R162_package.py"),
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
    # ---- R162 证据 ----
    ("evidence_r162_preview/preview_meta.json",
     "candidate_b_c2/evidence_r162_preview/preview_meta.json"),
    ("evidence_r162_preview/run.log", "candidate_b_c2/evidence_r162_preview/run.log"),
    ("evidence_r162_preview/r156_runtime_verify.json",
     "candidate_b_c2/evidence_r162_preview/r156_runtime_verify.json"),
    ("evidence_r162_preview/r158_runtime_verify.json",
     "candidate_b_c2/evidence_r162_preview/r158_runtime_verify.json"),
    ("evidence_r162_rig_verify.json", "candidate_b_c2/evidence_r162_rig_verify.json"),
    ("evidence_r162_measure.json", "candidate_b_c2/evidence_r162_measure.json"),
    ("assets/character_R158/bake_report.json", "candidate_b_c2/assets/character_R158/bake_report.json"),
    ("assets/character_R138_derived/r138_source_checksums.json",
     "candidate_b_c2/assets/character_R138_derived/r138_source_checksums.json"),
    ("assets/character_R138_derived/walk_right_mirror/derive_report.json",
     "candidate_b_c2/assets/character_R138_derived/walk_right_mirror/derive_report.json"),
]

for _f in R162_FRAMES + R162_PROPS:
    REVIEW_FILES.append((f"assets/character_R158/{_f}", f"candidate_b_c2/assets/character_R158/{_f}"))

_GIFS = [
    "R158_click_cheer_wave.gif", "R158_click_cheer_hands_up.gif",
    "R158_click_cheer_heart.gif", "R158_click_cheer_clap.gif",
    "R158_click_cheer_jump.gif", "R158_click_cheer_tilt.gif",
]
# R162 的 GIF 目录 (真实运行重采集后重新合成)
PREVIEW_FILES = [(f"evidence_r162_gifs/{g}", f"preview/{g}") for g in _GIFS]
PREVIEW_FILES += [
    ("evidence_r162_gifs/R158_click_pool_overview.png", "preview/R158_click_pool_overview.png"),
]

DOC_FILES = [
    ("docs/R162_QA_REPORT.md", "docs/R162_QA_REPORT.md"),
    ("docs/R162_DELIVERY_INDEX.md", "docs/R162_DELIVERY_INDEX.md"),
]

README = """R162 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: __GENERATED_AT__
提交:     __COMMIT__

本轮主题: 修复点击动作的视觉缺陷 (承接 R158) —— 拼接残影 / 断线 / 头顶破损 / 手势清晰度

candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
                  + assets/character_R158/  ★ R162 重烘焙:
                     - 18 张动作帧 (6 个点击动作 × 3 帧)
                     - 1 个程序化矢量爱心特效 PNG (已移到**头侧空白区**, 不遮脸不遮手)
                     - bake_report.json (含每帧姿态参数与唯一性自检)
preview/          ★ 真实运行预览 (可直接观看, 6 个 GIF + 1 张总览图)
evidence/         运行时客观量化 (23 + 6 项) + rig 层缺陷验证 + e2e 机器报告
                   + 真实采集元数据 + 真实运行日志
docs/             R162 质量报告 + 交付索引

本轮完成定义 → 证据
--------------------------------
1. 拼接残影 / 断线 (手臂连接处)
   · 根因①: 重建大褂外缘时, 描边颜色取自描边**外侧**的窗口 —— 那里在底图里是
     透明像素, RGB 残值随机 ⇒ 描边有时纯黑有时纯白 ⇒ 整条衣身边缘成**虚线**。
     修法: 保留底图剪影描边带原像素 (OUT_KEEP=5), 描边色只从底图接缝线取。
   · 根因②: 洪水填充从**肩膀上方**绕进大褂胸口 ⇒ 手臂一转衣身跟着飞 ⇒ 白色残块。
     修法: 按底图实测的接缝线 SEAM_L 给手臂掩膜内侧封顶 (越界行数 = 0)。
   · 根因③: 袖子外侧那条**青色高光带**留在掩膜外 ⇒ 原地留下青色虚线。
     修法: 沿不透明像素一路走到真正的剪影, 整段并入掩膜 (外侧青色残留 0 px)。
   · 附带: 旋转改预乘 alpha 双线性 (最近邻会把斜描边重采样成 1px 阶梯)。
   证据: tests/r162_click_defects.test.js R2-2 + 43_R162_defect_verify.py
         (重建后衣身外缘连续 236/236 行、缺口 0)。

2. 头顶图像破损 (cheer_jump_0)
   · 根因: 烘焙顺序是 头部变换 → 整体压扁 → 贴五官, 而五官 donor 是**未压缩**帧
     ⇒ 五官被按原坐标贴进已压扁的头顶。
   · 修法: 改为 手臂 → 贴五官 → 头部变换 → 整体压扁。
   证据: R2-1 (cheer_jump_0 头部 y<260 肤色像素 2605 → 0)。

3. 比心 / 鼓掌在 200×240 实际尺寸下的清晰度
   · R158 遗留: 比心与鼓掌的手臂角度几乎相同 (两个动作长得一样), 且"鼓掌"的旧参数
     实际是"双臂平举"。R162 重新标定: 比心 = 双手在下颌前合成心形; 鼓掌 = 肘部外张、
     手心相对、领口高度张开→合拢 (两掌间距 92→0→64 纹理 px)。
   · 爱心特效从**胸口正中央**移到**头侧左上空白区** (压在躯干上会把手势盖掉),
     200px 下 23.5×23.5 屏幕 px, 与脸/手/躯干重叠 0 px。
   证据: R2-3 / R2-4 / R2-5 + preview/R158_click_pool_overview.png。

4. 判据本身是有效的 (已用旧素材复验)
   把 assets/character_R158/ 整目录换回 R158 旧素材, 重跑
   `node tests/r162_click_defects.test.js` ⇒ **0 passed / 5 failed**;
   换回 R162 素材 ⇒ **5 passed / 0 failed**。

5. 回归防线
   · R138 原始 23 帧 SHA256 逐字节未变 (人物身份与服装未改)。
   · R156 的 7 个道具 + 5 个场景逐字节保留; R148 行走方向、���113 拖拽核心未动。
   · 单元 152/152, 运行时 23/23 + 6/6, rig 验证全过, e2e 59 PASS / 0 FAIL。

做不到的事 (如实列出, 未硬标 PASS)
--------------------------------
- **手指级几何"真比心"在桌宠实际显示尺寸下不可读** —— compact 200x240 缩放 0.196319,
  整只开口约 12x16 屏幕 px, 单指宽约 2px, 围不出可辨认的闭合心形
  ⇒ 比心用"双手在下颌前合成心形 + 头侧爱心特效"的可读性方案, 动作描述里如实写明。
- **真正的 180° 背面转身仍做不到** —— R138 全库只有正面素材, R158 已下架并给出
  精确的新素材需求清单, 本轮不涉及, 清单原样保留。
- **比心帧两腕之间的小青色竖条是袖口腕带本身** (结构真实存在), 不是残留;
  "没有额外青色残影"已用客观判据证明 (外侧青色残留 0 px)。
- **手臂摆动本质是剪影式切割动画** —— 本轮不重做动画系统; 在实测的 6 组角度内
  肉眼不可见切割感, 超出该角度范围仍可能看出切割痕迹。
- **Mac 真机验收 = PENDING** (沙箱无法完成真实鼠标手感与真机观感判断)。

复审要点
--------
1. node  candidates/candidate_b_c2/tests/r162_click_defects.test.js   (5 项 R162 缺陷回归)
2. node  candidates/candidate_b_c2/tests/r158_click_actions.test.js   (25 项)
3. python3 candidates/candidate_b_c2/43_R162_defect_verify.py         (rig 层缺陷验证)
4. python3 candidates/candidate_b_c2/39_R158_runtime_verify.py --preview-dir candidates/candidate_b_c2/evidence_r162_preview
5. python3 candidates/candidate_b_c2/34_R156_runtime_verify.py --preview-dir candidates/candidate_b_c2/evidence_r162_preview
6. python3 candidates/candidate_b_c2/37_R158_action_bake.py             (重放烘焙, 内置唯一性自检)
7. python3 candidates/candidate_b_c2/38_R158_manifest_update.py          (manifest 幂等更新)
8. python3 candidates/candidate_b_c2/40_R158_preview_gif.py --preview-dir candidates/candidate_b_c2/evidence_r162_preview --out-dir candidates/candidate_b_c2/evidence_r162_gifs
9. bash   candidates/candidate_b_c2/R147_e2e_test.sh                    (真实 Electron 全量回归)
10. python3 candidates/candidate_b_c2/tools/r144_drag_core_diff.py      (R113 拖拽核心逐字未改)

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
        zf.writestr("evidence/README_R162_review.txt", readme)
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
    print("R162 打包:")
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

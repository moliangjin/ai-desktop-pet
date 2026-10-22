#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R167 交付打包器 — 生成轻量审查包 + 完整备份 + SHA256。

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

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R167_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r167.zip" % time.strftime("%Y%m%d_%H%M%S"))

R165_FRAMES = [
    "cheer_wave_0.png", "cheer_wave_1.png", "cheer_wave_2.png",
    "cheer_hands_up_0.png", "cheer_hands_up_1.png", "cheer_hands_up_2.png",
    "cheer_heart_0.png", "cheer_heart_1.png", "cheer_heart_2.png",
    "cheer_clap_0.png", "cheer_clap_1.png", "cheer_clap_2.png",
    "cheer_jump_0.png", "cheer_jump_1.png", "cheer_jump_2.png",
    "cheer_tilt_0.png", "cheer_tilt_1.png", "cheer_tilt_2.png",
]
R165_PROPS = ["prop_heart.png"]
# R167 新增的场景道具 (★ 键盘属于 character_R156/ 场景道具库, 不在 character_R158/)
R167_PROPS = []
# R165/R167 重做/新增的场景道具 (进包, 供复审直接对比)
R165_SCENE_PROPS = ["prop_bed.png", "prop_quilt.png", "prop_moon.png",
                    "prop_desk.png", "prop_desk_surface.png", "prop_screen_glow.png",
                    "prop_chair.png", "prop_keyboard.png"]

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
    # ---- R167 新增脚本 ----
    ("67_R167_diag_sit_arms.py", "candidate_b_c2/67_R167_diag_sit_arms.py"),
    ("68_R167_sleep_props.py", "candidate_b_c2/68_R167_sleep_props.py"),
    ("69_R167_spike_work.py", "candidate_b_c2/69_R167_spike_work.py"),
    ("71_R167_scene_verify.py", "candidate_b_c2/71_R167_scene_verify.py"),
    ("72_R167_evidence.py", "candidate_b_c2/72_R167_evidence.py"),
    ("73_R167_package.py", "candidate_b_c2/73_R167_package.py"),
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
    ("evidence_r167_preview/preview_meta.json",
     "candidate_b_c2/evidence_r167_preview/preview_meta.json"),
    ("evidence_r167_preview/run.log",
     "candidate_b_c2/evidence_r167_preview/run.log"),
    ("evidence_r167_preview/r156_runtime_verify.json",
     "candidate_b_c2/evidence_r167_preview/r156_runtime_verify.json"),
    ("evidence_r167_preview/r158_runtime_verify.json",
     "candidate_b_c2/evidence_r167_preview/r158_runtime_verify.json"),
    ("evidence_r167_arm_verify.json",
     "candidate_b_c2/evidence_r167_arm_verify.json"),
    ("evidence_r147_e2e.json",
     "candidate_b_c2/evidence_r147_e2e.json"),
    ("evidence_r167_scene_verify.json",
     "candidate_b_c2/evidence_r167_scene_verify.json"),
    ("evidence_r167_measure.json",
     "candidate_b_c2/evidence_r167_measure.json"),
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

for _f in R165_FRAMES + R165_PROPS + R167_PROPS:
    REVIEW_FILES.append((f"assets/character_R158/{_f}", f"candidate_b_c2/assets/character_R158/{_f}"))
for _f in R165_SCENE_PROPS:
    REVIEW_FILES.append((f"assets/character_R156/{_f}", f"candidate_b_c2/assets/character_R156/{_f}"))
# R167 重烘焙的办公帧 (剪掉下半身 + 双手按键盘) —— 复审必须能直接看到原帧
for _f in ("work_1.png", "work_2.png"):
    REVIEW_FILES.append((f"assets/character_R156/{_f}", f"candidate_b_c2/assets/character_R156/{_f}"))

_GIFS = [
    "R158_click_cheer_wave.gif", "R158_click_cheer_hands_up.gif",
    "R158_click_cheer_heart.gif", "R158_click_cheer_clap.gif",
    "R158_click_cheer_jump.gif", "R158_click_cheer_tilt.gif",
]
PREVIEW_FILES = [(f"evidence_r167_gifs/{g}", f"preview/{g}") for g in _GIFS]
PREVIEW_FILES += [
    ("evidence_r167_gifs/R158_click_pool_overview.png", "preview/R158_click_pool_overview.png"),
]

# R167 的场景前后对比图 (真实显示尺寸)
_SCENE_CMP = [
    "办公场景_修复前后_200x240.png", "办公场景_修复前后_256x256.png",
    "办公场景_双手放大_前后对比.png",
    "办公场景_打字动作两帧_200x240.png", "办公场景_打字动作_双手放大.png",
    "睡眠场景_修复前后_200x240.png", "睡眠场景_修复前后_256x256.png",
    "睡眠场景_被子床放大_前后对比.png",
    "点击动作池_逐帧总览_R167_200x240.png",
]
for _f in _SCENE_CMP:
    PREVIEW_FILES.append((f"evidence_r167_compare/{_f}",
                          "preview/场景对比/" + _f))

# R165 的前后对比图 (保留, 供对照"上一轮修成什么样")
_SCENE_CMP_R165 = [
    "办公场景_修复前后_200x240.png", "办公场景_修复前后_256x256.png",
    "睡眠场景_修复前后_200x240.png", "睡眠场景_修复前后_256x256.png",
    "点击动作_cheer_clap_修复前后_200x240.png",
    "点击动作_cheer_hands_up_修复前后_200x240.png",
    "点击动作_cheer_heart_修复前后_200x240.png",
    "点击动作_cheer_jump_修复前后_200x240.png",
    "点击动作_cheer_tilt_修复前后_200x240.png",
    "点击动作_cheer_wave_修复前后_200x240.png",
    "点击动作池_逐帧总览_R162旧素材_200x240.png",
    "点击动作池_逐帧总览_新素材_200x240.png",
]
for _f in _SCENE_CMP_R165:
    PREVIEW_FILES.append((f"evidence_r165_compare/{_f}",
                          "preview/场景对比_上一轮R165/" + _f))

DOC_FILES = [
    ("docs/R165_QA_REPORT.md", "docs/R165_QA_REPORT.md"),
    ("docs/R165_DELIVERY_INDEX.md", "docs/R165_DELIVERY_INDEX.md"),
    ("docs/R167_QA_REPORT.md", "docs/R167_QA_REPORT.md"),
    ("docs/R167_DELIVERY_INDEX.md", "docs/R167_DELIVERY_INDEX.md"),
]

README = """R167 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: __GENERATED_AT__
提交:     __COMMIT__

本轮主题: R165 审查 PARTIAL 后的最后两项视觉整改 ——
          办公场景"双手真正在键盘上打字" / 睡眠场景"柔软蓬松的浅蓝布被 + 看得见的床"
          (只修这两项, 点击动作成果原样保留, 不扩展功能)

candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
                  + assets/character_R158/  6 个点击动作 × 3 帧 (本轮未改动)
                  + assets/character_R156/  ★ R167 重做的场景道具
                    · prop_keyboard.png  ★新 (办公键盘, 透视梯形 + 4 排键位)
                    · prop_desk_surface.png / prop_desk.png  (加深台面 + 笔记本后移)
                    · prop_quilt.png / prop_bed.png  (浅蓝蓬松布被 + 床头立板/床架/床垫)
                    · work_1.png / work_2.png  ★重烘焙 (剪掉下半身 + 双手按键盘)
preview/           ★ 真实运行预览 GIF (6 个) + 总览图 + 办公/睡眠前后对比图
evidence/          真实 Electron 重采集元数据 + 运行日志 + 运行时客观校验
                   + R165/R167 客观判据报告 (C0~C5 / P2-1~P2-8 / P3-1~P3-7)
docs/             R165 + R167 质量报告 + 交付索引

R167 两项修复的证据链
--------------------------------
1. 办公场景"双手真正在操作键盘"
   真根因 (不是"手的位置不对", 是 **z 序根本不成立**):
     · 渲染顺序是 back 道具 → 角色 → front 道具; 台面在 back 层, 而角色的
       **大腿正好压在台面带上** ⇒ 台面被她的腿整片挡住, 键盘压根没地方出现,
       用户看到的永远是"双手搭在腿上";
     · 没有键盘这个道具 ⇒ "手按键盘"物理上不存在;
     · 笔记本底座落在台面**近沿**, 与键盘抢位置 ⇒ 透视不对。
   修法:
     · 角色帧在 y=592 以下剪掉下半身 (双手+腕带保留) ⇒ 台面从她腰部露出;
     · 新增 prop_keyboard.png (back 层, 远沿 566 / 近沿 664, 4 排键位 + 空格键,
       分隔线加粗到 4~5 纹理 px, 因为 200x240 上 1 纹理 px 只有 0.2 屏幕 px);
     · 笔记本后移 (盖板 y428..596 / 基座 y596..622) ⇒ 屏幕在后、键盘在前;
     · 台面加深 (近沿 668 → 700) ⇒ 真尺寸下台面有 21 屏幕 px 的纵深;
     · 打字动作: work_1 手指按下 / work_2 抬起 (手部质心位移 10.2 纹理 px)。
   客观判据: 71_R167_scene_verify.py 的 P2-1~P2-8, **全部在 200×240 真实合成图上量**
             (键盘可见像素、双落在键区的比例、两帧手部位移), 旧素材复验必 FAIL。

2. 睡眠场景"柔软蓬松的浅蓝布被 + 看得见的床"
   真根因: 被子是**平涂色块 + 硬边**, 没有任何高度/明暗层次; 床的立板与腿
           落在 200×240 窗口裁切线以下, 所以"床几乎看不见"。
   修法:
     · 被子改成**高度场 + Lambert 着色**: 形体 / 绗缝鼓包 / 折痕沟槽三层分开
       给权重, 鼓包自动出高光凹陷、沟槽自动出"一侧受光亮边 + 另一侧柔和阴影";
       配色由灰蓝改为浅蓝 (暗 #7EA6D1 → 亮 #E0EEFA);
     · 菱形绗缝 + 顶部翻折被沿 + 边缘羽化 (alpha blur 2.8 + 左沿淡出);
     · 床: 床头立板做高做宽 (上沿提到 y=228, 露出 90+ 屏幕 px 的木立板),
       床垫 + 木质床侧栏整体上移 40 纹理 px, 左右角腿可见;
     · 床整体横向缩到 1000 并右移 8px ⇒ 200x240 下左右都不越界。
   客观判据: P3-1~P3-7 (被子浅蓝 / 褶皱明暗 p90-p10 / 遮脸 / 床架与床垫在
             200x240 的可见像素), 旧素材复验必 FAIL。

3. 附带修正: 报表口径对齐 (42_R158_measure_report.py)
   · 发现 42 号报表脚本的面积判据没跟上 node 单测 C1 在 R165 做的"纵向压扁系数
     归一化", 于是把 cheer_jump 三帧里**故意压扁**的蓄力/落地帧误判成"整体压缩"
     (原始偏差 -15.19% > 15% 门槛)。这是**报表工具的 bug, 不是素材缺陷**:
     用 HEAD 的独立 worktree 复现, 同一脚本在 35a8822 上给出完全相同的数字,
     即该 FAIL 是 HEAD 自带的存量问题, 与 R167 无关。
   · 42 号脚本现按 node 单测 C1 的同一公式测量:
         ratio = 中位帧面积 / (基准面积 × 该帧 scale_y)
     阈值仍是 15%, 公式与阈值都没有放宽, 并**保留原始未归一化偏差字段**供复核。
     修正后 cheer_jump = +0.97% PASS (原始 -15.19%, 与 scale_y=0.84 一致,
     证明没有额外的水平压缩)。
   · 另发现 R165 归档里的 evidence_r165_measure.json 是**陈旧快照**:
     它记录的 cheer_wave/cheer_clap/cheer_jump 面积 (212244/203477/183127)
     与 HEAD 实际素材实测 (211501/208630/182192) 对不上 —— 即该 JSON 生成之后
     点击动作帧又被重烘焙过, 但 JSON 没有同步。本轮不改动 R165 历史归档,
     改用新生成的 evidence_r167_measure.json, 并在此如实记录该差异。
   · **R167 未改动任何点击动作素材**: assets/character_R158/ 18 张帧与 HEAD 逐字节一致。

复审要点
--------
1. python3 candidates/candidate_b_c2/71_R167_scene_verify.py   (办公+睡眠 15 项)
2. python3 candidates/candidate_b_c2/72_R167_evidence.py        (重新产出全部对比图)
3. python3 candidates/candidate_b_c2/45_R165_scene_preview.py --scene work --size 200x240
4. python3 candidates/candidate_b_c2/45_R165_scene_preview.py --scene sleep_loop --size 200x240
5. node  candidates/candidate_b_c2/tests/r156_click_props_work.test.js
6. python3 candidates/candidate_b_c2/46_R165_arm_verify.py --dir candidates/candidate_b_c2/assets/character_R158
7. python3 candidates/candidate_b_c2/34_R156_runtime_verify.py --preview-dir candidates/candidate_b_c2/evidence_r167_preview
8. python3 candidates/candidate_b_c2/39_R158_runtime_verify.py --preview-dir candidates/candidate_b_c2/evidence_r167_preview
9. bash   candidates/candidate_b_c2/R147_e2e_test.sh                (真实 Electron 全量回归)
10. 重放烘焙: 30_R156_props_bake.py → 68_R167_sleep_props.py → 29_R156_pose_bake.py → 38_R158_manifest_update.py

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
        zf.writestr("evidence/README_R167_review.txt", readme)
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
    print("R167 打包:")
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R170 交付打包器 — 生成轻量审查包 + 完整备份 + SHA256。

与 R167 的差别:
  · 新增 R170 的脚本 (80 spike / 81 吃水果帧烘焙 / 82 吃水果道具 / 83 客观判据 /
    84 证据产出 / 85 本打包器)
  · 新增 R170 的证据 (真实 Electron 重采集 + 运行时校验 + 客观判据 + GIF + 总览图)
  · 新增吃水果的 5 张角色帧 + 2 个场景道具 (prop_stool / prop_fruit_table) 一并入包
  · R158 的 18 张点击动作帧与 R167 的办公/睡眠素材照旧入包 (本轮未改动)

SHA256 写在 ZIP **旁边的独立 .sha256 文件** (不内嵌), 避免"改索引就改哈希"的循环自引用。

用法: python3 85_R170_package.py <commit>
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

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R170_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r170.zip" % time.strftime("%Y%m%d_%H%M%S"))

R158_FRAMES = [
    "cheer_wave_0.png", "cheer_wave_1.png", "cheer_wave_2.png",
    "cheer_hands_up_0.png", "cheer_hands_up_1.png", "cheer_hands_up_2.png",
    "cheer_heart_0.png", "cheer_heart_1.png", "cheer_heart_2.png",
    "cheer_clap_0.png", "cheer_clap_1.png", "cheer_clap_2.png",
    "cheer_jump_0.png", "cheer_jump_1.png", "cheer_jump_2.png",
    "cheer_tilt_0.png", "cheer_tilt_1.png", "cheer_tilt_2.png",
]
# R170 新增: 吃水果 5 帧 (角色帧, 在 character_R156/)
R170_EAT_FRAMES = ["eat_fruit_%d.png" % i for i in range(5)]
# 场景道具库 (character_R156/)
SCENE_PROPS = ["prop_bed.png", "prop_quilt.png", "prop_moon.png", "prop_sofa.png",
               "prop_chair.png", "prop_desk.png", "prop_desk_surface.png",
               "prop_screen_glow.png", "prop_keyboard.png",
               # R170: 吃水果场景的小凳 + 小边桌(果盘)
               "prop_stool.png", "prop_fruit_table.png"]
R156_CHAR_FRAMES = ["work_1.png", "work_2.png"]

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
    ("tests/r170_eat_fruit_work.test.js", "candidate_b_c2/tests/r170_eat_fruit_work.test.js"),
    ("tests/lib/png_reader.js", "candidate_b_c2/tests/lib/png_reader.js"),
    # ---- 工具 ----
    ("tools/r144_drag_core_diff.py", "candidate_b_c2/tools/r144_drag_core_diff.py"),
    ("tools/r144_layout_probe.js", "candidate_b_c2/tools/r144_layout_probe.js"),
    # ---- R170 新增脚本 ----
    ("80_R170_eat_fruit_spike.py", "candidate_b_c2/80_R170_eat_fruit_spike.py"),
    ("81_R170_eat_fruit_bake.py", "candidate_b_c2/81_R170_eat_fruit_bake.py"),
    ("82_R170_eat_fruit_props.py", "candidate_b_c2/82_R170_eat_fruit_props.py"),
    ("83_R170_scene_verify.py", "candidate_b_c2/83_R170_scene_verify.py"),
    ("84_R170_evidence.py", "candidate_b_c2/84_R170_evidence.py"),
    ("85_R170_package.py", "candidate_b_c2/85_R170_package.py"),
    ("86_R170_trigger_verify.py", "candidate_b_c2/86_R170_trigger_verify.py"),
    ("87_R170_gif.py", "candidate_b_c2/87_R170_gif.py"),
    # ---- 前序轮次脚本 (便于复算) ----
    ("36_R158_arm_rig.py", "candidate_b_c2/36_R158_arm_rig.py"),
    ("37_R158_action_bake.py", "candidate_b_c2/37_R158_action_bake.py"),
    ("38_R158_manifest_update.py", "candidate_b_c2/38_R158_manifest_update.py"),
    ("39_R158_runtime_verify.py", "candidate_b_c2/39_R158_runtime_verify.py"),
    ("42_R158_measure_report.py", "candidate_b_c2/42_R158_measure_report.py"),
    ("45_R165_scene_preview.py", "candidate_b_c2/45_R165_scene_preview.py"),
    ("46_R165_arm_verify.py", "candidate_b_c2/46_R165_arm_verify.py"),
    ("71_R167_scene_verify.py", "candidate_b_c2/71_R167_scene_verify.py"),
    ("72_R167_evidence.py", "candidate_b_c2/72_R167_evidence.py"),
    ("73_R167_package.py", "candidate_b_c2/73_R167_package.py"),
    ("29_R156_pose_bake.py", "candidate_b_c2/29_R156_pose_bake.py"),
    ("30_R156_props_bake.py", "candidate_b_c2/30_R156_props_bake.py"),
    ("34_R156_runtime_verify.py", "candidate_b_c2/34_R156_runtime_verify.py"),
    ("22_R153_pose_bake.py", "candidate_b_c2/22_R153_pose_bake.py"),
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
    ("evidence_r170_preview/preview_meta.json",
     "candidate_b_c2/evidence_r170_preview/preview_meta.json"),
    ("evidence_r170_preview/run.log",
     "candidate_b_c2/evidence_r170_preview/run.log"),
    ("evidence_r170_preview/r156_runtime_verify.json",
     "candidate_b_c2/evidence_r170_preview/r156_runtime_verify.json"),
    ("evidence_r170_preview/r158_runtime_verify.json",
     "candidate_b_c2/evidence_r170_preview/r158_runtime_verify.json"),
    ("evidence_r170_scene_verify.json",
     "candidate_b_c2/evidence_r170_scene_verify.json"),
    ("evidence_r170_arm_verify.json",
     "candidate_b_c2/evidence_r170_arm_verify.json"),
    ("evidence_r170_measure.json",
     "candidate_b_c2/evidence_r170_measure.json"),
    ("evidence_r170_trigger.json",
     "candidate_b_c2/evidence_r170_trigger.json"),
    # R170: 修复前 (R167 交付版 git 3893c28) 的真实连跑基线取证 —— 前后对比的另一半
    ("evidence_r170_trigger_before.json",
     "candidate_b_c2/evidence_r170_trigger_before.json"),
    ("evidence_r147_e2e.json",
     "candidate_b_c2/evidence_r147_e2e.json"),
    ("assets/character_R158/bake_report.json",
     "candidate_b_c2/assets/character_R158/bake_report.json"),
    ("assets/character_R156/props_report.json",
     "candidate_b_c2/assets/character_R156/props_report.json"),
    ("assets/character_R156/prop_scene_guides.json",
     "candidate_b_c2/assets/character_R156/prop_scene_guides.json"),
    ("assets/character_R156/eat_fruit_report.json",
     "candidate_b_c2/assets/character_R156/eat_fruit_report.json"),
    ("assets/character_R138_derived/r138_source_checksums.json",
     "candidate_b_c2/assets/character_R138_derived/r138_source_checksums.json"),
    ("assets/character_R138_derived/walk_right_mirror/derive_report.json",
     "candidate_b_c2/assets/character_R138_derived/walk_right_mirror/derive_report.json"),
]

for _f in R158_FRAMES:
    REVIEW_FILES.append((f"assets/character_R158/{_f}", f"candidate_b_c2/assets/character_R158/{_f}"))
for _f in R170_EAT_FRAMES + R156_CHAR_FRAMES:
    REVIEW_FILES.append((f"assets/character_R156/{_f}", f"candidate_b_c2/assets/character_R156/{_f}"))
for _f in SCENE_PROPS:
    REVIEW_FILES.append((f"assets/character_R156/{_f}", f"candidate_b_c2/assets/character_R156/{_f}"))
REVIEW_FILES.append(("assets/character_R158/prop_heart.png",
                     "candidate_b_c2/assets/character_R158/prop_heart.png"))

_GIFS = [
    "R158_click_cheer_wave.gif", "R158_click_cheer_hands_up.gif",
    "R158_click_cheer_heart.gif", "R158_click_cheer_clap.gif",
    "R158_click_cheer_jump.gif", "R158_click_cheer_tilt.gif",
    # R170 新增: 吃水果完整动作 + 办公打字 (真实运行采集)
    "R170_scene_eat_fruit.gif", "R170_scene_work.gif",
]
PREVIEW_FILES = [(f"evidence_r170_gifs/{g}", f"preview/{g}") for g in _GIFS]
PREVIEW_FILES += [
    ("evidence_r170_gifs/R158_click_pool_overview.png", "preview/R158_click_pool_overview.png"),
    # R170 新增总览图
    ("evidence_r170_gifs/R170_eat_fruit_overview.png", "preview/R170_eat_fruit_overview.png"),
    ("evidence_r170_gifs/R170_work_overview.png", "preview/R170_work_overview.png"),
    ("evidence_r170_gifs/R170_scenes_overview.png", "preview/R170_scenes_overview.png"),
]

_SCENE_CMP = [
    "办公场景_R167版_vs_R170_200x240.png", "办公场景_R167版_vs_R170_256x256.png",
    "办公场景_触发频率_修复前vs修复后.png",
    "吃水果场景_200x240.png", "吃水果场景_256x256.png",
    "吃水果_5帧逐帧总览_200x240.png", "吃水果_5帧放大_手果嘴.png",
]
for _f in _SCENE_CMP:
    PREVIEW_FILES.append((f"evidence_r170_compare/{_f}", "preview/场景对比/" + _f))

DOC_FILES = [
    ("docs/R165_QA_REPORT.md", "docs/R165_QA_REPORT.md"),
    ("docs/R165_DELIVERY_INDEX.md", "docs/R165_DELIVERY_INDEX.md"),
    ("docs/R167_QA_REPORT.md", "docs/R167_QA_REPORT.md"),
    ("docs/R167_DELIVERY_INDEX.md", "docs/R167_DELIVERY_INDEX.md"),
    ("docs/R170_QA_REPORT.md", "docs/R170_QA_REPORT.md"),
    ("docs/R170_DELIVERY_INDEX.md", "docs/R170_DELIVERY_INDEX.md"),
]

README = """R170 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: __GENERATED_AT__
提交:     __COMMIT__

本轮主题: R167 审查 PARTIAL 后的两项任务 ——
          ① 恢复"电脑办公场景" (用户在真机上发现它消失了)
          ② 新增"吃水果"生活行为 (EAT_FRUIT)

candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
                  + assets/character_R158/  6 个点击动作 × 3 帧 (本轮未改动)
                  + assets/character_R156/  ★ R170 吃水果帧 + 场景道具
                    · eat_fruit_0..4.png  ★新 (拿果→送到嘴边→咬一口→咀嚼→满足微笑)
                    · prop_stool.png / prop_fruit_table.png  ★新 (小圆凳 + 小边桌果盘)
                    · work_1/work_2 + prop_desk* / prop_keyboard / prop_screen_glow (R167 成果, 未改动)
preview/           ★ 真实运行预览 GIF (点击 6 个 + 吃水果 + 办公) + 总览图 + 场景对比图
evidence/          真实 Electron 重采集元数据 + 运行日志 + 运行时客观校验
                   + R170 客观判据报告 + 自主行为真实触发记录
docs/             R165 / R167 / R170 质量报告 + 交付索引

R170 两项任务的证据链
--------------------------------
1. 办公场景"在真机上消失"的真根因 (**不是**画面素材问题)
   · 实测: 真实 Electron 连跑 180s, 空闲决策只有 9 次, WORK 触发 **0 次**。
   · 根因是三个数叠加:
     ① manifest 的 behavior.config 是 **R141 时代的陈旧快照**, 静默覆盖引擎
        (src/behavior_engine.js) 的 R153/R156 默认值 —— sleep_probability 被改回
        0.3 (引擎 R153 已降到 0.10)、walk_probability 0.7 (引擎 0.62),
        而且**根本没有** work 权重;
     ② work_probability=0.10 在总权重 2.00 里只占 **5%** 单次命中率;
     ③ 长活动 (睡 20~45s / 打盹 7~15s / 坐 6~13s) 把空闲决策压到 ~20s 一次
        ⇒ 期望 **~6.7 分钟才出现一次**, 每次还只有 9~19s。
   · 修法: manifest 配置与引擎默认值**对齐**(加根因回归护栏 A1);
     work 权重 0.10→0.55 (命中率 ~22%)、时长 9~19s→16~28s、新增 60s 冷却;
     另修掉一个同源 bug: 点击反馈会**清掉**"有时长"状态的计时器且无人重排
     ⇒ 办公中点一下角色, 引擎永远停在 WORK (现在按剩余时间恢复)。
   · 验收专用入口: `--demo-scene work` / `--demo-scene eat_fruit`
     (自主决策暂停, 场景锁定; 与正式自主行为完全分离)。

2. 吃水果 (EAT_FRUIT) —— 5 帧连拍 + 独立场景
   · 帧: 0 伸手拿果 → 1 举到嘴边 → 2 低头张嘴咬一口 → 3 轻微咀嚼 → 4 满足地笑
   · 水果**画在角色帧内部** ⇒ 手掌与水果的接触是像素级精确的,
     不会出现"把水果贴在脸上冒充吃东西"。
   · 坐姿手臂 rig: R165 的关节坐标是站立底图硬编码的, 在坐姿上会切错
     (实测站立腕点 (654,556) 与坐姿真实腕点 (512,558) 相差 142 px)
     ⇒ R170 自标定坐姿的肩/肘/腕与接缝线, 旋转/合成复用 36_ 的已验证实现。
   · 手臂原位在大腿上会破洞 ⇒ 竖向克隆填充 (洞内像素沿同列向下取第一个
     "不透明且非手臂"的像素) ⇒ 大腿洞取到青色裤腿, 衣身洞取到白色大褂。
   · 道具: 小圆凳 + 小边桌(果盘), back 层, 不遮脸, 随状态出现/消失。
   · 已接入自主行为: 权重 0.36 / 时长 14~22s / 冷却 50s, 与办公**互斥**,
     播放期间行走/睡眠不得打断, 结束后回到正常生活状态。

复审要点
--------
1. python3 candidates/candidate_b_c2/83_R170_scene_verify.py    (两场景客观判据)
2. python3 candidates/candidate_b_c2/84_R170_evidence.py        (重新产出全部对比图)
3. node  candidates/candidate_b_c2/tests/r170_eat_fruit_work.test.js
4. node  candidates/candidate_b_c2/tests/r156_click_props_work.test.js
5. python3 candidates/candidate_b_c2/45_R165_scene_preview.py --scene work --size 200x240
6. python3 candidates/candidate_b_c2/45_R165_scene_preview.py --scene eat_fruit --size 200x240
7. python3 candidates/candidate_b_c2/46_R165_arm_verify.py --dir candidates/candidate_b_c2/assets/character_R158
8. python3 candidates/candidate_b_c2/34_R156_runtime_verify.py --preview-dir candidates/candidate_b_c2/evidence_r170_preview
9. python3 candidates/candidate_b_c2/39_R158_runtime_verify.py --preview-dir candidates/candidate_b_c2/evidence_r170_preview
10. bash   candidates/candidate_b_c2/R147_e2e_test.sh                (真实 Electron 全量回归)
11. 验收入口: candidates/candidate_b_c2/C2_Mac人工验收.command work / eat_fruit
12. 重放烘焙: 81_R170_eat_fruit_bake.py → 82_R170_eat_fruit_props.py → 38_R158_manifest_update.py

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
        zf.writestr("evidence/README_R170_review.txt", readme)
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
    print("R170 打包:")
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R153 交付打包器 — 生成轻量审查包 + 完整备份 + SHA256。

两份包:
  1) 轻量审查包 (供独立复审):
     源码 / 测试 / 脚本 / manifest / 证据 JSON /
     **R153 新烘焙的 12 张动作帧** (含在包内, 便于复审者自行验证"局部烘焙"性质) /
     **18 个可直接观看的运行预览 GIF** + 动作总览图 + 坐躺过渡帧条 /
     报告与索引
     —— 不含 R138 的 23 张原始 PNG (素材本体可从 R138 交付包取, 另有 SHA256 清单核对)
  2) 完整备份: 候选实现的全部内容 (含 R138 23 帧 + 派生 4 帧 + R153 12 帧) + 本轮文档

SHA256 写在 ZIP **旁边的独立 .sha256 文件** (不内嵌), 避免"改索引就改哈希"的循环自引用。

用法: python3 24_R153_package.py <commit>
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

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R153_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r153.zip" % time.strftime("%Y%m%d_%H%M%S"))

R153_FRAMES = [
    "blink_half.png", "blink_closed.png", "doze_sit.png",
    "head_tilt.png", "head_tilt_other.png", "head_nod.png", "head_nod_back.png",
    "glance_left.png", "glance_right.png", "happy.png",
    "sleep_breath_in.png", "sleep_breath_out.png",
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
    ("tests/lib/png_reader.js", "candidate_b_c2/tests/lib/png_reader.js"),
    # ---- 工具 ----
    ("tools/r144_drag_core_diff.py", "candidate_b_c2/tools/r144_drag_core_diff.py"),
    ("tools/r144_layout_probe.js", "candidate_b_c2/tools/r144_layout_probe.js"),
    # ---- R153 新增脚本 ----
    ("22_R153_pose_bake.py", "candidate_b_c2/22_R153_pose_bake.py"),
    ("23_R153_manifest_update.py", "candidate_b_c2/23_R153_manifest_update.py"),
    ("25_R153_walk_posture_verify.py", "candidate_b_c2/25_R153_walk_posture_verify.py"),
    ("26_R153_baked_contact_sheet.py", "candidate_b_c2/26_R153_baked_contact_sheet.py"),
    ("27_R153_runtime_verify.py", "candidate_b_c2/27_R153_runtime_verify.py"),
    ("28_R153_preview_gif.py", "candidate_b_c2/28_R153_preview_gif.py"),
    # ---- 前序轮次脚本 (便于复算) ----
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
    ("evidence_r153_posture.json", "candidate_b_c2/evidence_r153_runtime_posture.json"),
    ("evidence_r153_posture/posture_compare.png",
     "candidate_b_c2/evidence_r153_posture/posture_compare.png"),
    ("evidence_r153_baked/contact_sheet.png",
     "candidate_b_c2/evidence_r153_baked/contact_sheet.png"),
    ("evidence_r153_baked/head_zoom.png",
     "candidate_b_c2/evidence_r153_baked/head_zoom.png"),
    ("assets/character_R153/bake_report.json", "candidate_b_c2/assets/character_R153/bake_report.json"),
    ("assets/character_R138_derived/r138_source_checksums.json",
     "candidate_b_c2/assets/character_R138_derived/r138_source_checksums.json"),
    ("assets/character_R138_derived/walk_right_mirror/derive_report.json",
     "candidate_b_c2/assets/character_R138_derived/walk_right_mirror/derive_report.json"),
]

# R153 烘焙的 12 张新帧 (含在包内, 便于复审者自行验证"局部烘焙"性质)
for _f in R153_FRAMES:
    REVIEW_FILES.append((f"assets/character_R153/{_f}", f"candidate_b_c2/assets/character_R153/{_f}"))

# 预览 GIF (真实运行采集, 可直接观看)
_GIFS = [
    "R153_walk_left.gif", "R153_walk_right.gif", "R153_idle.gif",
    "R153_click.gif", "R153_wake.gif",
    "R153_lib_look_around.gif", "R153_lib_tilt_head.gif", "R153_lib_head_nod.gif",
    "R153_lib_happy.gif", "R153_lib_blink_soft.gif", "R153_lib_stretch.gif",
    "R153_lib_sit_rest.gif", "R153_lib_doze.gif", "R153_lib_sleep_breath.gif",
    "R153_lib_transition.gif", "R153_lib_sit_to_doze.gif",
]
PREVIEW_FILES = [(f"evidence_r153_gifs/{g}", f"preview/{g}") for g in _GIFS]
PREVIEW_FILES += [
    ("evidence_r153_gifs/R153_action_overview.png", "preview/R153_action_overview.png"),
    ("evidence_r153_gifs/R153_sit_to_lie_transition.png", "preview/R153_sit_to_lie_transition.png"),
    ("evidence_r153_preview/preview_meta.json", "evidence/preview_meta.json"),
]

DOC_FILES = [
    ("docs/R153_QA_REPORT.md", "docs/R153_QA_REPORT.md"),
    ("docs/R153_DELIVERY_INDEX.md", "docs/R153_DELIVERY_INDEX.md"),
]

README = """R153 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: %s
提交:     %s

本轮主题: 动作自然度与自主生活丰富度升级 (承接 R148)

candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
                  + assets/character_R153/  ★ R153 新增: 12 张局部烘焙动作帧
                     (眼部区域合成 / 头部连续权重场弯曲 / 胸口软遮罩微缩)
preview/          ★ 真实运行预览 (可直接观看, 18 个 GIF + 2 张图)
                   - R153_walk_left.gif / R153_walk_right.gif  行走 (R153: 整体错切归零, 重心端正)
                   - R153_idle.gif          自然待机 (不再出现"手放胸前")
                   - R153_click.gif         单击反馈 (歪头+眯眼笑)
                   - R153_wake.gif          睡眠点击唤醒 → 伸懒腰
                   - R153_lib_*.gif (10 个)  9 个新增动作 + 坐躺过渡 + 坐下打盹
                   - R153_action_overview.png      15 个动作并排总览
                   - R153_sit_to_lie_transition.png  坐→躺逐帧渐变帧条
evidence/         运行时客观量化 (evidence_r153_runtime.json) + 行走姿态测量 + 采集元数据
docs/             R153 质量报告 + 交付索引

用户反馈 → 根因 → 修复 (四项)
--------------------------------
1. 启动/点击"莫名抬手、手放胸前"
   根因: R138 的 idle_04 **不是眨眼帧**, 它是"右手横在胸前"的姿势;
         R147 的眨眼序列 [4,5] 与点击反馈都用到了它。
   修复: 眨眼序列 → [5] (纯闭眼, 手臂下垂); idle_04 列入永不播放;
         点击反馈改为 R153 烘焙的"歪头+眯眼笑"(happy) + 7px 弹跳。
   证据: 运行时 IDLE_BLINK frame=5 出现, frame=4 出现 0 次;
         点击段头部虹膜像素 min=9, 睁眼待机 min=90。

2. "坐下后瞬间变成躺姿"
   根因: sleep_enter 的**第 0 帧本身就是坐姿** → 动作级溶解实际是"坐→坐"(无变化);
         真正的躺姿出现在动画换帧那一瞬, 是硬切。
   修复: 新增**帧级**交叉溶解 (sleep_enter 320ms / wake_up 280ms / head_nod 180ms)。
   证据: 坐→躺之间实测 7 帧中间态 (d_sit 25.5→44.0, d_lie 75.4→35.3);
         运行时日志 "R153 FRAME_BLEND sleep_enter 0 -> 1 (320ms)"。

3. "行走时身体明显前倾, 像要摔倒"
   根因: R147 的**整体水平错切** skew_x (walk_left +0.085 / walk_right -0.11),
         整个身体偏离垂直轴。
   修复: 错切归零 —— R148 的派生镜像帧已自带正确迈步方向, 不再需要剪切表达方向。
   证据: 像素级躯干偏心 旧 0.0933 身高 (5.33°) → 新 0.0166 身高 (0.95°), 保留 17.8%;
         运行时实测 walk_left -0.01237 / walk_right +0.01216, 最大绝对值 0.01689 < 3% 门槛。

4. "现有动作太少、行为重复"
   根因: 运行时只有 6 组动作; 引擎是 "IDLE → 30%睡 / 70%走" 的机械二选一。
   修复: 15 个动作 (6 核心 + 9 新增); 引擎改为 5 类加权活动池 + 重复折扣 + 醒后冷却。
   证据: 见 preview/R153_action_overview.png 与 docs/R153_QA_REPORT.md。

本轮额外修掉的一个致命 bug (单测没抓到, 真实运行时才暴露)
----------------------------------------------------------
anim_clock.period() 直接 `return m.frame_ms`; 库动作的 frame_ms 是**每帧时长数组**
(如 blink_soft [130,170]) → 数组参与数值比较变 NaN → `now - lastAdvanceAt >= NaN` 恒 false
→ **帧永远不推进**。后果: 9 个库动作里有 5 个多帧动作在真实运行时全是静止的
(张望/歪头/点头/眨眼/呼吸 全部定格)。
修复: period() 支持每帧时长数组。回归防线: tests/r153_action_library.test.js J1/J2/J3。
修复后实测各动作"变化像素数": 张望 2698 / 歪头 3040 / 点头 8951 / 眨眼 8808 / 呼吸 1705。

复审要点
--------
1. node  candidates/candidate_b_c2/tests/r153_action_library.test.js  (22 项: 动作库/不虚增/帧级溶解/anim_clock 回归)
2. node  candidates/candidate_b_c2/tests/r141_behavior_engine.test.js (17 项: 活动池/打盹分层/醒后冷却)
3. node  candidates/candidate_b_c2/tests/r147_interaction.test.js      (23 项: 点击/眨眼/行走不倾斜)
4. node  candidates/candidate_b_c2/tests/r148_walk_direction.test.js  (8 项: 镜像严格性/资产字节)
5. python3 candidates/candidate_b_c2/25_R153_walk_posture_verify.py   (行走姿态像素级测量 + 对比图)
6. python3 candidates/candidate_b_c2/27_R153_runtime_verify.py --preview-dir <采集目录>  (运行时 6 项)
7. python3 candidates/candidate_b_c2/22_R153_pose_bake.py             (重放烘焙, 可复算)
8. bash   candidates/candidate_b_c2/R147_e2e_test.sh                 (真实 Electron 全量回归)
9. python3 candidates/candidate_b_c2/tools/r144_drag_core_diff.py    (R113 拖拽核心逐字未改)

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
        zf.writestr("evidence/README_R153_review.txt", README % (time.strftime("%Y-%m-%d %H:%M:%S"), commit))
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
                if f.endswith(".pyc"):
                    continue
                src = os.path.join(base, f)
                arc = os.path.relpath(src, ROOT)
                zf.write(src, arc)
                n += 1
        for rel, arc in DOC_FILES + [("docs/R148_QA_REPORT.md", "docs/R148_QA_REPORT.md"),
                                     ("docs/R148_DELIVERY_INDEX.md", "docs/R148_DELIVERY_INDEX.md")]:
            if add(zf, os.path.join(ROOT, rel), arc):
                n += 1
    return n


def main():
    commit = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print("R153 打包:")
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

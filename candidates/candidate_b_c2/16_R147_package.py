#!/usr/bin/env python3
"""R147 交付打包器 — 生成轻量审查包 + 完整备份 + SHA256。

两份包:
  1) 轻量审查包 (供独立复审):
     源码 / 测试 / 脚本 / manifest / 证据 JSON / **可观看的运行预览 GIF** / 报告与索引
     —— 不含 23 张 PNG (素材本体可从 R138 交付包取, 另有 SHA256 清单核对)
  2) 完整备份: 候选实现的全部内容 (含 23 帧素材) + 本轮文档

SHA256 写在 ZIP **旁边的独立 .sha256 文件** (不内嵌), 避免"改索引就改哈希"的循环自引用。

用法: python3 16_R147_package.py
"""
import hashlib
import os
import shutil
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))    # 仓库根 (HERE=candidates/candidate_b_c2)
CAND = HERE
OUT_DIR = "/Users/musk123/Downloads/minimax工作文件夹"
R138_WORK = "/Users/musk123/Downloads/minimax工作文件夹/图文工作/character_animation_R138"

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R147_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r147.zip" % time.strftime("%Y%m%d_%H%M%S"))

# --- 轻量审查包内容 ---
REVIEW_FILES = [
    # (源路径, 包内路径)
    ("src/main.js", "candidate_b_c2/src/main.js"),
    ("src/renderer.js", "candidate_b_c2/src/renderer.js"),
    ("src/behavior_engine.js", "candidate_b_c2/src/behavior_engine.js"),
    ("src/sprite_layout.js", "candidate_b_c2/src/sprite_layout.js"),
    ("src/idle_director.js", "candidate_b_c2/src/idle_director.js"),
    ("src/click_policy.js", "candidate_b_c2/src/click_policy.js"),
    ("src/anim_clock.js", "candidate_b_c2/src/anim_clock.js"),
    ("src/asset_gate.js", "candidate_b_c2/src/asset_gate.js"),
    ("src/renderer.html", "candidate_b_c2/src/renderer.html"),
    ("package.json", "candidate_b_c2/package.json"),
    ("assets/character_R141_manifest.json", "candidate_b_c2/assets/character_R141_manifest.json"),
    ("tests/r141_behavior_engine.test.js", "candidate_b_c2/tests/r141_behavior_engine.test.js"),
    ("tests/r144_layout.test.js", "candidate_b_c2/tests/r144_layout.test.js"),
    ("tests/r144_oneshot.test.js", "candidate_b_c2/tests/r144_oneshot.test.js"),
    ("tests/r144_assets_gate.test.js", "candidate_b_c2/tests/r144_assets_gate.test.js"),
    ("tests/r147_layout_pixi_parity.test.js", "candidate_b_c2/tests/r147_layout_pixi_parity.test.js"),
    ("tests/r147_interaction.test.js", "candidate_b_c2/tests/r147_interaction.test.js"),
    ("tests/lib/png_reader.js", "candidate_b_c2/tests/lib/png_reader.js"),
    ("tools/r144_drag_core_diff.py", "candidate_b_c2/tools/r144_drag_core_diff.py"),
    ("tools/r144_layout_probe.js", "candidate_b_c2/tools/r144_layout_probe.js"),
    ("08_R144_layout_builder.py", "candidate_b_c2/08_R144_layout_builder.py"),
    ("10_R147_gait_preview.py", "candidate_b_c2/10_R147_gait_preview.py"),
    ("11_R147_manifest_update.py", "candidate_b_c2/11_R147_manifest_update.py"),
    ("12_R147_gait_analysis.py", "candidate_b_c2/12_R147_gait_analysis.py"),
    ("13_R147_step_direction.py", "candidate_b_c2/13_R147_step_direction.py"),
    ("14_R147_preview_gif.py", "candidate_b_c2/14_R147_preview_gif.py"),
    ("15_R147_preview_verify.py", "candidate_b_c2/15_R147_preview_verify.py"),
    ("R141_e2e_test.sh", "candidate_b_c2/R141_e2e_test.sh"),
    ("R144_e2e_test.sh", "candidate_b_c2/R144_e2e_test.sh"),
    ("R147_e2e_test.sh", "candidate_b_c2/R147_e2e_test.sh"),
    ("run.sh", "candidate_b_c2/run.sh"),
    ("C2_Mac人工验收.command", "candidate_b_c2/C2_Mac人工验收.command"),
    ("evidence_r147_e2e.json", "candidate_b_c2/evidence_r147_e2e.json"),
    ("evidence_r144/character_R138_frames_SHA256.txt", "candidate_b_c2/evidence_r147/character_R138_frames_SHA256.txt"),
]
PREVIEW_FILES = [
    ("evidence_r147_preview/R147_walk_left.gif", "preview/R147_walk_left.gif"),
    ("evidence_r147_preview/R147_walk_right.gif", "preview/R147_walk_right.gif"),
    ("evidence_r147_preview/R147_idle.gif", "preview/R147_idle.gif"),
    ("evidence_r147_preview/R147_click.gif", "preview/R147_click.gif"),
    ("evidence_r147_preview/R147_wake.gif", "preview/R147_wake.gif"),
    ("evidence_r147_preview/R147_preview_summary.png", "preview/R147_preview_summary.png"),
    ("evidence_r147_preview/preview_meta.json", "evidence/preview_meta.json"),
    ("evidence_r147_preview/preview_verify.json", "evidence/preview_verify.json"),
]
DOC_FILES = [
    ("docs/R147_QA_REPORT.md", "docs/R147_QA_REPORT.md"),
    ("docs/R147_DELIVERY_INDEX.md", "docs/R147_DELIVERY_INDEX.md"),
]

README = """R147 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: %s
提交:     %s

本包内容
--------
candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
preview/          ★ 真实运行预览 (可直接观看)
                   - R147_walk_left.gif   窗口真实向左移动 + walk_left + 向左倾斜
                   - R147_walk_right.gif  窗口真实向右移动 + walk_right + 向右倾斜
                   - R147_idle.gif        自然待机 (稳定站姿 + 自然眨眼, 无胸腔膨胀)
                   - R147_click.gif       鼠标单击反馈 (眨眼 + 轻微弹跳)
                   - R147_wake.gif        睡眠点击唤醒 (sleep_loop → wake_up → idle)
                   - R147_preview_summary.png  五场景并排汇总
evidence/         e2e 机器报告 + 真实采集帧的量化结果
docs/             R147 质量报告 + 交付索引

预览素材的来源 (诚实说明)
------------------------
GIF 中的角色像素是**真实 Electron 运行时 capturePage 截图**, 未做任何重绘。
行走场景里角色在画布上的横向位置 = 该帧窗口的**真实** x 位移 (见 preview_meta.json),
因此"往哪边走"是运行时真实发生的事, 不是手工摆位。

复审要点
--------
1. node candidates/candidate_b_c2/tests/r147_interaction.test.js   (23 项交互与动画质量)
2. node candidates/candidate_b_c2/tests/r147_layout_pixi_parity.test.js  (与真实 PixiJS 矩阵一致)
3. bash candidates/candidate_b_c2/R147_e2e_test.sh                (真实 Electron, 18 项)
4. python3 candidates/candidate_b_c2/tools/r144_drag_core_diff.py (R113 拖拽核心逐字未改)

素材本体 (23 帧 PNG) 不在本包内, 位于产品目录 assets/character_R138/ 与 R138 交付目录,
SHA256 清单见 evidence/character_R138_frames_SHA256.txt (本包内)。
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
        zf.writestr("evidence/README_R147_review.txt", README % (time.strftime("%Y-%m-%d %H:%M:%S"), commit))
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
        for rel, arc in DOC_FILES + [("docs/R144_QA_REPORT.md", "docs/R144_QA_REPORT.md"),
                                     ("docs/R144_DELIVERY_INDEX.md", "docs/R144_DELIVERY_INDEX.md")]:
            if add(zf, os.path.join(ROOT, rel), arc):
                n += 1
    return n


def main():
    commit = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print("R147 打包:")
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

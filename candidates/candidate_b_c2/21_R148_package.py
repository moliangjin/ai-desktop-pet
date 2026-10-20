#!/usr/bin/env python3
"""R148 交付打包器 — 生成轻量审查包 + 完整备份 + SHA256。

两份包:
  1) 轻量审查包 (供独立复审):
     源码 / 测试 / 脚本 / manifest / 证据 JSON / **可观看的运行预览 GIF** /
     **R148 新增的 4 张派生镜像帧** (含在包内, 便于复审者自行验证"整体镜像"性质) /
     报告与索引
     —— 不含 R138 的 23 张原始 PNG (素材本体可从 R138 交付包取, 另有 SHA256 清单核对)
  2) 完整备份: 候选实现的全部内容 (含 R138 23 帧 + 派生 4 帧) + 本轮文档

SHA256 写在 ZIP **旁边的独立 .sha256 文件** (不内嵌), 避免"改索引就改哈希"的循环自引用。

用法: python3 21_R148_package.py <commit>
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

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R148_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r148.zip" % time.strftime("%Y%m%d_%H%M%S"))

REVIEW_FILES = [
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
    ("tests/r148_walk_direction.test.js", "candidate_b_c2/tests/r148_walk_direction.test.js"),
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
    ("17_R148_mirror_derive.py", "candidate_b_c2/17_R148_mirror_derive.py"),
    ("18_R148_direction_verify.py", "candidate_b_c2/18_R148_direction_verify.py"),
    ("19_R148_manifest_update.py", "candidate_b_c2/19_R148_manifest_update.py"),
    ("20_R148_preview_gif.py", "candidate_b_c2/20_R148_preview_gif.py"),
    ("R141_e2e_test.sh", "candidate_b_c2/R141_e2e_test.sh"),
    ("R144_e2e_test.sh", "candidate_b_c2/R144_e2e_test.sh"),
    ("R147_e2e_test.sh", "candidate_b_c2/R147_e2e_test.sh"),
    ("run.sh", "candidate_b_c2/run.sh"),
    ("C2_Mac人工验收.command", "candidate_b_c2/C2_Mac人工验收.command"),
    ("evidence_r147_e2e.json", "candidate_b_c2/evidence_r147_e2e.json"),
    ("evidence_r144/character_R138_frames_SHA256.txt", "candidate_b_c2/evidence_r147/character_R138_frames_SHA256.txt"),
    # ---- R148 新增 ----
    ("evidence_r148_direction.json", "candidate_b_c2/evidence_r148_direction.json"),
    ("assets/character_R138_derived/r138_source_checksums.json",
     "candidate_b_c2/assets/character_R138_derived/r138_source_checksums.json"),
    ("assets/character_R138_derived/walk_right_mirror/derive_report.json",
     "candidate_b_c2/assets/character_R138_derived/walk_right_mirror/derive_report.json"),
    # R148 派生镜像帧 (含在包内, 便于复审者自行验证"整体水平镜像")
    ("assets/character_R138_derived/walk_right_mirror/walk_right_m_00.png",
     "candidate_b_c2/assets/character_R138_derived/walk_right_mirror/walk_right_m_00.png"),
    ("assets/character_R138_derived/walk_right_mirror/walk_right_m_01.png",
     "candidate_b_c2/assets/character_R138_derived/walk_right_mirror/walk_right_m_01.png"),
    ("assets/character_R138_derived/walk_right_mirror/walk_right_m_02.png",
     "candidate_b_c2/assets/character_R138_derived/walk_right_mirror/walk_right_m_02.png"),
    ("assets/character_R138_derived/walk_right_mirror/walk_right_m_03.png",
     "candidate_b_c2/assets/character_R138_derived/walk_right_mirror/walk_right_m_03.png"),
]
PREVIEW_FILES = [
    ("evidence_r148_preview/R148_walk_left.gif", "preview/R148_walk_left.gif"),
    ("evidence_r148_preview/R148_walk_right.gif", "preview/R148_walk_right.gif"),
    ("evidence_r148_preview/R148_edge_turn.gif", "preview/R148_edge_turn.gif"),
    ("evidence_r148_preview/R148_edge_turn_trail.png", "preview/R148_edge_turn_trail.png"),
    ("evidence_r148_preview/R148_idle.gif", "preview/R148_idle.gif"),
    ("evidence_r148_preview/R148_click.gif", "preview/R148_click.gif"),
    ("evidence_r148_preview/R148_wake.gif", "preview/R148_wake.gif"),
    ("evidence_r148_preview/R148_preview_summary.png", "preview/R148_preview_summary.png"),
    ("evidence_r148_preview/preview_meta.json", "evidence/preview_meta.json"),
]
DOC_FILES = [
    ("docs/R148_QA_REPORT.md", "docs/R148_QA_REPORT.md"),
    ("docs/R148_DELIVERY_INDEX.md", "docs/R148_DELIVERY_INDEX.md"),
]

README = """R148 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: %s
提交:     %s

本轮主题: walk_right 倒退步态修复 (R147 遗留)

candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
                  + assets/character_R138_derived/  ★ R148 新增: 4 张派生镜像帧
                     (由 walk_left 4 帧整体水平镜像 + 胸口徽章归位生成)
preview/          ★ 真实运行预览 (可直接观看)
                   - R148_walk_left.gif     窗口真实向左移动 (4.00 个完整步态循环)
                   - R148_walk_right.gif    窗口真实向右移动 (4.00 个完整步态循环, R148 修复后)
                   - R148_edge_turn.gif     撞边转向后的连续动作 (90 帧, 转向在第 45 帧)
                   - R148_edge_turn_trail.png  撞边场景窗口真实 x 轨迹
                   - R148_idle.gif          自然待机 (稳定站姿 + 自然眨眼)
                   - R148_click.gif         鼠标单击反馈
                   - R148_wake.gif          睡眠点击唤醒
                   - R148_preview_summary.png  六场景并排汇总
evidence/         方向几何测量结果 (evidence_r148_direction.json) + 采集元数据
docs/             R148 质量报告 + 交付索引

预览素材的来源 (诚实说明)
------------------------
GIF 中的角色像素是**真实 Electron 运行时 capturePage 截图**, 未做任何重绘。
行走场景里角色在画布上的横向位置 = 该帧窗口的**真实** x 位移 (见 evidence/preview_meta.json),
因此"往哪边走"是运行时真实发生的事, 不是手工摆位。

复审要点
--------
1. node candidates/candidate_b_c2/tests/r148_walk_direction.test.js   (8 项: 镜像严格性/徽章/资产字节)
2. python3 candidates/candidate_b_c2/18_R148_direction_verify.py      (鞋尖几何客观测量)
3. python3 candidates/candidate_b_c2/17_R148_mirror_derive.py        (重放派生, 可复算)
4. bash candidates/candidate_b_c2/R147_e2e_test.sh                  (真实 Electron, 18 项)
5. python3 candidates/candidate_b_c2/tools/r144_drag_core_diff.py   (R113 拖拽核心逐字未改)

方向如何被判定 (不看坐标符号/文件名/动画名)
------------------------------------------
"鞋尖几何": 分离靴子像素 -> 取落地靴 (靴底 y 最大) -> 鞋尖朝向 = 靴体重心相对靴筒口的偏移方向。
  walk_left      = [-1,-1,-1]  落脚侧全左   PASS
  walk_right 旧  = [-1,-1,-1]  落脚侧全左   FAIL  (客观复现用户反馈的倒退)
  walk_right R148= [+1,+1,+1]  落脚侧全右   PASS

素材本体 (R138 原始 23 帧 PNG) 不在本包内, 位于产品目录 assets/character_R138/ 与 R138 交付目录,
SHA256 清单见 evidence/character_R138_frames_SHA256.txt 与
candidate_b_c2/assets/character_R138_derived/r138_source_checksums.json。
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
        zf.writestr("evidence/README_R148_review.txt", README % (time.strftime("%Y-%m-%d %H:%M:%S"), commit))
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
        for rel, arc in DOC_FILES + [("docs/R147_QA_REPORT.md", "docs/R147_QA_REPORT.md"),
                                     ("docs/R147_DELIVERY_INDEX.md", "docs/R147_DELIVERY_INDEX.md")]:
            if add(zf, os.path.join(ROOT, rel), arc):
                n += 1
    return n


def main():
    commit = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    print("R148 打包:")
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

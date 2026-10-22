#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R173 交付打包器 —— 轻量审查包 + 完整备份 + SHA256。

与 R172 (94_) 的差别:
  · 新增 R173 脚本 (95 烘焙 / 96 manifest 更新 / 97 客观判据 / 98 证据产出 / 99 本打包器)
  · 新增 R173 素材: assets/character_R173/ 下的 work_1.png / work_2.png
    (3/4 侧身坐姿 + 斜向透视桌面 + 斜置显示器 + 双手压在键盘之上, 全部内嵌)
  · 新增 R173 证据: 真实 Electron 重采集元数据 + 客观判据 26/26 + 打字 GIF
    + 前后对比图 + 透视示意图
  · R172 的资产/脚本/证据一并入包 (历史成果可复审)

SHA256 写在 ZIP **旁边的独立 .sha256 文件** (不内嵌), 避免"改索引就改哈希"的循环自引用。

用法: python3 99_R173_package.py <commit>
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

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R173_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r173.zip" % time.strftime("%Y%m%d_%H%M%S"))

R173_ASSETS = ["work_1.png", "work_2.png", "bake_report.json"]

# 复用 R172 打包器的清单 (源文件、测试、工具、前序脚本、既有证据)
_spec_path = os.path.join(CAND, '94_R172_package.py')
with open(_spec_path, encoding='utf-8') as _f:
    _src = _f.read()
_ns = {'__name__': '_r172_pkg_base', '__file__': _spec_path}
exec(compile(_src, _spec_path, 'exec'), _ns)

REVIEW_FILES = list(_ns['REVIEW_FILES'])
PREVIEW_FILES = list(_ns['PREVIEW_FILES'])
DOC_FILES = list(_ns['DOC_FILES'])

# ---- R173 新增 ----
REVIEW_FILES += [
    ("95_R173_office_bake.py", "candidate_b_c2/95_R173_office_bake.py"),
    ("96_R173_manifest_update.py", "candidate_b_c2/96_R173_manifest_update.py"),
    ("97_R173_scene_verify.py", "candidate_b_c2/97_R173_scene_verify.py"),
    ("98_R173_evidence.py", "candidate_b_c2/98_R173_evidence.py"),
    ("99_R173_package.py", "candidate_b_c2/99_R173_package.py"),
    ("evidence_r173_preview/preview_meta.json",
     "candidate_b_c2/evidence_r173_preview/preview_meta.json"),
    ("evidence_r173_scene_verify.json",
     "candidate_b_c2/evidence_r173_scene_verify.json"),
]
for _f in R173_ASSETS:
    REVIEW_FILES.append((f"assets/character_R173/{_f}",
                         f"candidate_b_c2/assets/character_R173/{_f}"))

PREVIEW_FILES += [
    ("evidence_r173_gifs/R173_scene_work.gif", "preview/R173_scene_work.gif"),
    ("evidence_r173_gifs/R173_work_overview.png", "preview/R173_work_overview.png"),
]
for _f in ["办公场景_R172版_vs_R173_200x240.png",
           "办公场景_R172版_vs_R173_256x256.png",
           "办公场景_显示器朝向_放大前后对比.png",
           "办公场景_双手与键盘_放大前后对比.png",
           "办公场景_透视示意图_显示器朝向与视线.png",
           "办公场景_完整坐姿_200x240.png",
           "办公场景_完整坐姿_256x256.png"]:
    PREVIEW_FILES.append((f"evidence_r173_compare/{_f}", "preview/场景对比_R173/" + _f))

DOC_FILES += [
    ("docs/R173_QA_REPORT.md", "docs/R173_QA_REPORT.md"),
    ("docs/R173_DELIVERY_INDEX.md", "docs/R173_DELIVERY_INDEX.md"),
]

README = """R173 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: __GENERATED_AT__
提交:     __COMMIT__

本轮主题: 办公场景透视与手部遮挡最终整改 —— 用户 R173 真机截图再次确认 R172 的
          办公场景视觉 FAIL:
          ① 显示器**正面朝向观众**, 人物坐在显示器背面 (几何自相矛盾);
          ② 双手被键盘和桌面遮挡, 手掌看不见, 手臂→手腕→手指衔接不成立。

一、根因 (R172 的构图前提错了, 不是"再平移几像素"能解决的)
----------------------------------------------------------
R172 自己就把这条写进了 honest_limits ("正面坐姿 + 正对观众的显示器只能这样表达
看得到屏幕内容"), 却仍然当 PASS 交付。根因是**底图选了正面坐姿**:
正面角色 + 可见屏幕在几何上不可能自洽 —— 屏幕朝角色 ⇒ 角色背着屏幕;
屏幕朝观众 ⇒ 观众看到的是屏幕正面、角色坐在屏幕背面。

R173 的改法 (换底图 + 重建透视, 不是平移):
  1. **底图换成真 3/4 坐姿** sleep_enter_01_sit (膝盖与视线都朝画面左);
     它是现有素材里**唯一**的侧向坐姿 (吃水果/睡眠/行走都是正面或侧面站姿)。
  2. **显示器移到画面左侧更深处**, 屏面正面朝右(= 面向角色)、带一点朝观众的分量;
     远侧边明显更矮 ⇒ 上下边在近侧发散 ⇒ 观众从侧面看到被透视压缩的屏内容。
  3. **桌面改成斜向透视台面** (左端更远更高), 角色坐在桌子右端:
     角色 → 键盘 → 显示器 全部在同一条朝左的视线链上, 共用同一套透视。
  4. **手部图层**: 原手保留在身体帧 → 桌面盖住原位 → 手的像素**复制一份压在键盘之上**
     ⇒ 手掌不被键盘整体遮住, 指尖落在键区, 衔接全部来自原画 (没有假接缝)。
  5. 椅子/桌面/键盘/显示器/双手全部**内嵌进角色帧** (运行时道具按 action 整组挂载,
     做不到逐帧换层), 故 work 场景的 back/front 道具列表为空。

二、客观判据 (97_R173_scene_verify.py, 26/26 PASS)
---------------------------------------------------
  A1 屏幕远/近边高比 ≥1.35            (实测 1.804; R172 正面屏同口径 1.095 ⇒ FAIL)
  A2 上下边在近侧发散 (收敛点在远侧)
  A3 屏幕中心在角色面部左侧 ≥40px     (实测 278 vs 521)
  A4 头部非正面 (虹膜左右面积比 ≥1.10) (实测 1.197; 正面底图同口径 0.840)
  A5 屏内蓝白界面内容 ≥500px          (实测 27654)
  B1 手部皮肤落在键盘四边形内 ≥400px  (实测 2038)
  B2 两只手都在键盘四边形内且各 ≥180px (实测 946 / 1092)
  B3 键盘区内最终帧是肤色 (手未被键盘遮住)
  B4 桌沿/桌腿与手部皮肤相交 = 0px
  B5 手腕处袖口与皮肤相邻 (无断裂)     (实测 gap=0 / gap=0)
  C1/C2/C3/C4  200×240 与 256×256 下 人物/腿脚/双手/屏幕内容 同时可见
  D1 两帧手部位移 ≥3 纹理 px          (实测 9.09)
  D2 两帧头部位移 ≥5 纹理 px          (实测 6.56)
  E1/E2 全局缩放逐位不变 (200×240 = 0.19631901840490798 / 256×256 = 0.25357873210633947)
  F1~F4 既有成果 (吃水果/睡眠/R172 素材) 一字未动

三、回归 (全部实跑)
--------------------
  node 单元测试        12 个文件 / 168 断言 全过
  R147/R153/R156 e2e  PASS=60 FAIL=0 NOT_VERIFIED=0 (真实 Electron)
  71_R167 场景判据     R167 段 15/15 PASS (R162 对照段的失败是历史对照, 预期)
  46_R165 手臂判据     18 帧 / 18 PASS
  83_R170 场景判据     W3 (work 帧不得改动) 预期 FAIL —— R173 任务书要求改 work 帧
  97_R173 场景判据     26/26 PASS

四、如实登记的已知限制 (见 docs/R173_QA_REPORT.md)
-------------------------------------------------------
  · 屏幕内容在 200×240 下只有约 34×48 px, 只能读出"有蓝白界面内容", 读不出具体文字
    —— 这是"从侧面斜看"的必然结果 (透视压缩); 要看清内容就得让屏幕正对观众,
    而那正是 R172 被否掉的构图。
  · 桌偏高: 桌面远沿压在腕点下方 (手必须落在桌面上), 读起来像高脚桌 + 高凳。
  · 打字动作是手的整体位移 (±6 纹理 px) + 抬头/低头, 不是逐键动画。
  · 膝/大腿被桌面遮住, 小腿与靴子完整可见。
  · MAC_REAL_GUI_ACCEPTANCE = PENDING (未经用户真机肉眼确认)。

包内容
------
candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
                  + assets/character_R158/  6 个点击动作 × 3 帧 (未改动)
                  + assets/character_R156/  R170 吃水果帧 + 场景道具 (未改动)
                  + assets/character_R172/  R172 办公素材 (未改动, 可复审)
                  + assets/character_R173/  ★ R173 办公新素材
                    · work_1.png / work_2.png  ★新 (3/4 侧身 + 斜向桌面 + 斜置显示器 +
                      双手压在键盘之上, 全部内嵌)
preview/           ★ R173 办公打字 GIF (真实 Electron 采集) + 总览图
                  + 前后对比图 + 透视示意图
evidence/          真实 Electron 重采集元数据 + R173 客观判据报告 + e2e 报告
docs/             R165 / R167 / R170 / R172 / R173 质量报告 + 交付索引

复审要点
--------
1. python3 candidates/candidate_b_c2/97_R173_scene_verify.py    (26 项客观判据)
2. python3 candidates/candidate_b_c2/98_R173_evidence.py        (重新产出全部对比图)
3. python3 candidates/candidate_b_c2/45_R165_scene_preview.py --scene work --size 200x240
4. node  candidates/candidate_b_c2/tests/r156_click_props_work.test.js
5. node  candidates/candidate_b_c2/tests/r170_eat_fruit_work.test.js
6. bash   candidates/candidate_b_c2/R147_e2e_test.sh                (真实 Electron 全量回归)
7. 验收入口: candidates/candidate_b_c2/C2_Mac人工验收.command work
8. 重放烘焙: 95_R173_office_bake.py → 96_R173_manifest_update.py → 97_R173_scene_verify.py

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
        zf.writestr("evidence/README_R173_review.txt", readme)
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
    print("R173 打包:")
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R172 交付打包器 —— 轻量审查包 + 完整备份 + SHA256。

与 R170 (85_) 的差别:
  · 新增 R172 脚本 (89 spike / 90 办公素材烘焙 / 91 manifest 更新 /
    92 客观判据 / 93 证据产出 / 94 本打包器)
  · 新增 R172 素材: assets/character_R172/ 下的
    work_1.png / work_2.png (完整坐姿办公帧, 桌面/键盘/双手内嵌)
    prop_office_chair.png (办公转椅) / prop_office_monitor.png (3/4 显示器)
  · 新增 R172 证据: 真实 Electron 重采集元数据 + 客观判据 + 办公 GIF + 前后对比图
  · 45_R165_scene_preview.py 本轮修正了垂直落点 (与运行时对齐), 故一并入包

SHA256 写在 ZIP **旁边的独立 .sha256 文件** (不内嵌), 避免"改索引就改哈希"的循环自引用。

用法: python3 94_R172_package.py <commit>
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

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R172_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r172.zip" % time.strftime("%Y%m%d_%H%M%S"))

R172_ASSETS = ["work_1.png", "work_2.png",
               "prop_office_chair.png", "prop_office_monitor.png",
               "bake_report.json"]

# 复用 R170 打包器的清单 (源文件、测试、工具、前序脚本、既有证据)
_spec_path = os.path.join(CAND, '85_R170_package.py')
with open(_spec_path, encoding='utf-8') as _f:
    _src = _f.read()
_ns = {'__name__': '_r170_pkg_base', '__file__': _spec_path}
exec(compile(_src, _spec_path, 'exec'), _ns)

REVIEW_FILES = list(_ns['REVIEW_FILES'])
PREVIEW_FILES = list(_ns['PREVIEW_FILES'])
DOC_FILES = list(_ns['DOC_FILES'])

# ---- R172 新增 ----
REVIEW_FILES += [
    # R172 脚本
    ("89_R172_office_spike.py", "candidate_b_c2/89_R172_office_spike.py"),
    ("90_R172_office_bake.py", "candidate_b_c2/90_R172_office_bake.py"),
    ("91_R172_manifest_update.py", "candidate_b_c2/91_R172_manifest_update.py"),
    ("92_R172_scene_verify.py", "candidate_b_c2/92_R172_scene_verify.py"),
    ("93_R172_evidence.py", "candidate_b_c2/93_R172_evidence.py"),
    ("94_R172_package.py", "candidate_b_c2/94_R172_package.py"),
    # R172 证据
    ("evidence_r172_preview/preview_meta.json",
     "candidate_b_c2/evidence_r172_preview/preview_meta.json"),
    ("evidence_r172_scene_verify.json",
     "candidate_b_c2/evidence_r172_scene_verify.json"),
    ("evidence_r147_e2e.json", "candidate_b_c2/evidence_r147_e2e.json"),
]
for _f in R172_ASSETS:
    REVIEW_FILES.append((f"assets/character_R172/{_f}",
                         f"candidate_b_c2/assets/character_R172/{_f}"))

PREVIEW_FILES += [
    ("evidence_r172_gifs/R172_scene_work.gif", "preview/R172_scene_work.gif"),
    ("evidence_r172_gifs/R172_work_overview.png", "preview/R172_work_overview.png"),
]
for _f in ["办公场景_R170版_vs_R172_200x240.png",
           "办公场景_R170版_vs_R172_256x256.png",
           "办公场景_腿脚与屏幕_放大前后对比.png",
           "办公场景_桌面双手_放大前后对比.png",
           "办公场景_完整坐姿_200x240.png",
           "办公场景_完整坐姿_256x256.png",
           "办公场景_真机帧_vs_脚本预览.png"]:
    PREVIEW_FILES.append((f"evidence_r172_compare/{_f}", "preview/场景对比/" + _f))

DOC_FILES += [
    ("docs/R172_QA_REPORT.md", "docs/R172_QA_REPORT.md"),
    ("docs/R172_DELIVERY_INDEX.md", "docs/R172_DELIVERY_INDEX.md"),
]

README = """R172 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: __GENERATED_AT__
提交:     __COMMIT__

本轮主题: 办公场景构图重做 —— 用户 R172 真机截图确认 R170 的办公场景视觉 FAIL:
          ① 为了显示桌面, 直接裁掉了人物下半身, 双腿消失;
          ② 电脑主要显示背板, 用户看不到任何屏幕内容。

一、根因 (不是"少画了腿", 是图层归属错了)
--------------------------------------------
R167 的设计前提是: "台面在 back 层 ⇒ 正面坐姿的躯干/大腿整片挡住台面
⇒ 只能把下半身剪掉 (cut_lower_body, WORK_CUT_Y=592)"。
所以 R170 的办公场景里, 用户的两个抱怨都是这条设计前提的直接后果:
下半身被剪 + 电脑只能画成"背朝观众的笔记本盖板"。

R172 的改法 (换底图 + 换图层归属, 不再剪身体):
  1. 底图: sleep_enter_01_sit (跪坐, 膝盖高抬) → wake_up_01_sit_up
     (**双腿下垂、靴子踩地**), 整帧下移 76px 使脚底对齐地面行 1001;
  2. 桌面 / 键盘 / 双手 **画进角色帧内部** (PNG 内可控 z 序:
     身体 → 桌面 → 键盘 → 手 → 桌沿桌腿)
     ⇒ 桌面只遮住大腿 (局部遮挡腿, 不是删除下半身),
       小腿与靴子在桌下完整可见;
  3. 电脑改为 **3/4 透视的显示器正面**, 屏内画蓝白科技界面 (标题栏 + 侧栏 +
     代码行 + 状态块) ⇒ 用户真的看得到屏幕内容;
  4. 场景 back 层 = 办公转椅, front 层 = 显示器;
  5. 顺手修掉 45_R165_scene_preview.py 的**垂直落点 bug**:
     旧实现把"地面行"当成"纹理底行 1024", 整幅图比运行时**上移 15.58px**,
     预览图与真实 Electron 画面对不齐 (已用真实采集帧逐像素比对确认并修正)。

二、客观判据 (92_R172_scene_verify.py, 13/13 PASS)
---------------------------------------------------
  A1 桌下青色长袜像素 ≥ 150            (实测 775 / 1266)
  A2 桌下靴子像素 ≥ 120                (实测 1032 / 1684)
  A3 靴底最低行 ≥ 地面线 - 3px         (实测 234, 地面线 236)
  A4 屏幕亮内容 ≥ 260px 且高频细节 ≥ 12 (实测 728px / 23.56; 修复前 198px / 5.53)
  A5 双手皮肤 ≥ 700px、单只 ≥ 300px、≥0.50 落在键盘投影区
                                         (实测 1148px / 376px / 0.664)
  A6 手部肤色连通块 == 2               (实测 2)
  A7 两帧手部质心位移 ≥ 4 纹理 px       (实测 6.96)
  A8 白大褂 ≥ 0.30 且银白发 ≥ 0.08      (实测 0.4203 / 0.3485)
  A9 前景道具 ∩ 面部皮肤 = 0 px         (实测 0)
  B1 200×240 与 256×256 下 人物/腿脚/双手/屏幕 **同时**可见 (两档均达标)
  C1 角色帧桌沿以下腿脚像素: 修复后 70580 / 修复前 0 (绝对值对比)
  C2 屏幕高频细节: 修复后 23.56 / 修复前 5.53

三、回归 (全部实跑)
--------------------
  node 单元测试        12 个文件 / 167 断言 全过
  R147/R153/R156 e2e  PASS=60 FAIL=0 NOT_VERIFIED=0 (真实 Electron)
  71_R167 场景判据     R167 段 15/15 PASS (R162 对照段的失败是历史对照, 预期)
  46_R165 手臂判据     18 帧 / 18 PASS
  83_R170 场景判据     12/13 PASS (唯一 FAIL 是 W3 "work 帧不得改动",
                       而 R172 任务书明确要求改 work 帧 ⇒ 预期失败)
  92_R172 场景判据     13/13 PASS

四、如实登记的已知限制 (见 docs/R172_QA_REPORT.md L1~L7)
-------------------------------------------------------
  L1 双手没有真正收到键盘中央 (坐姿底图手腕间距 280px, 手臂长度不够)
  L2 袖口被桌面远沿遮住 (200×240 下只剩 2~3 屏幕 px)
  L3 显示器是"正面 3/4 的屏幕", 不是物理正确的背面同侧视角
  L4 打字动作是手部整体位移 + 抬头/低头, 不是逐键动画
  L5 45_ 预览器修正后, 旧轮次的**预览图**证据是上移 15.58px 的 (历史遗留),
     真实 Electron 采集帧一直是对的
  L6 MAC_REAL_GUI_ACCEPTANCE = PENDING (未经用户真机肉眼确认)
  L7 R170 吃水果场景的判据脚本 (83_ 的 W3) 预期 FAIL (work 帧按任务书已改)

包内容
------
candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
                  + assets/character_R158/  6 个点击动作 × 3 帧 (未改动)
                  + assets/character_R156/  R170 吃水果帧 + 场景道具 (未改动)
                  + assets/character_R172/  ★ R172 办公新素材
                    · work_1.png / work_2.png  ★新 (完整坐姿 + 桌面 + 键盘 + 双手)
                    · prop_office_chair.png   ★新 (办公转椅, back 层)
                    · prop_office_monitor.png ★新 (3/4 显示器, 屏内可见界面)
preview/           ★ 办公场景 GIF (真实 Electron 采集) + 总览图 + 前后对比图
evidence/          真实 Electron 重采集元数据 + R172 客观判据报告 + e2e 报告
docs/             R165 / R167 / R170 / R172 质量报告 + 交付索引

复审要点
--------
1. python3 candidates/candidate_b_c2/92_R172_scene_verify.py    (13 项客观判据)
2. python3 candidates/candidate_b_c2/93_R172_evidence.py        (重新产出全部对比图)
3. python3 candidates/candidate_b_c2/45_R165_scene_preview.py --scene work --size 200x240
4. node  candidates/candidate_b_c2/tests/r156_click_props_work.test.js
5. node  candidates/candidate_b_c2/tests/r170_eat_fruit_work.test.js
6. bash   candidates/candidate_b_c2/R147_e2e_test.sh                (真实 Electron 全量回归)
7. 验收入口: candidates/candidate_b_c2/C2_Mac人工验收.command work
8. 重放烘焙: 90_R172_office_bake.py → 91_R172_manifest_update.py → 92_R172_scene_verify.py

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
        zf.writestr("evidence/README_R172_review.txt", readme)
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
    print("R172 打包:")
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

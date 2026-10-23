#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R179 交付打包器 —— 轻量审查包 + 完整备份 + SHA256。

与 R177 (101_) 的差别:
  · 新增 R179 修复: 验收入口绝对路径 + 启动判据 / 精力增量结算 / 保存失败如实反馈
    + 开机自启真实结果回传
  · 新增 R179 验收证据: evidence_r177_runtime/ 里多出 run_F_acceptance.log
    (验收入口实跑输出) 与 run_G.log (故障注入实跑输出)
  · 新增 R179 文档: docs/R179_QA_REPORT.md / docs/R179_DELIVERY_INDEX.md

SHA256 写在 ZIP **旁边的独立 .sha256 文件** (不内嵌), 避免"改索引就改哈希"的循环自引用。

用法: python3 102_R179_package.py <commit>
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

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R179_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r179.zip" % time.strftime("%Y%m%d_%H%M%S"))

# 复用 R177 打包器的清单
_spec_path = os.path.join(CAND, '101_R177_package.py')
with open(_spec_path, encoding='utf-8') as _f:
    _src = _f.read()
_ns = {'__name__': '_r177_pkg_base', '__file__': _spec_path}
exec(compile(_src, _spec_path, 'exec'), _ns)

REVIEW_FILES = list(_ns['REVIEW_FILES'])
PREVIEW_FILES = list(_ns['PREVIEW_FILES'])
DOC_FILES = list(_ns['DOC_FILES'])
ROOT_REVIEW_FILES = list(_ns['ROOT_REVIEW_FILES'])

# ---- R179 新增 ----
REVIEW_FILES += [
    ("102_R179_package.py", "candidate_b_c2/102_R179_package.py"),
    # R179 新增的运行时证据 (验收入口实跑 + 故障注入实跑)
    ("evidence_r177_runtime/run_F_acceptance.log",
     "candidate_b_c2/evidence_r177_runtime/run_F_acceptance.log"),
    ("evidence_r177_runtime/run_G.log", "candidate_b_c2/evidence_r177_runtime/run_G.log"),
]

DOC_FILES += [
    ("docs/R179_QA_REPORT.md", "docs/R179_QA_REPORT.md"),
    ("docs/R179_DELIVERY_INDEX.md", "docs/R179_DELIVERY_INDEX.md"),
]

README = """R179 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: __GENERATED_AT__
提交:     __COMMIT__

本轮主题: R177 独立审查发现的三个实际问题 —— 修复 Mac 一键验收入口 / 心情精力计算 /
          设置保存失败的反馈。本轮**零联网、零 AI 调用、零充值 i2i、零新角色素材**,
          R177 已完成的全部功能与素材一字未动。

一、三个问题的根因与修法
----------------------------------------------------------
  1) Mac 一键验收入口起不来
     根因: 脚本 `cd` 到 one_click_test/ 后, 却用相对路径 `src/main.js` 启动 Electron
           —— 该路径不存在 (真实位置 candidates/candidate_b_c2/src/main.js)。
     修法: 统一绝对路径 $CAND/src/main.js + 启动前存在性自检(FATAL 明确报错)
           + 从真实运行日志里 grep `R144 ASSETS_READY` 作为"启动判据"
           + 新增 --smoke(只跑 8 秒) / --skip-auto 两种自动化模式。
     实测: 从 one_click_test/ 实跑 ⇒ 资源 23/23 就绪、行为引擎启动、
           自动进入办公场景、退出码 0。

  2) 心情精力被重复扣除
     根因: update() 用"累计清醒小时数"每次都整个再扣一遍, 而应用每 30 秒刷新一次。
     修法: 改成按**时间增量**扣 (新增 lastEnergyAt 状态, 随持久化一起保存/恢复);
           睡眠期间不扣; 睡醒时对齐结算基准; 单次扣除上限 6 小时(防休眠/时钟回拨)。
     实测: 已清醒 1 小时 + 每 30s 刷新 10 分钟 ⇒ 修复前第 18 次归零,
           修复后仍是 0.9417 (理论 0.941667 完全吻合); 重启恢复后接着按增量扣。

  3) 设置保存失败却显示"已保存"
     根因: applySettingsPatch() 无论 saveSettings 成功与否都返回 ok:true。
     修法: 新增 settings_store.commitSettings() —— 落盘失败 ⇒ ok:false + 错误原因 +
           设置保持原值; main.js 失败时**不应用**到运行时、**不改**内存设置;
           面板显示「保存失败(设置未改动):<原因>」并把控件重画回真实状态。
     实测: 故障注入(存储目录指到普通文件 ⇒ 写入必 ENOTDIR) ⇒
           SETTINGS_SAVE_FAILED / ok=false / 设置保持原值 / 磁盘无文件。

二、顺带修掉的同类问题
----------------------------------------------------------
  「开机自动启动」也是同一类谎报: macOS 上从源码直接跑(非打包 .app)必然
  `Operation not permitted`, 但开关会显示"已开"。现在 applyLaunchAtLogin() 返回真实
  结果并回传到面板, 由面板如实说明原因。
  **已知限制: 开机自启只有在打包成 .app 之后才真正生效。**

三、客观判据
----------------------------------------------------------
  单元测试   3 文件 / 54 断言全过 (心情 20 + 设置存储 18 + 菜单与设置 16)
             本轮新增: M17~M20 (精力增量/重启恢复/睡眠不扣/单次上限)
                       S15~S18 (commitSettings 成功与失败路径)
  真实 Electron 运行时验证  34/34 PASS
    A 写入设置 + 菜单命令走正式行为系统 + 大小/频率/点击反馈 + 心情落盘   14/14
    C 菜单命令"吃水果" ⇒ 场景道具挂载                                    3/3
    D 菜单命令"睡觉" ⇒ 床/月亮/被子挂载                                  2/2
    E 设置面板真实创建并读到磁盘上的设置                                 2/2
    F Mac 一键验收入口真的把桌宠拉起来 (Finder 双击等价路径)              4/4  ★新
    G 保存失败时如实报错/不谎报/不改设置/不写文件 (故障注入)              4/4  ★新
    B 重启恢复 (设置逐字段 + 心情逐字段 + 大小 + 频率)                    5/5
  回归   node 全量 15 文件全过; R147 e2e 真实 Electron PASS=60 FAIL=0;
         R167 15/15; R165 18/18; R173 26/26 (R170 W3 为 R173 改帧后的历史预期失败)

四、如实登记的已知限制 (见 docs/R179_QA_REPORT.md)
----------------------------------------------------------
  · 开机自动启动在开发态(从源码跑)必然失败, 需打包成 .app 才生效
  · 精力衰减是线性模型(每小时 -0.05), 且目前只作可见状态展示, 未参与心情评分
  · 单次精力扣除上限 6 小时 ⇒ 关机一整夜的消耗只算 6 小时
  · MAC_REAL_GUI_ACCEPTANCE = PENDING (菜单/设置面板观感与真实鼠标手感待真机确认)
  · 办公场景仍待用户视觉确认, **未**登记为最终产品验收通过
  · V0_0_RELEASE_STATUS = NOT_FROZEN (未擅自封版, 未进入 V0.1)

包内容
------
candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
                  + assets/character_R158/ 6 个点击动作 x 3 帧 (未改动)
                  + assets/character_R156/ R170 吃水果帧 + 场景道具 (未改动)
                  + assets/character_R172/ R172 办公素材 (未改动)
                  + assets/character_R173/ R173 办公新素材 (未改动)
candidate_b_c2/evidence_r177_runtime/  ★ 运行时验证证据 (A~G 共 7 份真实日志 + 判据 JSON)
one_click_test/   ★ R177/R179 Mac 一键验收入口 (.command 双击可用)
preview/          既有预览 GIF 与对比图 (R173 等历史证据)
evidence/         既有 e2e 报告与采集元数据
docs/             R165 / R167 / R170 / R172 / R173 / R177 / R179 质量报告 + 交付索引

复审要点
--------
1. node  candidates/candidate_b_c2/tests/r177_mood_engine.test.js     (20 断言)
2. node  candidates/candidate_b_c2/tests/r177_settings_store.test.js  (18 断言)
3. node  candidates/candidate_b_c2/tests/r177_menu_settings.test.js   (16 断言)
4. python3 candidates/candidate_b_c2/100_R177_runtime_verify.py        (真实 Electron 34 项)
5. bash   candidates/candidate_b_c2/R147_e2e_test.sh                  (真实 Electron 全量回归)
6. 一键验收入口: one_click_test/R177_验收入口.command  (Finder 双击)
   自动化验证"能否启动": bash one_click_test/run_r177_acceptance.sh --skip-auto --smoke

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
        for rel, arc in ROOT_REVIEW_FILES:
            if add(zf, os.path.join(ROOT, rel), arc):
                n += 1
        for rel, arc in DOC_FILES:
            if add(zf, os.path.join(ROOT, rel), arc):
                n += 1
        readme = README.replace("__GENERATED_AT__", time.strftime("%Y-%m-%d %H:%M:%S")) \
                         .replace("__COMMIT__", commit)
        zf.writestr("evidence/README_R179_review.txt", readme)
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
        for fn in ('run_r177_acceptance.sh', 'R177_验收入口.command'):
            p = os.path.join(ROOT, 'one_click_test', fn)
            if add(zf, p, f"one_click_test/{fn}"):
                n += 1
    return n


def main():
    commit = sys.argv[1] if len(sys.argv) > 1 else 'HEAD'
    print("R179 打包:")
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

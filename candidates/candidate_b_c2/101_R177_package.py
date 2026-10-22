#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R177 交付打包器 —— 轻量审查包 + 完整备份 + SHA256。

与 R173 (99_) 的差别:
  · 新增 R177 源码: src/mood_engine.js / src/settings_store.js / src/menu_template.js
    + src/settings_panel.html / src/settings_panel.js
  · 新增 R177 测试: tests/r177_mood_engine.test.js / r177_settings_store.test.js
    / r177_menu_settings.test.js
  · 新增 R177 脚本: 100_R177_runtime_verify.py (真实 Electron 运行时验证)
    + 101_R177_package.py (本打包器)
  · 新增 R177 证据: evidence_r177_runtime/ (5 次真实 Electron 启动的日志 + 26 项判据报告)
  · 新增 Mac 一键验收入口: one_click_test/run_r177_acceptance.sh
    + one_click_test/R177_验收入口.command
  · R173 及更早的资产/脚本/证据一并入包 (历史成果可复审)

SHA256 写在 ZIP **旁边的独立 .sha256 文件** (不内嵌), 避免"改索引就改哈希"的循环自引用。

用法: python3 101_R177_package.py <commit>
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

REVIEW_ZIP = os.path.join(OUT_DIR, "character_animation_R177_review.zip")
BACKUP_ZIP = os.path.join(ROOT, "backup", "V0.0_backup_%s_r177.zip" % time.strftime("%Y%m%d_%H%M%S"))

# 复用 R173 打包器的清单 (源文件、测试、工具、前序脚本、既有证据)
_spec_path = os.path.join(CAND, '99_R173_package.py')
with open(_spec_path, encoding='utf-8') as _f:
    _src = _f.read()
_ns = {'__name__': '_r173_pkg_base', '__file__': _spec_path}
exec(compile(_src, _spec_path, 'exec'), _ns)

REVIEW_FILES = list(_ns['REVIEW_FILES'])
PREVIEW_FILES = list(_ns['PREVIEW_FILES'])
DOC_FILES = list(_ns['DOC_FILES'])

# ---- R177 新增 ----
REVIEW_FILES += [
    # 新增生产源码
    ("src/mood_engine.js", "candidate_b_c2/src/mood_engine.js"),
    ("src/settings_store.js", "candidate_b_c2/src/settings_store.js"),
    ("src/menu_template.js", "candidate_b_c2/src/menu_template.js"),
    ("src/settings_panel.html", "candidate_b_c2/src/settings_panel.html"),
    ("src/settings_panel.js", "candidate_b_c2/src/settings_panel.js"),
    # 新增测试
    ("tests/r177_mood_engine.test.js", "candidate_b_c2/tests/r177_mood_engine.test.js"),
    ("tests/r177_settings_store.test.js", "candidate_b_c2/tests/r177_settings_store.test.js"),
    ("tests/r177_menu_settings.test.js", "candidate_b_c2/tests/r177_menu_settings.test.js"),
    # 新增脚本
    ("100_R177_runtime_verify.py", "candidate_b_c2/100_R177_runtime_verify.py"),
    ("101_R177_package.py", "candidate_b_c2/101_R177_package.py"),
    # 运行时验证证据
    ("evidence_r177_runtime/r177_runtime_verify.json",
     "candidate_b_c2/evidence_r177_runtime/r177_runtime_verify.json"),
    ("evidence_r177_runtime/run_A.log", "evidence_r177_runtime/run_A.log"),
    ("evidence_r177_runtime/run_B.log", "evidence_r177_runtime/run_B.log"),
    ("evidence_r177_runtime/run_C.log", "evidence_r177_runtime/run_C.log"),
    ("evidence_r177_runtime/run_D.log", "evidence_r177_runtime/run_D.log"),
    ("evidence_r177_runtime/run_E.log", "evidence_r177_runtime/run_E.log"),
    ("evidence_r177_runtime/ud_A/pet_settings.json",
     "evidence_r177_runtime/ud_A/pet_settings.json"),
    ("evidence_r177_runtime/ud_A/pet_mood_state.json",
     "evidence_r177_runtime/ud_A/pet_mood_state.json"),
    # Mac 一键验收入口
    ("../one_click_test/run_r177_acceptance.sh", "one_click_test/run_r177_acceptance.sh"),
    ("../one_click_test/R177_验收入口.command", "one_click_test/R177_验收入口.command"),
]

DOC_FILES += [
    ("docs/R177_QA_REPORT.md", "docs/R177_QA_REPORT.md"),
    ("docs/R177_DELIVERY_INDEX.md", "docs/R177_DELIVERY_INDEX.md"),
]

README = """R177 审查包说明 (AI 智能陪伴桌宠 V0.0)
=========================================
生成时间: __GENERATED_AT__
提交:     __COMMIT__

本轮主题: 纯离线体验增强 —— 本地性格与心情系统 / 桌宠控制菜单 / 设置面板 / 本地数据保存
          **本轮全程零联网、零 AI 调用、零充值 i2i、不生成任何新角色图片。**

一、边界声明 (先看这段, 它决定本轮交付能不能被接受)
----------------------------------------------------------
  · 没有 AI 聊天、没有联网语音、没有模型调用、没有云端记忆。
  · 心情是**纯规则**算出来的: 只由真实运行时事件推导
    (交互次数 / 闲置时长 / 清醒时长 / 本地时段 / 睡眠次数), **不产生任何台词**。
    ⇒ 她不会"说话", 也就不存在"用预设文字冒充 AI 人格"的可能。
    (单测 M16 显式断言: 心情引擎里没有任何 say/chat/talk/dialog 类接口。)
  · 本地保存的是**桌宠设置**与**基础心情状态**, 明确**不是** AI 长期记忆。
  · 所有数据只写本机 userData 目录, 不联网、不上传 (单测 S13 扫描源码断言无网络调用)。

二、四大功能怎么做的
----------------------------------------------------------
  1) 本地性格与心情系统   src/mood_engine.js
     - 四种心情: 开心 / 平静 / 困倦 / 无聊 (判定可复算, 无随机)
     - 心情 → 行为: 自主决策间隔系数、活动权重系数、点击动作池权重 (只改权重, 不改有无反馈)
  2) 桌宠控制菜单         src/menu_template.js + main.js (Electron 原生 Menu)
     - 右键角色弹出: 睡觉 / 醒来 / 坐沙发休息 / 电脑办公 / 吃水果 / 随机可爱动作
       + 设置… + 退出桌宠; 顶部只读显示当前心情
     - **每一项都走正式行为系统**: BehaviorEngine.command() 调用的是自主决策
       **完全相同**的内部路径 (_enterSleep/_startSit/_startWork/_startEatFruit/
       _startGesture/wakeUpByUser) ⇒ 状态转移、计时器、道具挂载、动作结束回落全部复用,
       不存在"只播一张演示图"的旁路。
     - 与自主决策只差两点: 不受同类冷却限制、接管当前排程 (用户明确要求就该立刻生效)
  3) 设置面板             src/settings_panel.html + src/settings_panel.js
     - 独立窗口 (340×486), 不叠在桌宠上、不污染桌宠外观, 没有调试项
     - 桌宠大小 / 自主活动频率 / 睡眠频率 / 点击反馈开关 / 开机自动启动
     - 开机自启只在 macOS/Windows 提供 (Linux 无登录项 API ⇒ 开关置灰并说明)
  4) 本地数据保存         src/settings_store.js
     - userData/pet_settings.json + userData/pet_mood_state.json
     - 原子写 (临时文件 + rename); 文件损坏 ⇒ 回退默认值且**不拖垮启动**
     - 重启后逐字段恢复 (真实 Electron 实测, 见下)

三、客观判据 (真实 Electron 实跑, 26/26 PASS)
----------------------------------------------------------
  A1 本地存储目录 = 指定 user-data-dir (确实写本机, 不联网)
  A2/A3/A4 设置经 applySettingsPatch 写入并落盘, 磁盘内容 = 写入值 (逐字段)
  A5/A6 菜单命令"电脑办公" ⇒ ok=true, 状态机 IDLE -> WORK (正式转移记录)
  A7/A8 渲染器真的切到办公场景 (set-action work applied=true);
        办公家具按 R173 口径已内嵌进角色帧 ⇒ mounted=none
  A9/A10 桌宠大小生效: 200×240 × 1.25 = 250×300, 窗口与渲染画布同尺寸
  A11 频率档位换算正确并作用到引擎 (high→间隔×0.6/权重×1.4, low→睡眠×0.35)
  A12 点击反馈开关已下发到渲染器
  A13/A14 心情状态落盘 + 退出前保存
  C1~C3 菜单命令"吃水果" ⇒ EAT_FRUIT, 道具真的挂载 (小凳 + 小边桌)
  D1/D2 菜单命令"睡觉" ⇒ SLEEP_ENTER, 床 + 月亮 + 被子真的挂载
  E1/E2 设置面板窗口真实创建, 读到的是磁盘上已保存的设置
  B1  重启后设置逐字段恢复 (大小/活动频率/睡眠频率/点击反馈/自启)
  B2/B3 重启后心情状态从磁盘恢复, 与启动时磁盘文件逐字段一致
  B4/B5 重启后桌宠大小与频率档位仍然生效

四、单元测试 (新增 3 个文件 / 46 项断言, 全过)
----------------------------------------------------------
  tests/r177_mood_engine.test.js     16 项 (含"无对话接口"硬边界断言)
  tests/r177_settings_store.test.js  14 项 (含"不联网"源码扫描断言)
  tests/r177_menu_settings.test.js   16 项 (含"菜单命令走正式行为系统"断言)

五、回归 (全部实跑)
--------------------
  node 单元测试        15 个文件 全过 (原有 12 + 新增 3)
  R147 e2e 真实 Electron  PASS=60 FAIL=0 NOT_VERIFIED=0
  R167 / R165 / R170 / R173 判据 全部维持既有结论

六、如实登记的已知限制 (见 docs/R177_QA_REPORT.md)
----------------------------------------------------------
  · 心情的"开心"判定很灵敏: 一次点击交互即进入开心 (互动分数 0.8 > 平静基准 0.6)。
  · 深夜 (23:00~06:00) 困倦分数高于开心, 因此夜里点击她可能表现得很困 (符合规则, 但需真机体感确认)。
  · 心情**不静默吞掉点击反馈** (只改权重不改有无): 本轮第一版曾让困倦禁用点击反馈,
    被 e2e 判 FAIL 抓出来 (破坏了 R156/R162 的"点击必须有可见反馈"不变量), 已改回默认不禁用。
  · 深夜 (23:00~06:00) 困倦分数高于开心, 夜里整体表现很困, 真机体感待确认。
  · 开机自动启动用的是 Electron 的 setLoginItemSettings, 首次勾选可能需要用户在
    "系统设置 → 通用 → 登录项"里确认一次 (macOS 机制)。
  · 桌宠大小是通过**窗口尺寸 + 画布重建**实现的, 属于"整体放大"而不是"重绘更高分辨率",
    所以在 1.6× 时画面是位图放大, 边缘会略有柔化。
  · MAC_REAL_GUI_ACCEPTANCE = PENDING (菜单、设置面板、拖拽隔离等仍需用户 Mac 真机确认)。
  · 办公场景仍待用户视觉确认, **未**登记为最终产品验收通过。

包内容
------
candidate_b_c2/   候选实现的全部源码、单元测试、e2e 脚本、manifest
                  + assets/character_R158/  6 个点击动作 × 3 帧 (未改动)
                  + assets/character_R156/  R170 吃水果帧 + 场景道具 (未改动)
                  + assets/character_R172/  R172 办公素材 (未改动)
                  + assets/character_R173/  R173 办公新素材 (未改动)
evidence_r177_runtime/  ★ 5 次真实 Electron 启动日志 + 26 项判据报告 + 本地落盘文件
one_click_test/   ★ R177 Mac 一键验收入口 (.command 双击可用)
preview/          既有预览 GIF 与对比图 (R173 等历史证据)
evidence/         既有 e2e 报告与采集元数据
docs/             R165 / R167 / R170 / R172 / R173 / R177 质量报告 + 交付索引

复审要点
--------
1. node  candidates/candidate_b_c2/tests/r177_mood_engine.test.js
2. node  candidates/candidate_b_c2/tests/r177_settings_store.test.js
3. node  candidates/candidate_b_c2/tests/r177_menu_settings.test.js
4. python3 candidates/candidate_b_c2/100_R177_runtime_verify.py   (真实 Electron 26 项判据)
5. bash   candidates/candidate_b_c2/R147_e2e_test.sh               (真实 Electron 全量回归)
6. 一键验收入口: one_click_test/R177_验收入口.command  (Finder 双击)

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
        zf.writestr("evidence/README_R177_review.txt", readme)
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
        # Mac 一键验收入口也进备份
        for fn in ('run_r177_acceptance.sh', 'R177_验收入口.command'):
            p = os.path.join(ROOT, 'one_click_test', fn)
            if add(zf, p, f"one_click_test/{fn}"):
                n += 1
    return n


def main():
    commit = sys.argv[1] if len(sys.argv) > 1 else 'HEAD'
    print("R177 打包:")
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

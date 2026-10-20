#!/usr/bin/env python3
"""R147 运行时 manifest 修订器 (确定性, 可重放, 幂等).

依据 (全部来自实测, 见 docs/R147_QA_REPORT.md §二):
  1. R138 的 walk_left / walk_right 是**两套不同姿势**, 不是镜像, 也不是改名:
     交叉像素差异 68k~152k (占不透明像素 30%~65%), 且
       · walk_left_01 踩地那只靴子的鞋尖朝左 (迈左步)
       · walk_right_01 踩地那只鞋的鞋尖朝右 (迈右步)
     → 两组素材各自的迈步方向本来就是对的, 因此**不替换帧来源**。
  2. 但两组素材的**躯干朝向都没有绑定移动方向**:
     角色整体正面朝镜头, 窗口向左移动时看不到任何"朝左"的姿态线索,
     只有脚下在动 → 用户观感就是"倒着走" (身体没转向, 腿在原地倒腾)。
     R147 授权的解法是"整体朝向处理" —— 对整帧做水平错切 (shear),
     让身体连同腿一起朝行进方向倾斜, 纹理不镜像, 身份/服装/发型完全不变。
  3. idle_01_inhale_peak 胸腔外扩 26px (实测轮廓宽 375→401), 是用户投诉的
     "待机时胸部剧烈向外突起、膨胀"。

修订:
  · walk_left : 保留原 4 帧, 加 lean.skew_x = +0.085 (PixiJS 语义 k>0 → 向左倾)
  · walk_right: 保留原 4 帧, 加 lean.skew_x = -0.075 (k<0 → 向右倾)
                 素材本身已有右向动势, 故幅度略小, 避免过度侧倾
  · idle      : 加 director 段 —— 稳定站姿 + 自然眨眼; 膨胀帧 1 与回落帧 2/3
                 不再进入播放序列, 但 6 帧仍全部加载 (资产完整 23/23)
  · 版本号     : R147-RUNTIME

幂等: 重复执行结果一致 (帧列表不被改动, 只写 lean / director / version)。
"""
import json
import os
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "assets", "character_R141_manifest.json")

# PixiJS 顶点语义: 局部 x' = lx + tan(skew.x) * ly ; ly = v - pivot_y
#   k > 0 → 上半身 (ly<0) 向左偏移 → 向左倾
#   k < 0 → 上半身向右偏移 → 向右倾
LEAN = {
    "walk_left": collections.OrderedDict([
        ("skew_x", 0.085),
        ("pivot_y", 921.6),
        ("direction", -1),
        ("note", "R147: 保留原 4 帧(迈步方向本就正确); 叠加整体向左倾斜, 身体与腿一起朝移动方向倾, 纹理不镜像"),
    ]),
    "walk_right": collections.OrderedDict([
        ("skew_x", -0.11),
        ("pivot_y", 921.6),
        ("direction", 1),
        ("note", "R147: 保留原 4 帧; 叠加整体向右倾斜(实测净倾斜与 walk_left 对称: 左 -13px / 右 +12px)"),
    ]),
}


def main():
    with open(MANIFEST, encoding="utf-8") as f:
        m = json.load(f, object_pairs_hook=collections.OrderedDict)

    # --- 行走: 帧列表保持原样, 只加方向倾斜 ---
    for action, lean in LEAN.items():
        a = m["actions"][action]
        if "extra_frames" in a:
            # 早期版本曾把 walk_left 改成播 walk_right 的帧, 这里还原
            del a["extra_frames"]
            a["frames"] = list(ORIGINAL_FRAMES[action])
        a["lean"] = lean

    # --- idle: 稳定站姿 + 自然眨眼, 膨胀帧不再播放 ---
    idle = m["actions"]["idle"]
    idle["director"] = collections.OrderedDict([
        ("enabled", True),
        ("base_index", 0),
        ("blink_sequence", [4, 5]),
        ("blink_frame_ms", [90, 110]),
        ("blink_interval_ms", [1600, 3400]),
        ("excluded_frames", [1, 2, 3]),
        ("note", "R147: idle_01_inhale_peak 胸腔剧烈膨胀(实测外扩 26px), 运行时不再播放; "
                 "改稳定站姿 + 自然眨眼(1.6~3.4s 随机间隔, 远慢于 R141 的 1.2s 机械循环)"),
    ])

    m["version"] = "R147-RUNTIME"
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("manifest 已更新:", MANIFEST)
    for action in LEAN:
        a = m["actions"][action]
        print(f"  {action}: 播放帧={len(a['frames'])} lean.skew_x={a['lean']['skew_x']} "
              f"direction={a['lean']['direction']}")
    print(f"  idle: 播放帧={len(m['actions']['idle']['frames'])} (director 控制实际显示帧)")
    total = sum(len(a["frames"]) for a in m["actions"].values())
    print(f"  资产帧总数 = {total}")
    return 0


# R138 原始帧列表 (用于从早期版本还原)
ORIGINAL_FRAMES = {
    "walk_left": [
        "character_R138/walk_left/walk_left_00_stand.png",
        "character_R138/walk_left/walk_left_01_left_step.png",
        "character_R138/walk_left/walk_left_02_pass.png",
        "character_R138/walk_left/walk_left_03_right_step.png",
    ],
    "walk_right": [
        "character_R138/walk_right/walk_right_00_stand.png",
        "character_R138/walk_right/walk_right_01_right_step.png",
        "character_R138/walk_right/walk_right_02_pass.png",
        "character_R138/walk_right/walk_right_03_left_step.png",
    ],
}


if __name__ == "__main__":
    sys.exit(main())

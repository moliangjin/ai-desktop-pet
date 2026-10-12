#!/usr/bin/env python3
"""
csv_builder.py — 把 PetAcceptor 写的 result JSON 转成 CSV 行，严格字段对齐。

V0.0 R45 设计要求：
  * 表头固定 19 列
  * 每条数据行严格 19 字段（用 csv.writer 自动加引号处理中文/逗号/换行）
  * 字段顺序：tested_at, candidate, version, commit, bundle_id, launch_ok,
              overall, launch, display, animation, click, drag, transparent,
              window_focus, multidisplay, notes, result_path, build_log_path,
              runtime_log_path
  * 多行 status 字段为枚举：PASS / FAIL / NOT_TESTED / DISABLED_SINGLE_DISPLAY
  * notes 字段把 items[].notes 合并为单字段，多行用 ; 分隔

用法：
  python3 csv_builder.py path/to/result.json >> evidence/build_logs/user_visual_report.csv
"""
import csv
import json
import sys
import io
import os

STABLE_FIELDS = [
    "tested_at", "candidate", "version", "commit", "bundle_id", "launch_ok",
    "overall",
    "launch", "display", "animation", "click", "drag", "transparent",
    "window_focus", "multidisplay",
    "notes", "result_path",
    "build_log_path", "runtime_log_path",
]

ITEM_KEYS = ["launch", "display", "animation", "click", "drag",
             "transparent", "window_focus", "multidisplay"]

VALID_STATUSES = {"PASS", "FAIL", "NOT_TESTED", "DISABLED_SINGLE_DISPLAY"}


def build_row(result_path):
    with open(result_path, "r", encoding="utf-8") as f:
        d = json.load(f)

    out = {k: "" for k in STABLE_FIELDS}
    # 直接字段
    out["tested_at"]   = d.get("tested_at", "")
    out["candidate"]   = d.get("candidate", "")
    out["version"]     = d.get("version", "")
    out["commit"]      = d.get("commit", "")
    out["bundle_id"]   = d.get("bundle_id", "")
    out["overall"]     = d.get("overall", "")
    out["result_path"] = result_path

    # items[].status 按 key 取
    items_by_key = {it["key"]: it for it in d.get("items", [])}
    for k in ITEM_KEYS:
        if k in items_by_key:
            s = items_by_key[k].get("status", "NOT_TESTED")
            if s not in VALID_STATUSES:
                raise ValueError(f"bad status {s} on key {k}")
            out[k] = s
        else:
            out[k] = "NOT_TESTED"

    # 启动是否 ok：launch=PASS 才算
    out["launch_ok"] = "true" if out["launch"] == "PASS" else "false"

    # notes 合并
    notes = []
    for k in ITEM_KEYS:
        note = items_by_key.get(k, {}).get("notes", "")
        if note:
            notes.append(f"[{k}] {note}")
    out["notes"] = "; ".join(notes)

    # build/runtime log 路径推断
    base = os.path.basename(result_path).replace("_result.json", "")
    log_dir = os.path.dirname(result_path)
    out["build_log_path"]  = f"{log_dir}/{base}.log"
    out["runtime_log_path"] = f"{log_dir}/{base}_runtime.log"

    return out


def has_valid_header(csv_path):
    if not os.path.exists(csv_path): return False
    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
        return header == STABLE_FIELDS
    except Exception:
        return False


def ensure_csv_with_header(csv_path):
    if not has_valid_header(csv_path):
        # 文件不存在、或首行不是我们 STABLE_FIELDS 顺序：truncate 写入 header
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=STABLE_FIELDS)
            writer.writeheader()


def append_row(csv_path, row):
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=STABLE_FIELDS)
        writer.writerow(row)


def validate_csv(csv_path):
    """Head+every-row 必须有 (len(STABLE_FIELDS)) 字段。返回 list of errors."""
    errors = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return ["CSV is empty"]
    header = rows[0]
    expected = len(STABLE_FIELDS)
    if len(header) != expected:
        errors.append(f"header has {len(header)} fields, expected {expected}: {header}")
    for i, r in enumerate(rows[1:], start=2):
        if len(r) != expected:
            errors.append(f"row {i} has {len(r)} fields, expected {expected}: {r}")
    return errors


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: csv_builder.py <result.json> <csv_path> [--validate]", file=sys.stderr)
        sys.exit(2)
    result_path = os.path.abspath(sys.argv[1])
    csv_path = os.path.abspath(sys.argv[2])
    ensure_csv_with_header(csv_path)
    row = build_row(result_path)
    append_row(csv_path, row)
    if "--validate" in sys.argv:
        errors = validate_csv(csv_path)
        if errors:
            for e in errors:
                print(f"VALIDATE ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"CSV OK rows={sum(1 for _ in open(csv_path)) - 1} fields={len(STABLE_FIELDS)}")

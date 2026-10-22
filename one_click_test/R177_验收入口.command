#!/bin/bash
# R177 一键验收入口 (Finder 双击版)
# 真正的逻辑在 run_r177_acceptance.sh, 这里只负责定位目录并转交。
cd "$(dirname "$0")" || exit 1
exec bash ./run_r177_acceptance.sh "$@"

#!/bin/bash
# tools/passthrough_poc/自动验收.command
#
# V0.0 R79 一键入口 (重写)
#   1. 检查本地原生测试器是否存在
#   2. 必要时自动构建 (clang)
#   3. 构建失败立即停止并显示首个关键错误
#   4. 检查 Accessibility 授权
#   5. 未授权时给出最少必要申请说明
#   6. 授权后启动 Node.js orchestrator (调原生 click + 解析 PoC stdout tick)
#   7. 中途异常 / 超时立即停止
#   8. 生成独立 run_id 的 TXT / JSON / CSV 结果

set +e
cd "$(dirname "$0")"

clear
echo "=========================================="
echo " R79 一键自动验收"
echo "=========================================="

# Step 1: 检查 + 构建
if [ ! -x ./build/m79_native_click ]; then
    echo "[1/5] 编译原生测试器 (clang)..."
    bash ./m79_build.sh
    if [ ! -x ./build/m79_native_click ]; then
        echo "  FAILED. 检查 m79_build.log"
        exit 2
    fi
fi
echo "[1/5] OK: ./build/m79_native_click 存在"

# Step 2: 自检
echo ""
echo "[2/5] 自检 (非 GUI, 只检查 AX 权限)..."
SELF=$(./build/m79_native_click --self-test)
echo "  $SELF"

# Step 3: AX 权限检查
if ! echo "$SELF" | grep -q '"accessibility_granted":true'; then
    echo ""
    echo "[3/5] Accessibility 权限不足"
    echo "  修复: 系统设置 -> 隐私与安全 -> 辅助功能"
    echo "  勾选 Terminal.app (或你用来跑这个 .command 的宿主应用)"
    echo "  勾选后请重新双击本 .command"
    exit 3
fi
echo "[3/5] OK: Accessibility granted"

# Step 4: 启动 orchestrator
echo ""
echo "[4/5] 启动 Node.js orchestrator..."
node ./m79_orchestrator.js
RC=$?
echo ""
echo "[5/5] orchestrator exit=$RC"
echo "  结果在 /tmp/m79_<run_id>.{txt,json,csv}"
ls -la /tmp/m79_*.{txt,json,csv} 2>/dev/null | head -3
exit $RC

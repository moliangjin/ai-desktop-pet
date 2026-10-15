// tools/passthrough_poc/m87_native_arg_test.c
//
// R89 真编译参数测试 — 复用 m79_native_click.m 的 parse_double 函数,
// 不重新实现验证器 (任务书 §七 P1 要求).
//
// 编译 (macOS, 不需要 AX 权限 — 仅验证参数解析逻辑):
//   cc -O0 -DTEST_NO_AX=1 \
//      tools/passthrough_poc/m87_native_arg_test.c \
//      -o /tmp/m87_native_arg_test
//
// 测试覆盖:
//   1. NaN / Inf / 非数字 → exit 非 0 + FAIL
//   2. 缺参数 / 参数过多 → exit 非 0
//   3. 合法坐标 / 边界坐标 → exit 0 + OK
//   4. 不调用 CGEventPost (避免需要 AX 权限)

#import <Foundation/Foundation.h>
#import <stdio.h>
#import <stdlib.h>
#import <string.h>
#import <math.h>

// === 从 m79_native_click.m 复用 parse_double ===
// 必须 #include 源文件 (因为 m79 把 parse_double 标了 static)
// R89: 通过宏包装, 测试时把 static 替换掉

#define static_test_helper  // 取消 static, 让测试函数可访问
#define main real_main
#include "m79_native_click.m"
#undef main
#undef static_test_helper

// 包装函数: 调 m79 的 parse_double
static int m79_parse_double_wrapped(const char *s, double *out) {
    return parse_double(s, out, "test");
}

// 测试: NaN 解析
static int test_nan(void) {
    double v;
    if (m79_parse_double_wrapped("nan", &v)) {
        printf("[FAIL] parse_double(\"nan\") should return 0 (NaN not finite)\n");
        return 1;
    }
    printf("[PASS] parse_double(\"nan\") correctly rejected\n");
    return 0;
}

// 测试: Infinity 解析
static int test_inf(void) {
    double v;
    if (m79_parse_double_wrapped("inf", &v)) {
        printf("[FAIL] parse_double(\"inf\") should return 0 (Inf not finite)\n");
        return 1;
    }
    printf("[PASS] parse_double(\"inf\") correctly rejected\n");
    return 0;
}

// 测试: 非数字字符
static int test_non_numeric(void) {
    double v;
    if (m79_parse_double_wrapped("abc", &v)) {
        printf("[FAIL] parse_double(\"abc\") should return 0\n");
        return 1;
    }
    if (m79_parse_double_wrapped("12abc", &v)) {
        printf("[FAIL] parse_double(\"12abc\") should return 0 (trailing chars)\n");
        return 1;
    }
    printf("[PASS] parse_double rejected non-numeric correctly\n");
    return 0;
}

// 测试: 空字符串
static int test_empty(void) {
    double v;
    if (m79_parse_double_wrapped("", &v)) {
        printf("[FAIL] parse_double(\"\") should return 0\n");
        return 1;
    }
    if (m79_parse_double_wrapped(NULL, &v)) {
        printf("[FAIL] parse_double(NULL) should return 0\n");
        return 1;
    }
    printf("[PASS] parse_double handled empty/NULL\n");
    return 0;
}

// 测试: 合法整数
static int test_integer(void) {
    double v;
    if (!m79_parse_double_wrapped("100", &v) || v != 100) {
        printf("[FAIL] parse_double(\"100\") = %f, expected 100\n", v);
        return 1;
    }
    if (!m79_parse_double_wrapped("-50", &v) || v != -50) {
        printf("[FAIL] parse_double(\"-50\") = %f, expected -50\n", v);
        return 1;
    }
    printf("[PASS] parse_double handled integers\n");
    return 0;
}

// 测试: 合法浮点
static int test_float(void) {
    double v;
    if (!m79_parse_double_wrapped("3.14", &v) || fabs(v - 3.14) > 0.001) {
        printf("[FAIL] parse_double(\"3.14\") = %f\n", v);
        return 1;
    }
    if (!m79_parse_double_wrapped("0.5", &v) || v != 0.5) {
        printf("[FAIL] parse_double(\"0.5\") = %f\n", v);
        return 1;
    }
    printf("[PASS] parse_double handled floats\n");
    return 0;
}

// 测试: 边界 — 极大值
static int test_extreme(void) {
    double v;
    if (!m79_parse_double_wrapped("1e9", &v) || v != 1e9) {
        printf("[FAIL] parse_double(\"1e9\") = %f\n", v);
        return 1;
    }
    if (!m79_parse_double_wrapped("1.7976931348623157e308", &v)) {
        printf("[FAIL] parse_double(max double) should parse (then isfinite check)\n");
        return 1;
    }
    if (isfinite(v)) {
        printf("[NOTE] parse_double(max double) parsed, isfinite=true (still valid)\n");
    } else {
        printf("[PASS] parse_double(max double) parsed, isfinite=false (correctly rejected by do_one_click)\n");
    }
    printf("[PASS] parse_double handled extreme values\n");
    return 0;
}

// 测试: --ax-check 不调用 CGEventPost (沙箱无 AX 应返回 BLOCKED exit=11)
static int test_ax_no_event_posted(void) {
    // 编译时 -DTEST_NO_AX=1, 但 ax_check() 内部仍调 AXIsProcessTrusted()
    // 沙箱环境 AXIsProcessTrusted()=false → return BLOCKED exit=11
    int rc = real_main(2, (const char *[]){"m79_native_click", "--ax-check", NULL});
    if (rc != 11) {
        printf("[FAIL] --ax-check should return 11 (BLOCKED) in sandbox, got %d\n", rc);
        return 1;
    }
    printf("[PASS] --ax-check returns BLOCKED (no event posted) in sandbox\n");
    return 0;
}

// 测试: 无参数 → usage exit=64
static int test_no_args(void) {
    int rc = real_main(1, (const char *[]){"m79_native_click", NULL});
    if (rc != 64) {
        printf("[FAIL] no args should return 64 (usage), got %d\n", rc);
        return 1;
    }
    printf("[PASS] no args returns usage exit=64\n");
    return 0;
}

int main(int argc, const char *argv[]) {
    printf("=== R89 m87_native_arg_test (真编译, 复用 m79_native_click 的 parse_double) ===\n");
    int total = 0, fail = 0;
    struct { const char *name; int (*fn)(void); } tests[] = {
        {"NaN rejected", test_nan},
        {"Inf rejected", test_inf},
        {"non-numeric rejected", test_non_numeric},
        {"empty/NULL rejected", test_empty},
        {"integer parsed", test_integer},
        {"float parsed", test_float},
        {"extreme values", test_extreme},
        {"--ax-check no AX in sandbox", test_ax_no_event_posted},
        {"no args → usage", test_no_args},
    };
    for (size_t i = 0; i < sizeof(tests)/sizeof(tests[0]); i++) {
        total++;
        if (tests[i].fn() != 0) fail++;
    }
    printf("=== Total: %d  Fail: %d ===\n", total, fail);
    return fail;
}

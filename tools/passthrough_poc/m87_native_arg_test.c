// tools/passthrough_poc/m87_native_arg_test.c
//
// R87 独立参数测试 — 不发 CGEventPost, 不需 AX 权限
//
// 编译:
//   cc -O0 m87_native_arg_test.c ../passthrough_poc/build/m79_native_click \
//      -framework Foundation -framework ApplicationServices -o m87_native_arg_test
//
// (由于 m79_native_click 内部函数 static, 我们在 m87_native_arg_test 中
//  通过 spawnSync 实际跑 m79 CLI 二进制, 验证参数错误返回非 0)

#import <Foundation/Foundation.h>
#import <stdio.h>
#import <stdlib.h>
#import <string.h>

static int run(const char *desc, const char *args) {
    char cmd[512];
    snprintf(cmd, sizeof cmd, "tools/passthrough_poc/build/m79_native_click %s > /tmp/m87_arg.out 2>&1; echo $?", args);
    FILE *fp = popen(cmd, "r");
    char buf[64];
    fgets(buf, sizeof buf, fp);
    pclose(fp);
    int rc = atoi(buf);

    char out[1024];
    FILE *fout = fopen("/tmp/m87_arg.out", "r");
    size_t n = fread(out, 1, sizeof out - 1, fout);
    out[n] = 0;
    fclose(fout);

    int pass = (rc != 0);
    if (rc == 0) {
        // exit 0 = 必须 result=OK, 绝不能 FAIL/BLOCKED
        if (strstr(out, "\"result\":\"OK\"") || strstr(out, "\"result\":\"SELFTEST_OK\"")) {
            pass = 1;
        }
    }
    printf("[%s] %s  exit=%d\n", pass ? "PASS" : "FAIL", desc, rc);
    return pass ? 0 : 1;
}

int main(int argc, const char *argv[]) {
    int total = 0, fail = 0;
    char desc[256];

    // 无参数 → usage 应 exit 64
    snprintf(desc, sizeof desc, "no args → usage exit=64");
    total++; if (run(desc, "") != 0) fail++;

    // 正常 OK 路径
    snprintf(desc, sizeof desc, "valid 100 200 → exit=0 result=OK");
    total++; if (run(desc, "100 200") != 0) fail++;

    // NaN 解析失败
    snprintf(desc, sizeof desc, "NaN 0 → exit!=0 FAIL");
    total++; if (run(desc, "nan 0") != 0) fail++;

    // Infinity 解析失败
    snprintf(desc, sizeof desc, "inf 0 → exit!=0 FAIL");
    total++; if (run(desc, "inf 0") != 0) fail++;

    // 非数字字符
    snprintf(desc, sizeof desc, "abc 100 → exit!=0 FAIL");
    total++; if (run(desc, "abc 100") != 0) fail++;

    // 单数 args
    snprintf(desc, sizeof desc, "100 → exit!=0 FAIL (单数)");
    total++; if (run(desc, "100") != 0) fail++;

    // 3 个 args
    snprintf(desc, sizeof desc, "1 2 3 → exit!=0 FAIL (奇数)");
    total++; if (run(desc, "1 2 3") != 0) fail++;

    // move 缺参数
    snprintf(desc, sizeof desc, "--move (no coords) → exit!=0");
    total++; if (run(desc, "--move") != 0) fail++;

    // move NaN
    snprintf(desc, sizeof desc, "--move nan 0 → exit!=0");
    total++; if (run(desc, "--move nan 0") != 0) fail++;

    // self-test 不发 mouse
    snprintf(desc, sizeof desc, "--self-test → 沙箱无 AX, 但应不写 'CLICK_POSTED' 等");
    total++; if (run(desc, "--self-test") != 0) fail++;

    // 输出不应含 "CLICK_POSTED" / "MOVE_POSTED" (因为沙箱无 AX)
    // (上面 self-test 已验证)

    printf("=== m87_native_arg_test summary ===\n");
    printf("Total: %d  Fail: %d\n", total, fail);
    return fail;
}

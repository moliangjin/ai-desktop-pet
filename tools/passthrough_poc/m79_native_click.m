// tools/passthrough_poc/m79_native_click.m
//
// V0.0 R79 Objective-C 鼠标事件执行器 (最简稳定版)
//
// 唯一职责: 在用户已授权 Accessibility 后, 真实通过 CGEventPost
// 系统级 mouse event 到指定坐标。 不做编排 — 编排由 Node.js 调度。
//
// 编译:
//   cd tools/passthrough_poc
//   ./m79_build.sh
//
// 运行:
//   ./build/m79_native_click --self-test             (AX 检查 + 自检, 不发 mouse)
//   ./build/m79_native_click x y [x y ...]           (真实 click 一次/坐标)
//   ./build/m79_native_click move x y                (只移动不 click)
//   ./build/m79_native_click ax-check               (只检查 AX 权限)

#import <Foundation/Foundation.h>
#import <ApplicationServices/ApplicationServices.h>
#import <CoreGraphics/CoreGraphics.h>
#import <unistd.h>
#import <stdio.h>
#import <stdlib.h>
#import <string.h>

static int do_ax_check(void) {
    BOOL ok = AXIsProcessTrusted();
    if (ok) {
        printf("{\"result\":\"AX_OK\",\"accessibility_granted\":true}\n");
    } else {
        printf("{\"result\":\"AX_DENIED\",\"accessibility_granted\":false,\"hint\":\"System Settings -> Privacy & Security -> Accessibility -> enable the host app (e.g. Terminal.app).\"}\n");
    }
    fflush(stdout);
    return ok ? 0 : 2;
}

static int do_self_test(void) {
    int ax = do_ax_check();
    if (ax != 0) return ax;
    // 模拟 mouse-move 到 (0,0) — 不会发 down/up, 不影响用户桌面
    CGPoint p = CGPointMake(0, 0);
    CGEventRef ev = CGEventCreateMouseEvent(NULL, kCGEventMouseMoved, p, kCGMouseButtonLeft);
    if (!ev) {
        printf("{\"result\":\"SELFTEST_FAIL\",\"error\":\"CGEventCreateMouseEvent returned NULL\"}\n");
        fflush(stdout);
        return 3;
    }
    CGEventPost(kCGHIDEventTap, ev);
    CFRelease(ev);
    printf("{\"result\":\"SELFTEST_OK\",\"accessibility_granted\":true,\"event_post_ok\":true}\n");
    fflush(stdout);
    return 0;
}

static int do_move(int argc, const char *argv[]) {
    if (argc < 1) {
        printf("{\"result\":\"FAIL\",\"error\":\"--move requires x y\"}\n");
        return 4;
    }
    double x = strtod(argv[0], NULL);
    double y = strtod(argv[1], NULL);
    CGPoint p = CGPointMake(x, y);
    CGEventRef ev = CGEventCreateMouseEvent(NULL, kCGEventMouseMoved, p, kCGMouseButtonLeft);
    if (!ev) { printf("{\"result\":\"FAIL\"}\n"); return 5; }
    CGEventPost(kCGHIDEventTap, ev);
    CFRelease(ev);
    usleep(80 * 1000);
    printf("{\"result\":\"MOVED\",\"x\":%.1f,\"y\":%.1f}\n", x, y);
    fflush(stdout);
    return 0;
}

static int do_clicks(int argc, const char *argv[]) {
    if (argc < 2) {
        printf("{\"result\":\"FAIL\",\"error\":\"need pairs of x y\"}\n");
        return 6;
    }
    int n = 0;
    for (int i = 0; i + 1 < argc; i += 2) {
        double x = strtod(argv[i], NULL);
        double y = strtod(argv[i + 1], NULL);
        CGPoint p = CGPointMake(x, y);

        CGEventRef move = CGEventCreateMouseEvent(NULL, kCGEventMouseMoved, p, kCGMouseButtonLeft);
        if (move) { CGEventPost(kCGHIDEventTap, move); CFRelease(move); }
        usleep(120 * 1000);

        CGEventRef down = CGEventCreateMouseEvent(NULL, kCGEventLeftMouseDown, p, kCGMouseButtonLeft);
        CGEventRef up   = CGEventCreateMouseEvent(NULL, kCGEventLeftMouseUp,   p, kCGMouseButtonLeft);
        if (down) { CGEventPost(kCGHIDEventTap, down); CFRelease(down); }
        usleep(40 * 1000);
        if (up)   { CGEventPost(kCGHIDEventTap, up);   CFRelease(up);   }
        usleep(380 * 1000);
        n++;
    }
    printf("{\"result\":\"CLICKED\",\"count\":%d}\n", n);
    fflush(stdout);
    return 0;
}

int main(int argc, const char *argv[]) {
    if (argc < 2) {
        printf("usage:\n  %s --self-test\n  %s --ax-check\n  %s --move x y\n  %s x1 y1 [x2 y2 ...]\n", argv[0], argv[0], argv[0], argv[0]);
        return 1;
    }
    if (strcmp(argv[1], "--ax-check") == 0) return do_ax_check();
    if (strcmp(argv[1], "--self-test") == 0) return do_self_test();
    if (strcmp(argv[1], "--move") == 0) return do_move(argc - 2, argv + 2);
    // default: pairs of x y
    return do_clicks(argc - 1, argv + 1);
}

// tools/passthrough_poc/m79_native_click.m
//
// V0.0 R81 Objective-C 鼠标事件执行器 (修订 — 完全不发 mouse 的自检)
//
// 子命令:
//   --ax-check             只查 Accessibility, 不发任何事件
//   --self-test           不发任何 mouse 事件; 只做事件对象创建 + 释放 + 数值校验
//   --move x y             发一次 mouse-moved 到 (x, y); 需 AX 权限
//   x1 y1 [x2 y2 ...]      发多次 mouse-move + down/up pairs; 需 AX 权限
//
// 任何校验失败立即返回非 0 退出码 + JSON {result: "FAIL" | "BLOCKED", reason: ...}
// EVENT_POSTED != TARGET_EVENT_RECEIVED — 我们只能保证事件被系统派发,
// 实际目标是否接收需要外部验证 (R79 orchestrator 读 click count).

#import <Foundation/Foundation.h>
#import <ApplicationServices/ApplicationServices.h>
#import <CoreGraphics/CoreGraphics.h>
#import <unistd.h>
#import <stdio.h>
#import <stdlib.h>
#import <string.h>
#import <math.h>

// R86: exit codes — 0 only for real OK, non-zero for FAIL/BLOCKED/etc.
static int out_json_ok(const char *s) {
    printf("%s\n", s);
    fflush(stdout);
    return 0;
}
static int out_json_with_code(const char *s, int code) {
    printf("%s\n", s);
    fflush(stdout);
    return code;
}
static int out_fail(const char *reason) {
    char buf[512];
    snprintf(buf, sizeof buf, "{\"result\":\"FAIL\",\"reason\":\"%s\"}", reason);
    return out_json_with_code(buf, 10);
}
static int out_blocked(const char *reason) {
    char buf[512];
    snprintf(buf, sizeof buf, "{\"result\":\"BLOCKED\",\"reason\":\"%s\"}", reason);
    return out_json_with_code(buf, 11);
}
static int out_ok(const char *kind) {
    char buf[256];
    snprintf(buf, sizeof buf, "{\"result\":\"OK\",\"event\":\"%s\",\"note\":\"event_posted_not_target_received\"}", kind);
    return out_json_ok(buf);
}

static int ax_check(void) {
    BOOL ok = AXIsProcessTrusted();
    if (ok) return out_json_ok("{\"result\":\"OK\",\"accessibility_granted\":true}");
    return out_blocked("Accessibility not granted; user must enable in System Settings -> Privacy & Security -> Accessibility");
}

static int self_test(void) {
    // R81: 完全不发任何 mouse 事件. 只验证:
    //   1. AX 权限状态 (不 click)
    //   2. 参数解析 (无坐标参数时不报错)
    //   3. 事件对象能正确创建和释放
    // 不向系统派发任何 mouse event.
    if (!AXIsProcessTrusted()) {
        return out_blocked("Accessibility not granted; user must enable in System Settings");
    }
    // 创建 1 个 mouse-moved 事件对象, 立刻 release; 不 post 到系统
    CGPoint p = CGPointMake(0, 0);
    CGEventRef ev = CGEventCreateMouseEvent(NULL, kCGEventMouseMoved, p, kCGMouseButtonLeft);
    if (!ev) return out_fail("CGEventCreateMouseEvent returned NULL");
    CFRelease(ev);
    // 验证 CGEventPost 函数指针存在 (链接检查)
    void *pfn = (void *)CGEventPost;
    if (pfn == NULL) return out_fail("CGEventPost symbol missing");
    return out_json_ok("{\"result\":\"SELFTEST_OK\",\"accessibility_granted\":true,\"event_post_fn\":\"linked\",\"no_event_dispatched\":true}");
}

static int parse_double(const char *s, double *out, const char *name) {
    if (!s || !*s) return 0;
    char *end = NULL;
    double v = strtod(s, &end);
    if (end == s || *end != '\0') return 0;
    if (!isfinite(v)) return 0;
    *out = v;
    return 1;
}

static int do_one_click(double x, double y) {
    // R81 严格校验: 坐标有限数 + 屏幕边界
    if (!isfinite(x) || !isfinite(y)) return out_fail("coord not finite");
    CGDirectDisplayID display = CGMainDisplayID();
    CGRect bounds = CGDisplayBounds(display);
    if (x < bounds.origin.x - 1 || x > bounds.origin.x + bounds.size.width + 1 ||
        y < bounds.origin.y - 1 || y > bounds.origin.y + bounds.size.height + 1) {
        return out_fail("coord outside main display bounds");
    }
    CGPoint p = CGPointMake(x, y);
    CGEventRef move = CGEventCreateMouseEvent(NULL, kCGEventMouseMoved, p, kCGMouseButtonLeft);
    if (!move) return out_fail("CGEventCreateMouseEvent (move) returned NULL");
    CGEventPost(kCGHIDEventTap, move);
    CFRelease(move);
    usleep(120 * 1000);
    CGEventRef down = CGEventCreateMouseEvent(NULL, kCGEventLeftMouseDown, p, kCGMouseButtonLeft);
    CGEventRef up   = CGEventCreateMouseEvent(NULL, kCGEventLeftMouseUp,   p, kCGMouseButtonLeft);
    if (!down || !up) {
        if (down) CFRelease(down);
        if (up) CFRelease(up);
        return out_fail("CGEventCreateMouseEvent (down/up) returned NULL");
    }
    CGEventPost(kCGHIDEventTap, down);
    usleep(40 * 1000);
    CGEventPost(kCGHIDEventTap, up);
    CFRelease(down);
    CFRelease(up);
    usleep(380 * 1000);
    return out_ok("CLICK_POSTED_NOT_TARGET_RECEIVED");
}

int main(int argc, const char *argv[]) {
    if (argc < 2) {
        printf("usage:\n  %s --ax-check\n  %s --self-test\n  %s --move x y\n  %s x1 y1 [x2 y2 ...]\n",
               argv[0], argv[0], argv[0], argv[0]);
        return 64;  // usage = non-zero
    }
    if (strcmp(argv[1], "--ax-check") == 0) {
        return ax_check();  // 0 OK, 11 BLOCKED
    }
    if (strcmp(argv[1], "--self-test") == 0) {
        return self_test();  // 0 SELFTEST_OK, 10 FAIL
    }
    if (strcmp(argv[1], "--move") == 0) {
        if (argc < 4) return out_fail("--move requires x y");
        double x, y;
        if (!parse_double(argv[2], &x, "x") || !parse_double(argv[3], &y, "y")) {
            return out_fail("coord parse error");
        }
        if (!AXIsProcessTrusted()) return out_blocked("Accessibility not granted");
        if (!isfinite(x) || !isfinite(y)) return out_fail("coord not finite");
        CGPoint p = CGPointMake(x, y);
        CGEventRef ev = CGEventCreateMouseEvent(NULL, kCGEventMouseMoved, p, kCGMouseButtonLeft);
        if (!ev) return out_fail("CGEventCreateMouseEvent returned NULL");
        CGEventPost(kCGHIDEventTap, ev);
        CFRelease(ev);
        return out_ok("MOVE_POSTED");
    }
    if (((argc - 1) % 2) != 0) return out_fail("x y must be in pairs");
    if (!AXIsProcessTrusted()) return out_blocked("Accessibility not granted");
    int n = 0;
    for (int i = 1; i + 1 < argc; i += 2) {
        double x, y;
        if (!parse_double(argv[i], &x, "x") || !parse_double(argv[i+1], &y, "y")) {
            return out_fail("coord parse error");
        }
        if (do_one_click(x, y) != 0) return 6;
        n++;
    }
    char buf[128];
    snprintf(buf, sizeof buf, "{\"result\":\"OK\",\"clicked\":%d,\"note\":\"event_posted_not_target_received\"}", n);
    return out_json_ok(buf);
}

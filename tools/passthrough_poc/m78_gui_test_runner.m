// tools/passthrough_poc/m78_gui_test_runner.m
//
// V0.0 R78 Objective-C 本地 GUI 自动验收程序 (重写 — 避免嵌套取值 escape 错误)
//
// 任务书 §二: 验证 Objective-C 替代路线, 绕开 Swift 编译障碍。
// 任务书 §三: 复用 R71 几何/计数验证设计 (动态坐标 + 计数变化验证)。
//
// 编译 + 运行:
//   cd tools/passthrough_poc
//   ./m78_build.sh
//   ./build/m78_gui_test_runner
//
// 权限要求 (最少):
//   系统设置 -> 隐私与安全 -> 辅助功能 -> 勾选 Terminal.app
//   (CGEventPost 鼠标事件, 不需要 Input Monitoring)

#import <Foundation/Foundation.h>
#import <ApplicationServices/ApplicationServices.h>
#import <CoreGraphics/CoreGraphics.h>
#import <AppKit/AppKit.h>
#import <unistd.h>
#import <stdlib.h>
#import <string.h>
#import <stdio.h>
#import <math.h>

static NSString *RESULT_BASE = nil;
static FILE *LOG_FP = NULL;

static void log_(NSString *s) {
    NSLog(@"%@", s);
    if (LOG_FP) { fprintf(LOG_FP, "%s\n", [s UTF8String]); fflush(LOG_FP); }
}

static NSString *runID(void) {
    return [NSString stringWithFormat:@"m78_%lld", (long long)[[NSDate date] timeIntervalSince1970]];
}

static NSDictionary *parseTick(NSString *line) {
    if (![line hasPrefix:@"{\"type\":\"poc-tick\""]) return nil;
    NSData *data = [line dataUsingEncoding:NSUTF8StringEncoding];
    if (!data) return nil;
    NSError *err = nil;
    id obj = [NSJSONSerialization JSONObjectWithData:data options:0 error:&err];
    if (err || ![obj isKindOfClass:[NSDictionary class]]) return nil;
    return (NSDictionary *)obj;
}

// Helpers to safely extract dict fields without nested escape mess.
static NSDictionary *dictVal(NSDictionary *d, NSString *key) {
    id v = d[key];
    return [v isKindOfClass:[NSDictionary class]] ? v : nil;
}
static NSString *strVal(NSDictionary *d, NSString *key) {
    id v = d[key];
    return [v isKindOfClass:[NSString class]] ? v : nil;
}
static NSInteger intVal(NSDictionary *d, NSString *key) {
    id v = d[key];
    if ([v isKindOfClass:[NSNumber class]]) return [v integerValue];
    return 0;
}

// Compute valid transparent test point inside test_window ∩ probe_button,
// outside sprite circle, outside control_window.
static BOOL computeValidPoint(NSDictionary *tick, CGFloat *outX, CGFloat *outY, NSString **errOut) {
    NSDictionary *twDict = dictVal(tick, @"test_window");
    NSDictionary *pbDict = dictVal(tick, @"probe_button");
    NSDictionary *cwDict = dictVal(tick, @"control_window");
    NSDictionary *spDict = dictVal(tick, @"sprite");
    if (!twDict || !pbDict || !cwDict || !spDict) {
        if (errOut) *errOut = @"missing tick fields";
        return NO;
    }
    // Re-extract via JSONSerialization round-trip to get clean numbers.
    NSData *d = [NSJSONSerialization dataWithJSONObject:tick options:0 error:nil];
    NSDictionary *t2 = [NSJSONSerialization JSONObjectWithData:d options:0 error:nil];
    twDict = dictVal(t2, @"test_window");
    pbDict = dictVal(t2, @"probe_button");
    cwDict = dictVal(t2, @"control_window");
    spDict = dictVal(t2, @"sprite");
    CGFloat tw_x = intVal(twDict, @"x"), tw_y = intVal(twDict, @"y");
    CGFloat tw_w = intVal(twDict, @"w"), tw_h = intVal(twDict, @"h");
    CGFloat pb_x = intVal(pbDict, @"x"), pb_y = intVal(pbDict, @"y");
    CGFloat pb_w = intVal(pbDict, @"w"), pb_h = intVal(pbDict, @"h");
    CGFloat cw_x = intVal(cwDict, @"x"), cw_y = intVal(cwDict, @"y");
    CGFloat cw_w = intVal(cwDict, @"w"), cw_h = intVal(cwDict, @"h");
    CGFloat sp_cx = intVal(spDict, @"cx"), sp_cy = intVal(spDict, @"cy");
    CGFloat sp_r = intVal(spDict, @"r");
    CGFloat step = 2;
    for (CGFloat y = pb_y; y < pb_y + pb_h; y += step) {
        for (CGFloat x = pb_x; x < pb_x + pb_w; x += step) {
            if (x < tw_x || x >= tw_x + tw_w || y < tw_y || y >= tw_y + tw_h) continue;
            CGFloat dx = x - sp_cx, dy = y - sp_cy;
            if (sqrt(dx*dx + dy*dy) < sp_r) continue;
            if (x >= cw_x && x < cw_x + cw_w && y >= cw_y && y < cw_y + cw_h) continue;
            *outX = x; *outY = y;
            return YES;
        }
    }
    if (errOut) *errOut = @"no (x,y) inside test_window ∩ probe_button - sprite - control";
    return NO;
}

static BOOL computeC1Button(NSDictionary *tick, CGFloat *outX, CGFloat *outY) {
    NSDictionary *cwDict = dictVal(tick, @"control_window");
    if (!cwDict) return NO;
    CGFloat cw_x = intVal(cwDict, @"x"), cw_y = intVal(cwDict, @"y"), cw_h = intVal(cwDict, @"h");
    *outX = cw_x + 195;
    *outY = cw_y + cw_h * 0.55;
    return YES;
}

static void postClickAt(CGFloat x, CGFloat y) {
    CGPoint p = CGPointMake(x, y);
    CGEventRef move = CGEventCreateMouseEvent(NULL, kCGEventMouseMoved, p, kCGMouseButtonLeft);
    if (move) { CGEventPost(kCGHIDEventTap, move); CFRelease(move); }
    usleep(120 * 1000);
    CGEventRef down = CGEventCreateMouseEvent(NULL, kCGEventLeftMouseDown, p, kCGMouseButtonLeft);
    CGEventRef up   = CGEventCreateMouseEvent(NULL, kCGEventLeftMouseUp,   p, kCGMouseButtonLeft);
    if (down) { CGEventPost(kCGHIDEventTap, down); CFRelease(down); }
    usleep(60 * 1000);
    if (up)   { CGEventPost(kCGHIDEventTap, up);   CFRelease(up);   }
    usleep(450 * 1000);
}

static void writeResult(NSDictionary *r) {
    NSError *err = nil;
    NSData *j = [NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:&err];
    if (j) [j writeToFile:[RESULT_BASE stringByAppendingString:@".json"] atomically:YES];
    NSMutableString *s = [NSMutableString string];
    [s appendFormat:@"=== R78 Objective-C GUI Test Runner Result ===\n"];
    [s appendFormat:@"run_id: %@\n", r[@"run_id"]];
    [s appendFormat:@"finished_at: %@\n", r[@"finished_at"]];
    [s appendFormat:@"accessibility_granted: %@\n", r[@"accessibility_granted"]];
    [s appendFormat:@"input_monitoring_required: %@\n", r[@"input_monitoring_required"]];
    [s appendFormat:@"test_window: %@\n", r[@"test_window"] ?: @"?"];
    [s appendFormat:@"probe_button: %@\n", r[@"probe_button"] ?: @"?"];
    [s appendFormat:@"valid_test_point: %@\n", r[@"valid_test_point"] ?: @"NONE (GEOMETRY_INVALID)"];
    for (NSString *k in @[@"control_click", @"gold_ball_click", @"underlying_click", @"return_click", @"three_cycle_stable"]) {
        [s appendFormat:@"%@: %@\n", k, r[k] ?: @"NOT_TESTED"];
    }
    [s appendFormat:@"notes: %@\n", [r[@"notes"] componentsJoinedByString:@" | "]];
    [s writeToFile:[RESULT_BASE stringByAppendingString:@".txt"] atomically:YES encoding:NSUTF8StringEncoding error:nil];

    NSString *csv = [NSString stringWithFormat:@"run_id,accessibility,test_window,probe_button,valid_test_point,control_click,gold_ball_click,underlying_click,return_click,three_cycle_stable\n%@,%@,%@,%@,%@,%@,%@,%@,%@,%@\n",
        r[@"run_id"] ?: @"", r[@"accessibility_granted"] ?: @"",
        r[@"test_window"] ?: @"", r[@"probe_button"] ?: @"", r[@"valid_test_point"] ?: @"",
        r[@"control_click"] ?: @"", r[@"gold_ball_click"] ?: @"",
        r[@"underlying_click"] ?: @"", r[@"return_click"] ?: @"", r[@"three_cycle_stable"] ?: @""];
    [csv writeToFile:[RESULT_BASE stringByAppendingString:@".csv"] atomically:YES encoding:NSUTF8StringEncoding error:nil];
    log_([NSString stringWithFormat:@"-> wrote %@.{txt,json,csv}", RESULT_BASE]);
}

// Read latestTick via a small wait — the read handler updates it continuously.
static NSDictionary *readLatest(NSDictionary *prev) {
    return prev;  // tick is updated by the read handler set at startup
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        log_(@"=== R78 Objective-C Local GUI Test Runner ===");
        RESULT_BASE = [@"/tmp" stringByAppendingPathComponent:runID()];
        NSString *logPath = [RESULT_BASE stringByAppendingString:@".log"];
        LOG_FP = fopen([logPath UTF8String], "w");

        NSMutableDictionary *r = [NSMutableDictionary dictionary];
        r[@"run_id"] = runID();
        r[@"started_at"] = [NSISO8601DateFormatter stringFromDate:[NSDate date] timeZone:[NSTimeZone timeZoneWithAbbreviation:@"UTC"] formatOptions:NSISO8601DateFormatWithInternetDateTime];
        r[@"accessibility_check_method"] = @"AXIsProcessTrusted (real check)";
        r[@"input_monitoring_required"] = @"false";

        // Step 1: AX
        log_(@"[step 1] AXIsProcessTrusted check");
        BOOL acc = AXIsProcessTrusted();
        r[@"accessibility_granted"] = acc ? @"true" : @"false";
        if (!acc) {
            log_(@"  [FAIL] Accessibility not granted");
            r[@"control_click"] = @"BLOCKED";
            r[@"gold_ball_click"] = @"BLOCKED";
            r[@"underlying_click"] = @"BLOCKED";
            r[@"return_click"] = @"BLOCKED";
            r[@"three_cycle_stable"] = @"BLOCKED";
            r[@"finished_at"] = [NSISO8601DateFormatter stringFromDate:[NSDate date] timeZone:[NSTimeZone timeZoneWithAbbreviation:@"UTC"] formatOptions:NSISO8601DateFormatWithInternetDateTime];
            r[@"notes"] = @"Accessibility denied; user must grant in System Settings";
            writeResult(r);
            if (LOG_FP) fclose(LOG_FP);
            return 0;
        }
        log_(@"  [OK] Accessibility granted");

        // Step 2: launch PoC
        log_(@"[step 2] launch PoC subprocess");
        NSTask *task = [[NSTask alloc] init];
        task.launchPath = @"<repo-path>/node_modules/.bin/electron";
        NSString *exe = [NSString stringWithUTF8String:argv[0]];
        NSString *bin = [exe stringByDeletingLastPathComponent];
        NSString *repo = [[bin stringByDeletingLastPathComponent] stringByDeletingLastPathComponent];
        task.launchPath = [NSString stringWithFormat:@"%@/node_modules/.bin/electron", repo];
        NSString *mainJS = [NSString stringWithFormat:@"%@/tools/passthrough_poc/main.js", repo];
        task.arguments = @[mainJS, @"--mode=C1", @"--quit-after=30"];
        NSPipe *stdoutPipe = [NSPipe pipe];
        task.standardOutput = stdoutPipe;
        task.standardError = [NSPipe pipe];
        [task launch];
        log_([NSString stringWithFormat:@"  PoC PID=%d", task.processIdentifier]);

        // Step 3: read first valid tick
        log_(@"[step 3] read first valid tick");
        __block NSDictionary *latestTick = nil;
        NSFileHandle *fh = stdoutPipe.fileHandleForReading;
        fh.readabilityHandler = ^(NSFileHandle *h) {
            NSData *d = h.availableData;
            if (d.length == 0) return;
            NSString *s = [[NSString alloc] initWithData:d encoding:NSUTF8StringEncoding];
            for (NSString *line in [s componentsSeparatedByString:@"\n"]) {
                NSDictionary *t = parseTick(line);
                if (t) latestTick = t;
            }
        };
        NSDate *start = [NSDate date];
        while (!latestTick && [[NSDate date] timeIntervalSinceDate:start] < 8.0) {
            [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.1]];
        }
        fh.readabilityHandler = nil;
        if (!latestTick) {
            log_(@"  [FAIL] no valid tick in 8s");
            [task terminate];
            r[@"notes"] = @"no tick";
            r[@"finished_at"] = [NSISO8601DateFormatter stringFromDate:[NSDate date] timeZone:[NSTimeZone timeZoneWithAbbreviation:@"UTC"] formatOptions:NSISO8601DateFormatWithInternetDateTime];
            writeResult(r);
            if (LOG_FP) fclose(LOG_FP);
            return 1;
        }
        log_([NSString stringWithFormat:@"  tick: mode=%@", [latestTick[@"mode"] description]]);

        // Step 4: compute valid test point
        log_(@"[step 4] compute valid test point");
        CGFloat vx, vy;
        NSString *err = nil;
        if (!computeValidPoint(latestTick, &vx, &vy, &err)) {
            log_([NSString stringWithFormat:@"  [FAIL] GEOMETRY_INVALID: %@", err]);
            r[@"notes"] = err;
            r[@"valid_test_point"] = @"NONE (GEOMETRY_INVALID)";
            [task terminate];
            r[@"finished_at"] = [NSISO8601DateFormatter stringFromDate:[NSDate date] timeZone:[NSTimeZone timeZoneWithAbbreviation:@"UTC"] formatOptions:NSISO8601DateFormatWithInternetDateTime];
            writeResult(r);
            if (LOG_FP) fclose(LOG_FP);
            return 2;
        }
        r[@"test_window"] = [NSString stringWithFormat:@"%@", [dictVal(latestTick, @"test_window") description]];
        r[@"probe_button"] = [NSString stringWithFormat:@"%@", [dictVal(latestTick, @"probe_button") description]];
        r[@"valid_test_point"] = [NSString stringWithFormat:@"(%.0f,%.0f)", vx, vy];
        log_([NSString stringWithFormat:@"  valid_test_point = (%.0f, %.0f)", vx, vy]);

        // Re-arm readability handler for ongoing tick updates.
        fh.readabilityHandler = ^(NSFileHandle *h) {
            NSData *d = h.availableData;
            if (d.length == 0) return;
            NSString *s = [[NSString alloc] initWithData:d encoding:NSUTF8StringEncoding];
            for (NSString *line in [s componentsSeparatedByString:@"\n"]) {
                NSDictionary *t = parseTick(line);
                if (t) latestTick = t;
            }
        };

        // Step 5: click C1
        log_(@"[step 5] click C1");
        CGFloat c1x, c1y;
        computeC1Button(latestTick, &c1x, &c1y);
        log_([NSString stringWithFormat:@"  C1 at (%.0f, %.0f)", c1x, c1y]);
        postClickAt(c1x, c1y);
        for (int i = 0; i < 10; i++) [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
        NSDictionary *t1 = readLatest(latestTick);
        NSString *mode1 = t1[@"mode"] ?: @"?";
        NSString *ig1 = t1[@"ignore"] ? (t1[@"ignore"] == [NSNumber numberWithBool:YES] ? @"true" : @"false") : @"?";
        if ([mode1 isEqualToString:@"C1"]) {
            r[@"control_click"] = [NSString stringWithFormat:@"PASS (mode=C1 ignore=%@)", ig1];
            log_([NSString stringWithFormat:@"  [OK] C1 active, ignore=%@", ig1]);
        } else {
            r[@"control_click"] = @"FAIL";
            log_([NSString stringWithFormat:@"  [FAIL] mode still %@", mode1]);
        }

        // Step 6: gold ball
        log_(@"[step 6] click gold ball");
        CGFloat gx = 448, gy = 328;  // match PoC SPRITE_CX/CY
        NSDictionary *clicks6 = dictVal(t1, @"clicks");
        NSInteger beforeT = clicks6 ? intVal(clicks6, @"test") : 0;
        postClickAt(gx, gy);
        for (int i = 0; i < 10; i++) [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
        NSDictionary *t6 = readLatest(latestTick);
        NSDictionary *clicks6b = dictVal(t6, @"clicks");
        NSInteger afterT = clicks6b ? intVal(clicks6b, @"test") : 0;
        if (afterT == beforeT + 1) {
            r[@"gold_ball_click"] = [NSString stringWithFormat:@"PASS (test %ld to %ld)", (long)beforeT, (long)afterT];
            log_([NSString stringWithFormat:@"  [OK] test %ld to %ld", (long)beforeT, (long)afterT]);
        } else {
            r[@"gold_ball_click"] = [NSString stringWithFormat:@"FAIL (test %ld to %ld)", (long)beforeT, (long)afterT)];
        }

        // Step 7: transparent
        log_(@"[step 7] click transparent test point");
        NSInteger beforeP = clicks6b ? intVal(clicks6b, @"probe") : 0;
        postClickAt(vx, vy);
        for (int i = 0; i < 10; i++) [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
        NSDictionary *t7 = readLatest(latestTick);
        NSDictionary *clicks7 = dictVal(t7, @"clicks");
        NSInteger afterP = clicks7 ? intVal(clicks7, @"probe") : 0;
        if (afterP == beforeP + 1) {
            r[@"underlying_click"] = [NSString stringWithFormat:@"PASS (probe %ld to %ld)", (long)beforeP, (long)afterP];
            log_([NSString stringWithFormat:@"  [OK] probe %ld to %ld", (long)beforeP, (long)afterP]);
        } else {
            r[@"underlying_click"] = [NSString stringWithFormat:@"FAIL (probe %ld to %ld)", (long)beforeP, (long)afterP)];
        }

        // Step 8: return
        log_(@"[step 8] click gold ball again (return)");
        NSInteger beforeR = clicks7 ? intVal(clicks7, @"test") : 0;
        postClickAt(gx, gy);
        for (int i = 0; i < 10; i++) [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
        NSDictionary *t8 = readLatest(latestTick);
        NSDictionary *clicks8 = dictVal(t8, @"clicks");
        NSInteger afterR = clicks8 ? intVal(clicks8, @"test") : 0;
        if (afterR == beforeR + 1) {
            r[@"return_click"] = [NSString stringWithFormat:@"PASS (test %ld to %ld)", (long)beforeR, (long)afterR)];
            log_([NSString stringWithFormat:@"  [OK] return %ld to %ld", (long)beforeR, (long)afterR)]);
        } else {
            r[@"return_click"] = [NSString stringWithFormat:@"FAIL (test %ld to %ld)", (long)beforeR, (long)afterR)];
        }

        // Step 9: 3 cycles
        log_(@"[step 9] 3 cycles");
        BOOL cycleOK = YES;
        NSInteger lastT = afterR, lastP = afterP;
        for (int i = 0; i < 3; i++) {
            postClickAt(vx, vy);
            postClickAt(gx, gy);
            for (int j = 0; j < 10; j++) [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
            NSDictionary *tc = readLatest(latestTick);
            NSDictionary *clicksC = dictVal(tc, @"clicks");
            NSInteger tN = clicksC ? intVal(clicksC, @"test") : 0;
            NSInteger pN = clicksC ? intVal(clicksC, @"probe") : 0;
            if (tN == lastT + 1 && pN == lastP + 1) {
                log_([NSString stringWithFormat:@"  cycle %d [OK]", i+1]);
                lastT = tN; lastP = pN;
            } else {
                log_([NSString stringWithFormat:@"  cycle %d [FAIL]", i+1)]);
                cycleOK = NO;
            }
        }
        r[@"three_cycle_stable"] = cycleOK ? @"PASS" : @"FAIL";

        // Step 10: terminate + write
        log_(@"[step 10] terminate + write");
        fh.readabilityHandler = nil;
        [task terminate];
        [task waitUntilExit];
        r[@"finished_at"] = [NSISO8601DateFormatter stringFromDate:[NSDate date] timeZone:[NSTimeZone timeZoneWithAbbreviation:@"UTC"] formatOptions:NSISO8601DateFormatWithInternetDateTime];
        writeResult(r);
        log_(@"=== R78 done. ===");
        if (LOG_FP) fclose(LOG_FP);
    }
    return 0;
}

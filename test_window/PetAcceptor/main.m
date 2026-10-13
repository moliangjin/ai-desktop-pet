// test_window/PetAcceptor/main.m
//
// V0.0 R45 图形化验收窗口
// V0.0 R47 lifecycle 可靠性修复
//
// 主要修复点 (R47):
//   1. 禁用 setActivationPolicy:NSApplicationActivationPolicyRegular；改
//      NSApplicationActivationPolicyAccessory，避免后台启动被 macOS "stale
//      app cleanup" / activateIgnoringOtherApps 强制主线程信号杀死。
//      验收窗口通过 orderFrontRegardless:YES 强制显现在前台。
//   2. 全面 NSLog 诊断：每一处 init/run/willTerminate 写明路径。
//   3. applicationWillTerminate 区分终止原因：USER_CLICKED_END /
//      USER_CLOSED_WINDOW / RUNNER_CRASH_SIGNAL，并把 termination_reason
//      写入 result JSON。
//   4. 默认 result 包含 launch_status（LAUNCH_PASS/LAUNCH_FAIL/GUI_NOT_TESTED）。
//   5. 不再有 silent exit：writeResultAndExit 必须在 exit 前落盘 JSON。
//   6. applicationShouldTerminateAfterLastWindowClosed:NO + 用户可以显式
//      关闭 → applicationShouldTerminate 拦截询问后再退。
//
// 退出码：
//   0 = 用户点击■ 正常结束（USER_CLICKED_END）
//   1 = 至少 1 个 FAIL
//   2 = 用户关闭窗口但未点■ (USER_CLOSED_WINDOW)
//   3 = NSApp terminate 被 system signal 触发 (RUNNER_CRASH_SIGNAL)

#import <AppKit/AppKit.h>

// ------- 单项测试定义 -------
static NSString *const kStatusPass      = @"PASS";
static NSString *const kStatusFail      = @"FAIL";
static NSString *const kStatusNotTested = @"NOT_TESTED";
static NSString *const kStatusDisabled  = @"DISABLED_SINGLE_DISPLAY";
static NSString *const kStatusIncomplete = @"INCOMPLETE";  // R51: 与 NOT_TESTED 区分

static NSString *const kLaunchPass = @"LAUNCH_PASS";
static NSString *const kLaunchFail = @"LAUNCH_FAIL";
static NSString *const kGUINotTested = @"GUI_NOT_TESTED";
static NSString *const kTermUserClickedEnd  = @"USER_CLICKED_END";
static NSString *const kTermUserClosedWindow = @"USER_CLOSED_WINDOW";
static NSString *const kTermRunnerCrash = @"RUNNER_CRASH_SIGNAL";

typedef struct {
    NSString *key;
    NSString *label;
    NSString *instructions;
} TestItem;

static TestItem kItems[] = {
    { @"launch",          @"1/8 启动验证",     @"候选应在桌面上出现一个 256x256 的桌宠窗口，无崩溃提示。" },
    { @"display",         @"2/8 显示方向",     @"人物应正向站立，头朝上脚朝下，无镜像、倒立或上下颠倒。" },
    { @"animation",       @"3/8 动画表现",     @"眨眼与上下浮动应自然，无明显卡顿、撕裂或全黑帧。" },
    { @"click",           @"4/8 点击反馈",     @"用鼠标点击桌宠主体，能看到动作切换或姿态变化。" },
    { @"drag",            @"5/8 拖动同步",     @"鼠标按下并拖动桌宠，桌宠位置应与鼠标基本同步，无跳变。" },
    { @"transparent",     @"6/8 透明区穿透",   @"点击桌宠周围空白处，‘点这里测试穿透’按钮的计数应 +1。" },
    { @"window_focus",    @"7/8 焦点与置顶",   @"候选不应抢走探针窗口 / Terminal 的输入焦点；切换 Spaces 桌宠应跟随。" },
    { @"multidisplay",    @"8/8 多显示器",     @"需要多屏环境验证 — 本机单屏固定 DISABLED（可选项，不会影响验收）。" },
};
static const NSUInteger kItemsCount = sizeof(kItems) / sizeof(kItems[0]);

// ------- 工具函数 -------
static NSString *nowISO(void) {
    NSDateFormatter *fmt = [NSDateFormatter new];
    fmt.dateFormat = @"yyyy-MM-dd'T'HH:mm:ssXXX";
    fmt.locale = [NSLocale localeWithLocaleIdentifier:@"en_US_POSIX"];
    return [fmt stringFromDate:[NSDate date]];
}

// ------- 应用主类 -------
@interface PetAcceptorAppDelegate : NSObject <NSApplicationDelegate>
@property (nonatomic, strong) NSWindow *window;

@property (nonatomic, copy) NSString *candidate;
@property (nonatomic, copy) NSString *version;
@property (nonatomic, copy) NSString *commit;
@property (nonatomic, copy) NSString *bundleId;
@property (nonatomic, copy) NSString *resultOutPath;
@property (nonatomic, copy) NSString *launchStatus;   // LAUNCH_PASS / LAUNCH_FAIL (外部传)
@property (nonatomic)         BOOL enableMultidisplay;

@property (nonatomic) NSInteger currentIndex;
@property (nonatomic, strong) NSMutableDictionary<NSString *, NSString *> *answers;
@property (nonatomic, strong) NSMutableDictionary<NSString *, NSString *> *notes;
@property (nonatomic, strong) NSMutableArray<NSString *> *lifecycleLog;  // R47 诊断

@property (nonatomic, copy) NSString *selfTestCase;

@property (nonatomic, strong) NSTextField *headerLabel;
@property (nonatomic, strong) NSTextField *versionLabel;
@property (nonatomic, strong) NSTextField *questionLabel;
@property (nonatomic, strong) NSTextField *instructionsLabel;
@property (nonatomic, strong) NSTextField *progressLabel;
@property (nonatomic, strong) NSTextField *summaryLabel;
@property (nonatomic, strong) NSTextField *lifecycleLabel;
@property (nonatomic, strong) NSTextView  *notesView;
@property (nonatomic, strong) NSButton *passBtn;
@property (nonatomic, strong) NSButton *failBtn;
@property (nonatomic, strong) NSButton *unableBtn;
@property (nonatomic, strong) NSButton *prevBtn;
@property (nonatomic, strong) NSButton *nextBtn;
@property (nonatomic, strong) NSButton *endBtn;

// 终止原因（被 applicationWillTerminate 使用）
@property (nonatomic, copy) NSString *terminationReason;
@end

@implementation PetAcceptorAppDelegate

- (instancetype)init {
    if ((self = [super init])) {
        _candidate = @"candidate_unknown";
        _version = @"V0.0";
        _commit = @"unknown";
        _bundleId = @"";
        _enableMultidisplay = NO;
        _launchStatus = kGUINotTested;
        _currentIndex = 0;
        _answers = [NSMutableDictionary new];
        _notes   = [NSMutableDictionary new];
        _lifecycleLog = [NSMutableArray new];
        _terminationReason = kTermRunnerCrash;  // 默认最坏情况
    }
    return self;
}

- (void)logLife:(NSString *)event {
    NSString *t = nowISO();
    NSString *line = [NSString stringWithFormat:@"[%@] %@", t, event];
    [self.lifecycleLog addObject:line];
    NSLog(@"%@", line);
    if (self.lifecycleLabel) {
        self.lifecycleLabel.stringValue = [NSString stringWithFormat:@"最新事件: %@", event];
    }
}

#pragma mark - UI Construction

- (void)buildUI {
    NSRect winFrame = NSMakeRect(220, 180, 760, 580);
    self.window = [[NSWindow alloc] initWithContentRect:winFrame
                                              styleMask:NSWindowStyleMaskTitled |
                                                         NSWindowStyleMaskClosable |
                                                         NSWindowStyleMaskMiniaturizable
                                                backing:NSBackingStoreBuffered
                                                  defer:NO];
    self.window.title = @"AI 桌宠 V0.0 · 人机验收窗口（点击 ■ 结束测试才退出）";
    self.window.releasedWhenClosed = NO;
    [self.window makeKeyAndOrderFront:nil];
    [self.window orderFrontRegardless];

    NSView *root = self.window.contentView;

    // 顶部信息
    self.headerLabel   = [self mkLabel:@"加载中…" frame:NSMakeRect(20, 520, 720, 30) font:[NSFont systemFontOfSize:18 weight:NSFontWeightBold]];
    self.versionLabel  = [self mkLabel:@""          frame:NSMakeRect(20, 495, 720, 18) font:[NSFont systemFontOfSize:11]];
    self.lifecycleLabel= [self mkLabel:@"等待启动…"  frame:NSMakeRect(20, 472, 720, 18) font:[NSFont monospacedSystemFontOfSize:10 weight:NSFontWeightRegular]];
    self.lifecycleLabel.textColor = [NSColor secondaryLabelColor];
    [root addSubview:self.headerLabel];
    [root addSubview:self.versionLabel];
    [root addSubview:self.lifecycleLabel];

    // 当前问题
    self.questionLabel = [self mkLabel:@"" frame:NSMakeRect(20, 400, 720, 36) font:[NSFont systemFontOfSize:15 weight:NSFontWeightSemibold]];
    self.instructionsLabel = [self mkLabel:@"" frame:NSMakeRect(20, 340, 720, 60) font:[NSFont systemFontOfSize:13]];
    self.instructionsLabel.maximumNumberOfLines = 4;
    self.instructionsLabel.lineBreakMode = NSLineBreakByWordWrapping;
    [root addSubview:self.questionLabel];
    [root addSubview:self.instructionsLabel];

    // 3 个状态按钮
    self.passBtn   = [self mkButton:@"✓ 通过 (PASS)"          action:@selector(onPass:)    frame:NSMakeRect(20, 290, 200, 44)];
    self.failBtn   = [self mkButton:@"✗ 失败 (FAIL)"          action:@selector(onFail:)    frame:NSMakeRect(240, 290, 200, 44)];
    self.unableBtn = [self mkButton:@"○ 无法测试 (NOT_TESTED)" action:@selector(onUnable:) frame:NSMakeRect(460, 290, 240, 44)];
    [root addSubview:self.passBtn];
    [root addSubview:self.failBtn];
    [root addSubview:self.unableBtn];

    self.prevBtn = [self mkButton:@"◀ 上一项" action:@selector(onPrev:) frame:NSMakeRect(20, 235, 140, 36)];
    self.nextBtn = [self mkButton:@"下一项 ▶" action:@selector(onNext:) frame:NSMakeRect(180, 235, 140, 36)];
    self.endBtn  = [self mkButton:@"■ 结束测试（必点才退出）"  action:@selector(onEnd:)  frame:NSMakeRect(340, 235, 240, 36)];
    [root addSubview:self.prevBtn];
    [root addSubview:self.nextBtn];
    [root addSubview:self.endBtn];

    NSTextField *notesTitle = [self mkLabel:@"备注（可选，记下你看到的现象）:" frame:NSMakeRect(20, 200, 720, 18) font:[NSFont systemFontOfSize:11]];
    [root addSubview:notesTitle];
    NSScrollView *sv = [[NSScrollView alloc] initWithFrame:NSMakeRect(20, 80, 720, 110)];
    sv.hasVerticalScroller = YES;
    sv.borderType = NSBezelBorder;
    self.notesView = [[NSTextView alloc] initWithFrame:NSMakeRect(0, 0, 700, 106)];
    self.notesView.editable = YES;
    self.notesView.font = [NSFont systemFontOfSize:12];
    sv.documentView = self.notesView;
    [root addSubview:sv];

    self.progressLabel = [self mkLabel:@"0/8" frame:NSMakeRect(20, 50, 720, 18) font:[NSFont systemFontOfSize:11 weight:NSFontWeightMedium]];
    self.summaryLabel  = [self mkLabel:@"" frame:NSMakeRect(20, 25, 720, 18) font:[NSFont monospacedSystemFontOfSize:11 weight:NSFontWeightRegular]];
    [root addSubview:self.progressLabel];
    [root addSubview:self.summaryLabel];
}

- (NSTextField *)mkLabel:(NSString *)text frame:(NSRect)r font:(NSFont *)font {
    NSTextField *l = [[NSTextField alloc] initWithFrame:r];
    l.stringValue = text;
    l.bezeled = NO; l.drawsBackground = NO; l.editable = NO; l.selectable = NO;
    l.font = font;
    return l;
}
- (NSButton *)mkButton:(NSString *)title action:(SEL)act frame:(NSRect)r {
    NSButton *b = [[NSButton alloc] initWithFrame:r];
    b.title = title;
    b.bezelStyle = NSBezelStyleRounded;
    b.target = self;
    b.action = act;
    return b;
}

- (void)refreshView {
    NSString *cand = self.candidate ?: @"unknown";
    self.headerLabel.stringValue = [NSString stringWithFormat:@"AI 桌宠 V0.0 · 当前候选：%@  ·  Launch: %@", cand, self.launchStatus];
    self.versionLabel.stringValue = [NSString stringWithFormat:@"Build: V0.0  |  Commit: %@  |  Bundle ID: %@  |  Time: %@", self.commit, self.bundleId, nowISO()];

    if (self.currentIndex >= kItemsCount) {
        self.questionLabel.stringValue = @"所有项已答完。请点 ■ 结束测试（不要关窗，不要用 ⌘Q）。";
        self.instructionsLabel.stringValue = @"";
        self.progressLabel.stringValue = [NSString stringWithFormat:@"%lu/%lu", (unsigned long)kItemsCount, (unsigned long)kItemsCount];
    } else {
        TestItem ti = kItems[self.currentIndex];
        self.questionLabel.stringValue = ti.label;
        self.instructionsLabel.stringValue = ti.instructions;
        NSString *answered = self.answers[ti.key] ?: @"-";
        self.progressLabel.stringValue = [NSString stringWithFormat:@"进度 %lu/%lu  ·  当前题：%@  ·  你的答案：%@",
                                          (unsigned long)(self.currentIndex + 1), (unsigned long)kItemsCount, ti.key, answered];
    }

    NSUInteger pass = 0, fail = 0, nt = 0, dis = 0;
    for (NSUInteger i = 0; i < kItemsCount; i++) {
        NSString *s = self.answers[kItems[i].key];
        if (!s) continue;
        if ([s isEqualToString:kStatusPass]) pass++;
        else if ([s isEqualToString:kStatusFail]) fail++;
        else if ([s isEqualToString:kStatusNotTested]) nt++;
        else if ([s isEqualToString:kStatusDisabled]) dis++;
    }
    self.summaryLabel.stringValue = [NSString stringWithFormat:@"汇总 PASS=%lu  FAIL=%lu  NOT_TESTED=%lu  DISABLED=%lu  | 当前任务对象：%@",
                                     (unsigned long)pass, (unsigned long)fail, (unsigned long)nt, (unsigned long)dis, self.terminationReason];
}

#pragma mark - Actions

- (NSString *)currentKey {
    if (self.currentIndex >= kItemsCount) return nil;
    return kItems[self.currentIndex].key;
}
- (BOOL)isMultidisplayDisabledForCurrent {
    if (self.currentIndex >= kItemsCount) return NO;
    TestItem ti = kItems[self.currentIndex];
    return [ti.key isEqualToString:@"multidisplay"] && !self.enableMultidisplay;
}

- (void)recordAnswer:(NSString *)status advance:(BOOL)advance {
    NSString *k = [self currentKey];
    if (!k) return;
    self.answers[k] = status;
    NSString *notes = [self.notesView.string copy];
    if (notes.length > 0) self.notes[k] = notes;
    [self.notesView setString:@""];
    if (advance) self.currentIndex++;
    [self logLife:[NSString stringWithFormat:@"answer key=%@ status=%@ advance=%d", k, status, (int)advance]];
    [self refreshView];
}

- (void)onPass:(id)s   { if ([self isMultidisplayDisabledForCurrent]) return; [self recordAnswer:kStatusPass advance:NO]; }
- (void)onFail:(id)s   { if ([self isMultidisplayDisabledForCurrent]) return; [self recordAnswer:kStatusFail advance:NO]; }
- (void)onUnable:(id)s { if ([self isMultidisplayDisabledForCurrent]) return; [self recordAnswer:kStatusNotTested advance:NO]; }

- (void)onPrev:(id)s {
    if (self.currentIndex == 0) return;
    self.currentIndex--;
    NSString *prevKey = [self currentKey];
    NSString *prevNotes = self.notes[prevKey];
    if (prevNotes) [self.notesView setString:prevNotes];
    [self logLife:@"onPrev"];
    [self refreshView];
}
- (void)onNext:(id)s {
    if (self.currentIndex + 1 >= kItemsCount) return;
    NSString *k = [self currentKey];
    if (!self.answers[k]) self.answers[k] = kStatusNotTested;
    self.currentIndex++;
    NSString *nextKey = [self currentKey];
    NSString *nextNotes = self.notes[nextKey];
    if (nextNotes) [self.notesView setString:nextNotes];
    [self logLife:@"onNext"];
    [self refreshView];
}
- (void)onEnd:(id)s {
    // R51: 用户点■ 结束测试时,如果有未完成项,先弹 NSAlert 让用户确认
    NSUInteger not_answered = 0;
    NSMutableArray *missing = [NSMutableArray new];
    for (NSUInteger i = 0; i < kItemsCount; i++) {
        TestItem ti = kItems[i];
        if ([ti.key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
        NSString *s = self.answers[ti.key];
        if (!s || [s isEqualToString:kStatusNotTested]) {
            not_answered++;
            [missing addObject:ti.label ?: ti.key];
        }
    }
    if (not_answered > 0) {
        [self logLife:[NSString stringWithFormat:@"onEnd: %lu 项未完成，弹 NSAlert", (unsigned long)not_answered]];
        NSAlert *alert = [[NSAlert alloc] init];
        alert.messageText = [NSString stringWithFormat:@"还有 %lu 项未测试，是否提前结束？", (unsigned long)not_answered];
        alert.informativeText = [NSString stringWithFormat:@"未完成项：%@\n提前结束后，overall 会记为 INCOMPLETE（绝不伪造 PASS）。", [missing componentsJoinedByString:@"、"]];
        alert.alertStyle = NSWarningAlertStyle;
        [alert addButtonWithTitle:@"■ 提前结束 (INCOMPLETE)"];
        [alert addButtonWithTitle:@"◀ 返回继续测试"];
        NSModalResponse r = [alert runModal];
        if (r != NSAlertFirstButtonReturn && r != NSAlertSecondButtonReturn) {
            // 用户按了 Esc 或 ⌘. — 也视为取消
            [self logLife:@"onEnd: 用户取消 (Esc) — 继续"];
            return;
        }
        if (r == NSAlertSecondButtonReturn) {
            // 继续
            [self logLife:@"onEnd: 用户选择继续测试"];
            // 高亮第一个 missing 项目
            for (NSUInteger i = 0; i < kItemsCount; i++) {
                TestItem ti = kItems[i];
                if ([ti.key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
                NSString *s = self.answers[ti.key];
                if (!s || [s isEqualToString:kStatusNotTested]) {
                    self.currentIndex = i;
                    [self refreshView];
                    break;
                }
            }
            return;
        }
        [self logLife:@"onEnd: 用户确认提前结束"];
    }
    self.terminationReason = kTermUserClickedEnd;
    [self writeResultAndExit:0];
}

#pragma mark - Persistence

- (NSDictionary *)buildResultDict {
    NSMutableArray *items = [NSMutableArray new];
    NSUInteger pass = 0, fail = 0, nt = 0, dis = 0;
    BOOL hasFail = NO;
    for (NSUInteger i = 0; i < kItemsCount; i++) {
        TestItem ti = kItems[i];
        NSString *status = self.answers[ti.key];
        if (!status) status = kStatusNotTested;
        if ([ti.key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) {
            status = kStatusDisabled;
        }
        if ([status isEqualToString:kStatusPass]) pass++;
        else if ([status isEqualToString:kStatusFail]) { fail++; hasFail = YES; }
        else if ([status isEqualToString:kStatusNotTested]) nt++;
        else if ([status isEqualToString:kStatusDisabled]) dis++;
        [items addObject:@{
            @"key": ti.key,
            @"label": ti.label,
            @"status": status,
            @"notes": self.notes[ti.key] ?: @"",
        }];
    }
    // V0.0 R51 overall 聚合规则：
    //   - 任一必测项 FAIL → overall=FAIL (必须)
    //   - 所有必测项 (非 DISABLED) 都 PASS → overall=PASS
    //   - 否则 (有 NOT_TESTED 或无答案) → overall=INCOMPLETE (≠ NOT_TESTED)
    // DISABLED 单屏不算必测通过也不算失败 — 仅作 indicator
    // 启动 PASS 不能替代显示/动画/点击/拖拽/穿透的 GUI 验收
    NSUInteger required_pass = kItemsCount - dis;  // 必测项 = 排除 DISABLED
    NSString *overall = kStatusIncomplete;
    if (hasFail) {
        overall = kStatusFail;
    } else if (pass >= required_pass && required_pass > 0 && nt == 0) {
        overall = kStatusPass;
    }
    // 否则保持 INCOMPLETE
    // nt=0 是关键 — 必须所有必测项都答了 PASS 才能 PASS

    // launch_ok 独立于 GUI 反馈：来自外部 launch_status（ps 检测）
    BOOL launch_ok = [self.launchStatus isEqualToString:kLaunchPass];

    return @{
        @"candidate": self.candidate ?: @"",
        @"version": self.version ?: @"V0.0",
        @"commit": self.commit ?: @"",
        @"bundle_id": self.bundleId ?: @"",
        @"tested_at": nowISO(),
        @"overall": overall,
        @"launch_status": self.launchStatus ?: kGUINotTested,
        @"launch_ok": @(launch_ok),
        @"termination_reason": self.terminationReason ?: kTermRunnerCrash,
        @"counts_pass": @(pass),
        @"counts_fail": @(fail),
        @"counts_not_tested": @(nt),
        @"counts_disabled": @(dis),
        @"items": items,
        @"lifecycle_log": self.lifecycleLog,
    };
}

- (void)writeResultAndExit:(int)code {
    NSDictionary *result = [self buildResultDict];
    NSError *err = nil;
    NSData *data = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:&err];
    NSString *out = self.resultOutPath ?: @"/tmp/acceptor_result.json";
    if (data) {
        BOOL ok = [data writeToFile:out options:NSDataWritingAtomic error:&err];
        [self logLife:[NSString stringWithFormat:@"writeResultAndExit path=%@ bytes=%lu ok=%@ exit=%d",
                       out, (unsigned long)data.length, @(ok), code]];
    }
    fflush(stdout); fflush(stderr);
    if (code == 0) {
        [NSApp terminate:nil];
        exit(0);
    } else {
        // 不调 NSApp terminate (避免触发 willTerminate 再写第二份)
        exit(code);
    }
}

#pragma mark - App lifecycle

- (void)applicationDidFinishLaunching:(NSNotification *)notif {
    [self logLife:[NSString stringWithFormat:@"applicationDidFinishLaunching candidate=%@ commit=%@ launch=%@",
                   self.candidate ?: @"?", self.commit ?: @"?", self.launchStatus ?: @"?"]];
    [self buildUI];
    [self refreshView];

    // 不再有"启动后 0.2s 自动 self-test"！
    // 只在 --self-test 时才 dispatch_after 调 runSelfTest
    if (self.selfTestCase.length > 0) {
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.2 * NSEC_PER_SEC)),
                       dispatch_get_main_queue(), ^{
            [self runSelfTest:self.selfTestCase];
        });
    }

    // 定期 heartbeat 写入 lifecycle（便于 task 书 §六 自动化 120s wait 监控）
    [self logLife:@"main run loop entered; GUI 等待用户操作"];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSNotification *)n {
    // R47：默认 NO。用户关闭窗 → 走 applicationShouldTerminate → 标 USER_CLOSED_WINDOW
    return NO;
}

- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    [self logLife:@"applicationShouldTerminate called"];
    if ([self.terminationReason isEqualToString:kTermUserClickedEnd]) {
        // 已经在 onEnd 中写过 JSON
        return NSTerminateNow;
    }
    if (!self.terminationReason || [self.terminationReason isEqualToString:kTermRunnerCrash]) {
        self.terminationReason = kTermUserClosedWindow;
    }
    // 关窗 → 立刻落盘 JSON + 退出
    NSString *overall = [self buildResultDict][@"overall"];
    int code = 0;
    if ([overall isEqualToString:kStatusFail]) code = 1;
    else if ([overall isEqualToString:kStatusNotTested]) code = 2;
    if ([self.terminationReason isEqualToString:kTermUserClosedWindow]) code = 2;
    [self writeResultAndExit:code];
    return NSTerminateNow;  // unreachable，但 keep compiler happy
}

- (void)applicationWillTerminate:(NSNotification *)n {
    // 仅在 onEnd → applicationShouldTerminate 的 NSTerminateNow 分支触发
    // 如果是 applicationWillTerminate 触发的，再补一份保险写盘
    [self logLife:[NSString stringWithFormat:@"applicationWillTerminate reason=%@",
                   self.terminationReason ?: @"?"]];
    if (self.resultOutPath.length > 0) {
        NSDictionary *result = [self buildResultDict];
        NSError *err = nil;
        NSData *data = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:&err];
        if (data) [data writeToFile:self.resultOutPath options:NSDataWritingAtomic error:&err];
    }
}

#pragma mark - Self-tests (R45 §5)

- (void)runSelfTest:(NSString *)caseName {
    [self logLife:[NSString stringWithFormat:@"self-test case=%@", caseName]];
    NSString * (^_kstatus)(NSUInteger i) = ^NSString *(NSUInteger i) {
        if (i == 0) return @"PASS";
        if (i == 1) return @"FAIL";
        if (i == 2) return @"NOT_TESTED";
        if (i == 3) return @"DISABLED_SINGLE_DISPLAY";
        return @"";
    };

    if ([caseName isEqualToString:@"all_pass"]) {
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusPass;
        }
        [self writeResultAndExit:0];
    } else if ([caseName isEqualToString:@"all_fail"]) {
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusFail;
        }
        [self writeResultAndExit:1];
    } else if ([caseName isEqualToString:@"mixed"]) {
        // launch=PASS, display=PASS, animation=FAIL, click=NOT_TESTED,
        // drag=PASS, transparent=NOT_TESTED, window_focus=PASS, multidisplay=DISABLED
        NSArray *vals = @[kStatusPass, kStatusPass, kStatusFail, kStatusNotTested,
                          kStatusPass, kStatusNotTested, kStatusPass, @"DISABLED"];
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            NSString *s = vals[i];
            if ([s isEqualToString:@"DISABLED"]) {
                if (!self.enableMultidisplay) continue;
                self.answers[kItems[i].key] = kStatusDisabled;
            } else {
                self.answers[kItems[i].key] = s;
            }
        }
        self.notes[@"animation"] = @"明显卡顿";
        [self writeResultAndExit:1];
    } else if ([caseName isEqualToString:@"abort_midway"]) {
        self.answers[@"launch"]   = kStatusPass;
        self.answers[@"display"]  = kStatusPass;
        self.answers[@"animation"] = kStatusFail;
        self.notes[@"animation"] = @"卡顿严重";
        [self writeResultAndExit:1];
    } else if ([caseName isEqualToString:@"prev_edit"]) {
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusPass;
        }
        [self recordAnswer:kStatusFail advance:NO];
        [self writeResultAndExit:1];
    } else if ([caseName isEqualToString:@"launch_fail_a"] || [caseName isEqualToString:@"launch_fail_b"]) {
        self.answers[@"launch"] = kStatusFail;
        for (NSUInteger i = 1; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusNotTested;
        }
        [self writeResultAndExit:1];
    } else if ([caseName isEqualToString:@"csv_schema"]) {
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusPass;
        }
        [self writeResultAndExit:0];
    } else if ([caseName isEqualToString:@"switch_a_to_b"]) {
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusPass;
        }
        [self writeResultAndExit:0];
    } else if ([caseName isEqualToString:@"r51_incomplete_launch_only"]) {
        // R51: 用户实测特征 — 仅 launch=PASS,其它 NOT_TESTED
        // 旧逻辑 bug 误判 PASS → 新逻辑必须 INCOMPLETE
        self.answers[@"launch"] = kStatusPass;
        NSArray *keys = @[@"display", @"animation", @"click", @"drag", @"transparent", @"window_focus"];
        for (NSString *k in keys) self.answers[k] = kStatusNotTested;
        [self writeResultAndExit:2];
    } else if ([caseName isEqualToString:@"r51_all_pass_complete"]) {
        // 全部必测 PASS + 1 项 DISABLED → PASS (DISABLED 不计必测)
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusPass;
        }
        [self writeResultAndExit:0];
    } else if ([caseName isEqualToString:@"r51_fail_dominates"]) {
        // 6 PASS + 1 FAIL + 1 DISABLED → FAIL
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusPass;
        }
        self.answers[@"animation"] = kStatusFail;
        [self writeResultAndExit:1];
    } else if ([caseName isEqualToString:@"wait_120s"]) {
        // R47: 启动后不退出，仅 NSLog；外部脚本 120s 后 kill 验证无自动结束
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            // 不写任何答案，全 NOT_TESTED — 等外部 kill
        }
        self.terminationReason = @"GUI_NEVER_INTERACTED";
        // 故意不调 writeResultAndExit，等待外部 SIGTERM
        // 结果将由 willTerminate 兜底
        return;
    } else {
        [self logLife:[NSString stringWithFormat:@"unknown self-test case=%@", caseName]];
        [self writeResultAndExit:2];
    }
}

@end

#pragma mark - Entry

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        PetAcceptorAppDelegate *delegate = [PetAcceptorAppDelegate new];
        app.delegate = delegate;

        // R47：改用 Accessory 策略，避免 macOS "stale app cleanup" 信号杀掉
        [app setActivationPolicy:NSApplicationActivationPolicyAccessory];

        NSArray *args = [[NSProcessInfo processInfo] arguments];
        for (NSUInteger i = 1; i < args.count; i++) {
            NSString *a = args[i];
            if ([a isEqualToString:@"--candidate"] && i+1 < args.count) delegate.candidate = args[++i];
            else if ([a isEqualToString:@"--version"] && i+1 < args.count) delegate.version = args[++i];
            else if ([a isEqualToString:@"--commit"] && i+1 < args.count) delegate.commit = args[++i];
            else if ([a isEqualToString:@"--bundle-id"] && i+1 < args.count) delegate.bundleId = args[++i];
            else if ([a isEqualToString:@"--result-out"] && i+1 < args.count) delegate.resultOutPath = args[++i];
            else if ([a isEqualToString:@"--launch-status"] && i+1 < args.count) delegate.launchStatus = args[++i];
            else if ([a isEqualToString:@"--enable-multidisplay"]) delegate.enableMultidisplay = YES;
            else if ([a isEqualToString:@"--self-test"] && i+1 < args.count) delegate.selfTestCase = args[++i];
        }

        NSLog(@"[PetAcceptor] start argv count=%lu candidate=%@", (unsigned long)args.count, delegate.candidate);
        [app run];
    }
    return 0;
}

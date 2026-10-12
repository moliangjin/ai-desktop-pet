// test_window/PetAcceptor/main.m
//
// V0.0 R45 图形化验收窗口
//
// 独立的 AppKit app，作为桌宠的人机验收 UI。
//
// 用法（正常模式）：
//   PetAcceptor \
//     --candidate candidate_a \
//     --version V0.0 \
//     --commit 4826c99 \
//     --bundle-id com.test.petA \
//     --result-out /path/to/acceptor_result.json \
//     --auto-launch-ms 0
//
// 用法（自测模式，由 build_self_tests.sh 调用）：
//   PetAcceptor --self-test <case_name>
//   PetAcceptor --self-test all
//   case 列表： all_pass, all_fail, mixed, abort_midway, prev_edit,
//              launch_fail_a, launch_fail_b, csv_schema, switch_a_to_b
//
// 退出码：
//   0 = 全部 Pass
//   1 = 出现 Fail
//   2 = 受阻 (NOT_TESTED due to user abort)
//   3 = 自测阶段启动失败 (内部分支自己仿真)

#import <AppKit/AppKit.h>

// ------- 单项测试定义 -------
static NSString *const kStatusPass      = @"PASS";
static NSString *const kStatusFail      = @"FAIL";
static NSString *const kStatusNotTested = @"NOT_TESTED";
static NSString *const kStatusDisabled  = @"DISABLED_SINGLE_DISPLAY";

// 7 项 + 1 项单屏固定 DISABLED，共 8 项
// 单屏固定 disabled 是硬规则 — 主控可以显式 override，namespace 见 --no-disable-multidisplay
typedef struct {
    NSString *key;
    NSString *label;            // 显示在窗口顶部的问题文案
    NSString *instructions;     // 用户做该测试时的具体动作
} TestItem;

static TestItem kItems[] = {
    { @"launch",
      @"1/8 启动验证",
      @"候选应在桌面上出现一个 256x256 的桌宠窗口，无崩溃提示。" },
    { @"display",
      @"2/8 显示方向",
      @"人物应正向站立，头朝上脚朝下，无镜像、倒立或上下颠倒。" },
    { @"animation",
      @"3/8 动画表现",
      @"眨眼与上下浮动应自然，无明显卡顿、撕裂或全黑帧。" },
    { @"click",
      @"4/8 点击反馈",
      @"用鼠标点击桌宠主体，能看到动作切换或姿态变化。" },
    { @"drag",
      @"5/8 拖动同步",
      @"鼠标按下并拖动桌宠，桌宠位置应与鼠标基本同步，无跳变。" },
    { @"transparent",
      @"6/8 透明区穿透",
      @"点击桌宠周围空白处，‘点这里测试穿透’ 按钮的计数应 +1。" },
    { @"window_focus",
      @"7/8 焦点与置顶",
      @"候选不应抢走探针窗口 / Terminal 的输入焦点；切换 Spaces 桌宠应跟随。" },
    { @"multidisplay",
      @"8/8 多显示器",
      @"需要多屏环境验证 — 本机单屏固定 DISABLED（可选项，不会影响验收）。" },
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

// 配置
@property (nonatomic, copy) NSString *candidate;       // candidate_a or candidate_b
@property (nonatomic, copy) NSString *version;          // "V0.0"
@property (nonatomic, copy) NSString *commit;           // git hash
@property (nonatomic, copy) NSString *bundleId;         // com.test.petA
@property (nonatomic, copy) NSString *resultOutPath;    // /path/to/result.json
@property (nonatomic)         BOOL enableMultidisplay;  // 默认 NO (单屏)

// 运行时状态
@property (nonatomic) NSInteger currentIndex;           // 当前题号
@property (nonatomic, strong) NSMutableDictionary<NSString *, NSString *> *answers;
@property (nonatomic, strong) NSMutableDictionary<NSString *, NSString *> *notes;

// 自测模式
@property (nonatomic, copy) NSString *selfTestCase;     // nil = 正常模式

// UI 引用
@property (nonatomic, strong) NSTextField *headerLabel;
@property (nonatomic, strong) NSTextField *versionLabel;
@property (nonatomic, strong) NSTextField *questionLabel;
@property (nonatomic, strong) NSTextField *instructionsLabel;
@property (nonatomic, strong) NSTextField *progressLabel;
@property (nonatomic, strong) NSTextField *summaryLabel;
@property (nonatomic, strong) NSTextView  *notesView;
@property (nonatomic, strong) NSButton *passBtn;
@property (nonatomic, strong) NSButton *failBtn;
@property (nonatomic, strong) NSButton *unableBtn;
@property (nonatomic, strong) NSButton *prevBtn;
@property (nonatomic, strong) NSButton *nextBtn;
@property (nonatomic, strong) NSButton *endBtn;
@end

@implementation PetAcceptorAppDelegate

- (instancetype)init {
    if ((self = [super init])) {
        _candidate = @"candidate_unknown";
        _version = @"V0.0";
        _commit = @"unknown";
        _bundleId = @"";
        _enableMultidisplay = NO;
        _currentIndex = 0;
        _answers = [NSMutableDictionary new];
        _notes   = [NSMutableDictionary new];
    }
    return self;
}

#pragma mark - UI Construction

- (void)buildUI {
    NSRect winFrame = NSMakeRect(220, 180, 720, 540);
    self.window = [[NSWindow alloc] initWithContentRect:winFrame
                                              styleMask:NSWindowStyleMaskTitled |
                                                         NSWindowStyleMaskClosable |
                                                         NSWindowStyleMaskMiniaturizable
                                                backing:NSBackingStoreBuffered
                                                  defer:NO];
    self.window.title = @"AI 桌宠 V0.0 — 人机验收窗口";
    self.window.releasedWhenClosed = NO;
    [self.window makeKeyAndOrderFront:nil];

    NSView *root = self.window.contentView;

    // --- 顶部信息区 ---
    self.headerLabel   = [self mkLabel:@"加载中…" frame:NSMakeRect(20, 480, 660, 30) font:[NSFont systemFontOfSize:18 weight:NSFontWeightBold]];
    self.versionLabel  = [self mkLabel:@""          frame:NSMakeRect(20, 455, 660, 18) font:[NSFont systemFontOfSize:11]];
    [root addSubview:self.headerLabel];
    [root addSubview:self.versionLabel];

    // --- 当前问题区 ---
    self.questionLabel = [self mkLabel:@"" frame:NSMakeRect(20, 380, 660, 36) font:[NSFont systemFontOfSize:15 weight:NSFontWeightSemibold]];
    self.instructionsLabel = [self mkLabel:@"" frame:NSMakeRect(20, 320, 660, 60) font:[NSFont systemFontOfSize:13]];
    self.instructionsLabel.maximumNumberOfLines = 4;
    self.instructionsLabel.lineBreakMode = NSLineBreakByWordWrapping;
    [root addSubview:self.questionLabel];
    [root addSubview:self.instructionsLabel];

    // --- 三个状态按钮 ---
    self.passBtn   = [self mkButton:@"✓ 通过 (PASS)"          action:@selector(onPass:)    frame:NSMakeRect(20, 270, 180, 44)];
    self.failBtn   = [self mkButton:@"✗ 失败 (FAIL)"          action:@selector(onFail:)    frame:NSMakeRect(220, 270, 180, 44)];
    self.unableBtn = [self mkButton:@"○ 无法测试 (NOT_TESTED)" action:@selector(onUnable:) frame:NSMakeRect(420, 270, 200, 44)];
    [root addSubview:self.passBtn];
    [root addSubview:self.failBtn];
    [root addSubview:self.unableBtn];

    // --- 上一项 / 下一项 / 结束 ---
    self.prevBtn = [self mkButton:@"◀ 上一项" action:@selector(onPrev:) frame:NSMakeRect(20, 215, 140, 36)];
    self.nextBtn = [self mkButton:@"下一项 ▶" action:@selector(onNext:) frame:NSMakeRect(180, 215, 140, 36)];
    self.endBtn  = [self mkButton:@"■ 结束测试"  action:@selector(onEnd:)  frame:NSMakeRect(340, 215, 140, 36)];
    [root addSubview:self.prevBtn];
    [root addSubview:self.nextBtn];
    [root addSubview:self.endBtn];

    // --- 备注 ---
    NSTextField *notesTitle = [self mkLabel:@"备注（可选，记下你看到的现象）:" frame:NSMakeRect(20, 188, 660, 18) font:[NSFont systemFontOfSize:11]];
    [root addSubview:notesTitle];
    NSScrollView *sv = [[NSScrollView alloc] initWithFrame:NSMakeRect(20, 80, 660, 100)];
    sv.hasVerticalScroller = YES;
    sv.borderType = NSBezelBorder;
    self.notesView = [[NSTextView alloc] initWithFrame:NSMakeRect(0, 0, 640, 96)];
    self.notesView.editable = YES;
    self.notesView.font = [NSFont systemFontOfSize:12];
    sv.documentView = self.notesView;
    [root addSubview:sv];

    // --- 进度 + 汇总 ---
    self.progressLabel = [self mkLabel:@"0/8" frame:NSMakeRect(20, 50, 660, 18) font:[NSFont systemFontOfSize:11 weight:NSFontWeightMedium]];
    self.summaryLabel  = [self mkLabel:@"" frame:NSMakeRect(20, 25, 660, 18) font:[NSFont monospacedSystemFontOfSize:11 weight:NSFontWeightRegular]];
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
    self.headerLabel.stringValue = [NSString stringWithFormat:@"AI 桌宠 V0.0 · 当前候选：%@", cand];
    self.versionLabel.stringValue = [NSString stringWithFormat:@"Build: V0.0  |  Commit: %@  |  Bundle ID: %@  |  Time: %@", self.commit, self.bundleId, nowISO()];

    if (self.currentIndex >= kItemsCount) {
        self.questionLabel.stringValue = @"所有项已答完，请点 ■ 结束测试。";
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

    // 汇总
    NSUInteger pass = 0, fail = 0, nt = 0, dis = 0;
    for (NSUInteger i = 0; i < kItemsCount; i++) {
        NSString *s = self.answers[kItems[i].key];
        if (!s) continue;
        if ([s isEqualToString:kStatusPass]) pass++;
        else if ([s isEqualToString:kStatusFail]) fail++;
        else if ([s isEqualToString:kStatusNotTested]) nt++;
        else if ([s isEqualToString:kStatusDisabled]) dis++;
    }
    self.summaryLabel.stringValue = [NSString stringWithFormat:@"汇总 PASS=%lu  FAIL=%lu  NOT_TESTED=%lu  DISABLED=%lu",
                                     (unsigned long)pass, (unsigned long)fail, (unsigned long)nt, (unsigned long)dis];
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
    if (advance) {
        self.currentIndex++;
    }
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
    [self refreshView];
}
- (void)onNext:(id)s {
    if (self.currentIndex + 1 >= kItemsCount) return;
    NSString *k = [self currentKey];
    if (!self.answers[k]) self.answers[k] = kStatusNotTested;  // 未答 → NOT_TESTED（不允许默认 PASS）
    self.currentIndex++;
    NSString *nextKey = [self currentKey];
    NSString *nextNotes = self.notes[nextKey];
    if (nextNotes) [self.notesView setString:nextNotes];
    [self refreshView];
}
- (void)onEnd:(id)s {
    [self writeResultAndExit];
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
        // 单屏硬规则覆盖
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
    NSString *overall = kStatusPass;
    if (hasFail) overall = kStatusFail;
    else if (pass == 0) overall = kStatusNotTested;

    return @{
        @"candidate": self.candidate ?: @"",
        @"version": self.version ?: @"V0.0",
        @"commit": self.commit ?: @"",
        @"bundle_id": self.bundleId ?: @"",
        @"tested_at": nowISO(),
        @"overall": overall,
        @"counts_pass": @(pass),
        @"counts_fail": @(fail),
        @"counts_not_tested": @(nt),
        @"counts_disabled": @(dis),
        @"items": items,
    };
}

- (void)writeResultAndExit {
    NSDictionary *result = [self buildResultDict];
    NSError *err = nil;
    NSData *data = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:&err];
    NSString *out = self.resultOutPath ?: @"/tmp/acceptor_result.json";
    if (data) {
        [data writeToFile:out options:NSDataWritingAtomic error:&err];
        NSLog(@"[PetAcceptor] wrote %@ (%lu bytes)", out, (unsigned long)data.length);
    }
    NSString *overall = result[@"overall"];
    int code = 0;
    if ([overall isEqualToString:kStatusFail]) code = 1;
    else if ([overall isEqualToString:kStatusNotTested]) code = 2;
    [NSApp terminate:nil];
    exit(code);
}

#pragma mark - App lifecycle

- (void)applicationDidFinishLaunching:(NSNotification *)notif {
    [self buildUI];
    [self refreshView];

    // 启动模式：正常 GUI / 自测
    if (self.selfTestCase.length > 0) {
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.2 * NSEC_PER_SEC)),
                       dispatch_get_main_queue(), ^{
            [self runSelfTest:self.selfTestCase];
        });
    }
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSNotification *)n {
    return YES;
}

- (void)applicationWillTerminate:(NSNotification *)n {
    // 用户关窗时也写一份结果（未答项默认 NOT_TESTED）
    if (self.resultOutPath.length > 0) {
        NSDictionary *result = [self buildResultDict];
        NSError *err = nil;
        NSData *data = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:&err];
        if (data) [data writeToFile:self.resultOutPath options:NSDataWritingAtomic error:&err];
    }
}

#pragma mark - Self-tests (R45 §5)

- (void)runSelfTest:(NSString *)caseName {
    NSLog(@"[PetAcceptor] self-test case=%@", caseName);
    if ([caseName isEqualToString:@"all_pass"]) {
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusPass;
        }
        [self writeResultAndExit];
    } else if ([caseName isEqualToString:@"all_fail"]) {
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusFail;
        }
        [self writeResultAndExit];
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
        [self writeResultAndExit];
    } else if ([caseName isEqualToString:@"abort_midway"]) {
        // 只答前 3 项，然后退出 — 后面应保持 NOT_TESTED
        self.answers[@"launch"]   = kStatusPass;
        self.answers[@"display"]  = kStatusPass;
        self.answers[@"animation"] = kStatusFail;
        // 其余不答 → 退出后填 NOT_TESTED
        self.notes[@"animation"] = @"卡顿严重";
        [self writeResultAndExit];
    } else if ([caseName isEqualToString:@"prev_edit"]) {
        // 第一轮答全部 PASS，然后跳回改 1 项为 FAIL
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusPass;
        }
        [self recordAnswer:kStatusFail advance:NO];  // first item (launch) was the current
        [self writeResultAndExit];
    } else if ([caseName isEqualToString:@"launch_fail_a"] || [caseName isEqualToString:@"launch_fail_b"]) {
        // 模拟"候选启动失败"：launch=FAIL → 后面强制 NOT_TESTED
        self.answers[@"launch"] = kStatusFail;
        // 即使后面写 PASS，逻辑上无法实测；以 NOT_TESTED 兜底
        for (NSUInteger i = 1; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusNotTested;
        }
        [self writeResultAndExit];
    } else if ([caseName isEqualToString:@"csv_schema"]) {
        // 全部 PASS，验证 candidate/commit/version 都写入了文件
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusPass;
        }
        [self writeResultAndExit];
    } else if ([caseName isEqualToString:@"switch_a_to_b"]) {
        for (NSUInteger i = 0; i < kItemsCount; i++) {
            if ([kItems[i].key isEqualToString:@"multidisplay"] && !self.enableMultidisplay) continue;
            self.answers[kItems[i].key] = kStatusPass;
        }
        [self writeResultAndExit];
    } else if ([caseName isEqualToString:@"all"]) {
        // 调用脚本外部循环，本 case 只打印 OK
        NSLog(@"[PetAcceptor] all self-tests placeholder — run via build_self_tests.sh");
        [self writeResultAndExit];
    } else {
        NSLog(@"[PetAcceptor] unknown self-test case '%@'; not answering anything", caseName);
        [self writeResultAndExit];
    }
}

@end

#pragma mark - Entry

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        PetAcceptorAppDelegate *delegate = [PetAcceptorAppDelegate new];
        app.delegate = delegate;
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];

        // 解析 CLI
        NSArray *args = [[NSProcessInfo processInfo] arguments];
        for (NSUInteger i = 1; i < args.count; i++) {
            NSString *a = args[i];
            if ([a isEqualToString:@"--candidate"] && i+1 < args.count) delegate.candidate = args[++i];
            else if ([a isEqualToString:@"--version"] && i+1 < args.count) delegate.version = args[++i];
            else if ([a isEqualToString:@"--commit"] && i+1 < args.count) delegate.commit = args[++i];
            else if ([a isEqualToString:@"--bundle-id"] && i+1 < args.count) delegate.bundleId = args[++i];
            else if ([a isEqualToString:@"--result-out"] && i+1 < args.count) delegate.resultOutPath = args[++i];
            else if ([a isEqualToString:@"--enable-multidisplay"]) delegate.enableMultidisplay = YES;
            else if ([a isEqualToString:@"--self-test"] && i+1 < args.count) delegate.selfTestCase = args[++i];
        }

        // 关键：让 AppKit 接管 run loop
        [app activateIgnoringOtherApps:YES];
        [app run];
    }
    return 0;
}

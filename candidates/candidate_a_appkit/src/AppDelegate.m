#import "AppDelegate.h"
#import "PetWindow.h"
#import "PetView.h"
#import "PerfSampler.h"

@interface AppDelegate ()
@property (nonatomic, strong) NSWindow *petWindow;
@property (nonatomic, strong) NSStatusItem *statusItem;
@property (nonatomic, strong) NSTimer *perfTimer;
@property (nonatomic, copy)   NSString *perfOutPath;
@end

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)n {
    NSArray *args = [[NSProcessInfo processInfo] arguments];
    NSString *manifest = nil;
    NSInteger winSize = 256;
    NSInteger winX = 100, winY = 100;
    for (NSUInteger i = 1; i < args.count; i++) {
        NSString *a = args[i];
        if ([a isEqualToString:@"--manifest"] && i+1 < args.count) manifest = args[++i];
        else if ([a isEqualToString:@"--size"] && i+1 < args.count) winSize = [args[++i] integerValue];
        else if ([a isEqualToString:@"--x"] && i+1 < args.count) winX = [args[++i] integerValue];
        else if ([a isEqualToString:@"--y"] && i+1 < args.count) winY = [args[++i] integerValue];
        else if ([a isEqualToString:@"--perf-out"] && i+1 < args.count) self.perfOutPath = args[++i];
        else if ([a isEqualToString:@"--quit-after"] && i+1 < args.count) {
            NSTimeInterval secs = [args[++i] doubleValue];
            [NSTimer scheduledTimerWithTimeInterval:secs repeats:NO block:^(NSTimer *t) {
                [self quitApp];
            }];
        }
    }
    if (!manifest) {
        NSLog(@"[AppDelegate] FATAL: no --manifest given");
        exit(2);
    }
    NSRect frame = NSMakeRect(winX, winY, winSize, winSize);
    PetWindow *w = [[PetWindow alloc] initWithFrame:frame manifestPath:manifest];
    self.petWindow = w;
    [(PetView *)w.contentView startTicking];
    [w makeKeyAndOrderFront:nil];
    NSLog(@"[AppDelegate] pet window up: %@ frame=%@", w.title, NSStringFromRect(w.frame));

    // Status menu: minimal entry to verify menu-bar integration (PRD FR-A.1).
    self.statusItem = [[NSStatusBar systemStatusBar] statusItemWithLength:NSVariableStatusItemLength];
    self.statusItem.title = @"🐾";
    NSMenu *m = [[NSMenu alloc] init];
    [m addItemWithTitle:@"Show Pet" action:@selector(showPet:) keyEquivalent:@""];
    [m addItemWithTitle:@"Hide Pet" action:@selector(hidePet:) keyEquivalent:@""];
    [m addItem:[NSMenuItem separatorItem]];
    [m addItemWithTitle:@"Action: idle" action:@selector(actIdle:) keyEquivalent:@""];
    [m addItemWithTitle:@"Action: walk" action:@selector(actWalk:) keyEquivalent:@""];
    [m addItemWithTitle:@"Action: jump" action:@selector(actJump:) keyEquivalent:@""];
    [m addItemWithTitle:@"Action: drag" action:@selector(actDrag:) keyEquivalent:@""];
    [m addItem:[NSMenuItem separatorItem]];
    [m addItemWithTitle:@"Reset Perf" action:@selector(resetPerfAction:) keyEquivalent:@""];
    [m addItemWithTitle:@"Dump Perf" action:@selector(dumpPerfAction:) keyEquivalent:@""];
    [m addItem:[NSMenuItem separatorItem]];
    [m addItemWithTitle:@"Quit" action:@selector(quitAction:) keyEquivalent:@"q"];
    for (NSMenuItem *it in m.itemArray) it.target = self;
    self.statusItem.menu = m;

    if (self.perfOutPath) {
        __weak typeof(self) weakSelf = self;
        // V0.0 R43: move file I/O off the main thread.
        // Background serial queue avoids every-second fileExistsAtPath /
        // fileHandleForWritingAtPath / seekToEndOfFile / writeData / closeFile
        // blocking the AppKit main run loop, which was the dominant source of
        // dropped frames in the R41 GUI run.
        dispatch_queue_t perfQueue = dispatch_queue_create("com.v0.perfsampler", DISPATCH_QUEUE_SERIAL);
        self.perfTimer = [NSTimer scheduledTimerWithTimeInterval:1.0 repeats:YES block:^(NSTimer *t) {
            __strong typeof(weakSelf) self = weakSelf;
            if (!self) return;
            // Snapshot is light (reads atomic ints) so still safe on main.
            NSDictionary *snap = [self snapshotPerf];
            NSString *perfPath = [self.perfOutPath copy];
            dispatch_async(perfQueue, ^{
                NSArray *cols = @[@"timestamp", @"action", @"fps", @"frame_advances_per_sec",
                                  @"frame_ms_p50", @"frame_ms_p95", @"rss_mb", @"cpu_percent"];
                NSString *row = [NSString stringWithFormat:@"%@,%@,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f",
                                 snap[@"timestamp"], snap[@"action"],
                                 [snap[@"fps"] doubleValue],
                                 [snap[@"frame_advances_per_sec"] doubleValue],
                                 [snap[@"frame_ms_p50"] doubleValue],
                                 [snap[@"frame_ms_p95"] doubleValue],
                                 [snap[@"rss_mb"] doubleValue],
                                 [snap[@"cpu_percent"] doubleValue]];
                NSString *parent = [perfPath stringByDeletingLastPathComponent];
                [[NSFileManager defaultManager] createDirectoryAtPath:parent withIntermediateDirectories:YES attributes:nil error:nil];
                BOOL exists = [[NSFileManager defaultManager] fileExistsAtPath:perfPath];
                NSFileHandle *fh = [NSFileHandle fileHandleForWritingAtPath:perfPath];
                if (!fh) {
                    [[NSFileManager defaultManager] createFileAtPath:perfPath contents:[NSData data] attributes:nil];
                    fh = [NSFileHandle fileHandleForWritingAtPath:perfPath];
                }
                [fh seekToEndOfFile];
                if (!exists) {
                    [fh writeData:[[cols componentsJoinedByString:@","] dataUsingEncoding:NSUTF8StringEncoding]];
                    [fh writeData:[@"\n" dataUsingEncoding:NSUTF8StringEncoding]];
                }
                [fh writeData:[[row stringByAppendingString:@"\n"] dataUsingEncoding:NSUTF8StringEncoding]];
                [fh closeFile];
            });
        }];
    }
}


- (void)applicationWillTerminate:(NSNotification *)n {
    [(PetView *)self.petWindow.contentView stopTicking];
    [(PetView *)self.petWindow.contentView logDiagnostics];
    NSLog(@"[AppDelegate] terminating cleanly");
}

- (void)showPet:(id)s       { [self.petWindow orderFront:nil]; }
- (void)hidePet:(id)s       { [self.petWindow orderOut:nil]; }
- (void)actIdle:(id)s       { [self setAction:@"idle"]; }
- (void)actWalk:(id)s       { [self setAction:@"walk"]; }
- (void)actJump:(id)s       { [self setAction:@"jump"]; }
- (void)actDrag:(id)s       { [self setAction:@"drag"]; }
- (void)resetPerfAction:(id)s { [self resetPerf]; }
- (void)dumpPerfAction:(id)s  {
    NSDictionary *d = [self snapshotPerf];
    NSLog(@"[AppDelegate] perf dump: %@", d);
}
- (void)quitAction:(id)s    { [self quitApp]; }

- (void)setAction:(NSString *)action {
    [(PetView *)self.petWindow.contentView setAction:action];
}

- (void)quitApp {
    [NSApp terminate:nil];
}

- (void)resetPerf {
    PetView *v = (PetView *)self.petWindow.contentView;
    [v.sampler reset];
}

- (NSDictionary *)snapshotPerf {
    PetView *v = (PetView *)self.petWindow.contentView;
    PerfSnapshot s = [v.sampler snapshot];
    NSDateFormatter *fmt = [NSDateFormatter new];
    fmt.dateFormat = @"yyyy-MM-dd HH:mm:ss";
    return @{
        @"timestamp": [fmt stringFromDate:[NSDate dateWithTimeIntervalSince1970:s.timestamp]],
        @"action": v.currentAction ?: @"idle",
        @"fps": @(s.fps),
        @"frame_advances_per_sec": @(v.lastSecondFrameAdvances),
        @"frame_ms_p50": @(s.frameMsP50),
        @"frame_ms_p95": @(s.frameMsP95),
        @"rss_mb": @(s.rssMB),
        @"cpu_percent": @(s.cpuPercent),
    };
}

@end

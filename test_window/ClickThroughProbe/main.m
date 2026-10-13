// test_window/ClickThroughProbe/main.m
//
// V0.0 R39 passthrough probe.
// V0.0 R53 geometry-aware probe:
//
//   R53 task书 §四：必须证明 probe 按钮真的位于 candidate 桌宠窗口矩形的下方，
//   否则点击透明区不算穿透成功。
//
//   Probe 现在支持 CLI 参数：
//     --x <px>            window origin x (default 100)
//     --y <px>            window origin y (default 100)
//     --w <px>            window width   (default 360)
//     --h <px>            window height  (default 180)
//     --under-pet-x <px>  candidate pet window origin x (default 0)
//     --under-pet-y <px>  candidate pet window origin y (default 0)
//     --under-pet-w <px>  candidate pet window width   (default 256)
//     --under-pet-h <px>  candidate pet window height  (default 256)
//
//   如果 probe 窗口和 pet 窗口不相交，启动时会 NSLog FAIL 并强制漂移到
//   pet 矩形内部居中，确保后续穿透测试有效。
//
//   Probe 还在标题栏显示几何信息：
//     "Probe @ (100,100) 360x180 ; pet @ (600,600) 256x256 ; OVERLAP=yes"
//   用户肉眼可立即判断重叠是否就位。

#import <AppKit/AppKit.h>

@interface ProbeAppDelegate : NSObject <NSApplicationDelegate>
@property (nonatomic, strong) NSWindow *window;
@property (nonatomic, strong) NSTextField *label;
@property (nonatomic, strong) NSTextField *geomLabel;
@property (nonatomic, assign) NSInteger clicks;
@property (nonatomic, assign) NSRect petRect;
@property (nonatomic, assign) NSRect probeRect;
@end

@implementation ProbeAppDelegate

- (BOOL)probeRect:(NSRect)p intersectsPetRect:(NSRect)pet {
    return NSIntersectsRect(p, pet);
}

- (void)applicationDidFinishLaunching:(NSNotification *)notif {
    CGFloat x = 100, y = 100, w = 360, h = 180;
    CGFloat px = 0, py = 0, pw = 256, ph = 256;

    // 解析 CLI
    NSArray *args = [[NSProcessInfo processInfo] arguments];
    for (NSUInteger i = 1; i < args.count; i++) {
        NSString *a = args[i];
        if ([a isEqualToString:@"--x"] && i+1 < args.count) x = [args[++i] doubleValue];
        else if ([a isEqualToString:@"--y"] && i+1 < args.count) y = [args[++i] doubleValue];
        else if ([a isEqualToString:@"--w"] && i+1 < args.count) w = [args[++i] doubleValue];
        else if ([a isEqualToString:@"--h"] && i+1 < args.count) h = [args[++i] doubleValue];
        else if ([a isEqualToString:@"--under-pet-x"] && i+1 < args.count) px = [args[++i] doubleValue];
        else if ([a isEqualToString:@"--under-pet-y"] && i+1 < args.count) py = [args[++i] doubleValue];
        else if ([a isEqualToString:@"--under-pet-w"] && i+1 < args.count) pw = [args[++i] doubleValue];
        else if ([a isEqualToString:@"--under-pet-h"] && i+1 < args.count) ph = [args[++i] doubleValue];
    }

    self.petRect  = NSMakeRect(px, py, pw, ph);
    self.probeRect = NSMakeRect(x, y, w, h);

    if (![self probeRect:self.probeRect intersectsPetRect:self.petRect]) {
        NSLog(@"[Probe] FAIL geometry: probe %@ 与 pet %@ 不重叠，自动漂移",
              NSStringFromRect(self.probeRect), NSStringFromRect(self.petRect));
        // 漂移：把 probe 居中叠到 pet 内
        CGFloat cx = px + pw/2.0 - w/2.0;
        CGFloat cy = py + ph/2.0 - h/2.0;
        self.probeRect = NSMakeRect(cx, cy, w, h);
        x = cx; y = cy;
    } else {
        NSLog(@"[Probe] geometry OK: probe %@ intersects pet %@",
              NSStringFromRect(self.probeRect), NSStringFromRect(self.petRect));
    }

    NSRect frame = self.probeRect;
    self.window = [[NSWindow alloc] initWithContentRect:frame
                                              styleMask:NSWindowStyleMaskTitled |
                                                         NSWindowStyleMaskClosable |
                                                         NSWindowStyleMaskResizable
                                                backing:NSBackingStoreBuffered
                                                  defer:NO];
    BOOL overlap = [self probeRect:self.probeRect intersectsPetRect:self.petRect];
    NSString *geom = [NSString stringWithFormat:@"几何: probe=(%.0f,%.0f) %.0fx%.0f  /  pet=(%.0f,%.0f) %.0fx%.0f  /  OVERLAP=%@",
                       x, y, w, h, px, py, pw, ph, overlap ? @"YES" : @"NO"];
    self.window.title = [NSString stringWithFormat:@"透明区穿透探针 · %@", overlap ? @"已就位" : @"错位!"];
    [self.window makeKeyAndOrderFront:nil];

    NSView *content = self.window.contentView;

    NSTextField *heading = [[NSTextField alloc] initWithFrame:NSMakeRect(20, 130, 320, 22)];
    heading.stringValue = @"AI 桌宠透明区点击测试 — 每次点击我 +1";
    heading.bezeled = NO; heading.drawsBackground = NO; heading.editable = NO; heading.selectable = NO;
    heading.font = [NSFont systemFontOfSize:13 weight:NSFontWeightSemibold];
    [content addSubview:heading];

    NSButton *button = [[NSButton alloc] initWithFrame:NSMakeRect(20, 60, 320, 50)];
    button.title = @"点这里测试穿透";
    button.bezelStyle = NSBezelStyleRounded;
    button.font = [NSFont systemFontOfSize:15 weight:NSFontWeightMedium];
    button.target = self;
    button.action = @selector(buttonClicked:);
    [content addSubview:button];

    self.label = [[NSTextField alloc] initWithFrame:NSMakeRect(20, 30, 320, 22)];
    self.label.stringValue = @"已点击次数: 0";
    self.label.bezeled = NO; self.label.drawsBackground = NO; self.label.editable = NO; self.label.selectable = NO;
    self.label.font = [NSFont monospacedSystemFontOfSize:13 weight:NSFontWeightRegular];
    [content addSubview:self.label];

    self.geomLabel = [[NSTextField alloc] initWithFrame:NSMakeRect(20, 5, 520, 18)];
    self.geomLabel.stringValue = geom;
    self.geomLabel.bezeled = NO; self.geomLabel.drawsBackground = NO; self.geomLabel.editable = NO; self.geomLabel.selectable = NO;
    self.geomLabel.font = [NSFont monospacedSystemFontOfSize:10 weight:NSFontWeightRegular];
    self.geomLabel.textColor = overlap ? [NSColor systemGreenColor] : [NSColor systemRedColor];
    [content addSubview:self.geomLabel];
}

- (void)buttonClicked:(id)sender {
    self.clicks++;
    self.label.stringValue = [NSString stringWithFormat:@"已点击次数: %ld", (long)self.clicks];
    NSLog(@"[Probe] click count -> %ld", (long)self.clicks);
}

@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        ProbeAppDelegate *delegate = [ProbeAppDelegate new];
        app.delegate = delegate;
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];
        [app activateIgnoringOtherApps:YES];
        [app run];
    }
    return 0;
}

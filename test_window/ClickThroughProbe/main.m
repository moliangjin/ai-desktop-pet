// test_window/ClickThroughProbe/main.m
//
// V0.0 R39 passthrough probe.
//
// A tiny standalone AppKit application that shows a 360x180 window with one
// button and one label. Every click on the button increments a counter shown
// in the label.
//
// Used together with the pet candidates to verify transparent-area mouse
// passthrough: when the pet is over this window and the cursor is on the
// pet's transparent pixels, clicking the pet area should NOT eat the click —
// it should fall through to this probe window, incrementing the counter.
//
// Build: see test_window/ClickThroughProbe/build.sh
// Run:   ./test_window/ClickThroughProbe/build/ClickThroughProbe.app/Contents/MacOS/ClickThroughProbe

#import <AppKit/AppKit.h>

@interface ProbeAppDelegate : NSObject <NSApplicationDelegate>
@property (nonatomic, strong) NSWindow *window;
@property (nonatomic, strong) NSTextField *label;
@property (nonatomic, assign) NSInteger clicks;
@end

@implementation ProbeAppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)notif {
    NSRect frame = NSMakeRect(220, 220, 360, 180);
    self.window = [[NSWindow alloc] initWithContentRect:frame
                                              styleMask:NSWindowStyleMaskTitled |
                                                         NSWindowStyleMaskClosable |
                                                         NSWindowStyleMaskResizable
                                                backing:NSBackingStoreBuffered
                                                  defer:NO];
    self.window.title = @"透明区穿透探针 · 点击我验证穿透";
    [self.window makeKeyAndOrderFront:nil];

    NSView *content = self.window.contentView;

    NSTextField *heading = [[NSTextField alloc] initWithFrame:NSMakeRect(20, 130, 320, 22)];
    heading.stringValue = @"AI 桌宠透明区点击测试 — 每次点击我 +1";
    heading.bezeled = NO;
    heading.drawsBackground = NO;
    heading.editable = NO;
    heading.selectable = NO;
    heading.font = [NSFont systemFontOfSize:13 weight:NSFontWeightSemibold];
    [content addSubview:heading];

    NSButton *button = [[NSButton alloc] initWithFrame:NSMakeRect(20, 70, 320, 50)];
    button.title = @"点这里测试穿透";
    button.bezelStyle = NSBezelStyleRounded;
    button.font = [NSFont systemFontOfSize:15 weight:NSFontWeightMedium];
    button.target = self;
    button.action = @selector(buttonClicked:);
    [content addSubview:button];

    self.label = [[NSTextField alloc] initWithFrame:NSMakeRect(20, 30, 320, 22)];
    self.label.stringValue = @"已点击次数: 0";
    self.label.bezeled = NO;
    self.label.drawsBackground = NO;
    self.label.editable = NO;
    self.label.selectable = NO;
    self.label.font = [NSFont monospacedSystemFontOfSize:13 weight:NSFontWeightRegular];
    [content addSubview:self.label];
}

- (void)buttonClicked:(id)sender {
    self.clicks++;
    self.label.stringValue = [NSString stringWithFormat:@"已点击次数: %ld", (long)self.clicks];
    NSLog(@"[Probe] click count -> %ld", (long)self.clicks);
}

// T05 focus/raise check: clicking the window's title bar / a non-button area
// should still bring this window to front. The button is intentionally large
// so that when the pet window's transparent pixel is over this button, the
// click should land here.
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

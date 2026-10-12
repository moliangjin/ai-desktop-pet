#import "PetWindow.h"
#import "Manifest.h"

@interface PetWindow ()
@property (nonatomic, strong) PetView *petView;
@property (nonatomic, strong) NSTimer *trackingTimer;
@end

@implementation PetWindow

+ (NSWindow *)createWithFrame:(NSRect)frame manifestPath:(NSString *)manifestPath {
    // Use NSWindow (not NSPanel) so we can opt into FullScreenAuxiliary behavior.
    NSUInteger style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel;
    NSWindow *w = [[NSWindow alloc] initWithContentRect:frame
                                              styleMask:style
                                                backing:NSBackingStoreBuffered
                                                  defer:NO];
    return w;
}

- (instancetype)initWithFrame:(NSRect)frame manifestPath:(NSString *)manifestPath {
    self = [super initWithContentRect:frame
                            styleMask:NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
                              backing:NSBackingStoreBuffered
                                defer:NO];
    if (self) {
        // Aggressive transparency chain. Set in this order; several are
        // required on macOS 14 to defeat the default opaque backing store.
        self.styleMask = NSWindowStyleMaskBorderless;
        self.opaque = NO;
        self.backgroundColor = [NSColor colorWithCalibratedRed:0 green:0 blue:0 alpha:0.0];
        self.hasShadow = NO;
        self.ignoresMouseEvents = NO;
        self.level = NSFloatingWindowLevel;
        self.collectionBehavior = NSWindowCollectionBehaviorCanJoinAllSpaces |
                                   NSWindowCollectionBehaviorFullScreenAuxiliary |
                                   NSWindowCollectionBehaviorTransient;
        self.movableByWindowBackground = YES;
        if (@available(macOS 13.0, *)) {
            self.titlebarAppearsTransparent = YES;
        }
        self.titleVisibility = NSWindowTitleHidden;
        // Some macOS 14 sessions cache the backing store; force a re-issue.
        [self setOpaque:NO];
        [self setBackgroundColor:[NSColor clearColor]];

        _petView = [[PetView alloc] initWithFrame:NSMakeRect(0, 0, frame.size.width, frame.size.height)];
        _petView.store = [FrameStore new];
        _petView.sampler = [PerfSampler new];
        self.contentView = _petView;
        // Force content view to layer-backed with explicit clear background.
        self.contentView.wantsLayer = YES;
        self.contentView.layer = [CALayer layer];
        self.contentView.layer.opaque = NO;
        self.contentView.layer.backgroundColor = CGColorGetConstantColor(kCGColorClear);
        self.contentView.layerContentsRedrawPolicy = NSViewLayerContentsRedrawOnSetNeedsDisplay;
        // Some macOS 14 sessions require setAlphaValue < 1 to opt into
        // per-pixel compositing for borderless borderless windows.
        self.alphaValue = 0.999;

        _manifestPath = [manifestPath copy];
        [self loadManifest];

        // Tracking timer updates per-pixel passthrough decision.
        __weak typeof(self) weakSelf = self;
        _trackingTimer = [NSTimer scheduledTimerWithTimeInterval:1.0/30.0
                                                         repeats:YES
                                                           block:^(NSTimer *t) {
            __strong typeof(weakSelf) self = weakSelf;
            if (!self || self.passthrough) return;
            NSPoint mp = [NSEvent mouseLocation];
            NSRect wf = self.frame;
            CGFloat localX = mp.x - wf.origin.x;
            CGFloat localY = mp.y - wf.origin.y;
            NSPoint local = NSMakePoint(localX, localY);
            [self updateMouseRegionAt:local];
        }];

        // Re-assert transparency after the window is on-screen.
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.1 * NSEC_PER_SEC)),
                       dispatch_get_main_queue(), ^{
            [self setOpaque:NO];
            [self setBackgroundColor:[NSColor clearColor]];
            [self.contentView setWantsLayer:YES];
            self.contentView.layer.backgroundColor = CGColorGetConstantColor(kCGColorClear);
        });
    }
    return self;
}

- (void)loadManifest {
    NSArray *order = @[@"idle", @"walk", @"jump", @"drag"];
    NSUInteger total = 0;
    for (NSString *a in order) {
        total += [self.petView.store loadAction:a manifestPath:self.manifestPath];
    }
    NSLog(@"[PetWindow] total frames loaded=%lu", (unsigned long)total);
    [self.petView setAction:@"idle"];
}

- (void)setWholeWindowPassthrough:(BOOL)p {
    self.passthrough = p;
    [self setIgnoresMouseEvents:p];
    NSLog(@"[PetWindow] whole-window passthrough=%@", @(p));
}

- (void)updateMouseRegionAt:(NSPoint)windowPoint {
    NSPoint local = [self.petView convertPoint:windowPoint fromView:nil];
    BOOL hit = [self.petView localPointHits:local];
    BOOL current = self.ignoresMouseEvents;
    if (current == !hit) return;
    [self setIgnoresMouseEvents:!hit];
}

- (void)_handleBackgroundClick:(id)dummy {
    NSLog(@"[PetWindow] background click absorbed (no passthrough)");
}

@end

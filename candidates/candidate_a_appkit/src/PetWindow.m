#import "PetWindow.h"
#import "Manifest.h"

@interface PetWindow ()
@property (nonatomic, strong) PetView *petView;
@end

@implementation PetWindow

+ (NSWindow *)createWithFrame:(NSRect)frame manifestPath:(NSString *)manifestPath {
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
        // Aggressive transparency chain — required on macOS 14 to defeat the
        // default opaque backing store on a borderless window.
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
        [self setOpaque:NO];
        [self setBackgroundColor:[NSColor clearColor]];

        _petView = [[PetView alloc] initWithFrame:NSMakeRect(0, 0, frame.size.width, frame.size.height)];
        _petView.store = [FrameStore new];
        _petView.sampler = [PerfSampler new];
        self.contentView = _petView;
        // R38 fix: keep standard NSView drawRect path; do NOT force a CALayer
        // (that would route rendering through empty updateLayer and the sprite
        // would never draw).
        self.alphaValue = 0.999;
        NSLog(@"[PetWindow] init frame=%@ size=%@ level=%ld",
              NSStringFromRect(self.frame), NSStringFromSize(self.frame.size), (long)self.level);

        _manifestPath = [manifestPath copy];
        [self loadManifest];

        // V0.0 R39: transparent-area passthrough is driven from PetView's
        // 5 Hz hit-test loop (see PetView._advance). We intentionally do NOT
        // install a 30 Hz / 60 Hz tracking timer here — those competed with
        // mouseDown delivery in R37 and made clicks impossible. 5 Hz is slow
        // enough to never fight a mouseDown (which can take 50–150 ms before
        // AppKit recognizes it as a click) and fast enough that a cursor
        // resting on transparent pixels starts passing clicks through to the
        // underlying window within ~200 ms.

        // Re-assert transparency after the window is on-screen, in case the
        // WindowServer cached a pre-update backing store.
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.1 * NSEC_PER_SEC)),
                       dispatch_get_main_queue(), ^{
            [self setOpaque:NO];
            [self setBackgroundColor:[NSColor clearColor]];
            [self.contentView setNeedsDisplay:YES];
            NSLog(@"[PetWindow] post-show re-assert: opaque=%d alpha=%.3f",
                  (int)self.isOpaque, self.alphaValue);
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

#pragma mark - Public passthrough API

/// Whole-window passthrough is the PARTIAL mode used for T02 demonstrations
/// where the user explicitly disables all role interaction. The normal
/// path (per-hitbox passthrough) is implemented inside PetView and does not
/// use this method.
- (void)setWholeWindowPassthrough:(BOOL)p {
    self.passthrough = p;
    [self setIgnoresMouseEvents:p];
    NSLog(@"[PetWindow] whole-window passthrough=%@", @(p));
}

// Kept for backwards compatibility — the per-hitbox logic was migrated into
// PetView._advance on the 5 Hz cadence. Manually invoking this is harmless.
- (void)updateMouseRegionAt:(NSPoint)windowPoint {
    NSPoint local = [self.petView convertPoint:windowPoint fromView:nil];
    BOOL hit = [self.petView localPointHits:local];
    [self setIgnoresMouseEvents:!hit];
}

- (void)_handleBackgroundClick:(id)dummy {
    NSLog(@"[PetWindow] background click absorbed (no passthrough)");
}

@end

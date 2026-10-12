#import <AppKit/AppKit.h>
#import "FrameStore.h"
#import "PerfSampler.h"

NS_ASSUME_NONNULL_BEGIN

/// NSView subclass that draws the current animation frame, handles hit-testing
/// against the hitbox, and implements drag-to-move + screen-edge clamp.
@interface PetView : NSView

@property (nonatomic, strong) FrameStore *store;
@property (nonatomic, strong) PerfSampler *sampler;
@property (nonatomic, copy)   NSString *currentAction;
@property (nonatomic, readonly) NSRect spriteRect;        // bounding rect of drawn sprite
@property (nonatomic, readonly) NSRect hitboxRect;        // transparent-vs-hit rect
@property (nonatomic, readonly) BOOL hovered;
@property (nonatomic, readonly) NSInteger dragStartFrame;

- (void)setAction:(NSString *)action;   // switches animation; safe at any time
- (void)startTicking;                    // install CADisplayLink equivalent (NSTimer)
- (void)stopTicking;

/// Pretty-print state to stderr; useful for T08 logs.
- (void)logDiagnostics;

/// Returns YES if localPoint is inside the visible hitbox rect.
/// (For T02 real hit-test after window ignoresMouseEvents toggling.)
- (BOOL)localPointHits:(NSPoint)p;

@end

NS_ASSUME_NONNULL_END

#import <AppKit/AppKit.h>
#import "PetView.h"

NS_ASSUME_NONNULL_BEGIN

/// A borderless NSWindow hosting a PetView. Implements T02 mouse-passthrough
/// by toggling ignoresMouseEvents on the window border while keeping the hitbox
/// inside the sprite reactive.
@interface PetWindow : NSWindow

@property (nonatomic, strong, readonly) PetView *petView;
@property (nonatomic, copy)   NSString *manifestPath;
@property (nonatomic) BOOL passthrough;       // YES => ignore mouse events on full window (PARTIAL T02 mode)

- (instancetype)initWithFrame:(NSRect)frame manifestPath:(NSString *)manifestPath;

/// Toggle the entire window's mouse event handling.
/// (Partial path of T02: passes all clicks to underlying app; role interaction
/// disabled. Used to demonstrate that a real win-level switch exists.)
- (void)setWholeWindowPassthrough:(BOOL)passthrough;

/// When NOT passthrough: track mouse moves and use them to set
/// ignoresMouseEvents dynamically per-pixel (best-effort via region lookup).
- (void)updateMouseRegionAt:(NSPoint)windowPoint;

@end

NS_ASSUME_NONNULL_END

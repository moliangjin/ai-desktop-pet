#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>

NS_ASSUME_NONNULL_BEGIN

/// Cache of CGImageRef per action.
/// Lazily loads PNGs from disk; reports per-frame load failures.
@interface FrameStore : NSObject

- (instancetype)init;

/// Load all frames for `action` declared by `manifest`.
/// Returns the number of frames successfully loaded; missing frames log to stderr
/// but do not abort other frames. This matches PRD §5 FR-G (graceful degradation).
- (NSUInteger)loadAction:(NSString *)actionName manifestPath:(NSString *)manifestPath;

/// Returns CGImageRef for (action, frameIndex), or NULL if not loaded.
- (nullable CGImageRef)imageForAction:(NSString *)action frameIndex:(NSUInteger)idx;

/// Number of frames currently loaded for the action (0 if action unknown).
- (NSUInteger)frameCountForAction:(NSString *)action;

/// Number of failed loads across all actions.
@property (nonatomic, readonly) NSUInteger failureCount;

/// All actions loaded so far.
- (NSArray<NSString *> *)loadedActions;

@end

NS_ASSUME_NONNULL_END

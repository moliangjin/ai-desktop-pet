#import <AppKit/AppKit.h>

NS_ASSUME_NONNULL_BEGIN

/// AppDelegate owns the PetWindow, perf sampler thread, and a status menu.
/// On macOS, access the pet window via `((AppDelegate *)NSApp.delegate).petWindow`.
@interface AppDelegate : NSObject <NSApplicationDelegate>

@property (nonatomic, strong, readonly) NSWindow *petWindow;

/// Run-time hooks for automated tests (T08 etc).
- (void)setAction:(NSString *)action;
- (void)quitApp;
- (void)resetPerf;
- (NSDictionary *)snapshotPerf;

@end

NS_ASSUME_NONNULL_END

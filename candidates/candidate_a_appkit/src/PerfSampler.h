#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

typedef struct {
    NSTimeInterval timestamp;
    double fps;
    double frameMsP50;
    double frameMsP95;
    double rssMB;
    double cpuPercent;
} PerfSnapshot;

/// Lightweight in-process sampler.
/// FPS: per-second sample of `tick:` calls (must be called once per draw).
/// frame_ms: per-call delta, P50/P95 reported on `snapshot`.
/// RSS: read from /proc-style mach `task_info`.
/// CPU%: estimate from mach thread basic info on macOS.
@interface PerfSampler : NSObject

- (instancetype)init;

/// Call once per frame draw.
- (void)tick;

/// Append a CSV row to `path` (creates parent dirs).
- (BOOL)appendCSV:(NSString *)path columns:(NSArray<NSString *> *)columns;

/// Build a snapshot of current numbers.
- (PerfSnapshot)snapshot;

/// Reset internal rolling window.
- (void)reset;

@end

NS_ASSUME_NONNULL_END

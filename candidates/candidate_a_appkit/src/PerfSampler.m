#import "PerfSampler.h"
#import <mach/mach.h>
#import <sys/resource.h>

@interface PerfSampler () {
    uint64_t _lastTickUs;
    NSMutableArray<NSNumber *> *_frameDeltas;
    NSTimeInterval _windowStart;
    NSUInteger _framesTotal;
    NSUInteger _framesLastSecond;
    NSTimeInterval _secondBoundary;
}
@end

static NSTimeInterval nowSec(void) {
    return (NSTimeInterval)[[NSDate date] timeIntervalSince1970];
}

@implementation PerfSampler

- (instancetype)init {
    self = [super init];
    if (self) {
        _lastTickUs = (uint64_t)(nowSec() * 1e6);
        _frameDeltas = [NSMutableArray new];
        _windowStart = nowSec();
        _secondBoundary = floor(_windowStart) + 1.0;
    }
    return self;
}

- (void)tick {
    uint64_t nowUs = (uint64_t)(nowSec() * 1e6);
    int64_t delta = (int64_t)(nowUs - _lastTickUs);
    _lastTickUs = nowUs;
    if (delta > 0 && delta < 1000000) {
        @synchronized (_frameDeltas) {
            [_frameDeltas addObject:@(delta / 1000.0)]; // store ms
            if (_frameDeltas.count > 4096) [_frameDeltas removeObjectsInRange:NSMakeRange(0, 2048)];
        }
    }
    _framesTotal++;
    NSTimeInterval nowS = nowSec();
    while (nowS >= _secondBoundary) {
        _secondBoundary += 1.0;
        _framesLastSecond = 0;
    }
    _framesLastSecond++;
}

- (double)_percentileFromDeltas:(double)p {
    @synchronized (_frameDeltas) {
        if (_frameDeltas.count == 0) return 0;
        NSArray *sorted = [_frameDeltas sortedArrayUsingSelector:@selector(compare:)];
        NSUInteger idx = (NSUInteger)(p * (sorted.count - 1));
        return [sorted[idx] doubleValue];
    }
}

- (double)_rssMB {
    struct mach_task_basic_info info;
    mach_msg_type_number_t cnt = MACH_TASK_BASIC_INFO_COUNT;
    if (task_info(mach_task_self(), MACH_TASK_BASIC_INFO, (task_info_t)&info, &cnt) == KERN_SUCCESS) {
        return info.resident_size / (1024.0 * 1024.0);
    }
    return -1;
}

- (double)_cpuPercent {
    struct task_thread_times_info info;
    mach_msg_type_number_t cnt = TASK_THREAD_TIMES_INFO_COUNT;
    if (task_info(mach_task_self(), TASK_THREAD_TIMES_INFO, (task_info_t)&info, &cnt) == KERN_SUCCESS) {
        double user = info.user_time.seconds + info.user_time.microseconds / 1e6;
        double sys  = info.system_time.seconds + info.system_time.microseconds / 1e6;
        double total = user + sys;
        NSTimeInterval elapsed = nowSec() - _windowStart;
        if (elapsed <= 0) return 0;
        return (total / elapsed) * 100.0; // % of 1 logical core (macOS single-core reference)
    }
    return -1;
}

- (PerfSnapshot)snapshot {
    PerfSnapshot s;
    s.timestamp = nowSec();
    NSTimeInterval elapsed = s.timestamp - _windowStart;
    // Use rolling 1-second count when available; fall back to whole-window avg.
    if (elapsed >= 1.0 && _framesTotal > 0) {
        s.fps = (double)_framesLastSecond;
    } else {
        s.fps = elapsed > 0 ? (double)_framesTotal / elapsed : 0;
    }
    s.frameMsP50 = [self _percentileFromDeltas:0.50];
    s.frameMsP95 = [self _percentileFromDeltas:0.95];
    s.rssMB = [self _rssMB];
    s.cpuPercent = [self _cpuPercent];
    return s;
}

- (BOOL)appendCSV:(NSString *)path columns:(NSArray<NSString *> *)columns {
    NSString *parent = [path stringByDeletingLastPathComponent];
    [[NSFileManager defaultManager] createDirectoryAtPath:parent
                              withIntermediateDirectories:YES
                                               attributes:nil error:nil];
    BOOL exists = [[NSFileManager defaultManager] fileExistsAtPath:path];
    NSFileHandle *fh = [NSFileHandle fileHandleForWritingAtPath:path];
    if (!fh) {
        [[NSFileManager defaultManager] createFileAtPath:path contents:[NSData data] attributes:nil];
        fh = [NSFileHandle fileHandleForWritingAtPath:path];
    }
    if (!fh) return NO;
    [fh seekToEndOfFile];
    if (!exists) {
        [fh writeData:[[columns componentsJoinedByString:@","] dataUsingEncoding:NSUTF8StringEncoding]];
        [fh writeData:[@"\n" dataUsingEncoding:NSUTF8StringEncoding]];
    }
    [fh writeData:[[[columns componentsJoinedByString:@","] stringByAppendingString:@"\n"]
                    dataUsingEncoding:NSUTF8StringEncoding]];
    [fh closeFile];
    return YES;
}

- (void)reset {
    @synchronized (_frameDeltas) { [_frameDeltas removeAllObjects]; }
    _windowStart = nowSec();
    _secondBoundary = floor(_windowStart) + 1.0;
    _framesTotal = 0;
    _framesLastSecond = 0;
}

@end

#import "FrameStore.h"
#import "Manifest.h"

@interface FrameStore () {
    NSMutableDictionary<NSString *, NSMutableArray *> *_cache;  // each element either (id)CGImageRef or (id)NULL
}
@property (nonatomic) NSUInteger failureCount;
@end

static CGImageRef loadPNG(NSString *path) {
    NSURL *url = [NSURL fileURLWithPath:path];
    CGImageSourceRef src = CGImageSourceCreateWithURL((__bridge CFURLRef)url, NULL);
    if (!src) return NULL;
    CGImageRef img = CGImageSourceCreateImageAtIndex(src, 0, NULL);
    CFRelease(src);
    return img;
}

@implementation FrameStore

- (instancetype)init {
    self = [super init];
    if (self) _cache = [NSMutableDictionary new];
    return self;
}

- (NSUInteger)loadAction:(NSString *)actionName manifestPath:(NSString *)manifestPath {
    NSError *err = nil;
    Manifest *m = [[Manifest alloc] initWithJSONPath:manifestPath error:&err];
    if (!m) {
        NSLog(@"[FrameStore] manifest load failed: %@", err);
        return 0;
    }
    ManifestAction *a = [m actionForName:actionName];
    if (!a) {
        NSLog(@"[FrameStore] action %@ not in manifest", actionName);
        return 0;
    }
    NSMutableArray *frames = [NSMutableArray new];
    for (NSString *rel in a.frames) {
        NSString *abs = [m resolvePath:rel];
        if (!abs) {
            NSLog(@"[FrameStore] reject unsafe path: %@", rel);
            self.failureCount++;
            [frames addObject:(id)NULL];
            continue;
        }
        CGImageRef img = loadPNG(abs);
        if (!img) {
            NSLog(@"[FrameStore] load fail: %@", abs);
            self.failureCount++;
            [frames addObject:(id)NULL];
            continue;
        }
        [frames addObject:(__bridge id)img];
    }
    _cache[actionName] = frames;
    NSUInteger ok = 0;
    for (id f in frames) if (f != (id)NULL) ok++;
    NSLog(@"[FrameStore] action=%@ loaded=%lu/%lu", actionName, (unsigned long)ok,
          (unsigned long)frames.count);
    return ok;
}

- (nullable CGImageRef)imageForAction:(NSString *)action frameIndex:(NSUInteger)idx {
    NSArray *frames = _cache[action];
    if (!frames || idx >= frames.count) return NULL;
    id v = frames[idx];
    if (v == (id)NULL) return NULL;
    return (__bridge CGImageRef)v;
}

- (NSUInteger)frameCountForAction:(NSString *)action {
    NSArray *frames = _cache[action];
    return frames ? frames.count : 0;
}

- (NSArray<NSString *> *)loadedActions {
    return _cache.allKeys;
}

- (void)dealloc {
    for (NSArray *frames in _cache.allValues) {
        for (id img in frames) {
            if (img != (id)NULL) CFRelease((__bridge CFTypeRef)img);
        }
    }
}

@end

#import "Manifest.h"

@implementation ManifestAction
@end

@implementation Manifest

- (nullable instancetype)initWithJSONPath:(NSString *)path
                                    error:(NSError * _Nullable * _Nullable)error {
    self = [super init];
    if (!self) return nil;

    NSData *data = [NSData dataWithContentsOfFile:path];
    if (!data) {
        if (error) *error = [NSError errorWithDomain:@"Manifest" code:1
                                userInfo:@{NSLocalizedDescriptionKey:@"cannot read manifest file"}];
        return nil;
    }
    NSError *jsonErr = nil;
    id obj = [NSJSONSerialization JSONObjectWithData:data options:0 error:&jsonErr];
    if (![obj isKindOfClass:[NSDictionary class]]) {
        if (error) *error = jsonErr ?: [NSError errorWithDomain:@"Manifest" code:2
                                       userInfo:@{NSLocalizedDescriptionKey:@"manifest root not object"}];
        return nil;
    }
    NSDictionary *root = obj;

    _characterId     = [root[@"character_id"] copy] ?: @"unknown";
    _appearanceId    = [root[@"appearance_id"] copy] ?: @"default";
    _displayName     = [root[@"display_name"] copy] ?: @"noname";
    _canvasPx        = [root[@"canvas_px"] copy] ?: @[@256, @256];
    _anchorNorm      = [root[@"anchor_normalized"] copy] ?: @[@0.5, @0.9];
    _hitboxNorm      = [root[@"hitbox_normalized"] copy] ?: @[@0.29, @0.24, @0.72, @0.87];
    _animationOrder  = [root[@"animation_order"] copy] ?: @[];
    NSDictionary *atlas = root[@"atlas"];
    _atlasFrameSizePx = atlas[@"frame_size_px"] ?: @[@256, @256];

    NSMutableDictionary *acts = [NSMutableDictionary new];
    NSDictionary *raw = root[@"actions"];
    if (![raw isKindOfClass:[NSDictionary class]]) {
        if (error) *error = [NSError errorWithDomain:@"Manifest" code:3
                                userInfo:@{NSLocalizedDescriptionKey:@"actions not dict"}];
        return nil;
    }
    for (NSString *k in raw) {
        NSDictionary *v = raw[k];
        if (![v isKindOfClass:[NSDictionary class]]) continue;
        ManifestAction *a = [ManifestAction new];
        a.name = [k copy];
        a.fps  = [v[@"fps"] integerValue];
        a.loop = [v[@"loop"] boolValue];
        NSArray *frames = v[@"frames"];
        if (![frames isKindOfClass:[NSArray class]]) frames = @[];
        a.frames = [frames copy];
        acts[k] = a;
    }
    _actions = [acts copy];

    _baseDir = [[path stringByDeletingLastPathComponent] copy];
    return self;
}

- (nullable ManifestAction *)actionForName:(NSString *)name {
    return _actions[name];
}

/// Resolves a relative path against baseDir.
/// Rejects absolute paths and `..` traversal segments (security: matches PRD §4 FR-E.2).
- (NSString *)resolvePath:(NSString *)relative {
    if ([relative hasPrefix:@"/"]) {
        return nil; // absolute path forbidden
    }
    NSArray<NSString *> *parts = [relative pathComponents];
    for (NSString *p in parts) {
        if ([p isEqualToString:@".."]) {
            return nil; // directory traversal forbidden
        }
    }
    return [_baseDir stringByAppendingPathComponent:relative];
}

@end

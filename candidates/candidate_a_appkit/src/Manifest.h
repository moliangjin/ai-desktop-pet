#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

/// One animation entry parsed from `actions.<name>`.
@interface ManifestAction : NSObject
@property (nonatomic, copy) NSString *name;
@property (nonatomic) NSInteger fps;
@property (nonatomic) BOOL loop;
@property (nonatomic, copy) NSArray<NSString *> *frames;
@end

/// Parsed `manifest.json` for one prototype character.
/// Validates required keys and resolves per-frame relative paths.
@interface Manifest : NSObject

@property (nonatomic, copy, readonly) NSString *characterId;
@property (nonatomic, copy, readonly) NSString *appearanceId;
@property (nonatomic, copy, readonly) NSString *displayName;
@property (nonatomic, copy, readonly) NSArray<NSNumber *> *canvasPx;        // [w, h]
@property (nonatomic, copy, readonly) NSArray<NSNumber *> *anchorNorm;     // [x, y]
@property (nonatomic, copy, readonly) NSArray<NSNumber *> *hitboxNorm;     // [x, y, w, h]
@property (nonatomic, copy, readonly) NSArray<NSNumber *> *atlasFrameSizePx;
@property (nonatomic, copy, readonly) NSArray<NSString *> *animationOrder;
@property (nonatomic, copy, readonly) NSDictionary<NSString *, ManifestAction *> *actions;
@property (nonatomic, copy, readonly) NSString *baseDir;     // directory of manifest.json

- (nullable instancetype)initWithJSONPath:(NSString *)path
                                    error:(NSError * _Nullable * _Nullable)error;

- (nullable ManifestAction *)actionForName:(NSString *)name;
- (NSString *)resolvePath:(NSString *)relative;

@end

NS_ASSUME_NONNULL_END

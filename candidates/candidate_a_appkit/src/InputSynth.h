#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>

NS_ASSUME_NONNULL_BEGIN

/// Synthesize mouse events at screen coordinates.
/// Used for V0.0 automated testing of T02 (hit), T04 (drag), T05 (focus).
/// Events are sent only at the requested local point; no global key stealing.
@interface InputSynth : NSObject

+ (void)moveMouseTo:(CGPoint)point;
+ (void)leftMouseDownAt:(CGPoint)point;
+ (void)leftMouseUpAt:(CGPoint)point;
+ (void)leftClickAt:(CGPoint)point;     // down+up
+ (void)leftDragFrom:(CGPoint)start to:(CGPoint)end steps:(NSUInteger)steps;

@end

NS_ASSUME_NONNULL_END

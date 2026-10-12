#import "InputSynth.h"

static void postEvent(CGEventType t, CGPoint p, CGMouseButton btn) {
    CGEventRef e = CGEventCreateMouseEvent(NULL, t, p, btn);
    if (!e) return;
    CGEventPost(kCGHIDEventTap, e);
    CFRelease(e);
}

@implementation InputSynth

+ (void)moveMouseTo:(CGPoint)point {
    CGEventRef e = CGEventCreateMouseEvent(NULL, kCGEventMouseMoved, point, kCGMouseButtonLeft);
    if (e) { CGEventPost(kCGHIDEventTap, e); CFRelease(e); }
}

+ (void)leftMouseDownAt:(CGPoint)point {
    postEvent(kCGEventLeftMouseDown, point, kCGMouseButtonLeft);
}

+ (void)leftMouseUpAt:(CGPoint)point {
    postEvent(kCGEventLeftMouseUp, point, kCGMouseButtonLeft);
}

+ (void)leftClickAt:(CGPoint)point {
    [self leftMouseDownAt:point];
    [self leftMouseUpAt:point];
}

+ (void)leftDragFrom:(CGPoint)start to:(CGPoint)end steps:(NSUInteger)steps {
    CGEventRef down = CGEventCreateMouseEvent(NULL, kCGEventLeftMouseDown, start, kCGMouseButtonLeft);
    CGEventPost(kCGHIDEventTap, down);
    CFRelease(down);

    if (steps == 0) steps = 1;
    for (NSUInteger i = 1; i <= steps; i++) {
        CGFloat t = (CGFloat)i / steps;
        CGPoint p = CGPointMake(start.x + (end.x - start.x) * t,
                                start.y + (end.y - start.y) * t);
        CGEventRef drag = CGEventCreateMouseEvent(NULL, kCGEventLeftMouseDragged, p, kCGMouseButtonLeft);
        CGEventPost(kCGHIDEventTap, drag);
        CFRelease(drag);
        usleep(8000); // 8ms ≈ 120Hz
    }

    CGEventRef up = CGEventCreateMouseEvent(NULL, kCGEventLeftMouseUp, end, kCGMouseButtonLeft);
    CGEventPost(kCGHIDEventTap, up);
    CFRelease(up);
}

@end

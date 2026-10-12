#import "PetView.h"
#import "Manifest.h"

@interface PetView () {
    NSTimer *_timer;
    NSInteger _frameIdx;
    NSTimeInterval _frameStartedAt;
    NSInteger _hitCount;
    NSInteger _missCount;
    BOOL _dragging;
    NSPoint _dragOriginWindow;
    NSPoint _dragOriginMouse;
}
@property (nonatomic) BOOL hovered;
@property (nonatomic) NSInteger dragStartFrame;
@end

@implementation PetView

- (instancetype)initWithFrame:(NSRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        _store = [FrameStore new];
        _sampler = [PerfSampler new];
        _currentAction = @"idle";
        _frameIdx = 0;
        _frameStartedAt = [NSDate timeIntervalSinceReferenceDate];
    }
    return self;
}

- (void)dealloc {
    [_timer invalidate];
}

- (NSRect)spriteRect {
    return [self bounds];
}

- (NSRect)hitboxRect {
    NSArray *hb = self.store ? @[@0.29, @0.24, @0.72, @0.87] : @[@0.29, @0.24, @0.72, @0.87];
    NSRect b = self.bounds;
    return NSMakeRect(b.origin.x + [hb[0] doubleValue] * b.size.width,
                      b.origin.y + [hb[1] doubleValue] * b.size.height,
                      [hb[2] doubleValue] * b.size.width - [hb[0] doubleValue] * b.size.width,
                      [hb[3] doubleValue] * b.size.height - [hb[1] doubleValue] * b.size.height);
}

- (BOOL)localPointHits:(NSPoint)p {
    if (!NSPointInRect(p, self.bounds)) return NO;
    return NSPointInRect(p, [self hitboxRect]);
}

- (void)setAction:(NSString *)action {
    if ([action isEqualToString:_currentAction]) return;
    NSLog(@"[PetView] action switch: %@ -> %@", _currentAction, action);
    _currentAction = [action copy];
    _frameIdx = 0;
    _frameStartedAt = [NSDate timeIntervalSinceReferenceDate];
    [self.sampler tick];
    [self setNeedsDisplay:YES];
}

- (void)startTicking {
    if (_timer) return;
    _timer = [NSTimer scheduledTimerWithTimeInterval:1.0/60.0
                                              target:self
                                            selector:@selector(_advance:)
                                            userInfo:nil
                                             repeats:YES];
    [[NSRunLoop currentRunLoop] addTimer:_timer forMode:NSRunLoopCommonModes];
}

- (void)stopTicking {
    [_timer invalidate];
    _timer = nil;
}

- (void)_advance:(NSTimer *)t {
    NSUInteger n = [self.store frameCountForAction:self.currentAction];
    if (n == 0) return;
    NSInteger fps = 8;     // match manifest idle fps
    NSTimeInterval now = [NSDate timeIntervalSinceReferenceDate];
    NSTimeInterval dt = now - _frameStartedAt;
    NSTimeInterval per = 1.0 / fps;
    if (dt >= per) {
        _frameIdx = (_frameIdx + 1) % n;
        _frameStartedAt = now;
        [self.sampler tick];
        [self setNeedsDisplay:YES];
    }
}

- (void)drawRect:(NSRect)dirtyRect {
    CGContextRef ctx = [[NSGraphicsContext currentContext] CGContext];
    CGContextClearRect(ctx, self.bounds);
    CGImageRef img = [self.store imageForAction:self.currentAction frameIndex:(NSUInteger)_frameIdx];
    if (img) {
        CGContextSaveGState(ctx);
        CGContextTranslateCTM(ctx, 0, self.bounds.size.height);
        CGContextScaleCTM(ctx, 1, -1);
        CGRect r = CGRectMake(0, 0, self.bounds.size.width, self.bounds.size.height);
        CGContextDrawImage(ctx, r, img);
        CGContextRestoreGState(ctx);
    } else {
        // Fallback: fully transparent — let compositor see through.
        CGContextSetRGBFillColor(ctx, 0, 0, 0, 0.0);
        CGContextFillRect(ctx, self.bounds);
    }
}

- (BOOL)isOpaque { return NO; }
- (BOOL)wantsUpdateLayer { return YES; }
- (void)updateLayer { /* no-op; layer-backed content is rendered in drawRect */ }

#pragma mark - Mouse

- (void)mouseDown:(NSEvent *)e {
    NSPoint local = [self convertPoint:e.locationInWindow fromView:nil];
    if (![self localPointHits:local]) {
        _missCount++;
        NSLog(@"[PetView] miss at local=%@", NSStringFromPoint(local));
        return;
    }
    _hitCount++;
    _dragging = YES;
    self.dragStartFrame = _frameIdx;
    _dragOriginWindow = e.locationInWindow;
    _dragOriginMouse = [NSEvent mouseLocation];
    [self setAction:@"drag"];
}

- (void)mouseDragged:(NSEvent *)e {
    if (!_dragging) return;
    NSPoint cur = e.locationInWindow;
    NSPoint delta = NSMakePoint(cur.x - _dragOriginWindow.x, cur.y - _dragOriginWindow.y);
    NSWindow *w = self.window;
    NSPoint origin = w.frame.origin;
    NSRect newFrame = w.frame;
    newFrame.origin = NSMakePoint(origin.x + delta.x, origin.y + delta.y);
    // Clamp inside visible screen
    NSRect screen = [[NSScreen mainScreen] visibleFrame];
    CGFloat minX = NSMinX(screen);
    CGFloat maxX = NSMaxX(screen) - newFrame.size.width;
    CGFloat minY = NSMinY(screen);
    CGFloat maxY = NSMaxY(screen) - newFrame.size.height;
    newFrame.origin.x = MAX(minX, MIN(maxX, newFrame.origin.x));
    newFrame.origin.y = MAX(minY, MIN(maxY, newFrame.origin.y));
    [w setFrameOrigin:newFrame.origin];
    _dragOriginWindow = cur;
}

- (void)mouseUp:(NSEvent *)e {
    if (!_dragging) return;
    _dragging = NO;
    [self setAction:@"idle"];
}

- (void)mouseEntered:(NSEvent *)e { self.hovered = YES; }
- (void)mouseExited:(NSEvent *)e  { self.hovered = NO; }

- (void)logDiagnostics {
    NSLog(@"[PetView] diag action=%@ frame=%ld hits=%ld miss=%ld hover=%d",
          _currentAction, (long)_frameIdx, (long)_hitCount, (long)_missCount,
          (int)self.hovered);
}

@end

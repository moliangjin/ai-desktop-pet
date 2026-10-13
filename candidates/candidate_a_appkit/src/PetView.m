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
    NSInteger _frameAdvancesThisSecond;
    NSTimeInterval _frameAdvanceWindowStart;
    NSInteger _lastSecondFrameAdvances;
    // V0.0 R39: transparent-area passthrough state
    NSTimeInterval _lastHitboxCheckAt;
    BOOL _lastHitboxInside;       // did the cursor land on the opaque sprite last time?
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
        _frameAdvanceWindowStart = [NSDate timeIntervalSinceReferenceDate];
        _lastSecondFrameAdvances = 0;
        _lastHitboxCheckAt = 0;
        _lastHitboxInside = YES;
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
    // R38 fix: 60Hz tick for prompt reaction to action switches and drag events,
    // while per-frame sprite advance is throttled by the 8 fps manifest inside
    // _advance (so the visible animation does not run at 60fps).
    _timer = [NSTimer timerWithTimeInterval:1.0/60.0
                                     target:self
                                   selector:@selector(_advance:)
                                   userInfo:nil
                                    repeats:YES];
    [[NSRunLoop mainRunLoop] addTimer:_timer forMode:NSRunLoopCommonModes];
}

- (void)stopTicking {
    [_timer invalidate];
    _timer = nil;
}

- (void)_advance:(NSTimer *)t {
    NSUInteger n = [self.store frameCountForAction:self.currentAction];
    [self.sampler tick];
    NSTimeInterval nowS = [NSDate timeIntervalSinceReferenceDate];
    if (nowS - _frameAdvanceWindowStart >= 1.0) {
        _lastSecondFrameAdvances = _frameAdvancesThisSecond;
        _frameAdvanceWindowStart = nowS;
        _frameAdvancesThisSecond = 0;
    }
    if (n == 0) return;
    NSInteger fps = 8;
    NSTimeInterval dt = nowS - _frameStartedAt;
    NSTimeInterval per = 1.0 / fps;
    if (dt >= per) {
        _frameIdx = (_frameIdx + 1) % n;
        _frameStartedAt = nowS;
        _frameAdvancesThisSecond++;
        [self setNeedsDisplay:YES];
    }

    // V0.0 R39: transparent-area passthrough via 5Hz hitbox test.
    // 5Hz is too slow to compete with mouseDown timing (mouseDown can last
    // 50-100ms before being recognized, so 200ms gaps let AppKit deliver
    // events normally), but fast enough that an idle cursor hovering the
    // transparent corner stops stealing clicks from the window underneath
    // within ~200ms.
    if (nowS - _lastHitboxCheckAt >= 1.0/5.0) {
        _lastHitboxCheckAt = nowS;
        [self _evaluateHitboxForMousePassthrough];
    }
}

- (void)_evaluateHitboxForMousePassthrough {
    NSWindow *w = self.window;
    if (!w || _dragging) {
        // While dragging, always accept events (the user is actively clicking).
        if (w && w.ignoresMouseEvents) {
            [w setIgnoresMouseEvents:NO];
        }
        _lastHitboxInside = YES;
        return;
    }
    NSPoint mouse = [NSEvent mouseLocation];   // global screen coordinates
    NSRect winFrame = w.frame;
    if (!NSPointInRect(mouse, winFrame)) {
        // Cursor left our window — keep us accepting so we do not eat events
        // for some other app that just shadowed us.
        if (w.ignoresMouseEvents) [w setIgnoresMouseEvents:NO];
        _lastHitboxInside = YES;
        return;
    }
    NSPoint inWindow = [w convertPointFromScreen:mouse];
    NSPoint inView = [self convertPoint:inWindow fromView:nil];
    BOOL hit = [self localPointHits:inView];
    BOOL shouldIgnore = !hit;
    if (w.ignoresMouseEvents != shouldIgnore) {
        [w setIgnoresMouseEvents:shouldIgnore];
        // R43: do NOT NSLog here — the toggle fires up to 5 times per second
        // and NSLog goes through ASL/syslogd which adds measurable main-thread
        // latency on the AppKit main run loop.
    }
    _lastHitboxInside = hit;
}

- (void)drawRect:(NSRect)dirtyRect {
    CGContextRef ctx = [[NSGraphicsContext currentContext] CGContext];
    CGContextClearRect(ctx, self.bounds);
    CGImageRef img = [self.store imageForAction:self.currentAction frameIndex:(NSUInteger)_frameIdx];
    if (img) {
        CGRect r = CGRectMake(0, 0, self.bounds.size.width, self.bounds.size.height);
        // V0.0 R53 orientation strategy — 5 种策略可热切换；诊断真实方向问题
        // 默认 original（保留 R38 行为），其它由 PET_DRAW_ORIENTATION env 指定
        const char *strategy = getenv("PET_DRAW_ORIENTATION");
        NSString *s = strategy ? [NSString stringWithUTF8String:strategy] : @"original";
        if ([s isEqualToString:@"flipped_no_transform"]) {
            // R43 方案：isFlipped=YES + 不 transform;要求 view y 轴朝下
            CGContextDrawImage(ctx, r, img);
        } else if ([s isEqualToString:@"notflipped_with_transform"]) {
            // R38 方案：isFlipped=NO + translate(0,h)+scale(1,-1)
            CGContextSaveGState(ctx);
            CGContextTranslateCTM(ctx, 0, self.bounds.size.height);
            CGContextScaleCTM(ctx, 1, -1);
            CGContextDrawImage(ctx, r, img);
            CGContextRestoreGState(ctx);
        } else if ([s isEqualToString:@"notflipped_no_transform"]) {
            // 测试：isFlipped=NO + 不 transform — 看 CG 默认行为
            CGContextDrawImage(ctx, r, img);
        } else if ([s isEqualToString:@"flipped_with_transform"]) {
            // 反向：isFlipped=YES + transform
            CGContextSaveGState(ctx);
            CGContextTranslateCTM(ctx, 0, self.bounds.size.height);
            CGContextScaleCTM(ctx, 1, -1);
            CGContextDrawImage(ctx, r, img);
            CGContextRestoreGState(ctx);
        } else {
            // 'original' = 保留 R43 行为
            CGContextDrawImage(ctx, r, img);
        }
    } else {
        CGContextSetRGBFillColor(ctx, 0, 0, 0, 0.0);
        CGContextFillRect(ctx, self.bounds);
    }
}

- (BOOL)isOpaque { return NO; }
- (BOOL)isFlipped {
    const char *strategy = getenv("PET_DRAW_ORIENTATION");
    NSString *s = strategy ? [NSString stringWithUTF8String:strategy] : @"original";
    // R53: 5 策略下 isFlipped 配对
    if ([s isEqualToString:@"flipped_no_transform"]) return YES;  // R43
    if ([s isEqualToString:@"flipped_with_transform"]) return YES;
    return NO;  // original / notflipped_no_transform / notflipped_with_transform
}
- (BOOL)wantsUpdateLayer { return NO; }

#pragma mark - Mouse

- (void)mouseDown:(NSEvent *)e {
    NSLog(@"[PetView] mouseDown local=%@", NSStringFromPoint([self convertPoint:e.locationInWindow fromView:nil]));
    NSPoint local = [self convertPoint:e.locationInWindow fromView:nil];
    // R39: force the window back to receiving events so this mouseDown is not
    // dropped by a stale ignoresMouseEvents=YES from the 5Hz passthrough loop.
    if (self.window.ignoresMouseEvents) {
        [self.window setIgnoresMouseEvents:NO];
    }
    if (![self localPointHits:local]) {
        _missCount++;
        NSLog(@"[PetView] miss at local=%@", NSStringFromPoint(local));
        // R39 transparent miss: re-enable ignore for the next event tick so
        // the click can propagate to the underlying window; the 5Hz loop
        // will re-evaluate from the new cursor position.
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.05 * NSEC_PER_SEC)),
                       dispatch_get_main_queue(), ^{
            if (!self->_dragging) {
                [self.window setIgnoresMouseEvents:YES];
                NSLog(@"[PetView] post-miss: re-ignored for passthrough");
            }
        });
        return;
    }
    _hitCount++;
    _dragging = YES;
    self.dragStartFrame = _frameIdx;
    _dragOriginWindow = e.locationInWindow;
    _dragOriginMouse = [NSEvent mouseLocation];
    [self setAction:@"drag"];
    NSLog(@"[PetView] HIT drag-start action=drag");
}

- (void)mouseDragged:(NSEvent *)e {
    // R53: 在 0.05s 上做 drag_latency 采样 (不写 syslog 避开 R43 教训)
    NSTimeInterval drag_latency_ms = 0;
    NSDate *t0 = [NSDate date];
    if (!_dragging) return;
    if (self.window.ignoresMouseEvents) {
        [self.window setIgnoresMouseEvents:NO];
    }
    NSPoint cur = e.locationInWindow;
    NSPoint delta = NSMakePoint(cur.x - _dragOriginWindow.x, cur.y - _dragOriginWindow.y);
    NSWindow *w = self.window;
    NSPoint origin = w.frame.origin;
    NSRect newFrame = w.frame;
    newFrame.origin = NSMakePoint(origin.x + delta.x, origin.y + delta.y);
    NSRect screen = [[NSScreen mainScreen] visibleFrame];
    CGFloat minX = NSMinX(screen);
    CGFloat maxX = NSMaxX(screen) - newFrame.size.width;
    CGFloat minY = NSMinY(screen);
    CGFloat maxY = NSMaxY(screen) - newFrame.size.height;
    newFrame.origin.x = MAX(minX, MIN(maxX, newFrame.origin.x));
    newFrame.origin.y = MAX(minY, MIN(maxY, newFrame.origin.y));
    [w setFrameOrigin:newFrame.origin];
    _dragOriginWindow = cur;
    // 测量 setFrameOrigin→frame change 实际耗时
    NSTimeInterval dt = [[NSDate date] timeIntervalSinceDate:t0];
    drag_latency_ms = dt * 1000.0;
    if (drag_latency_ms > 16.0) {  // < 16ms = 60fps 标准,超过 16ms 算掉帧
        NSLog(@"[DragLatency] WARN %.2fms > 16ms threshold (origin=%.1f,%.1f)",
              drag_latency_ms, newFrame.origin.x, newFrame.origin.y);
    }
}

- (void)mouseUp:(NSEvent *)e {
    NSLog(@"[PetView] mouseUp dragging=%d", _dragging);
    if (!_dragging) return;
    _dragging = NO;
    [self setAction:@"idle"];
    // R39: immediately re-evaluate passthrough on mouse-up; if the user
    // released over a transparent pixel, restore ignore within this frame.
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.05 * NSEC_PER_SEC)),
                   dispatch_get_main_queue(), ^{
        [self _evaluateHitboxForMousePassthrough];
    });
    NSLog(@"[PetView] drag-end action=idle");
}

- (void)mouseEntered:(NSEvent *)e { self.hovered = YES; NSLog(@"[PetView] mouseEntered"); }
- (void)mouseExited:(NSEvent *)e  { self.hovered = NO; NSLog(@"[PetView] mouseExited"); }

- (void)logDiagnostics {
    NSLog(@"[PetView] diag action=%@ frame=%ld hits=%ld miss=%ld hover=%d ignore=%@",
          _currentAction, (long)_frameIdx, (long)_hitCount, (long)_missCount,
          (int)self.hovered, @(self.window.ignoresMouseEvents));
}

@end

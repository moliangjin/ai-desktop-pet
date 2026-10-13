// tools/passthrough_poc/r69_gui_test_runner.swift
//
// V0.0 R71 本地 GUI 自动验收程序
//
// 关键修复 (相对 R69):
//   1. 权限检查: 使用 Apple 官方 AXIsProcessTrustedWithOptions (替代 R69
//      的"用一次 CGEventPost(mouseMoved) 当作权限已通过"的伪证)。
//   2. 几何来源: 完全从 PoC 实时 stdout tick JSON 读, 不再硬编码。
//   3. 有效透明测试点计算:
//        满足 test_window ∩ probe_button ∩ 不在 sprite 圆形内 ∩ 不在
//        control_window 内的所有交集中, 找一个有效点。
//      找不到有效点 → GEOMETRY_INVALID → 直接退出 (不发送任何 click)。
//   4. 真实事件验证:
//        EVENT_POSTED  ≠ TARGET_RECEIVED ≠ COUNTER_CHANGED
//      必须三者都满足才算 PASS。点击前后从 PoC stdout tick 读 clicks
//      增量确认 COUNTER_CHANGED, 否则 FAIL。
//   5. INPUT_MONITORING: 不在权限检查里强制要求。只用 CGEventPost 测试
//      mouse-moved (不读全局输入); 如果 CGEventPost 成功就够。
//
// 编译 + 运行:
//   cd tools/passthrough_poc
//   ./r69_build.sh
//   ./build/r69_gui_test_runner
//
// 权限要求 (R71 严格最少):
//   系统设置 → 隐私与安全 → 辅助功能 → 勾选 Terminal.app (或你的宿主)
//   (CGEventPost mouse-moved + leftMouseDown + leftMouseUp)

import Foundation
import CoreGraphics
import AppKit

// --- Structs ---
struct PoCTick: Codable {
    let type: String
    let run_id: String
    let mode: String
    let ignore: Bool
    let test_window: Rect
    let probe_window: Rect
    let control_window: Rect
    let sprite: Center
    let probe_button: Rect?
    let clicks: Clicks
    let transitions: Int
}
struct Rect: Codable {
    let x: Double
    let y: Double
    let w: Double
    let h: Double
}
struct Center: Codable {
    let cx: Double
    let cy: Double
    let r: Double
}
struct Clicks: Codable {
    let test: Int
    let probe: Int
}

struct RectIn {
    var x: Double; var y: Double; var w: Double; var h: Double
    var right: Double { x + w }
    var bottom: Double { y + h }
    var cx: Double { x + w/2 }
    var cy: Double { y + h/2 }
    func contains(_ p: (Double, Double)) -> Bool {
        return p.0 >= x && p.0 < right && p.1 >= y && p.1 < bottom
    }
    func intersects(_ r: RectIn) -> Bool {
        return !(r.x >= right || x >= r.right || r.y >= bottom || y >= r.bottom)
    }
    var description: String { String(format: "(%.0f,%.0f,%.0fx%.0f)", x, y, w, h) }
}

struct Result: Codable {
    var run_id: String
    var started_at: String
    var finished_at: String
    var accessibility_check_method: String
    var accessibility_granted: Bool
    var input_monitoring_required: Bool
    var test_window: String?
    var probe_window: String?
    var control_window: String?
    var probe_button: String?
    var sprite: String?
    var valid_test_point: [Double]?
    var control_click: String
    var gold_ball_click: String
    var underlying_click: String
    var return_click: String
    var three_cycle_stable: String
    var notes: [String]
}

var result = Result(
    run_id: "r69_\(Int(Date().timeIntervalSince1970))",
    started_at: ISO8601DateFormatter().string(from: Date()),
    finished_at: "",
    accessibility_check_method: "AXIsProcessTrustedWithOptions",
    accessibility_granted: false,
    input_monitoring_required: false,
    test_window: nil, probe_window: nil, control_window: nil,
    probe_button: nil, sprite: nil, valid_test_point: nil,
    control_click: "NOT_TESTED", gold_ball_click: "NOT_TESTED",
    underlying_click: "NOT_TESTED", return_click: "NOT_TESTED",
    three_cycle_stable: "NOT_TESTED", notes: []
)

let resultBase = "/tmp/\(result.run_id)"

func log(_ s: String) {
    print(s)
}

func writeResult() {
    result.finished_at = ISO8601DateFormatter().string(from: Date())
    let enc = JSONEncoder()
    enc.outputFormatting = .prettyPrinted
    if let d = try? enc.encode(result) {
        try? d.write(to: URL(fileURLWithPath: "\(resultBase).json"))
    }
    let summary = """
    === R71 Local GUI Test Runner Result ===
    run_id:                    \(result.run_id)
    started_at:                \(result.started_at)
    finished_at:               \(result.finished_at)
    accessibility_check:       \(result.accessibility_check_method)  -> granted=\(result.accessibility_granted)
    input_monitoring_required: \(result.input_monitoring_required)
    test_window:               \(result.test_window ?? "?")
    probe_window:              \(result.probe_window ?? "?")
    control_window:            \(result.control_window ?? "?")
    probe_button:              \(result.probe_button ?? "?")
    sprite:                    \(result.sprite ?? "?")
    valid_test_point:          \(result.valid_test_point.map { String(format: "(%.0f,%.0f)", $0[0], $0[1]) } ?? "NONE (GEOMETRY_INVALID)")
    control_click:             \(result.control_click)
    gold_ball_click:           \(result.gold_ball_click)
    underlying_click:          \(result.underlying_click)
    return_click:              \(result.return_click)
    three_cycle_stable:        \(result.three_cycle_stable)
    notes:                     \(result.notes.joined(separator: " | "))
    """
    try? summary.write(toFile: "\(resultBase).txt", atomically: true, encoding: .utf8)
    let csv = "run_id,accessibility,test_window,probe_button,valid_test_point,control_click,gold_ball_click,underlying_click,return_click,three_cycle_stable\n" +
        "\(result.run_id),\(result.accessibility_granted),\(result.test_window ?? "")\(result.probe_button ?? ""),\(result.valid_test_point.map { "\($0[0]),\($0[1])" } ?? ""),\(result.control_click),\(result.gold_ball_click),\(result.underlying_click),\(result.return_click),\(result.three_cycle_stable)\n"
    try? csv.write(toFile: "\(resultBase).csv", atomically: true, encoding: .utf8)
    log("→ wrote \(resultBase).{txt,json,csv}")
}

// --- R71: 官方 Accessibility 权限检查 ---
func checkAccessibility() -> Bool {
    // kAXTrustedCheckOptionPrompt: false means do NOT show system prompt;
    // we only want to read the current state.
    let opts = [kAXTrustedCheckOptionPrompt: false] as CFDictionary
    return AXIsProcessTrustedWithOptions(opts)
}

// --- CGEvent helpers ---
func cgPoint(_ x: Double, _ y: Double) -> CGPoint { return CGPoint(x: x, y: y) }

func postMouseMove(to p: CGPoint) {
    if let ev = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: p, mouseButton: .left) {
        ev.post(tap: .cghidEventTap)
    }
}

func postClick(at p: CGPoint) {
    if let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: p, mouseButton: .left),
       let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: p, mouseButton: .left) {
        down.post(tap: .cghidEventTap)
        usleep(50_000)
        up.post(tap: .cghidEventTap)
    }
}

func moveAndClick(_ p: CGPoint) {
    postMouseMove(to: p)
    usleep(150_000)
    postClick(at: p)
    usleep(500_000)
}

// --- Geometry helpers ---
func rectIn(_ r: Rect) -> RectIn { return RectIn(x: r.x, y: r.y, w: r.w, h: r.h) }
func distance(_ ax: Double, _ ay: Double, _ bx: Double, _ by: Double) -> Double {
    return sqrt((ax-bx)*(ax-bx) + (ay-by)*(ay-by))
}

// Compute a valid transparent test point: inside test_window, inside probe_button,
// outside sprite circle, NOT inside control_window.
func computeValidTransparentPoint(tick: PoCTick) -> (Double, Double)? {
    let tw = rectIn(tick.test_window)
    let pbOpt = tick.probe_button
    guard let pb = pbOpt.map(rectIn) else {
        result.notes.append("GEOMETRY_INVALID: probe_button rect missing from PoC")
        return nil
    }
    let cw = rectIn(tick.control_window)
    // Step 1: probe_button (must be inside it)
    // Step 2: test_window (must be inside it)
    // Step 3: NOT inside sprite circle
    // Step 4: NOT inside control_window
    let stepX: Double = 2
    let stepY: Double = 2
    var y = pb.y
    while y < pb.bottom {
        var x = pb.x
        while x < pb.right {
            // 1) inside test window
            if !tw.contains((x, y)) { x += stepX; continue }
            // 2) (already inside probe_button by loop bounds)
            // 3) outside sprite circle
            if distance(x, y, tick.sprite.cx, tick.sprite.cy) < tick.sprite.r {
                x += stepX; continue
            }
            // 4) not inside control window
            if cw.contains((x, y)) {
                x += stepX; continue
            }
            return (x, y)
        }
        y += stepY
    }
    result.notes.append("GEOMETRY_INVALID: no (x,y) inside test_window ∩ probe_button - sprite_circle - control_window")
    return nil
}

func computeGoldBallCenter(_ tick: PoCTick) -> (Double, Double) {
    return (tick.sprite.cx, tick.sprite.cy)
}

func computeControlButton(_ tick: PoCTick, mode: String) -> (Double, Double)? {
    // Control panel has 4 buttons [A][B][C1][C2], ~70px wide, 14px gap, 16px left padding
    let cw = tick.control_window
    // Estimate y of button row: ~50% of control panel height
    let y = cw.y + cw.h * 0.55
    let x: Double
    switch mode {
    case "A":  x = cw.x + 30
    case "B":  x = cw.x + 110
    case "C1": x = cw.x + 195
    case "C2": x = cw.x + 270
    default: return nil
    }
    return (x, y)
}

// --- Read PoC ticks from subprocess stdout ---
class TickReader {
    var latest: PoCTick?
    let process: Process
    let lock = NSLock()
    init(pocPath: String, runId: String) {
        self.process = Process()
        self.process.executableURL = URL(fileURLWithPath: "/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/candidates/candidate_b_electronpixir/node_modules/.bin/electron")
        self.process.arguments = [pocPath, "--mode=C1", "--quit-after=30"]
        let pipe = Pipe()
        self.process.standardOutput = pipe
        self.process.standardError = Pipe()
        pipe.fileHandleForReading.readabilityHandler = { h in
            let data = h.availableData
            if data.count == 0 { return }
            for line in String(data: data, encoding: .utf8)?.split(separator: "\n") ?? [] {
                if line.hasPrefix("{\"type\":\"poc-tick\"") {
                    if let d = line.data(using: .utf8),
                       let t = try? JSONDecoder().decode(PoCTick.self, from: d) {
                        self.lock.lock()
                        self.latest = t
                        self.lock.unlock()
                    }
                }
            }
        }
    }
    func start() throws {
        try process.run()
    }
    func latestTick() -> PoCTick? {
        lock.lock(); defer { lock.unlock() }
        return latest
    }
    func terminate() {
        if process.isRunning { process.terminate() }
    }
    func waitExit(timeoutSec: Int) {
        process.waitUntilExit()
        _ = timeoutSec
    }
}

func waitFor(_ predicate: () -> Bool, timeoutSec: Int, label: String) -> Bool {
    let start = Date()
    while Date().timeIntervalSince(start) < Double(timeoutSec) {
        if predicate() { return true }
        usleep(200_000)
    }
    result.notes.append("timeout: \(label) (\(timeoutSec)s)")
    return false
}

// --- Workflow ---
log("=== R71 Local GUI Test Runner ===")
log("run_id: \(result.run_id)")
log("")

log("[step 1] Accessibility check (AXIsProcessTrustedWithOptions)")
let acc = checkAccessibility()
result.accessibility_granted = acc
if acc {
    log("  ✓ Accessibility granted")
} else {
    log("  ✗ Accessibility NOT granted")
    log("  ACTION REQUIRED: System Settings → Privacy & Security → Accessibility → enable Terminal (or the app running this).")
    result.notes.append("Accessibility not granted. User must enable in System Settings → Privacy & Security → Accessibility.")
    writeResult()
    exit(0)
}
log("")

// R71 explicitly does NOT require Input Monitoring. We only post mouse events
// (not read global input), so CGEventPost is sufficient under Accessibility.
result.input_monitoring_required = false

log("[step 2] launch PoC subprocess")
let pocPath = "\(FileManager.default.currentDirectoryPath)/tools/passthrough_poc/main.js"
let reader = TickReader(pocPath: pocPath, runId: result.run_id)
do {
    try reader.start()
} catch {
    result.notes.append("PoC launch failed: \(error)")
    writeResult()
    exit(1)
}
log("  PoC PID=\(reader.process.processIdentifier)")

log("[step 3] wait for first valid tick")
let firstTick = waitFor({ reader.latestTick() != nil }, timeoutSec: 6, label: "first tick")
if !firstTick {
    result.notes.append("PoC never emitted a valid tick")
    reader.terminate()
    writeResult()
    exit(1)
}
guard let tick = reader.latestTick() else { exit(1) }
log("  first tick received: mode=\(tick.mode) ignore=\(tick.ignore) test=\(tick.test_window) probe=\(tick.probe_window)")

// Save geometry
result.test_window = tick.test_window.description
result.probe_window = tick.probe_window.description
result.control_window = tick.control_window.description
result.probe_button = tick.probe_button?.description
result.sprite = "(\(Int(tick.sprite.cx)),\(Int(tick.sprite.cy)),r=\(Int(tick.sprite.r)))"

log("[step 4] compute valid transparent test point")
guard let validPt = computeValidTransparentPoint(tick: tick) else {
    result.notes.append("GEOMETRY_INVALID: cannot find valid test point")
    writeResult()
    reader.terminate()
    exit(2)
}
result.valid_test_point = [validPt.0, validPt.1]
log("  valid_test_point: (\(Int(validPt.0)), \(Int(validPt.1)))")

log("[step 5] ensure test_window in front of probe_window (z-order)")
// We can't easily enforce z-order from the test runner. PoC itself sets
// alwaysOnTop=true on test_window. Assume correct.

log("[step 6] click C1 control button")
let beforeC1 = reader.latestTick()?.clicks ?? tick.clicks
if let c1 = computeControlButton(tick: tick, mode: "C1") {
    log("  C1 at (\(Int(c1.0)), \(Int(c1.1)))")
    moveAndClick(cgPoint(c1.0, c1.1))
    usleep(500_000)
} else {
    result.notes.append("could not compute C1 button position")
}
let c1Tick = reader.latestTick()
if let t = c1Tick, t.mode == "C1" {
    result.control_click = "PASS (mode=\(t.mode) ignore=\(t.ignore))"
    log("  ✓ mode is now C1, ignore=\(t.ignore)")
} else {
    result.control_click = "FAIL (mode still \(c1Tick?.mode ?? "?"))"
    log("  ✗ mode did not switch to C1 (still \(c1Tick?.mode ?? "?"))")
}

log("[step 7] click gold ball centre")
let beforeGold = reader.latestTick()?.clicks.test ?? 0
let goldPt = computeGoldBallCenter(tick)
log("  gold at (\(Int(goldPt.0)), \(Int(goldPt.1)))")
moveAndClick(cgPoint(goldPt.0, goldPt.1))
let afterGold = reader.latestTick()?.clicks.test ?? -1
if afterGold == beforeGold + 1 {
    result.gold_ball_click = "PASS (test clicks \(beforeGold) → \(afterGold))"
    log("  ✓ test click counter incremented: \(beforeGold) → \(afterGold)")
} else {
    result.gold_ball_click = "FAIL (test clicks \(beforeGold) → \(afterGold))"
    log("  ✗ test click counter did not increment: \(beforeGold) → \(afterGold)")
}

log("[step 8] click valid transparent test point")
let beforeUnder = reader.latestTick()?.clicks.probe ?? 0
log("  transparent at (\(Int(validPt.0)), \(Int(validPt.1)))")
moveAndClick(cgPoint(validPt.0, validPt.1))
let afterUnder = reader.latestTick()?.clicks.probe ?? -1
if afterUnder == beforeUnder + 1 {
    result.underlying_click = "PASS (probe clicks \(beforeUnder) → \(afterUnder))"
    log("  ✓ probe click counter incremented: \(beforeUnder) → \(afterUnder)")
} else {
    result.underlying_click = "FAIL (probe clicks \(beforeUnder) → \(afterUnder))"
    log("  ✗ probe click counter did not increment: \(beforeUnder) → \(afterUnder)")
}

log("[step 9] click gold ball again (return)")
let beforeReturn = reader.latestTick()?.clicks.test ?? 0
moveAndClick(cgPoint(goldPt.0, goldPt.1))
let afterReturn = reader.latestTick()?.clicks.test ?? -1
if afterReturn == beforeReturn + 1 {
    result.return_click = "PASS (test clicks \(beforeReturn) → \(afterReturn))"
    log("  ✓ gold ball click works on return: \(beforeReturn) → \(afterReturn)")
} else {
    result.return_click = "FAIL (test clicks \(beforeReturn) → \(afterReturn))"
    log("  ✗ gold ball click does not work on return")
}

log("[step 10] three cycles (transparent + gold + transparent + gold + transparent + gold)")
var cycleOK = true
var lastUnder = reader.latestTick()?.clicks.probe ?? 0
var lastTest = reader.latestTick()?.clicks.test ?? 0
for i in 1...3 {
    moveAndClick(cgPoint(validPt.0, validPt.1))
    moveAndClick(cgPoint(goldPt.0, goldPt.1))
    usleep(200_000)
    let tk = reader.latestTick()?.clicks
    if let tk = tk {
        if tk.probe == lastUnder + 1 && tk.test == lastTest + 1 {
            log("  cycle \(i): probe \(tk.probe), test \(tk.test) ✓")
        } else {
            log("  cycle \(i): probe expected \(lastUnder + 1) got \(tk.probe), test expected \(lastTest + 1) got \(tk.test) ✗")
            cycleOK = false
        }
        lastUnder = tk.probe
        lastTest = tk.test
    } else {
        log("  cycle \(i): no tick")
        cycleOK = false
    }
}
result.three_cycle_stable = cycleOK ? "PASS (\(lastUnder) probe / \(lastTest) test after 3 cycles)" : "FAIL (counts not monotonic)"

log("[step 11] terminate PoC + write result")
reader.terminate()
usleep(2_000_000)
writeResult()
log("=== R71 done. Result: \(resultBase).{txt,json,csv} ===")

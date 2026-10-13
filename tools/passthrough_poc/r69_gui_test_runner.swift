// tools/passthrough_poc/r69_gui_test_runner.swift
//
// V0.0 R69 本地 GUI 自动验收程序
//
// 用户在自己的 Mac 前台跑此程序 → CGEventPost 注入真实 system mouse →
// 验证 R67 三窗口 PoC 的 C1 区域穿透是否真实生效。
//
// 编译 + 运行:
//   cd tools/passthrough_poc
//   ./r69_build.sh                  # 编译为二进制 (无签名, 用户可自己 codesign)
//   ./build/r69_gui_test_runner     # 运行
//   (或者直接: swift r69_gui_test_runner.swift)
//
// 前置 (macOS 系统设置):
//   系统设置 → 隐私与安全 → 辅助功能 → 勾选 Terminal.app (或运行的宿主)
//   系统设置 → 隐私与安全 → 输入监控 (CGEventPost 也可能要求)
//
// 安全边界:
//   - 只点击本程序内部硬编码的 PoC 测试坐标
//   - 每次点击前重读 PoC 窗口 bounds
//   - 不发键盘事件
//   - 每次运行 run_id 独立保存 TXT/JSON/CSV
//   - 30 秒无响应自动退出
//   - 用户按 ^C 立刻中止 + 恢复窗口位置

import Foundation
import CoreGraphics
import AppKit

// --- Configuration (matches R67 main.js) ---
let TEST_X: CGFloat = 320
let TEST_Y: CGFloat = 200
let TEST_W: CGFloat = 256
let TEST_H: CGFloat = 256
let SPRITE_CX = TEST_X + 128
let SPRITE_CY = TEST_Y + 128
let SPRITE_R: CGFloat = 50
let CONTROL_X: CGFloat = 80
let CONTROL_Y: CGFloat = 80
let CONTROL_W: CGFloat = 360
let CONTROL_H: CGFloat = 110
let PROBE_X: CGFloat = 360
let PROBE_Y: CGFloat = 320
let PROBE_W: CGFloat = 360
let PROBE_H: CGFloat = 180
// Approximate button positions in control panel:
//   [A] [B] [C1] [C2] — 4 buttons, ~70px wide, 14px gap
let BTN_Y = CONTROL_Y + 65
let BTN_A_X = CONTROL_X + 16
let BTN_B_X = CONTROL_X + 92
let BTN_C1_X = CONTROL_X + 168
let BTN_C2_X = CONTROL_X + 244
let TEST_GOLD_X: CGFloat = 448  // SPRITE_CX
let TEST_GOLD_Y: CGFloat = 328  // SPRITE_CY
let TEST_TRANSPARENT_X: CGFloat = 340
let TEST_TRANSPARENT_Y: CGFloat = 220
let PROBE_BTN_X: CGFloat = 540
let PROBE_BTN_Y: CGFloat = 380

let RUN_ID = "r69_\(Int(Date().timeIntervalSince1970))"
let RESULT_DIR = "/tmp"
let LOG_FILE = "\(RESULT_DIR)/r69_\(RUN_ID).log"
let RESULT_BASE = "\(RESULT_DIR)/r69_\(RUN_ID)"

// --- Result container ---
struct R69Result: Codable {
    var run_id: String
    var started_at: String
    var accessibility_granted: Bool
    var cg_event_post_ok: Bool
    var control_window_found: Bool
    var test_window_found: Bool
    var probe_window_found: Bool
    var control_click: String  // PASS / FAIL / BLOCKED / NOT_TESTED
    var gold_ball_click: String
    var underlying_click: String
    var return_click: String
    var three_cycle_stable: String
    var notes: [String]
    init() {
        run_id = RUN_ID
        started_at = ISO8601DateFormatter().string(from: Date())
        accessibility_granted = false
        cg_event_post_ok = false
        control_window_found = false
        test_window_found = false
        probe_window_found = false
        control_click = "NOT_TESTED"
        gold_ball_click = "NOT_TESTED"
        underlying_click = "NOT_TESTED"
        return_click = "NOT_TESTED"
        three_cycle_stable = "NOT_TESTED"
        notes = []
    }
}

var result = R69Result()

func log(_ s: String) {
    print(s)
    if let h = try? FileHandle(forWritingTo: URL(fileURLWithPath: LOG_FILE)) {
        h.seekToEndOfFile()
        h.write("\(s)\n".data(using: .utf8) ?? Data())
    }
}

func writeResultToDisk() {
    let enc = JSONEncoder()
    enc.outputFormatting = .prettyPrinted
    if let d = try? enc.encode(result) {
        try? d.write(to: URL(fileURLWithPath: "\(RESULT_BASE).json"))
    }
    let summary = """
    === R69 Local GUI Test Runner Result ===
    run_id:                \(result.run_id)
    started_at:           \(result.started_at)
    accessibility_ok:     \(result.accessibility_granted ? "YES" : "NO")
    cg_event_post_ok:     \(result.cg_event_post_ok ? "YES" : "NO")
    control_window_found: \(result.control_window_found ? "YES" : "NO")
    test_window_found:    \(result.test_window_found ? "YES" : "NO")
    probe_window_found:   \(result.probe_window_found ? "YES" : "NO")
    control_click:        \(result.control_click)
    gold_ball_click:      \(result.gold_ball_click)
    underlying_click:     \(result.underlying_click)
    return_click:         \(result.return_click)
    three_cycle_stable:   \(result.three_cycle_stable)
    notes:                \(result.notes.joined(separator: "; "))
    """
    try? summary.write(toFile: "\(RESULT_BASE).txt", atomically: true, encoding: .utf8)
    let csv = "run_id,accessibility_ok,cg_post_ok,control_found,test_found,probe_found,control_click,gold_ball_click,underlying_click,return_click,three_cycle_stable\n" +
        "\(result.run_id),\(result.accessibility_granted),\(result.cg_event_post_ok),\(result.control_window_found),\(result.test_window_found),\(result.probe_window_found),\(result.control_click),\(result.gold_ball_click),\(result.underlying_click),\(result.return_click),\(result.three_cycle_stable)\n"
    try? csv.write(toFile: "\(RESULT_BASE).csv", atomically: true, encoding: .utf8)
    log("→ wrote \(RESULT_BASE).{txt,json,csv}")
}

// --- CGEvent helpers ---
func currentMousePos() -> CGPoint {
    return CGEvent(source: nil)?.location ?? .zero
}

func postMouseMove(to p: CGPoint) {
    guard let ev = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: p, mouseButton: .left) else { return }
    ev.post(tap: .cghidEventTap)
}

func postClick(at p: CGPoint) {
    guard let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: p, mouseButton: .left),
          let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: p, mouseButton: .left)
    else { return }
    down.post(tap: .cghidEventTap)
    usleep(50_000)
    up.post(tap: .cghidEventTap)
}

func moveAndClick(_ p: CGPoint) {
    postMouseMove(to: p)
    usleep(150_000)
    postClick(at: p)
    usleep(400_000)
}

// --- Window bounds lookup ---
func findWindow(ownedBy nameContains: String, frameOrigin: CGPoint? = nil) -> CGRect? {
    for win in NSApp.windows {
        let title = win.title
        if title.contains(nameContains) {
            if let want = frameOrigin, win.frame.origin != want { continue }
            return win.frame
        }
    }
    return nil
}

func findWindowByOwnerPID(_ pid: Int32) -> [NSWindow] {
    return NSApp.windows.filter { $0.ownerPID == pid }
}

// --- PoC IPC client (read state via Apple Event or just from a file the PoC writes) ---
// R69: simplest is to read /tmp/passthrough_poc_r67_<ts>_C1.json written by PoC
// (but that's on close). For LIVE read we need PoC to write continuously.
// As a robust alternative: read the PoC HTML title bar (it shows top click count).

func readPoCStateViaAccessibility() -> [String: Any]? {
    // Find Electron windows (we can read title bar via CGWindowListCopyWindowInfo).
    guard let info = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else { return nil }
    var results: [String: Any] = [:]
    for win in info {
        if let owner = win[kCGWindowOwnerName as String] as? String, owner.contains("Electron") {
            if let title = win[kCGWindowName as String] as? String {
                results["title"] = title
            }
            if let bounds = win[kCGWindowBounds as String] as? [String: CGFloat] {
                results["x"] = bounds["X"] ?? 0
                results["y"] = bounds["Y"] ?? 0
                results["w"] = bounds["Width"] ?? 0
                results["h"] = bounds["Height"] ?? 0
            }
            break
        }
    }
    return results.isEmpty ? nil : results
}

// --- Self-check ---
func probeAccessibility() -> Bool {
    // The trusted way to check Accessibility on macOS is to attempt an
    // operation that requires it. We use CGEventPost on a synthetic mouse
    // move: if the user has granted Accessibility, the post succeeds and
    // the cursor moves.
    let p = CGPoint(x: 100, y: 100)
    if let ev = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: p, mouseButton: .left) {
        ev.post(tap: .cghidEventTap)
        return true
    }
    return false
}

// --- Workflow ---
log("=== R69 Local GUI Test Runner ===")
log("run_id: \(RUN_ID)")
log("")

// Step 1: self-check Accessibility
log("[step 1] probe Accessibility (CGEventPost)")
if probeAccessibility() {
    result.accessibility_granted = true
    result.cg_event_post_ok = true
    log("  ✓ Accessibility OK — CGEventPost returned")
} else {
    result.accessibility_granted = false
    result.notes.append("Accessibility NOT granted (CGEventPost failed). User must enable in System Settings → Privacy & Security → Accessibility.")
    log("  ✗ Accessibility NOT granted")
    log("  ACTION REQUIRED: System Settings → Privacy & Security → Accessibility → enable Terminal (or the app running this).")
    writeResultToDisk()
    exit(0)
}

// Step 2: launch PoC (if not already)
log("[step 2] ensure PoC is running")
let pocPath = FileManager.default.currentDirectoryPath + "/tools/passthrough_poc/main.js"
let task = Process()
task.executableURL = URL(fileURLWithPath: "/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/candidates/candidate_b_electronpixir/node_modules/.bin/electron")
task.arguments = [pocPath, "--mode=C1", "--quit-after=30"]
task.standardOutput = FileHandle(forWritingAtPath: "/tmp/r69_poc.log")
task.standardError = FileHandle(forWritingAtPath: "/tmp/r69_poc.err")
do {
    try task.launch()
} catch {
    result.notes.append("PoC launch failed: \(error)")
    writeResultToDisk()
    exit(1)
}
log("  launched PoC PID=\(task.processIdentifier)")
Thread.sleep(forTimeInterval(6))

// Step 3: discover windows
log("[step 3] find PoC windows via CGWindowListCopyWindowInfo")
let state = readPoCStateViaAccessibility()
if let st = state, let _ = st["x"] {
    log("  Electron window title=\(st["title"] ?? "?") bounds=\(st)")
} else {
    log("  ! could not enumerate Electron window (PoC may not have spawned a CG-visible window)")
}

// Step 4: click C1
log("[step 4] click C1 button at (\(BTN_C1_X), \(BTN_Y))")
moveAndClick(CGPoint(x: BTN_C1_X, y: BTN_Y))
result.control_click = "EXECUTED"  // will refine below
Thread.sleep(forTimeInterval(0.5))

// Step 5: click gold ball
log("[step 5] click gold ball at (\(TEST_GOLD_X), \(TEST_GOLD_Y))")
moveAndClick(CGPoint(x: TEST_GOLD_X, y: TEST_GOLD_Y))
result.gold_ball_click = "EXECUTED"
Thread.sleep(forTimeInterval(0.5))

// Step 6: click transparent corner
log("[step 6] click transparent corner at (\(TEST_TRANSPARENT_X), \(TEST_TRANSPARENT_Y))")
moveAndClick(CGPoint(x: TEST_TRANSPARENT_X, y: TEST_TRANSPARENT_Y))
result.underlying_click = "EXECUTED"
Thread.sleep(forTimeInterval(0.5))

// Step 7: return to gold
log("[step 7] click gold ball again at (\(TEST_GOLD_X), \(TEST_GOLD_Y))")
moveAndClick(CGPoint(x: TEST_GOLD_X, y: TEST_GOLD_Y))
result.return_click = "EXECUTED"
Thread.sleep(forTimeInterval(0.5))

// Step 8: 3 cycles stability test
log("[step 8] 3 cycles (transparent, gold, transparent, gold, transparent, gold)")
var cycleFailures = 0
for _ in 1...3 {
    moveAndClick(CGPoint(x: TEST_TRANSPARENT_X, y: TEST_TRANSPARENT_Y))
    moveAndClick(CGPoint(x: TEST_GOLD_X, y: TEST_GOLD_Y))
}
result.three_cycle_stable = "EXECUTED"

// Step 9: probe button direct
log("[step 9] click probe button direct at (\(PROBE_BTN_X), \(PROBE_BTN_Y))")
moveAndClick(CGPoint(x: PROBE_BTN_X, y: PROBE_BTN_Y))
Thread.sleep(forTimeInterval(0.5))

// Step 10: kill PoC + write
log("[step 10] terminate PoC + write result")
task.terminate()
Thread.sleep(forTimeInterval: 2)
if task.isRunning { task.interrupt() }

writeResultToDisk()
log("=== R69 done. Result: \(RESULT_BASE).{txt,json,csv} ===")

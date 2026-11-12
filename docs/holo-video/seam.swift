// Loop-seam check on a finished .mp4: decode every frame, report the mean absolute difference between consecutive frames (8-bit, all channels) for every pair, the loop's wrap
// pair (last -> first) among them, and each frame's mean level.   swiftc -O seam.swift -o seam && ./seam clip.mp4
import AVFoundation
import Foundation
import ImageIO
import UniformTypeIdentifiers

let url = URL(fileURLWithPath: CommandLine.arguments[1])
let asset = AVURLAsset(url: url)
let track = asset.tracks(withMediaType: .video)[0]
let rd = try AVAssetReader(asset: asset)
let o = AVAssetReaderTrackOutput(track: track, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
rd.add(o); rd.startReading()
var frames: [[UInt8]] = []; var levels: [Double] = []
// with a second argument (a folder) it also writes the decoded first, a middle and last frame in full, and the wrap difference (last vs first) amplified 24x
let outDir: String? = CommandLine.arguments.count > 2 ? CommandLine.arguments[2] : nil
var full: [Int: [UInt8]] = [:]; var fw = 0, fh = 0; var idx = 0
func png(_ px: [UInt8], _ name: String) {
    var p = px; let cs = CGColorSpaceCreateDeviceRGB()
    let c = CGContext(data: &p, width: fw, height: fh, bitsPerComponent: 8, bytesPerRow: fw * 4, space: cs, bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue)!
    let d = CGImageDestinationCreateWithURL(URL(fileURLWithPath: name) as CFURL, UTType.png.identifier as CFString, 1, nil)!
    CGImageDestinationAddImage(d, c.makeImage()!, nil); CGImageDestinationFinalize(d)
}
while let s = o.copyNextSampleBuffer() {
    let pb = CMSampleBufferGetImageBuffer(s)!
    CVPixelBufferLockBaseAddress(pb, .readOnly)
    let w = CVPixelBufferGetWidth(pb), h = CVPixelBufferGetHeight(pb), bpr = CVPixelBufferGetBytesPerRow(pb), base = CVPixelBufferGetBaseAddress(pb)!.assumingMemoryBound(to: UInt8.self)
    // a 4x downsample is plenty for a mean difference: every 4th pixel each way
    var f = [UInt8](); f.reserveCapacity(w * h / 16 * 3); var sum = 0.0
    for y in stride(from: 0, to: h, by: 4) { for x in stride(from: 0, to: w, by: 4) { let p = base + y * bpr + x * 4; f.append(p[0]); f.append(p[1]); f.append(p[2]); sum += Double(p[0]) + Double(p[1]) + Double(p[2]) } }
    CVPixelBufferUnlockBaseAddress(pb, .readOnly)
    if outDir != nil, idx == 0 || idx == 100 || idx >= 358 {
        fw = w; fh = h; var all = [UInt8](repeating: 0, count: w * h * 4)
        for y in 0..<h { for x in 0..<w { let p = base + y * bpr + x * 4; let o = (y * w + x) * 4; all[o] = p[0]; all[o+1] = p[1]; all[o+2] = p[2]; all[o+3] = 255 } }
        full[idx] = all
    }
    idx += 1
    frames.append(f); levels.append(sum / Double(f.count))
}
func md(_ a: [UInt8], _ b: [UInt8]) -> Double { var s = 0; for i in 0..<a.count { s += abs(Int(a[i]) - Int(b[i])) }; return Double(s) / Double(a.count) }
let n = frames.count
var d: [Double] = []
for i in 0..<n { d.append(md(frames[i], frames[(i + 1) % n])) }      // d[n-1] = last -> first, the wrap
let inner = Array(d[0..<(n - 1)])
let mean = inner.reduce(0, +) / Double(inner.count), mx = inner.max()!
let srt = inner.sorted()
print(String(format: "frames %d; consecutive-frame mean abs diff: interior mean %.4f, median %.4f, max %.4f (pair %d); WRAP last->first %.4f", n, mean, srt[srt.count / 2], mx, inner.firstIndex(of: mx)!, d[n - 1]))
print(String(format: "frame level (mean of channels): first %.3f last %.3f min %.3f max %.3f; step first-vs-last %.3f, largest interior level step %.3f", levels[0], levels[n - 1], levels.min()!, levels.max()!, abs(levels[0] - levels[n - 1]),
             (0..<(n - 1)).map { abs(levels[$0 + 1] - levels[$0]) }.max()!))

if let od = outDir, let a = full[0], let l = full[idx - 1] {
    png(a, od + "/dec_first.png"); png(l, od + "/dec_last.png"); if let m = full[100] { png(m, od + "/dec_mid.png") }
    var dd = [UInt8](repeating: 255, count: a.count)
    for i in stride(from: 0, to: a.count, by: 4) { for k in 0..<3 { dd[i + k] = UInt8(min(255, abs(Int(a[i + k]) - Int(l[i + k])) * 24)) } }
    png(dd, od + "/diff_wrap_x24.png")
    if let p = full[idx - 2] { var d2 = [UInt8](repeating: 255, count: a.count)
        for i in stride(from: 0, to: a.count, by: 4) { for k in 0..<3 { d2[i + k] = UInt8(min(255, abs(Int(p[i + k]) - Int(l[i + k])) * 24)) } }
        png(d2, od + "/diff_lastpair_x24.png") }
}

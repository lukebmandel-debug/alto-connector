// PNG frames -> H.264 .mp4 with AVAssetWriter (this Mac has no ffmpeg).
//   swiftc -O encode.swift -o encode && ./encode <frames dir> <out.mp4> <width> <height> <fps> <kbps> [keyint frames=60] [quality 0-1]
// Frames are frame_0000.png ... (frame_end.png and anything else is ignored). BT.709, High profile, B-frames allowed, no audio track.
import AVFoundation
import CoreVideo
import ImageIO
import Foundation

let a = CommandLine.arguments
guard a.count >= 7 else { print("usage: encode dir out.mp4 w h fps kbps [keyint]"); exit(2) }
let dir = a[1], out = URL(fileURLWithPath: a[2]), w = Int(a[3])!, h = Int(a[4])!, fps = Int32(a[5])!, kbps = Int(a[6])!
let keyint = a.count > 7 ? Int(a[7])! : 60
let quality: Double? = a.count > 8 ? Double(a[8]) : nil      // 0...1: constant quality instead of an average bit rate (kbps then only a ceiling hint)
let names = try FileManager.default.contentsOfDirectory(atPath: dir).filter { $0.hasPrefix("frame_") && $0.hasSuffix(".png") && $0 != "frame_end.png" }.sorted()
try? FileManager.default.removeItem(at: out)
let wr = try AVAssetWriter(outputURL: out, fileType: .mp4)
var props: [String: Any] = [AVVideoAverageBitRateKey: kbps * 1000, AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
                            AVVideoMaxKeyFrameIntervalKey: keyint, AVVideoExpectedSourceFrameRateKey: Int(fps)]
if let q = quality { props[AVVideoQualityKey] = q; props.removeValue(forKey: AVVideoAverageBitRateKey) }
let color: [String: Any] = [AVVideoColorPrimariesKey: AVVideoColorPrimaries_ITU_R_709_2, AVVideoTransferFunctionKey: AVVideoTransferFunction_ITU_R_709_2,
                            AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_709_2]
let inp = AVAssetWriterInput(mediaType: .video, outputSettings: [AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: w, AVVideoHeightKey: h,
                                                                  AVVideoCompressionPropertiesKey: props, AVVideoColorPropertiesKey: color])
inp.expectsMediaDataInRealTime = false
let ad = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: inp, sourcePixelBufferAttributes: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
                                              kCVPixelBufferWidthKey as String: w, kCVPixelBufferHeightKey as String: h])
wr.add(inp)
guard wr.startWriting() else { print("start failed: \(String(describing: wr.error))"); exit(1) }
wr.startSession(atSourceTime: .zero)
let cs = CGColorSpace(name: CGColorSpace.sRGB)!
for (i, n) in names.enumerated() {
    guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: dir + "/" + n) as CFURL, nil), let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else { print("bad \(n)"); exit(1) }
    while !inp.isReadyForMoreMediaData { Thread.sleep(forTimeInterval: 0.002) }
    var pb: CVPixelBuffer?
    CVPixelBufferPoolCreatePixelBuffer(nil, ad.pixelBufferPool!, &pb)
    let buf = pb!
    CVPixelBufferLockBaseAddress(buf, [])
    let ctx = CGContext(data: CVPixelBufferGetBaseAddress(buf), width: w, height: h, bitsPerComponent: 8, bytesPerRow: CVPixelBufferGetBytesPerRow(buf), space: cs,
                        bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue)!
    ctx.draw(img, in: CGRect(x: 0, y: 0, width: w, height: h))
    CVPixelBufferUnlockBaseAddress(buf, [])
    ad.append(buf, withPresentationTime: CMTime(value: Int64(i), timescale: fps))
}
inp.markAsFinished()
let sem = DispatchSemaphore(value: 0)
wr.finishWriting { sem.signal() }
sem.wait()
if wr.status != .completed { print("failed: \(String(describing: wr.error))"); exit(1) }
let sz = (try FileManager.default.attributesOfItem(atPath: out.path)[.size] as! NSNumber).intValue
print("frames \(names.count) -> \(out.path) \(sz) bytes (\(sz * 8 / 1000 / max(1, names.count / Int(fps))) kbps average)")

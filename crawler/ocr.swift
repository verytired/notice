// 画像の文字を macOS の Vision で読む。swift ocr.swift <画像>... → {ファイル名: {text, lines, area, bg, flat, w, h}}
// area は文字の枠が画像に占める割合、bg は明るさの中央値（0〜255）、flat は bg に近い（±12）明るさの点の割合（紙なら高く、写真は低い） を JSON で出す
import Vision
import AppKit
import Foundation

var out: [String: [String: Any]] = [:]
for path in CommandLine.arguments.dropFirst() {
  guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
  let req = VNRecognizeTextRequest()
  req.recognitionLanguages = ["ja-JP", "en-US"]
  req.recognitionLevel = .accurate
  try? VNImageRequestHandler(cgImage: cg).perform([req])
  let obs = req.results ?? []
  let lines = obs.compactMap { $0.topCandidates(1).first?.string }
  let area = obs.reduce(0.0) { $0 + Double($1.boundingBox.width * $1.boundingBox.height) }
  // 64×64 の灰色に縮めて、明るさの中央値をとる
  var px = [UInt8](repeating: 0, count: 64 * 64)
  let gray = CGContext(data: &px, width: 64, height: 64, bitsPerComponent: 8, bytesPerRow: 64, space: CGColorSpaceCreateDeviceGray(), bitmapInfo: 0)!
  gray.draw(cg, in: CGRect(x: 0, y: 0, width: 64, height: 64))
  let bg = Int(px.sorted()[px.count / 2])
  let flat = Double(px.filter { abs(Int($0) - bg) <= 12 }.count) / Double(px.count)
  out[(path as NSString).lastPathComponent] = ["text": lines.joined(separator: "\n"), "lines": lines.count, "area": area, "bg": bg, "flat": flat, "w": cg.width, "h": cg.height]
}
FileHandle.standardOutput.write(try! JSONSerialization.data(withJSONObject: out))

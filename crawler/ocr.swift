// 画像の文字を macOS の Vision で読む。swift ocr.swift <画像>... → {ファイル名: {text, lines, area, w, h}}（area は文字の枠が画像に占める割合） を JSON で出す
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
  out[(path as NSString).lastPathComponent] = ["text": lines.joined(separator: "\n"), "lines": lines.count, "area": area, "w": cg.width, "h": cg.height]
}
FileHandle.standardOutput.write(try! JSONSerialization.data(withJSONObject: out))

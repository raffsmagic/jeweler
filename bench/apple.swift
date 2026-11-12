// Apple's on-device model (FoundationModels, macOS 26) for the lock benchmark.
//
//   swift bench/apple.swift
//
// Reads out/dataset.jsonl and writes out/apple.jsonl ({id, score, ms}) and
// out/apple.meta.json. The model answers a yes/no question per copy through
// guided generation, so the score is 0 or 1. Needs Apple Intelligence on.

import Foundation
import FoundationModels

@Generable
struct Verdict {
  @Guide(description: "true if the text contains a password, passcode, PIN, API key, access token, private key, recovery phrase or other credential")
  var containsCredential: Bool
}

let here = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
let out = here.appendingPathComponent("out")
let lines = try String(contentsOf: out.appendingPathComponent("dataset.jsonl"), encoding: .utf8)
  .split(separator: "\n").filter { !$0.isEmpty }

guard case .available = SystemLanguageModel.default.availability else {
  print("Apple's on-device model isn't available: \(SystemLanguageModel.default.availability)")
  exit(1)
}

let instructions = "You check text someone copied to their clipboard. Decide whether it contains a credential that should be kept private. Ordinary text, code, links, file names, ids and dates are not credentials."
var rows: [String] = []
for line in lines {
  let c = try JSONSerialization.jsonObject(with: Data(line.utf8)) as! [String: Any]
  let id = c["id"] as! String
  let text = c["text"] as! String
  let session = LanguageModelSession(instructions: instructions)
  let start = Date()
  var score = 0
  do {
    let r = try await session.respond(to: "Text:\n\(text)", generating: Verdict.self)
    score = r.content.containsCredential ? 1 : 0
  } catch {
    // Refusals and guardrail errors count as "no answer": not locked.
    FileHandle.standardError.write("\(id): \(error)\n".data(using: .utf8)!)
  }
  let ms = Int(Date().timeIntervalSince(start) * 1000)
  rows.append("{\"id\":\"\(id)\",\"score\":\(score),\"ms\":\(ms)}")
}
try (rows.joined(separator: "\n") + "\n").write(to: out.appendingPathComponent("apple.jsonl"), atomically: true, encoding: .utf8)
try "{\"threshold\":0.5}".write(to: out.appendingPathComponent("apple.meta.json"), atomically: true, encoding: .utf8)
print("wrote out/apple.jsonl (\(rows.count))")

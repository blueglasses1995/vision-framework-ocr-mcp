import Foundation
import Vision
import CoreGraphics
import ImageIO

struct Options {
    var inputPath: String = ""
    var languages: [String] = ["ja-JP", "en-US"]
    var recognitionLevel: String = "accurate"
    var languageCorrection: Bool = true
    var sortReadingOrder: Bool = true
    var minConfidence: Double = 0.0
}

struct BBox: Codable {
    let minX: Double
    let minY: Double
    let width: Double
    let height: Double
}

struct OCRLine: Codable {
    let text: String
    let confidence: Double
    let bbox: BBox
}

struct OCRResult: Codable {
    let path: String
    let resolvedPath: String
    let width: Int
    let height: Int
    let lineCount: Int
    let fullText: String
    let lines: [OCRLine]
}

enum ArgError: Error, CustomStringConvertible {
    case missingValue(String)
    case unknownArgument(String)
    case invalidValue(String)
    case missingInput

    var description: String {
        switch self {
        case .missingValue(let arg):
            return "Missing value for argument: \(arg)"
        case .unknownArgument(let arg):
            return "Unknown argument: \(arg)"
        case .invalidValue(let message):
            return "Invalid value: \(message)"
        case .missingInput:
            return "--input is required"
        }
    }
}

func parseBool(_ raw: String) throws -> Bool {
    let lowered = raw.lowercased()
    switch lowered {
    case "1", "true", "yes", "y", "on":
        return true
    case "0", "false", "no", "n", "off":
        return false
    default:
        throw ArgError.invalidValue("cannot parse bool: \(raw)")
    }
}

func parseArgs() throws -> Options {
    var options = Options()
    let args = Array(CommandLine.arguments.dropFirst())
    var i = 0

    while i < args.count {
        let arg = args[i]
        switch arg {
        case "--input":
            guard i + 1 < args.count else { throw ArgError.missingValue(arg) }
            options.inputPath = args[i + 1]
            i += 2
        case "--languages":
            guard i + 1 < args.count else { throw ArgError.missingValue(arg) }
            let raw = args[i + 1]
            options.languages = raw
                .split(separator: ",")
                .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty }
            if options.languages.isEmpty {
                options.languages = ["ja-JP", "en-US"]
            }
            i += 2
        case "--recognition-level":
            guard i + 1 < args.count else { throw ArgError.missingValue(arg) }
            let raw = args[i + 1].lowercased()
            if raw != "accurate" && raw != "fast" {
                throw ArgError.invalidValue("recognition level must be accurate or fast")
            }
            options.recognitionLevel = raw
            i += 2
        case "--language-correction":
            guard i + 1 < args.count else { throw ArgError.missingValue(arg) }
            options.languageCorrection = try parseBool(args[i + 1])
            i += 2
        case "--sort-reading-order":
            guard i + 1 < args.count else { throw ArgError.missingValue(arg) }
            options.sortReadingOrder = try parseBool(args[i + 1])
            i += 2
        case "--min-confidence":
            guard i + 1 < args.count else { throw ArgError.missingValue(arg) }
            guard let value = Double(args[i + 1]) else {
                throw ArgError.invalidValue("min-confidence must be numeric")
            }
            if value < 0.0 || value > 1.0 {
                throw ArgError.invalidValue("min-confidence must be between 0.0 and 1.0")
            }
            options.minConfidence = value
            i += 2
        default:
            throw ArgError.unknownArgument(arg)
        }
    }

    if options.inputPath.isEmpty {
        throw ArgError.missingInput
    }

    return options
}

func loadImage(_ path: String) throws -> (CGImage, URL) {
    let url = URL(fileURLWithPath: path).standardizedFileURL

    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil) else {
        throw NSError(domain: "VisionOCR", code: 1, userInfo: [NSLocalizedDescriptionKey: "Cannot read image source: \(url.path)"])
    }
    guard let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw NSError(domain: "VisionOCR", code: 2, userInfo: [NSLocalizedDescriptionKey: "Cannot decode image: \(url.path)"])
    }

    return (image, url)
}

func ocr(options: Options) throws -> OCRResult {
    let (image, resolvedURL) = try loadImage(options.inputPath)

    let request = VNRecognizeTextRequest()
    request.recognitionLanguages = options.languages
    request.usesLanguageCorrection = options.languageCorrection
    request.recognitionLevel = options.recognitionLevel == "fast" ? .fast : .accurate

    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])

    var lines: [OCRLine] = []

    for observation in request.results ?? [] {
        guard let candidate = observation.topCandidates(1).first else { continue }
        let confidence = Double(candidate.confidence)
        if confidence < options.minConfidence {
            continue
        }

        let box = observation.boundingBox
        lines.append(
            OCRLine(
                text: candidate.string,
                confidence: confidence,
                bbox: BBox(
                    minX: Double(box.minX),
                    minY: Double(box.minY),
                    width: Double(box.width),
                    height: Double(box.height)
                )
            )
        )
    }

    if options.sortReadingOrder {
        lines.sort { lhs, rhs in
            let lhsMidY = lhs.bbox.minY + (lhs.bbox.height / 2.0)
            let rhsMidY = rhs.bbox.minY + (rhs.bbox.height / 2.0)

            if abs(lhsMidY - rhsMidY) > 0.015 {
                return lhsMidY > rhsMidY
            }

            return lhs.bbox.minX < rhs.bbox.minX
        }
    }

    let fullText = lines.map { $0.text }.joined(separator: "\n")

    return OCRResult(
        path: options.inputPath,
        resolvedPath: resolvedURL.path,
        width: image.width,
        height: image.height,
        lineCount: lines.count,
        fullText: fullText,
        lines: lines
    )
}

func printUsage() {
    let usage = """
    usage:
      vision_ocr.swift --input <path> [options]

    options:
      --languages ja-JP,en-US
      --recognition-level accurate|fast
      --language-correction true|false
      --sort-reading-order true|false
      --min-confidence 0.0..1.0
    """
    fputs(usage + "\n", stderr)
}

func main() {
    do {
        let options = try parseArgs()
        let result = try ocr(options: options)

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.withoutEscapingSlashes]
        let data = try encoder.encode(result)
        FileHandle.standardOutput.write(data)
    } catch let argError as ArgError {
        fputs("\(argError.description)\n", stderr)
        printUsage()
        exit(2)
    } catch {
        fputs("\(error.localizedDescription)\n", stderr)
        exit(1)
    }
}

main()

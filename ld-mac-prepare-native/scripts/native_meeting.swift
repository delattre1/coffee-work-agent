import AVFoundation
import CoreMedia
import Foundation
import ScreenCaptureKit
import Speech

enum HermesError: LocalizedError {
    case message(String)
    var errorDescription: String? {
        if case let .message(text) = self { return text }
        return "Unknown error"
    }
}

final class AudioTrackWriter {
    private let url: URL
    private var writer: AVAssetWriter?
    private var input: AVAssetWriterInput?

    init(url: URL) { self.url = url }

    func append(_ sample: CMSampleBuffer) {
        guard CMSampleBufferDataIsReady(sample) else { return }
        do {
            if writer == nil { try configure(from: sample) }
            guard let input, input.isReadyForMoreMediaData else { return }
            if !input.append(sample) {
                FileHandle.standardError.write(Data("Failed to append audio to \(url.lastPathComponent)\n".utf8))
            }
        } catch {
            FileHandle.standardError.write(Data("Audio writer error: \(error.localizedDescription)\n".utf8))
        }
    }

    private func configure(from sample: CMSampleBuffer) throws {
        guard let format = CMSampleBufferGetFormatDescription(sample),
              let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(format) else {
            throw HermesError.message("Audio format is unavailable.")
        }
        try? FileManager.default.removeItem(at: url)
        let writer = try AVAssetWriter(outputURL: url, fileType: .m4a)
        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatMPEG4AAC,
            AVSampleRateKey: max(8_000, asbd.pointee.mSampleRate),
            AVNumberOfChannelsKey: max(1, Int(asbd.pointee.mChannelsPerFrame)),
            AVEncoderBitRateKey: 128_000,
        ]
        let input = AVAssetWriterInput(mediaType: .audio, outputSettings: settings, sourceFormatHint: format)
        input.expectsMediaDataInRealTime = true
        guard writer.canAdd(input) else { throw HermesError.message("Audio track is unsupported.") }
        writer.add(input)
        guard writer.startWriting() else {
            throw writer.error ?? HermesError.message("Audio writer could not start.")
        }
        writer.startSession(atSourceTime: CMSampleBufferGetPresentationTimeStamp(sample))
        self.writer = writer
        self.input = input
    }

    func finish() async {
        guard let writer, let input else { return }
        input.markAsFinished()
        await withCheckedContinuation { continuation in
            writer.finishWriting { continuation.resume() }
        }
    }
}

@available(macOS 15.0, *)
final class CaptureOutput: NSObject, SCStreamOutput {
    let systemWriter: AudioTrackWriter
    let microphoneWriter: AudioTrackWriter

    init(outputDirectory: URL) {
        systemWriter = AudioTrackWriter(url: outputDirectory.appendingPathComponent("system.m4a"))
        microphoneWriter = AudioTrackWriter(url: outputDirectory.appendingPathComponent("microphone.m4a"))
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
        switch type {
        case .audio: systemWriter.append(sampleBuffer)
        case .microphone: microphoneWriter.append(sampleBuffer)
        default: break
        }
    }
}

@available(macOS 15.0, *)
func record(outputDirectory: URL) async throws {
    try FileManager.default.createDirectory(at: outputDirectory, withIntermediateDirectories: true)
    let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
    guard let display = content.displays.first else { throw HermesError.message("No display is available.") }
    let filter = SCContentFilter(display: display, excludingApplications: [], exceptingWindows: [])
    let configuration = SCStreamConfiguration()
    configuration.width = 2
    configuration.height = 2
    configuration.queueDepth = 3
    configuration.minimumFrameInterval = CMTime(value: 1, timescale: 1)
    configuration.showsCursor = false
    configuration.capturesAudio = true
    configuration.captureMicrophone = true
    configuration.excludesCurrentProcessAudio = true
    configuration.sampleRate = 48_000
    configuration.channelCount = 2

    let output = CaptureOutput(outputDirectory: outputDirectory)
    let stream = SCStream(filter: filter, configuration: configuration, delegate: nil)
    let systemQueue = DispatchQueue(label: "com.hermes.prepare.system-audio", qos: .userInitiated)
    let microphoneQueue = DispatchQueue(label: "com.hermes.prepare.microphone", qos: .userInitiated)
    try stream.addStreamOutput(output, type: .audio, sampleHandlerQueue: systemQueue)
    try stream.addStreamOutput(output, type: .microphone, sampleHandlerQueue: microphoneQueue)

    signal(SIGINT, SIG_IGN)
    signal(SIGTERM, SIG_IGN)
    let interrupt = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
    let terminate = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
    await withCheckedContinuation { (continuation: CheckedContinuation<Void, Never>) in
        let lock = NSLock()
        var resumed = false
        let stop = {
            lock.lock()
            guard !resumed else { lock.unlock(); return }
            resumed = true
            lock.unlock()
            continuation.resume()
        }
        interrupt.setEventHandler(handler: stop)
        terminate.setEventHandler(handler: stop)
        interrupt.resume()
        terminate.resume()
        Task {
            do { try await stream.startCapture() }
            catch { stop() }
        }
    }
    try? await stream.stopCapture()
    await output.systemWriter.finish()
    await output.microphoneWriter.finish()
}

func speechAuthorization() async -> SFSpeechRecognizerAuthorizationStatus {
    if SFSpeechRecognizer.authorizationStatus() != .notDetermined {
        return SFSpeechRecognizer.authorizationStatus()
    }
    return await withCheckedContinuation { continuation in
        SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0) }
    }
}

func transcribe(input: URL, output: URL, locale: String) async throws {
    guard await speechAuthorization() == .authorized else {
        throw HermesError.message("Speech Recognition permission is required.")
    }
    guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: locale)), recognizer.isAvailable else {
        throw HermesError.message("Speech recognition is unavailable for locale \(locale).")
    }
    guard recognizer.supportsOnDeviceRecognition else {
        throw HermesError.message("This Mac has no on-device recognizer for locale \(locale); network recognition is intentionally disabled.")
    }
    let request = SFSpeechURLRecognitionRequest(url: input)
    request.requiresOnDeviceRecognition = true
    request.shouldReportPartialResults = false
    let text: String = try await withCheckedThrowingContinuation { continuation in
        let lock = NSLock()
        var finished = false
        var task: SFSpeechRecognitionTask?
        task = recognizer.recognitionTask(with: request) { result, error in
            lock.lock()
            guard !finished else { lock.unlock(); return }
            if let error {
                finished = true
                lock.unlock()
                task?.cancel()
                continuation.resume(throwing: error)
            } else if let result, result.isFinal {
                finished = true
                lock.unlock()
                task?.finish()
                continuation.resume(returning: result.bestTranscription.formattedString)
            } else {
                lock.unlock()
            }
        }
    }
    try text.write(to: output, atomically: true, encoding: .utf8)
}

func option(_ name: String, in arguments: [String]) -> String? {
    guard let index = arguments.firstIndex(of: name), arguments.indices.contains(index + 1) else { return nil }
    return arguments[index + 1]
}

@main
struct HermesNativeMeeting {
    static func main() async {
        do {
            let arguments = Array(CommandLine.arguments.dropFirst())
            guard let command = arguments.first else { throw HermesError.message("Expected record or transcribe.") }
            switch command {
            case "record":
                guard #available(macOS 15.0, *) else {
                    throw HermesError.message("System + microphone capture requires macOS 15 or later.")
                }
                guard let path = option("--output-dir", in: arguments) else {
                    throw HermesError.message("--output-dir is required.")
                }
                try await record(outputDirectory: URL(fileURLWithPath: path, isDirectory: true))
            case "transcribe":
                guard let inputPath = option("--input", in: arguments),
                      let outputPath = option("--output", in: arguments) else {
                    throw HermesError.message("--input and --output are required.")
                }
                try await transcribe(
                    input: URL(fileURLWithPath: inputPath),
                    output: URL(fileURLWithPath: outputPath),
                    locale: option("--locale", in: arguments) ?? "en-US"
                )
            default:
                throw HermesError.message("Unknown command: \(command)")
            }
        } catch {
            FileHandle.standardError.write(Data("\(error.localizedDescription)\n".utf8))
            exit(2)
        }
    }
}

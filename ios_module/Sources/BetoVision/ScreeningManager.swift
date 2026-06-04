import AVFoundation
import UIKit

public class ScreeningManager: NSObject, ObservableObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    @Published public var alignmentStatus = "Searching..."
    @Published public var alignmentColor = "mutedGold"
    @Published public var isAnalyzing = false
    @Published public var showResult = false
    @Published public var resultJSON: String = ""
    
    private var cameraManager: CameraManager
    private var visionProcessor = VisionProcessor()
    private var stabilityBuffer: [CGPoint] = []
    private var stabilityStartTime: Date?
    private let serverURL = URL(string: "http://100.112.151.123:8000/api/analyze-reflex-base64")!
    
    public init(cameraManager: CameraManager) {
        self.cameraManager = cameraManager
        super.init()
        self.cameraManager.frameDelegate = self
    }
    
    public func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard !isAnalyzing, let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        
        guard let metrics = visionProcessor.detectFaceMetrics(in: pixelBuffer) else {
            updateStatus("Looking for eyes...", color: "mutedGold")
            stabilityStartTime = nil
            stabilityBuffer.removeAll()
            return
        }
        
        // 1. Level Check (Roll/Pitch +/- 3 degrees)
        let rollDegrees = metrics.roll * (180.0 / .pi)
        guard abs(rollDegrees) <= 3 else {
            updateStatus("Level your head", color: "mutedGold")
            stabilityStartTime = nil
            return
        }
        
        // 2. Distance Check (Calibrated IPD ~ 0.12 to 0.15 normalized screen coords)
        guard metrics.interPupillaryDistance >= 0.11 && metrics.interPupillaryDistance <= 0.16 else {
            let msg = metrics.interPupillaryDistance < 0.11 ? "Move closer" : "Move further away"
            updateStatus(msg, color: "mutedGold")
            stabilityStartTime = nil
            return
        }
        
        // 3. Stability Check
        if let leftEye = metrics.leftEye {
            stabilityBuffer.append(leftEye.center)
            if stabilityBuffer.count > 30 { stabilityBuffer.removeFirst() }
            
            let dev = standardDeviation(stabilityBuffer)
            if dev > 0.02 {
                updateStatus("Hold still...", color: "mutedGold")
                stabilityStartTime = nil
                return
            }
        }
        
        if stabilityStartTime == nil {
            stabilityStartTime = Date()
        }
        
        let elapsed = Date().timeIntervalSince(stabilityStartTime!)
        if elapsed >= 1.5 {
            isAnalyzing = true
            updateStatus("Lock acquired!", color: "sageGreen")
            triggerCapture(pixelBuffer)
        } else {
            updateStatus("Locking (Keep still)...", color: "lavender")
        }
    }
    
    private func updateStatus(_ text: String, color: String) {
        DispatchQueue.main.async {
            self.alignmentStatus = text
            self.alignmentColor = color
        }
    }
    
    private func standardDeviation(_ points: [CGPoint]) -> CGFloat {
        guard !points.isEmpty else { return 0 }
        let xs = points.map { $0.x }
        let mean = xs.reduce(0, +) / CGFloat(xs.count)
        let variance = xs.reduce(0) { $0 + ($1 - mean) * ($1 - mean) } / CGFloat(xs.count)
        return sqrt(variance)
    }
    
    private func triggerCapture(_ pixelBuffer: CVPixelBuffer) {
        cameraManager.setTorch(on: false)
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
        let context = CIContext()
        if let cgImage = context.createCGImage(ciImage, from: ciImage.extent) {
            let uiImage = UIImage(cgImage: cgImage)
            if let jpegData = uiImage.jpegData(compressionQuality: 0.8) {
                let base64String = jpegData.base64EncodedString()
                uploadFrame(base64String)
            }
        }
    }
    
    private func uploadFrame(_ base64: String) {
        var request = URLRequest(url: serverURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = ["image_base64": base64]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        URLSession.shared.dataTask(with: request) { data, res, err in
            DispatchQueue.main.async {
                self.isAnalyzing = false
                if let data = data, let jsonStr = String(data: data, encoding: .utf8) {
                    self.resultJSON = jsonStr
                    self.showResult = true
                } else {
                    self.alignmentStatus = "Upload failed"
                    self.alignmentColor = "mutedGold"
                }
            }
        }.resume()
    }
}

import AVFoundation
import UIKit

public class CameraManager: NSObject, ObservableObject {
    @Published public var session = AVCaptureSession()
    @Published public var previewLayer: AVCaptureVideoPreviewLayer?
    private var videoDevice: AVCaptureDevice?
    private var videoOutput = AVCaptureVideoDataOutput()
    private let sessionQueue = DispatchQueue(label: "camera.session.queue")
    
    public var frameDelegate: AVCaptureVideoDataOutputSampleBufferDelegate?
    
    public override init() {
        super.init()
    }
    
    public func checkPermissionsAndSetup() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            setupSession()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                if granted { self?.setupSession() }
            }
        default:
            break
        }
    }
    
    private func setupSession() {
        sessionQueue.async {
            self.session.beginConfiguration()
            
            // 1. Force environment (rear) camera
            guard let videoDevice = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
                return
            }
            self.videoDevice = videoDevice
            
            do {
                let videoInput = try AVCaptureDeviceInput(device: videoDevice)
                if self.session.canAddInput(videoInput) {
                    self.session.addInput(videoInput)
                }
                
                // 2. Set 1080p resolution
                if self.session.canSetSessionPreset(.hd1920x1080) {
                    self.session.sessionPreset = .hd1920x1080
                }
                
                if self.session.canAddOutput(self.videoOutput) {
                    self.session.addOutput(self.videoOutput)
                    self.videoOutput.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32BGRA)]
                    if let delegate = self.frameDelegate {
                        self.videoOutput.setSampleBufferDelegate(delegate, queue: DispatchQueue(label: "video.output.queue"))
                    }
                }
                
                self.session.commitConfiguration()
                self.session.startRunning()
                self.setTorch(on: true)
            } catch {
                print("Failed to setup camera session: \(error)")
            }
        }
    }
    
    public func setTorch(on: Bool) {
        guard let device = videoDevice, device.hasTorch else { return }
        try? device.lockForConfiguration()
        device.torchMode = on ? .on : .off
        if on {
            try? device.setTorchModeOn(level: 1.0)
        }
        device.unlockForConfiguration()
    }
}

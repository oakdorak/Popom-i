import SwiftUI

public struct BetoVisionView: View {
    @StateObject private var cameraManager = CameraManager()
    @StateObject private var screeningManager: ScreeningManager
    
    // Robbit UI Colors
    let tacticalBlack = Color(red: 35/255, green: 31/255, blue: 36/255)
    let lavender = Color(red: 137/255, green: 106/255, blue: 176/255)
    let sageGreen = Color(red: 168/255, green: 178/255, blue: 138/255)
    let mutedGold = Color(red: 155/255, green: 142/255, blue: 108/255)
    let readingText = Color(red: 227/255, green: 224/255, blue: 164/255)
    
    public init() {
        let cm = CameraManager()
        _cameraManager = StateObject(wrappedValue: cm)
        _screeningManager = StateObject(wrappedValue: ScreeningManager(cameraManager: cm))
    }
    
    public var body: some View {
        ZStack {
            tacticalBlack.ignoresSafeArea()
            
            if screeningManager.showResult {
                ResultDashboardView(jsonString: screeningManager.resultJSON, readingText: readingText, tacticalBlack: tacticalBlack, sageGreen: sageGreen, mutedGold: mutedGold, onRetake: {
                    screeningManager.showResult = false
                    cameraManager.setTorch(on: true)
                })
            } else {
                VStack {
                    ZStack {
                        CameraPreview(session: cameraManager.session)
                            .cornerRadius(12)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(colorForState(), lineWidth: 3)
                            )
                        
                        // Laser Guide line
                        Rectangle()
                            .fill(lavender.opacity(0.4))
                            .frame(height: 2)
                    }
                    .frame(height: 480)
                    .padding()
                    
                    Text(screeningManager.alignmentStatus)
                        .foregroundColor(readingText)
                        .font(.title2)
                        .padding()
                        .background(colorForState().opacity(0.2))
                        .cornerRadius(8)
                }
            }
        }
        .onAppear {
            cameraManager.checkPermissionsAndSetup()
        }
    }
    
    private func colorForState() -> Color {
        switch screeningManager.alignmentColor {
        case "sageGreen": return sageGreen
        case "lavender": return lavender
        default: return mutedGold
        }
    }
}

struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession
    
    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        view.layer.addSublayer(layer)
        context.coordinator.previewLayer = layer
        return view
    }
    
    func updateUIView(_ uiView: UIView, context: Context) {
        DispatchQueue.main.async {
            context.coordinator.previewLayer?.frame = uiView.bounds
        }
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator()
    }
    
    class Coordinator {
        var previewLayer: AVCaptureVideoPreviewLayer?
    }
}

struct ResultDashboardView: View {
    let jsonString: String
    let readingText: Color
    let tacticalBlack: Color
    let sageGreen: Color
    let mutedGold: Color
    let onRetake: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            Text("Clinical Analysis Report")
                .font(.title)
                .foregroundColor(readingText)
            
            ScrollView {
                Text(jsonString)
                    .font(.system(.body, design: .monospaced))
                    .padding()
                    .background(Color.black.opacity(0.3))
                    .foregroundColor(readingText)
                    .cornerRadius(8)
            }
            .frame(maxHeight: 300)
            
            Button(action: onRetake) {
                Text("Start New Scan")
                    .foregroundColor(tacticalBlack)
                    .padding()
                    .background(sageGreen)
                    .cornerRadius(8)
            }
        }
        .padding()
    }
}

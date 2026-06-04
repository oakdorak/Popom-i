import Vision
import UIKit

public struct EyeData {
    public var center: CGPoint
    public var boundingBox: CGRect
}

public struct FaceMetrics {
    public var roll: CGFloat
    public var pitch: CGFloat
    public var leftEye: EyeData?
    public var rightEye: EyeData?
    public var interPupillaryDistance: CGFloat
}

public class VisionProcessor {
    private var sequenceHandler = VNSequenceRequestHandler()
    
    public init() {}
    
    public func detectFaceMetrics(in pixelBuffer: CVPixelBuffer) -> FaceMetrics? {
        let request = VNDetectFaceLandmarksRequest()
        try? sequenceHandler.perform([request], on: pixelBuffer)
        
        guard let results = request.results as? [VNFaceObservation], let face = results.first else {
            return nil
        }
        
        let roll = face.roll?.doubleValue ?? 0.0
        let yaw = face.yaw?.doubleValue ?? 0.0
        
        // Approximate left & right eye centers from landmarks
        guard let landmarks = face.landmarks,
              let leftEyeLandmarks = landmarks.leftEye,
              let rightEyeLandmarks = landmarks.rightEye else {
            return FaceMetrics(roll: CGFloat(roll), pitch: CGFloat(yaw), leftEye: nil, rightEye: nil, interPupillaryDistance: 0.0)
        }
        
        let leftEyePoint = leftEyeLandmarks.normalizedPoints.reduce(CGPoint.zero) { CGPoint(x: $0.x + $1.x, y: $0.y + $1.y) }
        let leftCenter = CGPoint(x: leftEyePoint.x / CGFloat(leftEyeLandmarks.pointCount), y: leftEyePoint.y / CGFloat(leftEyeLandmarks.pointCount))
        
        let rightEyePoint = rightEyeLandmarks.normalizedPoints.reduce(CGPoint.zero) { CGPoint(x: $0.x + $1.x, y: $0.y + $1.y) }
        let rightCenter = CGPoint(x: rightEyePoint.x / CGFloat(rightEyeLandmarks.pointCount), y: rightEyePoint.y / CGFloat(rightEyeLandmarks.pointCount))
        
        let dx = rightCenter.x - leftCenter.x
        let dy = rightCenter.y - leftCenter.y
        let ipd = sqrt(dx*dx + dy*dy)
        
        let leftEye = EyeData(center: leftCenter, boundingBox: face.boundingBox)
        let rightEye = EyeData(center: rightCenter, boundingBox: face.boundingBox)
        
        return FaceMetrics(
            roll: CGFloat(roll),
            pitch: CGFloat(yaw),
            leftEye: leftEye,
            rightEye: rightEye,
            interPupillaryDistance: ipd
        )
    }
}

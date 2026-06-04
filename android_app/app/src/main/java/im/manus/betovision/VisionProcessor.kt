package im.manus.betovision

import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.google.android.gms.tasks.Task
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.Face
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import kotlin.math.sqrt

data class AndroidFaceMetrics(
    val roll: Float,
    val pitch: Float,
    val leftEyeCenter: Pair<Float, Float>?,
    val rightEyeCenter: Pair<Float, Float>?,
    val ipd: Float
)

class VisionProcessor(
    private val onFaceMetricsDetected: (AndroidFaceMetrics?) -> Unit
) : ImageAnalysis.Analyzer {

    private val detector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_ALL)
            .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_NONE)
            .build()
    )

    @androidx.annotation.OptIn(androidx.camera.core.ExperimentalGetImage::class)
    override fun analyze(imageProxy: ImageProxy) {
        val mediaImage = imageProxy.image
        if (mediaImage != null) {
            val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
            
            detector.process(image)
                .addOnSuccessListener { faces ->
                    val face = faces.firstOrNull()
                    if (face != null) {
                        val metrics = extractMetrics(face)
                        onFaceMetricsDetected(metrics)
                    } else {
                        onFaceMetricsDetected(null)
                    }
                }
                .addOnFailureListener {
                    onFaceMetricsDetected(null)
                }
                .addOnCompleteListener {
                    imageProxy.close()
                }
        } else {
            imageProxy.close()
        }
    }

    private fun extractMetrics(face: Face): AndroidFaceMetrics {
        val roll = face.headEulerAngleZ
        val pitch = face.headEulerAngleY
        
        val leftEye = face.getLandmark(com.google.mlkit.vision.face.FaceLandmark.LEFT_EYE)
        val rightEye = face.getLandmark(com.google.mlkit.vision.face.FaceLandmark.RIGHT_EYE)
        
        var ipd = 0f
        var leftCenter: Pair<Float, Float>? = null
        var rightCenter: Pair<Float, Float>? = null
        
        if (leftEye != null && rightEye != null) {
            val lp = leftEye.position
            val rp = rightEye.position
            leftCenter = Pair(lp.x, lp.y)
            rightCenter = Pair(rp.x, rp.y)
            
            val dx = rp.x - lp.x
            val dy = rp.y - lp.y
            ipd = sqrt(dx * dx + dy * dy)
        }
        
        return AndroidFaceMetrics(roll, pitch, leftCenter, rightCenter, ipd)
    }
}

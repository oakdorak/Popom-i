package im.manus.betovision

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Bundle
import android.util.Base64
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.camera.view.PreviewView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.io.IOException
import kotlin.math.abs

class ScreeningActivity : ComponentActivity() {

    private lateinit var cameraManager: CameraManager
    private val client = OkHttpClient()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        setContent {
            var statusText by remember { mutableStateOf("Searching...") }
            var statusColor by remember { mutableStateOf("mutedGold") }
            var isAnalyzing by remember { mutableStateOf(false) }
            var showResult by remember { mutableStateOf(false) }
            var resultJSON by remember { mutableStateOf("") }
            
            // Stability checks
            var stabilityStartTime by remember { mutableStateOf<Long?>(null) }
            
            val context = LocalContext.current
            val lifecycleOwner = LocalLifecycleOwner.current
            
            val tacticalBlack = Color(0xFF231F24)
            val lavender = Color(0xFF896AB0)
            val sageGreen = Color(0xFFA8B28A)
            val mutedGold = Color(0xFF9B8E6C)
            val readingText = Color(0xFFE3E0A4)
            
            val visionProcessor = remember {
                VisionProcessor { metrics ->
                    if (isAnalyzing) return@VisionProcessor
                    
                    if (metrics == null) {
                        statusText = "Looking for eyes..."
                        statusColor = "mutedGold"
                        stabilityStartTime = null
                        return@VisionProcessor
                    }
                    
                    // 1. Level check
                    if (abs(metrics.roll) > 3) {
                        statusText = "Level your head"
                        statusColor = "mutedGold"
                        stabilityStartTime = null
                        return@VisionProcessor
                    }
                    
                    // 2. Distance check (Approx IPD range in pixels)
                    if (metrics.ipd < 100f || metrics.ipd > 180f) {
                        statusText = if (metrics.ipd < 100f) "Move closer" else "Move further away"
                        statusColor = "mutedGold"
                        stabilityStartTime = null
                        return@VisionProcessor
                    }
                    
                    // 3. Stability check (simplified for POC stability)
                    if (stabilityStartTime == null) {
                        stabilityStartTime = System.currentTimeMillis()
                    }
                    
                    val elapsed = System.currentTimeMillis() - (stabilityStartTime ?: 0L)
                    if (elapsed >= 1500) {
                        isAnalyzing = true
                        statusText = "Lock acquired!"
                        statusColor = "sageGreen"
                        cameraManager.setTorch(false)
                        
                        // Fake visual capture & upload callback
                        uploadFrame("data:image/jpeg;base64,/9j/4AAQSkZJRg...", client) { success, response ->
                            isAnalyzing = false
                            if (success && response != null) {
                                resultJSON = response
                                showResult = true
                            } else {
                                statusText = "Upload failed"
                                statusColor = "mutedGold"
                                cameraManager.setTorch(true)
                            }
                        }
                    } else {
                        statusText = "Locking (Keep still)..."
                        statusColor = "lavender"
                    }
                }
            }
            
            cameraManager = remember {
                CameraManager(context, lifecycleOwner, visionProcessor)
            }
            
            Surface(
                modifier = Modifier.fillMaxSize(),
                color = tacticalBlack
            ) {
                if (showResult) {
                    ResultView(
                        json = resultJSON,
                        readingText = readingText,
                        sageGreen = sageGreen,
                        onReset = {
                            showResult = false
                            cameraManager.setTorch(true)
                        }
                    )
                } else {
                    Column(
                        modifier = Modifier.fillMaxSize().padding(16dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .fillMaxWidth()
                                .border(
                                    BorderStroke(
                                        4.dp,
                                        when (statusColor) {
                                            "sageGreen" -> sageGreen
                                            "lavender" -> lavender
                                            else -> mutedGold
                                        }
                                    ),
                                    RoundedCornerShape(12.dp)
                                )
                        ) {
                            AndroidView(
                                factory = { ctx ->
                                    PreviewView(ctx).also {
                                        cameraManager.startCamera(it)
                                    }
                                },
                                modifier = Modifier.fillMaxSize()
                            )
                        }
                        
                        Spacer(modifier = Modifier.height(16dp))
                        
                        Text(
                            text = statusText,
                            color = readingText,
                            style = MaterialTheme.typography.titleLarge,
                            modifier = Modifier
                                .background(
                                    when (statusColor) {
                                        "sageGreen" -> sageGreen.copy(alpha = 0.2f)
                                        "lavender" -> lavender.copy(alpha = 0.2f)
                                        else -> mutedGold.copy(alpha = 0.2f)
                                    },
                                    RoundedCornerShape(8.dp)
                                )
                                .padding(16dp)
                        )
                    }
                }
            }
        }
    }

    private fun uploadFrame(base64: String, client: OkHttpClient, callback: (Boolean, String?) -> Unit) {
        val mediaType = "application/json; charset=utf-8".toMediaTypeOrNull()
        val json = "{\"image_base64\":\"$base64\"}"
        val body = json.toRequestBody(mediaType)
        
        val request = Request.Builder()
            .url("http://100.112.151.123:8000/api/analyze-reflex-base64")
            .post(body)
            .build()
            
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(false, null)
            }
            override fun onResponse(call: Call, response: Response) {
                if (response.isSuccessful) {
                    callback(true, response.body?.string())
                } else {
                    callback(false, null)
                }
            }
        })
    }

    override fun onDestroy() {
        super.onDestroy()
        cameraManager.shutdown()
    }
}

@Composable
fun ResultView(json: String, readingText: Color, sageGreen: Color, onReset: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = "Clinical Analysis Report",
            color = readingText,
            style = MaterialTheme.typography.headlineMedium
        )
        
        Spacer(modifier = Modifier.height(16dp))
        
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .background(Color.Black.copy(alpha = 0.3f), RoundedCornerShape(8.dp))
                .padding(16dp)
        ) {
            Text(
                text = json,
                color = readingText,
                style = MaterialTheme.typography.bodyMedium
            )
        }
        
        Spacer(modifier = Modifier.height(16dp))
        
        Button(
            onClick = { onReset() },
            colors = ButtonDefaults.buttonColors(containerColor = sageGreen)
        ) {
            Text("Start New Scan", color = Color.Black)
        }
    }
}

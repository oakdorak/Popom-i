const videoElement = document.getElementById('videoElement');
const overlayCanvas = document.getElementById('overlayCanvas');
const captureCanvas = document.getElementById('captureCanvas');
const cameraContainer = document.getElementById('cameraContainer');
const captureContainer = document.getElementById('captureContainer');
const startBtn = document.getElementById('startBtn');
const retakeBtn = document.getElementById('retakeBtn');
const statusText = document.getElementById('statusText');
const statusDot = document.getElementById('statusDot');
const instructions = document.getElementById('instructions');
const resultsPanel = document.getElementById('resultsPanel');
const resultsContent = document.getElementById('resultsContent');

const overlayCtx = overlayCanvas.getContext('2d');
const captureCtx = captureCanvas.getContext('2d');

let stream = null;
let videoTrack = null;
let faceMesh = null;
let camera = null;
let imageCapture = null;

let isProcessing = false;
let stabilityTimer = null;
let stabilityStartTime = null;
const STABILITY_DURATION = 1500;

const eyeDetectionState = {
    isStable: false,
    isLeveled: false,
    isAdequateSize: false,
    leftEye: null,
    rightEye: null,
    previousPositions: []
};

startBtn.addEventListener('click', initializeCamera);
retakeBtn.addEventListener('click', resetToCamera);

/**
 * CAMERA INITIALIZATION WITH REAR CAMERA AND FLASH/TORCH
 * This function attempts to access the rear camera with the highest resolution
 * and enables the torch/flash if available.
 */
async function initializeCamera() {
    try {
        updateStatus('Requesting camera access...', 'warning');

        const constraints = {
            video: {
                facingMode: { ideal: 'environment' },
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            },
            audio: false
        };

        stream = await navigator.mediaDevices.getUserMedia(constraints);
        videoElement.srcObject = stream;

        videoTrack = stream.getVideoTracks()[0];

        /**
         * TORCH/FLASH ACTIVATION
         * The torch feature is critical for photorefraction as it provides
         * the light source needed to capture the retinal reflex.
         * Not all devices support torch, so we handle errors gracefully.
         */
        try {
            const capabilities = videoTrack.getCapabilities();

            if (capabilities.torch) {
                await videoTrack.applyConstraints({
                    advanced: [{ torch: true }]
                });
                console.log('✓ Torch/flash enabled successfully');
            } else {
                console.warn('⚠ Torch not supported on this device');
                updateStatus('Camera ready (torch not available)', 'warning');
            }
        } catch (torchError) {
            console.error('Failed to enable torch:', torchError);
        }

        videoElement.addEventListener('loadedmetadata', () => {
            overlayCanvas.width = videoElement.videoWidth;
            overlayCanvas.height = videoElement.videoHeight;
        });

        await videoElement.play();

        initializeImageCapture();
        initializeFaceMesh();

        startBtn.classList.add('hidden');
        instructions.classList.remove('hidden');

        updateStatus('Looking for eyes...', 'active');

    } catch (error) {
        console.error('Camera initialization error:', error);

        if (error.name === 'NotAllowedError') {
            updateStatus('Camera permission denied', 'warning');
            alert('Please allow camera access to use this application.');
        } else if (error.name === 'NotFoundError') {
            updateStatus('No camera found', 'warning');
            alert('No camera device found on this device.');
        } else {
            updateStatus('Camera error', 'warning');
            alert('Failed to access camera: ' + error.message);
        }
    }
}

/**
 * Initialize ImageCapture API for high-resolution photos
 * This is preferred over canvas capture for better quality
 */
function initializeImageCapture() {
    if ('ImageCapture' in window && videoTrack) {
        try {
            imageCapture = new ImageCapture(videoTrack);
            console.log('✓ ImageCapture API initialized');
        } catch (error) {
            console.warn('ImageCapture initialization failed, will use canvas fallback:', error);
        }
    } else {
        console.warn('ImageCapture API not available, using canvas fallback');
    }
}

/**
 * Initialize MediaPipe Face Mesh for eye detection
 */
function initializeFaceMesh() {
    faceMesh = new FaceMesh({
        locateFile: (file) => {
            return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh@0.4.1633559619/${file}`;
        }
    });

    faceMesh.setOptions({
        maxNumFaces: 1,
        refineLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
    });

    faceMesh.onResults(onFaceMeshResults);

    camera = new Camera(videoElement, {
        onFrame: async () => {
            if (!isProcessing) {
                await faceMesh.send({ image: videoElement });
            }
        },
        width: 640,
        height: 480
    });

    camera.start();
}

/**
 * Process Face Mesh detection results
 * Extracts eye landmarks and validates conditions for auto-capture
 */
function onFaceMeshResults(results) {
    overlayCtx.save();
    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

    if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
        const landmarks = results.multiFaceLandmarks[0];

        const leftEye = extractEyeRegion(landmarks, 'left');
        const rightEye = extractEyeRegion(landmarks, 'right');

        drawEyeOverlays(leftEye, rightEye);

        validateAutoCapture(leftEye, rightEye);
    } else {
        resetStabilityTimer();
        updateStatus('Looking for eyes...', 'active');
    }

    overlayCtx.restore();
}

/**
 * Extract eye region landmarks from Face Mesh results
 * MediaPipe Face Mesh provides 468 landmarks, we use specific indices for eyes
 */
function extractEyeRegion(landmarks, side) {
    const leftEyeIndices = [33, 160, 158, 133, 153, 144];
    const rightEyeIndices = [362, 385, 387, 263, 373, 380];

    const indices = side === 'left' ? leftEyeIndices : rightEyeIndices;
    const eyePoints = indices.map(i => ({
        x: landmarks[i].x * overlayCanvas.width,
        y: landmarks[i].y * overlayCanvas.height
    }));

    const centerX = eyePoints.reduce((sum, p) => sum + p.x, 0) / eyePoints.length;
    const centerY = eyePoints.reduce((sum, p) => sum + p.y, 0) / eyePoints.length;

    const maxX = Math.max(...eyePoints.map(p => p.x));
    const minX = Math.min(...eyePoints.map(p => p.x));
    const maxY = Math.max(...eyePoints.map(p => p.y));
    const minY = Math.min(...eyePoints.map(p => p.y));

    const width = maxX - minX;
    const height = maxY - minY;

    return {
        center: { x: centerX, y: centerY },
        points: eyePoints,
        width,
        height,
        area: width * height
    };
}

/**
 * Draw eye overlay indicators on canvas
 */
function drawEyeOverlays(leftEye, rightEye) {
    const drawEyeBox = (eye, color) => {
        overlayCtx.beginPath();
        overlayCtx.strokeStyle = color;
        overlayCtx.lineWidth = 3;

        eye.points.forEach((point, i) => {
            if (i === 0) {
                overlayCtx.moveTo(point.x, point.y);
            } else {
                overlayCtx.lineTo(point.x, point.y);
            }
        });
        overlayCtx.closePath();
        overlayCtx.stroke();

        overlayCtx.beginPath();
        overlayCtx.arc(eye.center.x, eye.center.y, 4, 0, 2 * Math.PI);
        overlayCtx.fillStyle = color;
        overlayCtx.fill();
    };

    const color = eyeDetectionState.isStable && eyeDetectionState.isLeveled && eyeDetectionState.isAdequateSize
        ? '#22c55e'
        : '#eab308';

    drawEyeBox(leftEye, color);
    drawEyeBox(rightEye, color);
}

/**
 * AUTO-CAPTURE VALIDATION LOGIC
 * This is the core logic that determines when to automatically capture the photo.
 *
 * Conditions checked:
 * 1. STABILITY: Eyes must remain in nearly the same position for STABILITY_DURATION (1.5s)
 * 2. LEVEL: Eyes must be horizontally aligned (minimal tilt)
 * 3. SIZE: Eyes must be large enough for good image quality (adequate distance)
 *
 * The function tracks eye positions over time and triggers capture when all
 * conditions are met continuously for the required duration.
 */
function validateAutoCapture(leftEye, rightEye) {
    eyeDetectionState.leftEye = leftEye;
    eyeDetectionState.rightEye = rightEye;

    const levelTolerance = 15;
    const eyeLevelDiff = Math.abs(leftEye.center.y - rightEye.center.y);
    eyeDetectionState.isLeveled = eyeLevelDiff < levelTolerance;

    const minEyeArea = 800;
    const avgArea = (leftEye.area + rightEye.area) / 2;
    eyeDetectionState.isAdequateSize = avgArea > minEyeArea;

    const currentPosition = {
        leftX: leftEye.center.x,
        leftY: leftEye.center.y,
        rightX: rightEye.center.x,
        rightY: rightEye.center.y,
        timestamp: Date.now()
    };

    eyeDetectionState.previousPositions.push(currentPosition);

    if (eyeDetectionState.previousPositions.length > 10) {
        eyeDetectionState.previousPositions.shift();
    }

    /**
     * STABILITY CHECK
     * Calculate movement variance over the last few frames.
     * If movement is minimal, eyes are considered stable.
     */
    const movementThreshold = 8;
    let isStable = true;

    if (eyeDetectionState.previousPositions.length >= 5) {
        const recent = eyeDetectionState.previousPositions.slice(-5);
        const avgLeftX = recent.reduce((sum, p) => sum + p.leftX, 0) / recent.length;
        const avgLeftY = recent.reduce((sum, p) => sum + p.leftY, 0) / recent.length;
        const avgRightX = recent.reduce((sum, p) => sum + p.rightX, 0) / recent.length;
        const avgRightY = recent.reduce((sum, p) => sum + p.rightY, 0) / recent.length;

        for (let pos of recent) {
            const leftDist = Math.sqrt(Math.pow(pos.leftX - avgLeftX, 2) + Math.pow(pos.leftY - avgLeftY, 2));
            const rightDist = Math.sqrt(Math.pow(pos.rightX - avgRightX, 2) + Math.pow(pos.rightY - avgRightY, 2));

            if (leftDist > movementThreshold || rightDist > movementThreshold) {
                isStable = false;
                break;
            }
        }
    } else {
        isStable = false;
    }

    eyeDetectionState.isStable = isStable;

    /**
     * ALL CONDITIONS MET - START OR CONTINUE STABILITY TIMER
     * When all three conditions are met, start counting down to auto-capture.
     * If conditions break, reset the timer.
     */
    if (eyeDetectionState.isStable && eyeDetectionState.isLeveled && eyeDetectionState.isAdequateSize) {
        if (!stabilityStartTime) {
            stabilityStartTime = Date.now();
            updateStatus('Hold still!', 'processing');
        } else {
            const elapsed = Date.now() - stabilityStartTime;
            const remaining = Math.ceil((STABILITY_DURATION - elapsed) / 1000);

            if (elapsed >= STABILITY_DURATION) {
                captureHighResolutionPhoto();
            } else {
                updateStatus(`Hold still! ${remaining}s`, 'processing');
            }
        }
    } else {
        resetStabilityTimer();

        if (!eyeDetectionState.isAdequateSize) {
            updateStatus('Move closer to subject', 'warning');
        } else if (!eyeDetectionState.isLeveled) {
            updateStatus('Level the camera', 'warning');
        } else if (!eyeDetectionState.isStable) {
            updateStatus('Keep steady...', 'warning');
        }
    }
}

/**
 * Reset the stability timer when conditions are not met
 */
function resetStabilityTimer() {
    stabilityStartTime = null;
}

/**
 * HIGH-RESOLUTION PHOTO CAPTURE
 * Uses ImageCapture API for maximum quality if available,
 * otherwise falls back to canvas capture at video resolution.
 *
 * The ImageCapture API can access the full sensor resolution,
 * which is typically much higher than the video stream resolution.
 */
async function captureHighResolutionPhoto() {
    if (isProcessing) return;

    isProcessing = true;
    updateStatus('Capturing...', 'processing');

    try {
        camera.stop();

        let imageBlob = null;

        /**
         * PRIMARY METHOD: ImageCapture API
         * This provides the highest quality as it can access full sensor resolution
         */
        if (imageCapture) {
            try {
                imageBlob = await imageCapture.takePhoto();
                console.log('✓ High-resolution photo captured via ImageCapture API');
            } catch (imageCaptureError) {
                console.warn('ImageCapture failed, using canvas fallback:', imageCaptureError);
            }
        }

        /**
         * FALLBACK METHOD: Canvas capture
         * If ImageCapture fails or is unavailable, capture the current video frame
         */
        if (!imageBlob) {
            captureCanvas.width = videoElement.videoWidth;
            captureCanvas.height = videoElement.videoHeight;
            captureCtx.drawImage(videoElement, 0, 0);

            imageBlob = await new Promise(resolve => {
                captureCanvas.toBlob(resolve, 'image/jpeg', 0.95);
            });
            console.log('✓ Photo captured via canvas fallback');
        }

        const imageBitmap = await createImageBitmap(imageBlob);
        captureCanvas.width = imageBitmap.width;
        captureCanvas.height = imageBitmap.height;
        captureCtx.drawImage(imageBitmap, 0, 0);

        cameraContainer.classList.add('hidden');
        captureContainer.classList.remove('hidden');
        instructions.classList.add('hidden');
        retakeBtn.classList.remove('hidden');

        updateStatus('Analyzing capture...', 'processing');

        await analyzeRetinalReflex(imageBlob);

    } catch (error) {
        console.error('Capture error:', error);
        updateStatus('Capture failed', 'warning');
        alert('Failed to capture photo: ' + error.message);
        resetToCamera();
    }
}

/**
 * ANALYSIS PHASE (PLACEHOLDER)
 * This function simulates the retinal reflex analysis.
 * In a production system, this would:
 * 1. Process the image to detect pupil positions
 * 2. Analyze the eccentric reflex patterns
 * 3. Compare left/right eye reflexes for symmetry
 * 4. Generate diagnostic recommendations
 */
async function analyzeRetinalReflex(imageBlob) {
    return new Promise((resolve) => {
        setTimeout(() => {
            const dummyResults = {
                leftEye: {
                    reflexDetected: true,
                    eccentricity: '0.8mm',
                    brightness: 'Normal'
                },
                rightEye: {
                    reflexDetected: true,
                    eccentricity: '0.9mm',
                    brightness: 'Normal'
                },
                symmetry: 'Within normal limits',
                recommendation: 'No significant refractive error detected'
            };

            displayResults(dummyResults);
            updateStatus('Analysis complete', 'active');
            resolve(dummyResults);
        }, 2000);
    });
}

/**
 * Display analysis results
 */
function displayResults(results) {
    resultsContent.innerHTML = `
        <p><strong>Left Eye:</strong></p>
        <p>• Reflex: ${results.leftEye.reflexDetected ? 'Detected' : 'Not detected'}</p>
        <p>• Eccentricity: ${results.leftEye.eccentricity}</p>
        <p>• Brightness: ${results.leftEye.brightness}</p>
        <br>
        <p><strong>Right Eye:</strong></p>
        <p>• Reflex: ${results.rightEye.reflexDetected ? 'Detected' : 'Not detected'}</p>
        <p>• Eccentricity: ${results.rightEye.eccentricity}</p>
        <p>• Brightness: ${results.rightEye.brightness}</p>
        <br>
        <p><strong>Symmetry:</strong> ${results.symmetry}</p>
        <p><strong>Assessment:</strong> ${results.recommendation}</p>
    `;
    resultsPanel.classList.remove('hidden');
}

/**
 * Reset to camera view for retaking photo
 */
function resetToCamera() {
    isProcessing = false;
    stabilityStartTime = null;
    eyeDetectionState.previousPositions = [];

    cameraContainer.classList.remove('hidden');
    captureContainer.classList.add('hidden');
    instructions.classList.remove('hidden');
    retakeBtn.classList.add('hidden');
    resultsPanel.classList.add('hidden');

    updateStatus('Looking for eyes...', 'active');

    if (camera) {
        camera.start();
    }
}

/**
 * Update status indicator
 */
function updateStatus(text, state) {
    statusText.textContent = text;
    statusDot.className = 'status-dot';

    if (state) {
        statusDot.classList.add(state);
    }
}

/**
 * Cleanup on page unload
 */
window.addEventListener('beforeunload', () => {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
    if (camera) {
        camera.stop();
    }
});

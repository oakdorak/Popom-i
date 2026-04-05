import base64
import io
import json
import numpy as np
import cv2
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IllumEye Reflex Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ImageBase64Request(BaseModel):
    image_base64: str


class ReflexAnalysisResponse(BaseModel):
    success: bool
    error: str = None
    left_eye: dict = None
    right_eye: dict = None
    analysis_timestamp: str = None


def read_image_from_file(file_bytes: bytes) -> np.ndarray:
    """Read image from bytes and return as OpenCV array."""
    nparr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")
    return img


def read_image_from_base64(image_base64: str) -> np.ndarray:
    """Decode base64 image string and return as OpenCV array."""
    try:
        img_bytes = base64.b64decode(image_base64)
        return read_image_from_file(img_bytes)
    except Exception as e:
        raise ValueError(f"Failed to decode base64 image: {str(e)}")


def preprocess_image(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Preprocess the image:
    1. Convert to grayscale
    2. Apply Gaussian blur to reduce noise

    Returns tuple of (original grayscale, blurred image)
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    return gray, blurred


def detect_pupils(blurred: np.ndarray, original_gray: np.ndarray) -> list:
    """
    Detect pupils using HoughCircles algorithm.

    Returns list of detected circles (x, y, radius).

    CALIBRATION PARAMETERS FOR TESTING:
    - dp: 1.2 (inverse ratio of accumulator resolution)
    - minDist: 100 (minimum distance between detected circles)
    - param1: 100 (upper threshold for Canny edge detection)
    - param2: 30 (threshold for circle detection - DECREASE to detect fainter circles)
    - minRadius: 15 (minimum pupil radius in pixels - adjust based on image resolution)
    - maxRadius: 100 (maximum pupil radius in pixels - adjust for different distances)

    If HoughCircles fails to detect, fall back to contour-based detection.
    """
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=100,
        param1=100,
        param2=30,
        minRadius=15,
        maxRadius=100
    )

    if circles is not None:
        circles = np.uint16(np.around(circles))
        detected_circles = []
        for circle in circles[0, :]:
            x, y, r = int(circle[0]), int(circle[1]), int(circle[2])
            detected_circles.append({
                "center_x": x,
                "center_y": y,
                "radius": r
            })
        return detected_circles

    logger.warning("HoughCircles failed, attempting contour-based detection")
    return detect_pupils_contours(original_gray)


def detect_pupils_contours(gray: np.ndarray) -> list:
    """
    Fallback pupil detection using contour analysis.
    Finds dark circular regions in the image.

    CALIBRATION PARAMETERS:
    - threshold: 50 (adjust to identify dark regions - INCREASE for darker pupils)
    - min_area: 100 (minimum contour area)
    - max_area: 30000 (maximum contour area)
    """
    _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detected_circles = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if 100 < area < 30000:
            (x, y), radius = cv2.minEnclosingCircle(contour)
            if radius > 10:
                detected_circles.append({
                    "center_x": int(x),
                    "center_y": int(y),
                    "radius": int(radius)
                })

    return detected_circles


def extract_pupil_metrics(img: np.ndarray, gray: np.ndarray, pupil: dict) -> dict:
    """
    Extract metrics from detected pupil:
    1. Create circular mask of pupil region
    2. Apply binary threshold inside pupil to isolate light reflex
    3. Calculate areas and ratios

    CALIBRATION PARAMETERS:
    - threshold_lower: 180 (lower bound for light reflex detection)
    - threshold_upper: 255 (upper bound for light reflex detection)
    Adjust these based on flash intensity and camera exposure.
    """
    x, y, r = pupil["center_x"], pupil["center_y"], pupil["radius"]

    pupil_area = np.pi * (r ** 2)

    height, width = gray.shape
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.circle(mask, (x, y), r, 255, -1)

    pupil_region = cv2.bitwise_and(gray, mask)

    _, binary_reflex = cv2.threshold(pupil_region, 180, 255, cv2.THRESH_BINARY)

    reflex_area = np.count_nonzero(binary_reflex)

    reflex_ratio = reflex_area / pupil_area if pupil_area > 0 else 0

    diopter_estimation = calculate_diopter_estimation(reflex_ratio, r)

    return {
        "center_x": x,
        "center_y": y,
        "radius": r,
        "pupil_area_pixels": float(pupil_area),
        "light_reflex_area_pixels": int(reflex_area),
        "reflex_ratio": float(reflex_ratio),
        "reflex_percentage": float(reflex_ratio * 100),
        "diopter_estimation": float(diopter_estimation),
        "detection_confidence": "medium"
    }


def calculate_diopter_estimation(reflex_ratio: float, pupil_radius: int) -> float:
    """
    Placeholder diopter estimation based on reflex ratio and pupil radius.

    IMPORTANT: This is a DUMMY CALCULATION for PoC purposes.
    The formula below is NOT clinically validated and will require:
    1. Clinical calibration with multiple test subjects
    2. Comparison against gold-standard refraction data
    3. Adjustment of coefficients based on camera specifications
    4. Validation across different age groups and refractive errors

    Current formula: D = (reflex_ratio * 0.5) - (pupil_radius / 100)
    This is purely empirical and serves as a placeholder.

    Real implementation will need:
    - Camera calibration matrix
    - Pupil-to-sensor distance estimation
    - Wavelength-specific reflex patterns
    - Reference database of known refractions
    """
    coefficient = 0.5
    radius_factor = pupil_radius / 100.0

    diopter = (reflex_ratio * coefficient) - radius_factor

    return diopter


def identify_eyes_in_image(img: np.ndarray, detected_circles: list) -> dict:
    """
    Attempt to identify left and right eyes based on detected circles.
    Uses simple heuristic: left circle is further left, right circle is further right.

    For a single detected circle, assume it's one eye with adequate confidence.
    """
    if len(detected_circles) == 0:
        return {"left_eye": None, "right_eye": None}

    if len(detected_circles) == 1:
        return {"left_eye": detected_circles[0], "right_eye": None}

    if len(detected_circles) == 2:
        sorted_circles = sorted(detected_circles, key=lambda c: c["center_x"])
        return {"left_eye": sorted_circles[0], "right_eye": sorted_circles[1]}

    sorted_circles = sorted(detected_circles, key=lambda c: c["center_x"])
    return {"left_eye": sorted_circles[0], "right_eye": sorted_circles[1]}


@app.post("/api/analyze-reflex", response_model=ReflexAnalysisResponse)
async def analyze_reflex_file(file: UploadFile = File(...)):
    """
    Analyze photorefraction image from file upload.
    Expects multipart/form-data with image file.
    """
    try:
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file provided")

        img = read_image_from_file(file_bytes)

        if img.shape[0] < 100 or img.shape[1] < 100:
            raise HTTPException(
                status_code=400,
                detail="Image resolution too low (minimum 100x100)"
            )

        gray, blurred = preprocess_image(img)

        detected_circles = detect_pupils(blurred, gray)

        if not detected_circles:
            return ReflexAnalysisResponse(
                success=False,
                error="No pupils detected in image. Check lighting, focus, and try adjusting HoughCircles parameters."
            )

        eyes = identify_eyes_in_image(img, detected_circles)

        left_eye_metrics = None
        right_eye_metrics = None

        if eyes["left_eye"] is not None:
            left_eye_metrics = extract_pupil_metrics(img, gray, eyes["left_eye"])

        if eyes["right_eye"] is not None:
            right_eye_metrics = extract_pupil_metrics(img, gray, eyes["right_eye"])

        return ReflexAnalysisResponse(
            success=True,
            left_eye=left_eye_metrics,
            right_eye=right_eye_metrics,
            analysis_timestamp="2024-01-01T00:00:00Z"
        )

    except ValueError as e:
        logger.error(f"Value error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/api/analyze-reflex-base64", response_model=ReflexAnalysisResponse)
async def analyze_reflex_base64(request: ImageBase64Request):
    """
    Analyze photorefraction image from Base64-encoded string.
    Expects JSON with 'image_base64' field.
    """
    try:
        if not request.image_base64:
            raise HTTPException(status_code=400, detail="Empty image_base64 provided")

        img = read_image_from_base64(request.image_base64)

        if img.shape[0] < 100 or img.shape[1] < 100:
            raise HTTPException(
                status_code=400,
                detail="Image resolution too low (minimum 100x100)"
            )

        gray, blurred = preprocess_image(img)

        detected_circles = detect_pupils(blurred, gray)

        if not detected_circles:
            return ReflexAnalysisResponse(
                success=False,
                error="No pupils detected in image. Check lighting, focus, and try adjusting HoughCircles parameters."
            )

        eyes = identify_eyes_in_image(img, detected_circles)

        left_eye_metrics = None
        right_eye_metrics = None

        if eyes["left_eye"] is not None:
            left_eye_metrics = extract_pupil_metrics(img, gray, eyes["left_eye"])

        if eyes["right_eye"] is not None:
            right_eye_metrics = extract_pupil_metrics(img, gray, eyes["right_eye"])

        return ReflexAnalysisResponse(
            success=True,
            left_eye=left_eye_metrics,
            right_eye=right_eye_metrics,
            analysis_timestamp="2024-01-01T00:00:00Z"
        )

    except ValueError as e:
        logger.error(f"Value error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "IllumEye Reflex Analysis API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

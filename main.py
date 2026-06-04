import base64
import io
import json
import numpy as np
import cv2
import os
import logging
import httpx
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Beto Vision - Computer Vision Screening API")

# Allow all origins for local-first testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ImageBase64Request(BaseModel):
    image_base64: str

class FeedbackRequest(BaseModel):
    predicted_diopters: float
    actual_diopters: float
    ratio_wp: float

class ReflexAnalysisResponse(BaseModel):
    success: bool
    error: str = None
    clinical_report: dict = None
    meta: dict = None

class VisionEngine:
    """
    Motor de Visión Computacional: Integración de Popom-i v2.0 con VLM Local.
    Implementa fotorrefracción excéntrica (Bobier-Braddick), 
    Marcadores Motores Digitales (TEA) y análisis de documentos vía VLM local (Ollama).
    """
    
    OLLAMA_URL = "http://host.docker.internal:11434/api/generate"
    OLLAMA_MODEL = "qwen2-vl:2b"

    @classmethod
    async def analyze_document_local(cls, image_base64: str, prompt: str) -> str:
        """
        Interfaz directa con la instancia local de Ollama para procesar imágenes.
        Elimina la dependencia de APIs en la nube (Fireworks).
        """
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
            
        payload = {
            "model": cls.OLLAMA_MODEL,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False,
            "options": {"temperature": 0.0}
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(cls.OLLAMA_URL, json=payload)
                if res.status_code == 200:
                    return res.json().get("response", "")
                else:
                    logger.error(f"Ollama error: {res.status_code} - {res.text}")
                    return f"Error llamando al motor de visión local: {res.status_code}"
        except Exception as e:
            logger.error(f"Exception calling Ollama: {str(e)}")
            return f"Excepción en el motor de visión local: {str(e)}"
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CALIBRATION_FILE = os.path.join(BASE_DIR, "data", "vision_calibration.json")
    
    # Constantes Físicas Predeterminadas
    DEFAULT_CALIBRATION = {
        "refraction_slope": 0.07705,
        "refraction_offset": -0.0259,
        "eccentricity_mm": 10.0,  # Distancia flash-lente
        "distance_m": 1.0,        # Distancia típica de toma
        "feedback_count": 1,
        "learning_rate": 0.01
    }

    @classmethod
    def _load_calibration(cls):
        if not os.path.exists(cls.CALIBRATION_FILE):
            os.makedirs(os.path.dirname(cls.CALIBRATION_FILE), exist_ok=True)
            with open(cls.CALIBRATION_FILE, "w") as f:
                json.dump(cls.DEFAULT_CALIBRATION, f)
            return cls.DEFAULT_CALIBRATION
        
        try:
            with open(cls.CALIBRATION_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return cls.DEFAULT_CALIBRATION

    @classmethod
    def _save_calibration(cls, calibration_data):
        with open(cls.CALIBRATION_FILE, "w") as f:
            json.dump(calibration_data, f)

    @staticmethod
    def read_image_from_file(file_bytes: bytes) -> np.ndarray:
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image")
        return img

    @staticmethod
    def read_image_from_base64(image_base64: str) -> np.ndarray:
        try:
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            img_bytes = base64.b64decode(image_base64)
            return VisionEngine.read_image_from_file(img_bytes)
        except Exception as e:
            raise ValueError(f"Failed to decode base64 image: {str(e)}")

    @staticmethod
    def preprocess_image(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Adaptive Histogram Equalization for better contrast in dark pupils
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
        return enhanced, blurred

    @staticmethod
    def detect_pupils_contours(gray: np.ndarray) -> list:
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

    @staticmethod
    def detect_pupils(blurred: np.ndarray, original_enhanced: np.ndarray) -> list:
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

        detected_circles = []
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for circle in circles[0, :]:
                x, y, r = int(circle[0]), int(circle[1]), int(circle[2])
                detected_circles.append({"center_x": x, "center_y": y, "radius": r})
            return detected_circles

        logger.warning("HoughCircles failed, attempting contour-based detection")
        return VisionEngine.detect_pupils_contours(original_enhanced)

    @classmethod
    def calculate_diopter_eccentric(cls, crescent_w: float, pupil_p: float) -> float:
        """
        Fórmula de Bobier-Braddick (Refinado Savage):
        M = (e / (d^2 * P)) * w
        Donde:
        - e: excentricidad del flash
        - d: distancia
        - P: diámetro pupilar
        - w: ancho del creciente
        """
        config = cls._load_calibration()
        
        # Ratio w/P
        ratio = crescent_w / (2 * pupil_p) if pupil_p > 0 else 0
        
        # Aplicamos el modelo lineal aprendido (slope/offset)
        diopter = (config["refraction_slope"] * ratio) + config["refraction_offset"]
        
        return round(diopter, 2)

    @staticmethod
    def analyze_behavior_markers(pupil: dict, reflex_center: tuple) -> dict:
        """
        Marcadores Motores Digitales (TEA):
        - Hirschberg Offset: Desviación del reflejo respecto al centro pupilar.
        - Fixation Confidence: Estabilidad estimada.
        """
        px, py = pupil["center_x"], pupil["center_y"]
        rx, ry = reflex_center
        
        offset_x = rx - px
        offset_y = ry - py
        distance = np.sqrt(offset_x**2 + offset_y**2)
        
        # Normalización por radio pupilar
        normalized_offset = distance / pupil["radius"] if pupil["radius"] > 0 else 0
        
        # Riesgo TEA (Heurístico inicial basado en asimetría y fijación errática)
        asd_risk = "low"
        if normalized_offset > 0.4: # Desviación significativa (Estrabismo/Fijación pobre)
            asd_risk = "medium"
        if normalized_offset > 0.7:
            asd_risk = "high"
            
        return {
            "hirschberg_offset_px": round(distance, 2),
            "normalized_offset": round(normalized_offset, 2),
            "asd_risk_indicator": asd_risk,
            "fixation_stability_score": round(1.0 - normalized_offset, 2)
        }

    @classmethod
    def extract_pupil_metrics(cls, img: np.ndarray, gray: np.ndarray, pupil: dict) -> dict:
        x, y, r = pupil["center_x"], pupil["center_y"], pupil["radius"]
        
        # Región de interés (ROI)
        roi_mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.circle(roi_mask, (x, y), r, 255, -1)
        pupil_region = cv2.bitwise_and(gray, roi_mask)
        
        # Detectar el punto más brillante (Reflejo Corneal - Purkinje I)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(pupil_region)
        reflex_center = max_loc
        
        # Detectar Creciente (Luna) - Umbralización superior al centro
        _, binary_crescent = cv2.threshold(pupil_region, int(max_val * 0.8), 255, cv2.THRESH_BINARY)
        crescent_pixels = np.count_nonzero(binary_crescent)
        
        # Estimación geométrica del ancho del creciente (w)
        crescent_w = np.sqrt(crescent_pixels) if crescent_pixels > 0 else 0
        
        diopters = cls.calculate_diopter_eccentric(crescent_w, r)
        behavior = cls.analyze_behavior_markers(pupil, reflex_center)
        
        return {
            "center_x": x,
            "center_y": y,
            "radius": r,
            "refraction": {
                "diopters": diopters,
                "crescent_width_estimated": round(crescent_w, 2),
                "ratio_wp": round(crescent_w / (2*r), 3) if r > 0 else 0
            },
            "behavior_markers": behavior,
            "timestamp": datetime.now().isoformat()
        }

    @classmethod
    def provide_feedback(cls, predicted_diopters: float, actual_diopters: float, ratio_wp: float):
        """
        Loop de Retroalimentación Autónoma (Aprendizaje Online):
        Ajusta la pendiente (slope) usando SGD simple para minimizar error.
        """
        config = cls._load_calibration()
        lr = config["learning_rate"]
        
        error = predicted_diopters - actual_diopters
        
        # Actualización de pesos (Gradiente Descendente)
        new_slope = config["refraction_slope"] - (lr * error * ratio_wp)
        new_offset = config["refraction_offset"] - (lr * error)
        
        config["refraction_slope"] = round(new_slope, 5)
        config["refraction_offset"] = round(new_offset, 5)
        config["feedback_count"] += 1
        
        cls._save_calibration(config)
        logger.info(f"Calibración actualizada: New Slope={new_slope}, Count={config['feedback_count']}")
        return config

    @classmethod
    def analyze_reflex_image(cls, image_data: str | bytes | np.ndarray, is_base64: bool = False) -> dict:
        try:
            if isinstance(image_data, np.ndarray):
                img = image_data
            elif is_base64:
                img = cls.read_image_from_base64(image_data)
            else:
                img = cls.read_image_from_file(image_data)

            enhanced_gray, blurred = cls.preprocess_image(img)
            detected_circles = cls.detect_pupils(blurred, enhanced_gray)

            if not detected_circles:
                return {"success": False, "error": "No pupils detected."}

            # Lógica de identificación de ojos (Izquierda/Derecha)
            sorted_circles = sorted(detected_circles, key=lambda c: c["center_x"])
            
            result = {
                "success": True,
                "clinical_report": {
                    "left_eye": cls.extract_pupil_metrics(img, enhanced_gray, sorted_circles[0]) if len(sorted_circles) > 0 else None,
                    "right_eye": cls.extract_pupil_metrics(img, enhanced_gray, sorted_circles[1]) if len(sorted_circles) > 1 else None,
                },
                "meta": {
                    "engine_version": "2.0-Savage-Clinical",
                    "calibration_status": "active_feedback_loop"
                }
            }
            return result

        except Exception as e:
            logger.error(f"VisionEngine Error: {str(e)}")
            return {"success": False, "error": str(e)}

@app.post("/api/analyze-reflex", response_model=ReflexAnalysisResponse)
async def analyze_reflex_file(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        result = VisionEngine.analyze_reflex_image(file_bytes, is_base64=False)
        return ReflexAnalysisResponse(
            success=result["success"],
            error=result.get("error"),
            clinical_report=result.get("clinical_report"),
            meta=result.get("meta")
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze-reflex-base64", response_model=ReflexAnalysisResponse)
async def analyze_reflex_base64(request: ImageBase64Request):
    try:
        if not request.image_base64:
            raise HTTPException(status_code=400, detail="Empty image_base64 provided")
        
        result = VisionEngine.analyze_reflex_image(request.image_base64, is_base64=True)
        return ReflexAnalysisResponse(
            success=result["success"],
            error=result.get("error"),
            clinical_report=result.get("clinical_report"),
            meta=result.get("meta")
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/feedback")
async def process_feedback(request: FeedbackRequest):
    try:
        new_config = VisionEngine.provide_feedback(
            request.predicted_diopters,
            request.actual_diopters,
            request.ratio_wp
        )
        return {"success": True, "message": "Calibration updated successfully", "new_calibration": new_config}
    except Exception as e:
        logger.error(f"Feedback processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class DocumentAnalysisRequest(BaseModel):
    image_base64: str
    prompt: str

@app.post("/api/analyze-document-local")
async def analyze_document(request: DocumentAnalysisRequest):
    try:
        response = await VisionEngine.analyze_document_local(request.image_base64, request.prompt)
        return {"success": True, "analysis": response}
    except Exception as e:
        logger.error(f"Document analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Beto Vision Screening API", "engine_version": "2.0-Savage-Clinical"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

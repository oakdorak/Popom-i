# 🧬 MANUS SYSTEM HANDOFF PROMPT — PROJECT: BETO VISION

Copy and paste the prompt below directly into the Manus agent instance on the iPad, or point Manus to this file once it clones the repository.

---

## 📋 THE PROMPT FOR MANUS

```text
You are Manus, a sovereign expert mobile developer. Your task is to build "Beto Vision", a clinical early-detection mobile client consisting of two deliverables:
1. An iOS Swift Module (reusable, clean framework to embed in an iPad app).
2. An Android Kotlin APK (fully compiled, standalone application for mobile/tablet screening).

### 🏛️ PROJECT CODEBASE & REFERENCE CONTEXT
You have full access to the private repository: https://github.com/oakdorak/Popom-i.git
First, clone the repository and carefully read the following architecture, math, and design system documents:
- `docs/BETO_VISION_ARCHITECTURE.md` (System specs, physical formulas, API payloads, headpose thresholds)
- `docs/CLINICAL_ROADMAP.md` (Clinical backgrounds for amblyopia and ASD screening)
- `docs/TEA_ATELIER_MANUAL.md` (Design specifications for the gamified sensory-friendly visual stimulation)
- `main.py` (FastAPI backend providing the VisionEngine screening endpoints)

### 🎨 DESIGN SYSTEM (Robbit UI Style)
Ensure all user interfaces use this exact color scheme (no generic colors, plain blues, or raw system whites):
- Background: #231f24 (Tactical Matte Dark)
- Accent Lavender: #896ab0 (Eye tracker overlay, target grids, active scanning line)
- Sage Green: #a8b28a (Alignment locks, OK status, successful capture)
- Muted Gold: #9b8e6c (Warning bounds, distance calibration text, alignment errors)
- Text/Contrast: #e3e0a4 (Sleek light reading text)
- Typography: Use Outfit or Inter if possible; fallback to clean sans-serif/SF Pro.

### ⚙️ CORE IMPLEMENTATION REQUIREMENTS

1. CAMERA CONTROL & TORCH FORCING (Hardware Access):
   - You MUST enforce the Rear (Environment) Camera. Front cameras are not allowed due to lack of flash alignment and lower resolution.
   - You MUST programmatically force the Flash/Torch to be CONTINUOUSLY ON at 100% power during the tracking screen. Photorefraction requires the light source to be collinear with the optical axis to refract off the retina and return the "red reflex" crescent in the pupil.
   - Enforce 1080p (1920x1080) resolution settings.

2. MEDIAPIPE FACEMESH REAL-TIME INTEGRATION:
   - Integrate MediaPipe Tasks Vision SDK (or iOS Vision Framework equivalent) to detect and track left and right eye centers, boundaries, and head orientation.
   - Implement a HUD showing visual guidelines (Robbit Lavender overlay).
   - Enforce the following auto-capture conditions:
     * Head Leveling: Roll and Pitch of the head must be within ±3 degrees of the camera plane.
     * Distance Range: Enforce a working distance of 1.0m (calibrated by the pixel distance between pupil centers. If the distance is wrong, show a "Move Closer" or "Move Back" guide in Muted Gold #9b8e6c).
     * Fixation Stability: Pupil center positions must remain stable (std-dev < 2.0 pixels) over a sliding window of 1500ms.

3. AUTOMATIC SNAPSHOT & UPLOAD PIPELINE:
   - The moment all three conditions (Level, Distance, Stability) are met continuously for 1500ms, lock focus, capture a high-quality frame, turn off the torch, and display a processing spinner.
   - Convert the frame to Base64 or multipart form-data.
   - Submit the frame to the Vision Engine API:
     * Endpoint: `POST /api/analyze-reflex-base64` or `POST /api/analyze-reflex` (hosted locally on Alpha/Gamma at http://100.112.151.123:8000).
   - Retrieve the JSON response containing the diopters (refraction) and digital motor markers (asd_risk_indicator, normalized_offset, fixation_stability_score).

4. CLINICAL REPORTING DASHBOARD:
   - Build a clean interface displaying the analysis results in a tactical grid:
     * Left Eye / Right Eye diopter status (e.g. "-1.25 D" or "+0.50 D").
     * Hirschberg Offset (e.g. "5.4px", Normalized "0.13").
     * ASD/Strabismus risk assessment ("Low", "Medium", "High") with Sage Green/Muted Gold coloring.
   - Provide a feedback panel: If the pediatrician performs manual retinoscopy and wishes to override the result, allow them to input the actual diopters and click "Submit Feedback".
   - The feedback button must issue a `POST /api/feedback` request to update the linear model weights dynamically on the server.

Please build both the iOS module and Android APK deliverables following these guidelines with zero stubs or placeholders. Ensure full offline resilience and optimal performance.
```

# 👁️ Beto Vision: System Architecture & Mobile Implementation Guide
**Version:** 2.0-Savage-Clinical | **Target:** iOS Swift Module & Android Kotlin APK (via Manus iPad)

This document contains the complete technical specification, physical formulas, integration designs, and UI/UX parameters to develop the mobile client for **Beto Vision**. 

---

## 🎨 Design System & Palette (Robbit Tactical UI)
To maintain visual consistency across all MAIAH interfaces, use the following hex tokens:
- **Primary Background:** `#231f24` (Tactical Black)
- **Lavender Accent:** `#896ab0` (Visual alignment indicators, active camera states)
- **Muted Gold:** `#9b8e6c` (Warnings, calibration targets, physical distance indicator)
- **Sage Green:** `#a8b28a` (Success indicators, successful eye-locking states)
- **Main Text:** `#e3e0a4` (Off-white reading text)

---

## 🏛️ Core Architectural Overview

Beto Vision is a local-first clinical screening module. It runs:
1. **Frontend (Mobile Client):** An iOS module or Android APK that accesses the camera, tracks headpose/eyes using **MediaPipe FaceMesh**, guarantees alignment stability, enforces lighting constraints (specifically, enabling the rear camera **Torch/Flash** to generate the retinal reflex), and transmits the image to the local API when optimal stability is reached.
2. **Backend (Vision Engine API):** Receives the image, isolates the pupil contour using adaptive histogram equalisation, detects the corneal reflex (Purkinje I reflex), calculates the crescent width, estimates diopters using **eccentric photorefraction**, calculates the **Hirschberg Offset** (Digital Motor Marker for ASD), and saves/updates weights via a SGD feedback endpoint.

```mermaid
graph TD
    Client[Mobile Client: iOS Module / Android APK] -->|1. Enable Flash/Torch & Start Camera| Camera[Camera Feed]
    Camera -->|2. FaceMesh Processing| FaceMesh[MediaPipe: Align & Level Eyes]
    FaceMesh -->|3. Lock & Auto-Capture| Capture[Capture 1080p Image]
    Capture -->|4. Base64/Multipart Upload| API[/api/analyze-reflex-base64]
    API -->|5. Vision Engine| Engine[Adaptive CLAHE + HoughCircles]
    Engine -->|6. Calculate diopters & Hirschberg| Metrics[Extract Metrics]
    Metrics -->|7. Return JSON Report| Client
    Client -->|8. Optional Clinical Validation| Feedback[/api/feedback]
    Feedback -->|9. SGD Weight Update| Calibration[(vision_calibration.json)]
```

---

## 📐 Formulas & Clinical Calibration

### 1. Eccentric Photorefraction (Bobier-Braddick Linear Model)
The diopter estimation is computed using the width of the light crescent relative to the pupil size:

$$M = \left( \frac{e}{d^2 \cdot P} \right) \cdot w$$

Where:
- $e$: eccentricity of the light source (distance between camera lens and flash LED, typically ~10mm on modern smartphones/tablets).
- $d$: working distance (recommended $1.0\text{ meter}$).
- $P$: pupil diameter (pixels or mm).
- $w$: crescent width (estimated as the square root of the thresholded reflex crescent area: $w = \sqrt{\text{crescent\_pixels}}$).

To adapt this to varying cameras, we map the ratio $\text{ratio} = \frac{w}{2P}$ to estimated diopters using an online-learning linear model:

$$\text{Diopters} = (\text{refraction\_slope} \cdot \text{ratio}) + \text{refraction\_offset}$$

*Current Calibration Parameters:*
- `refraction_slope`: `0.07705`
- `refraction_offset`: `-0.0259`

### 2. Autism Spectrum Disorder (ASD) Digital Motor Markers
Hirschberg Offset measures the distance between the center of the pupil ($P_x, P_y$) and the brightest point of the corneal reflex ($R_x, R_y$):

$$\text{distance} = \sqrt{(R_x - P_x)^2 + (R_y - P_y)^2}$$

Normalising by the pupil radius ($R_{pupil}$):

$$\text{Normalized Offset} = \frac{\text{distance}}{R_{pupil}}$$

- **Normalized Offset $\le 0.4$:** Low Risk / Standard alignment.
- **Normalized Offset $0.4 < \text{Offset} \le 0.7$:** Medium Risk (possible strabismus / poor gaze fixation stability).
- **Normalized Offset $> 0.7$:** High Risk / Refractive asymmetry or strabismus.

---

## 📱 Mobile Client Implementation Checklist (for Manus iPad)

### 1. Camera Control Constraints (Critical)
*   **Rear Camera Priority:** The rear camera must be used to ensure high resolution and the availability of a powerful physical flash LED close to the lens.
*   **Flash Torch Mode:** The LED torch **must** be turned on continuously during the acquisition phase. In photorefraction, the continuous light is required to refract off the retina and illuminate the pupil's bottom half (the red reflex).
    - **iOS Swift:**
      ```swift
      guard let device = AVCaptureDevice.default(for: .video) else { return }
      if device.hasTorch {
          try device.lockForConfiguration()
          try device.setTorchModeOn(level: 1.0)
          device.unlockForConfiguration()
      }
      ```
    - **Android Kotlin:**
      ```kotlin
      cameraControl.enableTorch(true)
      ```

### 2. Alignment & Stability Logic (Client-side MediaPipe FaceMesh)
Before capturing the image, the mobile client must display an interactive HUD that guides the user. The app will auto-shoot only when the following criteria are met:
1.  **Level Check:** The angle of the line connecting both eye centers must be within $\pm 3^\circ$ relative to the horizontal screen plane.
2.  **Distance Check:** The distance between the pupil centers must fall in the optimal pixel range corresponding to a physical distance of $1.0\text{ meter} \pm 10\text{ cm}$.
3.  **Stability Check:** The standard deviation of the pupil center locations over a window of $1500\text{ ms}$ must be $< 2.0\text{ pixels}$.
4.  **Auto Capture:** Upon maintaining stability for $1500\text{ ms}$, the client automatically takes a photo, disables the torch, and posts it to the backend.

---

## 🛰️ Backend API Integration Specifications

### 1. Refraction & Marker Analysis
- **Endpoint:** `POST /api/analyze-reflex-base64`
- **Request Body (JSON):**
  ```json
  {
    "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
  }
  ```
- **Response Body (JSON):**
  ```json
  {
    "success": true,
    "clinical_report": {
      "left_eye": {
        "center_x": 482,
        "center_y": 612,
        "radius": 42,
        "refraction": {
          "diopters": -1.25,
          "crescent_width_estimated": 8.52,
          "ratio_wp": 0.101
        },
        "behavior_markers": {
          "hirschberg_offset_px": 5.4,
          "normalized_offset": 0.13,
          "asd_risk_indicator": "low",
          "fixation_stability_score": 0.87
        },
        "timestamp": "2026-06-04T14:10:00.123456"
      },
      "right_eye": {
        "center_x": 724,
        "center_y": 614,
        "radius": 41,
        "refraction": {
          "diopters": -1.30,
          "crescent_width_estimated": 8.24,
          "ratio_wp": 0.100
        },
        "behavior_markers": {
          "hirschberg_offset_px": 5.2,
          "normalized_offset": 0.12,
          "asd_risk_indicator": "low",
          "fixation_stability_score": 0.88
        },
        "timestamp": "2026-06-04T14:10:00.123456"
      }
    },
    "meta": {
      "engine_version": "2.0-Savage-Clinical",
      "calibration_status": "active_feedback_loop"
    }
  }
  ```

### 2. SGD Online Recalibration Loop
If the pediatrician performs a physical screening (e.g. retinoscopy) and overrides the predicted value, the system learns the offset for that specific sensor:
- **Endpoint:** `POST /api/feedback`
- **Request Body (JSON):**
  ```json
  {
    "predicted_diopters": -1.25,
    "actual_diopters": -1.50,
    "ratio_wp": 0.101
  }
  ```
- **Response Body (JSON):**
  ```json
  {
    "success": true,
    "message": "Calibration updated successfully",
    "new_calibration": {
      "refraction_slope": 0.0768,
      "refraction_offset": -0.0284,
      "eccentricity_mm": 10.0,
      "distance_m": 1.0,
      "feedback_count": 2,
      "learning_rate": 0.01
    }
  }
  ```

---
*Protocolo MAIAH: La precisión en el diagnóstico es el primer paso de la compasión clínica.* 🫡🚀🩺💎✨

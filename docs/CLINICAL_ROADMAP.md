# Beto PH: Clinical & Technological Roadmap (PH Expansion)

*This document outlines the strategic expansion of Beto Pediatría Humanizada from a clinical management tool into a proactive, AI-driven early detection platform. It is based on the intersection of advanced generative/computer vision AI and sensory-friendly clinical design.*

## The "Unfair Advantage" Philosophy
Beto PH leverages technology not to replace the pediatrician, but to remove bureaucratic and diagnostic friction, forcing "human union" (allowing the doctor to look at the patient, not the screen). We reject "stupid generative AI" in favor of compassionate, clinically validated tools.

---

## Phase 4: Proactive Neuro-Ophthalmological Screening

Based on recent medical literature and clinical guidelines (AAP, AAO), early detection in the 0-6 year window is critical. Beto PH will integrate tools to democratize access to expensive screenings.

### 1. Amblyopia & Refractive Errors (The Popom-i Integration)

**The Clinical Problem:**
The sensitive period for visual development ends around age 7-8. Uncorrected anisometropia is the most preventable cause of amblyopia, leading to deficits in visual acuity, attention, and executive functions (Black et al., 2021; Sen et al., 2021).
Current screening relies on physical photo-screeners (e.g., PlusoptiX) costing $5,000-$10,000 USD, making them inaccessible to many primary care pediatricians.

**The Beto PH Solution (Active):**
*   **Technology:** Eccentric Photorefraction via Computer Vision.
*   **Implementation:** We have grafted the `Popom-i` engine directly into the FastAPI backend (`backend/utils/vision_engine.py`). It analyzes the "red reflex" from a smartphone/tablet flash to estimate diopters and detect anisometropia.
*   **Next Steps:** Develop the React UI component for capturing the image with strict alignment guides and flash control.

### 2. Autism Spectrum Disorder (ASD) - Digital Motor Markers (DMMs)

**The Clinical Problem:**
ASD intervention before ages 2-3 yields significantly better neuroplastic outcomes. Atypical motor markers can be detected between 6-12 months, preceding classic socio-communicative symptoms (Scarcella et al., 2025). The current standard, the M-CHAT-R/F at 18-24 months, suffers from low specificity (~50%), reliance on parent perception, and high failure rates in follow-up.

**The Beto PH Solution (Planned):**
*   **Technology:** Browser-based Computer Vision (e.g., MediaPipe) & Intelligent Questionnaires.
*   **Implementation Strategy:**
    1.  **Smart M-CHAT:** Deliver adaptive questionnaires via the existing WhatsApp engine (Evolution API) *before* the consultation. Parse results and alert the doctor on the dashboard.
    2.  **Beto Play (Vision Module): (In Development - PH Mode)** Develop a short, gamified video module featuring the "Osito Doctor PH". While the child watches on a tablet, the front-facing camera analyzes digital motor markers (gaze tracking, blink rate, facial expression) to generate an early warning score, similar to the validated SenseToKnow app (Babu et al., 2024).
        - Integration legion has been deployed to build the frontend, backend, and computer vision pipelines concurrently.

### 3. Developmental Dysplasia of the Hip (DDH)

**The Clinical Problem:**
Prognosis is poor for hips that remain unstable or abnormal up to 2-3 years, whereas treatment with bracing before 6 months is effective and non-invasive. Late diagnosis leads to early degenerative dysplasia in adulthood. The current standard relies on physical examination (Ortolani, Barlow), which is operator-dependent and loses sensitivity after 3 months. Universal ultrasound is not recommended by the AAP.

**The Beto PH Solution (Planned):**
*   **Technology:** Intelligent Risk Profiling & Medical Image Analysis (AI).
*   **Implementation Strategy:**
    1.  **Automated Risk Triage:** Smart questionnaires capturing birth risk factors (breech presentation, family history) that trigger automated reminders for targeted physical exams or selective ultrasound referrals.
    2.  **Image Analysis (Future):** Integrate an open-source framework (like Retuve) to automatically measure alpha angles and acetabular indices on uploaded ultrasound/X-ray images within the EHR, reducing inter-observer variability.

### 4. Childhood Hearing Loss (Hipoacusia)

**The Clinical Problem:**
The first 3 years are critical for language development (1-3-6 goal: screen at 1 month, diagnose by 3, intervene by 6). Unidentified hearing loss causes irreversible deficits. Current neonatal screening misses post-neonatal/progressive loss (~10-20% of pediatric cases), and loss-to-follow-up rates are high. In-office behavioral observation is crude and imprecise.

**The Beto PH Solution (Planned):**
*   **Technology:** Objective Audiometric Integrations & Longitudinal Tracking.
*   **Implementation Strategy:**
    1.  **High-Risk Registry & Tracking:** Automated longitudinal tracking via WhatsApp to ensure completion of the 1-3-6 pathway for newborns, specifically targeting the high loss-to-follow-up rate.
    2.  **Parental Surveillance:** Deploy adaptive hearing milestone questionnaires at 6, 9, and 12 months to catch post-neonatal onset loss before significant language delay occurs.

---

## Scientific References

1.  **ASD & Motor Markers:** Scarcella, Ileana et al. (2025). Digital motor markers for early autism detection: promise, pitfalls, and a path to clinics. *Frontiers in Psychiatry*, 16. https://doi.org/10.3389/fpsyt.2025.1720138
2.  **ASD Pre-symptomatic Intervention:** Grzadzinski, Rebecca et al. (2021). Pre-symptomatic intervention for autism spectrum disorder (ASD): defining a research agenda. *Journal of Neurodevelopmental Disorders*, 13(1). https://doi.org/10.1186/s11689-021-09393-y
3.  **App-based ASD Screening:** Babu, Pradeep Raj Krishnappa et al. (2024). Validation of a Mobile App for Remote Autism Screening in Toddlers. *NEJM AI*, 1(10). https://doi.org/10.1056/aics2400510
4.  **Amblyopia Impact:** Black, Alex A. et al. (2021). Impact of Amblyopia on Visual Attention and Visual Search in Children. *Investigative Opthalmology & Visual Science*, 62(4), 15. https://doi.org/10.1167/iovs.62.4.15
5.  **AAO Practice Pattern:** Cruz, Oscar A. et al. (2023). Amblyopia Preferred Practice Pattern. *Ophthalmology*, 130(3), P136-P178. https://doi.org/10.1016/j.ophtha.2022.11.003
6.  **Amblyopia Management:** Sen, Sagnik, Singh, Pallavi, and Saxena, Rohit. (2021). Management of amblyopia in pediatric patients: Current insights. *Eye*, 36(1), 44-56. https://doi.org/10.1038/s41433-021-01669-w
7.  **DDH AAP Report:** Evaluation and Referral for Developmental Dysplasia of the Hip (2016). *Pediatrics*, 138(6). https://publications.aap.org/pediatrics/article/138/6/e20163107/52541/Evaluation-and-Referral-for-Developmental
8.  **Childhood Hearing Loss:** Loss to follow-up in early hearing detection and intervention programs. *BMJ Paediatrics Open*. https://doi.org/10.1136/bmjpo-2022-001752

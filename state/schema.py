from typing import TypedDict, List, Optional

class BotState(TypedDict):
    # ── User info ──────────────────────────────────────────────────
    messages:       List
    name:           str
    age:            str
    symptoms:       str
    duration:       str
    pain_level:     str
    city:           str
    patient_phone:  str
    patient_email:  str

    # ── Intake ─────────────────────────────────────────────────────
    intake_done:        bool
    intake_confidence:  float
    intake_rounds:      int
    find_doctor_response: Optional[str]

    # ── Diagnosis ──────────────────────────────────────────────────
    diagnosis:              str
    diagnosis_confidence:   float
    diagnosis_rounds:       int
    red_flag:               bool
    speciality:             str

    # ── RAG ────────────────────────────────────────────────────────
    rag_context:         List[str]
    rag_relevance_score: float
    rag_grounded:        bool
    rag_queries_tried:   List[str]

    # ── Triage ─────────────────────────────────────────────────────
    triage_level:    str
    triage_reasoning: str
    route:           str
    triage_done:     bool         

    # ── Doctor ─────────────────────────────────────────────────────
    doctors_list:      List
    selected_doctor:   Optional[dict]
    speciality_confidence: float

    # ── Booking ────────────────────────────────────────────────────
    booking_stage:     str
    appointment_day:   str
    appointment_time:  str
    human_approval:    bool
    no_doctor_speciality: str
    booking_complete:  bool        

    # ── Agent thinking display ─────────────────────────────────────
    agent_thoughts:  List[dict]
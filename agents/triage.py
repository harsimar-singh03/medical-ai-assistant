

import json
import re
from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)

RED_FLAGS = [
    "Chest pain with shortness of breath or sweating",
    "Stroke signs: sudden face drooping, arm weakness, or slurred speech",
    "Severe allergic reaction (throat swelling, cannot breathe)",
    "Uncontrolled or heavy bleeding",
    "Loss of consciousness or unresponsiveness",
    "Worst headache of life with stiff neck and fever",
    "Severe difficulty breathing at rest",
    "Rigid/board-like abdomen with severe pain",
    "Signs of sepsis: high fever + confusion + rapid heartbeat",
    "Active suicidal ideation or self-harm",
]


def _assess_severity(state: dict) -> dict:
    """LLM checks red flags and returns severity + reasoning."""
    red_flags_formatted = "\n".join(f"  - {f}" for f in RED_FLAGS)

    # ── patient info──
    user_messages = [
        m.content for m in state.get("messages", [])
        if isinstance(m, HumanMessage)
    ]
    full_story = "\n".join(user_messages)

    prompt = f"""
    You are a senior emergency triage nurse. Analyse the patient's story and assign severity.

    PATIENT STORY (everything the patient said):
    {full_story}

    ── STEP 1: RED FLAG CHECK ──
    For each red flag, label it PRESENT, ABSENT, or UNKNOWN based on the story:
{red_flags_formatted}

    ── STEP 2: CONTEXT ASSESSMENT ──
    - Is the patient describing an acute, life‑threatening situation?
    - Is the pain severe (8‑10/10)?
    - Are there signs of respiratory distress (heavy breathing, cannot breathe)?
    - Is the patient showing signs of shock (cold, clammy, confused)?

    ── STEP 3: SEVERITY DECISION ──
    EMERGENCY  → Active red flag present OR severe pain + respiratory/cardiac symptoms
    URGENT     → Needs doctor today
    MODERATE   → Needs doctor this week
    MILD       → Self‑care + monitor

    IMPORTANT: Heavy breathing + chest pain + pain 10/10 + feeling cold = EMERGENCY
               Do NOT underestimate respiratory distress combined with chest pain.

    Return ONLY valid JSON:
    {{
        "severity":          "EMERGENCY" or "URGENT" or "MODERATE" or "MILD",
        "confidence":        0.0 to 1.0,
        "reasoning":         "one clear sentence explaining the severity decision",
        "recommendation":    "specific next action for the patient"
    }}
    """
    try:
        raw = llm.invoke(prompt).content.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"   ❌ Triage thinking failed: {e}")
        return {
            "severity":       "MODERATE",
            "confidence":     0.5,
            "reasoning":      "Assessment incomplete — defaulting to moderate for safety.",
            "recommendation": "Please consult a doctor to be safe."
        }


def triage_agent(state: dict) -> dict:
    assessment = _assess_severity(state)

    severity       = assessment.get("severity", "MODERATE")
    confidence     = assessment.get("confidence", 0.5)
    reasoning      = assessment.get("reasoning", "")
    recommendation = assessment.get("recommendation", "")

    if severity == "EMERGENCY":
        route = "emergency"
        red_flag = True
    elif severity in ("URGENT", "MODERATE"):
        route = "doctor_finder"
        red_flag = False
    else:
        route = "self_care"
        red_flag = False

    

    msg = f" **Triage: {severity}**\n📋 {reasoning}\n💡 {recommendation}"

    if severity != "EMERGENCY":
        msg += "\n\nWould you like me to find a doctor near you?"

    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=msg))

    return {
        **state,
        "messages":         messages,
        "triage_level":     severity,
        "triage_reasoning": reasoning,
        "route":            route,
        "red_flag":         red_flag,
    }
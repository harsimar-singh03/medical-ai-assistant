
from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from agents.rag_pdf import get_relevant_context

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)

MAX_DIAGNOSIS_ROUNDS = 2         


#  Pydantic models 

class Condition(BaseModel):
    condition:   str = Field(description="Name of the medical condition")
    probability: str = Field(description="Likelihood: high, medium, or low")
    reasoning:   str = Field(description="One‑sentence explanation based on symptoms and medical reference")


class ClinicalThinking(BaseModel):
    differential:      list[Condition] = Field(description="2–3 possible conditions")
    reasoning_summary: str = Field(description="Two‑sentence clinical reasoning")
    red_flags:         list[str] = Field(
        description="Emergency warning signs that the patient explicitly described. "
                    "NEVER invent red flags that the patient did NOT mention."
    )
    critical_missing:  str | None = Field(
        None,
        description="The most important piece of information still missing to make a confident diagnosis, or null if confident"
    )


#  Speciality map

SPECIALITY_MAP = {
    "headache": "Neurologist", "migraine": "Neurologist",
    "chest pain": "Cardiologist", "heart": "Cardiologist",
    "breathing": "Pulmonologist", "asthma": "Pulmonologist",
    "skin": "Dermatologist", "rash": "Dermatologist",
    "stomach": "Gastroenterologist", "vomit": "Gastroenterologist",
    "joint": "Orthopedic Surgeon", "fracture": "Orthopedic Surgeon",
    "diabetes": "Endocrinologist", "thyroid": "Endocrinologist",
    "anxiety": "Psychiatrist", "depression": "Psychiatrist",
    "eye": "Ophthalmologist", "vision": "Ophthalmologist",
}

def _infer_speciality(conditions: list[Condition], symptoms: str) -> str:
    combined = (symptoms + " " + " ".join(c.condition for c in conditions)).lower()
    for keyword, speciality in SPECIALITY_MAP.items():
        if keyword in combined:
            return speciality
    return "General Physician"


#  Main agent 

def diagnosis_agent(state: dict) -> dict:
    symptoms = state.get("symptoms", "")
    city     = state.get("city", "your city")
    diagnosis_rounds = state.get("diagnosis_rounds", 0)

    # Gather all user messages for context
    all_user_msgs = " | ".join(
        m.content for m in state.get("messages", []) if isinstance(m, HumanMessage)
    )

    # 1. RAG retrieval
    contexts     = get_relevant_context(symptoms)
    context_text = "\n\n".join(contexts[:3]) if contexts else ""

    # 2. Structured clinical thinking
    structured_llm = llm.with_structured_output(ClinicalThinking)

    prompt = f"""
You are a senior physician. Analyse the patient below and return the diagnosis.

PATIENT (city: {city}, India):
Symptoms: {symptoms}

CONVERSATION (respect what the patient actually said):
{all_user_msgs[:600]}

MEDICAL REFERENCE:
{context_text[:1000] if context_text else "Use your clinical knowledge."}

INSTRUCTIONS:
- Provide 2–3 possible conditions with probabilities (high/medium/low) and brief reasoning.
- Red flags: ONLY list emergency signs that the patient explicitly described. Do NOT invent or assume any symptom not mentioned by the patient.
- If there is an important piece of information still missing to make a confident diagnosis, set "critical_missing" to that missing info (e.g., "Duration of fever", "Presence of neck stiffness"). If you are confident, set it to null.
- Provide a two‑sentence reasoning summary.
"""

    try:
        thinking = structured_llm.invoke(prompt)
    except Exception:
        thinking = ClinicalThinking(
            differential=[
                Condition(condition="Unspecified condition", probability="medium",
                          reasoning="Further evaluation needed.")
            ],
            reasoning_summary="Unable to determine precise diagnosis. Please consult a doctor.",
            red_flags=[],
            critical_missing=None,
        )

    # 3. Build message depending on round
    force  = (diagnosis_rounds + 1 >= MAX_DIAGNOSIS_ROUNDS)
    critical = thinking.critical_missing

    lines = []
    for c in thinking.differential:
        lines.append(f"**{c.condition}** ({c.probability} probability)")
        lines.append(f"   → {c.reasoning}")
    conditions_text = "\n".join(lines)
    reasoning = thinking.reasoning_summary
    red_text  = "\n\n🚨 **Urgent:** " + ", ".join(thinking.red_flags) if thinking.red_flags else ""

    messages = list(state.get("messages", []))

    if not force and critical:
        # Ask ONE follow‑up question 
        fq_prompt = (
            f"Clinical reasoning: {reasoning}\n"
            f"Most important missing info: {critical}\n"
            "Write ONE warm, clear follow‑up question (max 2 sentences)."
        )
        try:
            fq = llm.invoke(fq_prompt).content.strip()
        except Exception:
            fq = f"Could you tell me more about: {critical}?"

        message = (
            f"🔍 **Preliminary Assessment** (Round {diagnosis_rounds+1} of {MAX_DIAGNOSIS_ROUNDS})\n\n"
            f"{conditions_text}\n\n"
            f"📋 *{reasoning}*{red_text}\n\n"
            f"⚠️ *AI guidance only — not a substitute for professional medical advice.*\n\n"
            f"**To narrow this down:** {fq}"
        )
        messages.append(AIMessage(content=message))
        diagnosis_done = True
        intake_done = True
    else:
        # Final diagnosis
        speciality = _infer_speciality(thinking.differential, symptoms)
        message = (
            f"🩺 **Diagnosis Assessment**\n\n"
            f"{conditions_text}\n\n"
            f"📋 *{reasoning}*{red_text}\n\n"
            f"⚠️ *AI guidance only — not a substitute for professional medical advice.*\n\n"
            f"Would you like me to find a **{speciality}** near {city}?"
        )
        messages.append(AIMessage(content=message))
        diagnosis_done = True
        intake_done = True
        state["speciality"] = speciality

    return {
        **state,
        "messages":         messages,
        "diagnosis":        conditions_text,
        "diagnosis_rounds": diagnosis_rounds + 1,
        "diagnosis_done":   diagnosis_done,
        "intake_done":      intake_done,
        "red_flag":         len(thinking.red_flags) > 0,
    }
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)


#  Pydantic model 
class IntakeInfo(BaseModel):
    symptoms: str | None = Field(
        None, description="All symptoms mentioned, comma‑separated. Omit if none."
    )
    city: str | None = Field(
        None, description="City name or null if not mentioned"
    )


# Structured LLM 
_extractor = llm.with_structured_output(IntakeInfo)


def _extract_from_text(text: str) -> IntakeInfo | None:
    """Run the extraction LLM on a given text and return a validated IntakeInfo."""
    prompt = f"""
    Extract the following from the user's message:
    Message: "{text}"

    Return an object with:
    - symptoms: all symptoms mentioned (combine multiple), or null if none
    - city: the city name or null if not mentioned

    Examples:
    "headache and fever, Delhi" → symptoms: "headache, fever", city: "Delhi"
    "cold and cough" → symptoms: "cold, cough", city: null
    "delhi" → symptoms: null, city: "Delhi"
    """
    try:
        return _extractor.invoke(prompt)
    except Exception:
        return None


def intake_agent(state: dict) -> dict:
    messages = state.get("messages", [])
    rounds = state.get("intake_rounds", 0)

    # ── Greeting ─────────────────────────────────────────────
    if not messages:
        greeting = (
            "Hello! I'm your medical assistant. 🩺\n\n"
            "Please tell me:\n"
            "- **Your symptoms** (what are you feeling?)\n"
            "- **Your city** (so I can find doctors near you)\n\n"
            "For example: *headache and fever, Delhi*"
        )
        state["messages"] = [AIMessage(content=greeting)]
        state["intake_done"] = False
        state["intake_rounds"] = 0
        return state

    
    if isinstance(messages[-1], AIMessage):
        return state

    
    last_msg = messages[-1].content
    info = _extract_from_text(last_msg)

    if not info or (not info.symptoms and not info.city):
        # Fallback: combine all user messages and try again
        all_user_text = " ".join(
            m.content for m in messages if isinstance(m, HumanMessage)
        )
        info = _extract_from_text(all_user_text)

    if info is None:
        info = IntakeInfo(symptoms=None, city=None)

    #  Update state
    if info.symptoms:
        state["symptoms"] = info.symptoms
    if info.city and not state.get("city"):
        state["city"] = info.city

    #  Check completeness 
    missing = []
    if not state.get("symptoms"):
        missing.append("your symptoms")
    if not state.get("city"):
        missing.append("your city")

    rounds += 1
    force_done = rounds >= 3
    done = (not missing) or force_done

    if done:
        if force_done and missing:
            msg = f"✅ Proceeding with available info (missing: {', '.join(missing)})."
        else:
            msg = f"✅ Got it! Symptoms: {state.get('symptoms')} | City: {state.get('city')}"
        messages.append(AIMessage(content=msg))
    else:
        question = f"I still need: {', '.join(missing)}. Please provide them."
        messages.append(AIMessage(content=question))

    state["messages"] = messages
    state["intake_done"] = done
    state["intake_rounds"] = rounds
    return state
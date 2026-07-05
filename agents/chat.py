from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage
from agents.rag_pdf import search_medical_knowledge

llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.1)
chat_llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.4)


import streamlit as st
import os
try:
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    pass


# INTENT DETECTION 

def _detect_intent(user_message: str, diagnosis: str, symptoms: str) -> str:
    prompt = f"""You are an intent classifier for a medical chatbot.

        The patient was just shown this diagnosis:
        \"\"\"{diagnosis[:300]}\"\"\"

        Their symptoms: {symptoms}

        The patient now says: "{user_message}"

        Classify their intent. Choose EXACTLY ONE:
        - find_doctor  -> they want to find, book, or see a doctor
        - end_session  -> they don't want a doctor right now
        - question     -> they have a medical question

        Return ONLY one word: find_doctor, end_session, or question"""

    try:
        result = llm.invoke(prompt).content.strip().lower()
        if "find_doctor" in result:
            return "find_doctor"
        if "end_session" in result:
            return "end_session"
        return "question"
    except Exception:
        return "question"



def chat_agent(state: dict) -> dict:
    messages  = list(state.get("messages", []))
    symptoms  = state.get("symptoms", "")
    diagnosis = state.get("diagnosis", "")

    last_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_msg = msg.content.strip()
            break

    if not last_msg:
        return state

    # Intent detection
    intent = _detect_intent(last_msg, diagnosis, symptoms)

    if intent == "find_doctor":
        messages.append(AIMessage(content="Great! Let me find a doctor for you. 🩺"))
        return {**state, "messages": messages, "find_doctor_response": "yes"}

    if intent == "end_session":
        messages.append(AIMessage(content="No problem! If your symptoms worsen, please see a doctor. Take care! 🩺"))
        return {**state, "messages": messages, "find_doctor_response": "no"}

   
    # Build a transcript of the last 10 messages (both user and assistant)
    history = ""
    for m in messages[-10:]:
        role = "Patient" if isinstance(m, HumanMessage) else "Assistant"
        history += f"{role}: {m.content}\n"

    # RAG (optional, can be kept or removed for speed)
    contexts = search_medical_knowledge(f"{symptoms} {last_msg}", k=2)
    context_text = "\n\n".join(contexts) if contexts else ""

    #  BOOKING‑AWARE CLOSING LINE 
    booking_done = state.get("booking_complete") or (
        state.get("human_approval") and state.get("booking_stage") == "done"
    )
    if booking_done:
        closing_line = "Is there anything else I can help you with?"
    else:
        closing_line = "Would you like me to find a doctor near you, or do you have more questions?"

    prompt = f"""You are a helpful medical assistant. Below is the full conversation so far.

CONVERSATION:
{history}

The patient now asks: "{last_msg}"

Medical reference: {context_text if context_text else "Use your medical knowledge."}

Answer helpfully in 3-4 sentences.
If they ask what to do while waiting for an ambulance, give clear, practical advice.
Note: If the patient has already been triaged as EMERGENCY, DO NOT say "see a doctor". Instead, provide specific first aid advice based on their symptoms.
Important : if doctors have already been recommended, do NOT repeat the recommendation to see a doctor. Instead, focus on answering their question or providing advice based on their symptoms and diagnosis.
{closing_line}"""

    response = chat_llm.invoke(prompt)
    messages.append(AIMessage(content=response.content))
    return {**state, "messages": messages, "find_doctor_response": None}
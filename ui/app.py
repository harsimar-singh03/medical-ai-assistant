

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.intake import intake_agent
from agents.diagnosis import diagnosis_agent, MAX_DIAGNOSIS_ROUNDS
from agents.chat import chat_agent
from agents.triage import triage_agent
from agents.doctor_finder import doctor_finder_agent
from agents.booking import human_approval_node
from agents.emergency import emergency_node

load_dotenv()

st.set_page_config(page_title="🩺 Medical AI Assistant", page_icon="🏥", layout="wide")
st.title("🩺 Medical AI Assistant")
st.caption("Describe your symptoms and get medical guidance")

BLANK_STATE = {
    "messages": [],
    "name": "", "age": "", "symptoms": "",
    "duration": "", "pain_level": "", "city": "",
    "patient_phone": "", "patient_email": "",

    "intake_done":          False,
    "intake_rounds":        0,
    "find_doctor_response": None,

    "diagnosis":        "",
    "diagnosis_rounds": 0,
    "diagnosis_done":   False,
    "red_flag":         False,
    "speciality":       "",
    "diagnosis_asked":  False,

    "rag_context":         [],
    "rag_relevance_score": 0.0,
    "rag_grounded":        True,
    "rag_queries_tried":   [],

    "triage_level": "", "triage_reasoning": "", "route": "",
    "triage_done": False,

    "doctors_list":          [],
    "selected_doctor":       None,
    "speciality_confidence": 0.0,
    "booking_stage":         "select_doctor",
    "appointment_day":       "", "appointment_time": "",
    "human_approval":        False,
    "no_doctor_speciality":  "",
    "booking_complete":      False,

    "agent_thoughts": [],
}

if "state" not in st.session_state:
    st.session_state.state = dict(BLANK_STATE)

if "chat_started" not in st.session_state:
    st.session_state.chat_started = False


def current_phase(state: dict) -> str:
    if state.get("booking_complete"):
        return "CHAT"
    if state.get("human_approval") and state.get("booking_stage") == "done":
        return "CHAT"
    if state.get("doctors_list") or state.get("booking_stage") in ("no_doctor_found", "change_city"):
        return "BOOKING"

    #  MULTIPLE DIAGNOSIS ROUNDS BEFORE TRIAGE 
    if state.get("diagnosis_done") and not state.get("triage_done"):
        if state.get("diagnosis_rounds", 0) < MAX_DIAGNOSIS_ROUNDS:
            return "DIAGNOSIS"
        else:
            return "TRIAGE"

    if state.get("intake_done"):
        return "CHAT"
    return "INTAKE"


def show_last_ai(state: dict):
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage):
            with st.chat_message("assistant"):
                st.markdown(msg.content)
            break


# Render chat history
for msg in st.session_state.state["messages"]:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.markdown(msg.content)
    elif isinstance(msg, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(msg.content)


# Start button
if not st.session_state.chat_started:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Start Consultation", use_container_width=True, type="primary"):
            st.session_state.chat_started = True
            state = intake_agent(st.session_state.state)
            st.session_state.state = state
            st.rerun()


# Chat input
if st.session_state.chat_started:
    user_input = st.chat_input("Type your message here...")

    if user_input:
        state = st.session_state.state
        state["messages"].append(HumanMessage(content=user_input))
        with st.chat_message("user"):
            st.markdown(user_input)

        phase = current_phase(state)

        # PHASE 1: INTAKE
        if phase == "INTAKE":
            state = intake_agent(state)
            show_last_ai(state)
            if state.get("intake_done") and not state.get("diagnosis_done"):
                with st.spinner(" Analysing your symptoms..."):
                    state = diagnosis_agent(state)
                st.session_state.state = state
                st.rerun()

        #  NEW: DIAGNOSIS FOLLOW‑UP ROUND 
        elif phase == "DIAGNOSIS":
            with st.spinner(" Re‑evaluating your symptoms..."):
                state = diagnosis_agent(state)
            show_last_ai(state)
            if state.get("diagnosis_rounds", 0) >= MAX_DIAGNOSIS_ROUNDS:
                with st.spinner(" Assessing urgency..."):
                    state = triage_agent(state)
                state["triage_done"] = True
                if state.get("route") == "emergency":
                    state = emergency_node(state)
            st.session_state.state = state
            st.rerun()

        # TRIAGE PHASE 
        elif phase == "TRIAGE":
            with st.spinner(" Assessing urgency..."):
                state = triage_agent(state)
            state["triage_done"] = True
            if state.get("route") == "emergency":
                state = emergency_node(state)
            st.session_state.state = state
            st.rerun()

        #  CHAT 
        elif phase == "CHAT":
            state = chat_agent(state)
            show_last_ai(state)
            if state.get("find_doctor_response") == "yes":
                with st.spinner(" Searching for doctors..."):
                    state = doctor_finder_agent(state)
                show_last_ai(state)

        # PHASE 3: BOOKING
        elif phase == "BOOKING":
            state = human_approval_node(state)
            show_last_ai(state)
            if state.get("human_approval") and state.get("booking_stage") == "done":
                st.balloons()
                st.success(" Appointment Confirmed!")

        st.session_state.state = state
        st.rerun()


# Sidebar
with st.sidebar:
    st.header("📊 Session Info")
    state = st.session_state.state

    if state.get("name"):
        st.write(f"** {state['name']}**")
        if state.get("age"):  st.write(f" {state['age']} yrs")
        if state.get("city"): st.write(f" {state['city']}")

    if state.get("symptoms"):
        st.divider()
        st.write(f" **{state['symptoms']}**")
        

    if state.get("triage_level"):
        st.divider()
        st.metric("Severity", state["triage_level"])

    if state.get("diagnosis_done"):
        st.divider()
        if state.get("rag_grounded"):
            st.success(" RAG: Grounded in medical PDF")
        else:
            st.warning(" RAG: Using LLM general knowledge")

    if state.get("human_approval") and state.get("booking_stage") == "done":
        st.divider()
        st.success(" Appointment booked!")

    #  Agent Thinking 
    thoughts = state.get("agent_thoughts", [])
    if thoughts:
        st.divider()
        st.subheader("💭 Agent Thinking")
        for t in thoughts[-12:]:
            agent = t.get("agent", "?")
            with st.expander(f"🧠 {agent.upper()}"):
                st.write(t.get("thought", ""))

    st.divider()
    if st.button("🔄 Start New Chat"):
        st.session_state.clear()
        st.rerun()
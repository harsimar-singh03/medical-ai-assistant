import re
from langchain_core.messages import HumanMessage, AIMessage
from tools.time_utils import extract_day_time, validate_slot
from tools.booking_db import save_booking
from tools.email_tool import send_booking_email
from agents.doctor_finder import find_doctors

def _get_last_user_msg(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content.strip().lower()
    return ""



def _finalize_booking(state, doc):
    booking_data = {
        "patient_name": state.get("name", ""),
        "patient_age": state.get("age", ""),
        "patient_city": state.get("city", ""),
        "patient_phone": state.get("patient_phone", ""),
        "patient_email": state.get("patient_email", ""),
        "doctor_name": doc.get("Name", ""),
        "speciality": doc.get("Speciality", ""),
        "clinic_name": doc.get("Clinic Name", ""),
        "address": doc.get("Address", ""),
        "city": doc.get("City", ""),
        "day": state.get("appointment_day", ""),
        "time": state.get("appointment_time", ""),
        "fee": doc.get("Consultation Fee (₹)", ""),
        "doctor_phone": doc.get("Phone Number", "")
    }
    booking_id = save_booking(booking_data)
    send_booking_email(
        patient_name=state.get("name", ""),
        patient_email=state.get("patient_email", ""),
        doctor_name=doc.get("Name", ""),
        clinic_name=doc.get("Clinic Name", ""),
        address=doc.get("Address", ""),
        day=state.get("appointment_day", ""),
        time=state.get("appointment_time", ""),
        fee=doc.get("Consultation Fee (₹)", ""),
        doctor_phone=doc.get("Phone Number", ""),
        booking_id=booking_id
    )
    return booking_id




def _handle_select_doctor(state, messages, last_msg, doctors):
    if not doctors:
        messages.append(AIMessage(content="No doctors available. Please try again."))
        return {**state, "messages": messages, "human_approval": True}

    selected = None
    for i in range(1, len(doctors) + 1):
        if str(i) in last_msg:
            selected = doctors[i - 1]
            break

    if selected:
        msg = f" **Selected: {selected.get('Name', '')}**\n\n {selected.get('Available Days', '')}\n {selected.get('Available Hours', '')}\n\nWhich day and time? (e.g., 'Monday 11 AM')"
        messages.append(AIMessage(content=msg))
        return {**state, "messages": messages, "selected_doctor": selected, "booking_stage": "select_slot", "human_approval": False}
    messages.append(AIMessage(content="Please select a doctor by typing the number (e.g., '1')."))
    return {**state, "messages": messages, "human_approval": False}


def _handle_select_slot(state, messages, last_msg, selected_doctor):
    user_day, user_time = extract_day_time(last_msg)
    is_valid, error_msg = validate_slot(user_day, user_time,
                                        selected_doctor.get('Available Days', ''),
                                        selected_doctor.get('Available Hours', ''))
    if is_valid:
        msg = (f" **Great choice!**\n\n {selected_doctor.get('Name', '')}\n"
               f" {user_day.capitalize()} at {user_time.upper()}\n"
               f" ₹{selected_doctor.get('Consultation Fee (₹)', '')}\n\n"
               f" Please share:\n• Phone number\n• Email address\n\n(e.g., '98765xxxxx, xyz@gmail.com')")
        messages.append(AIMessage(content=msg))
        return {**state, "messages": messages, "appointment_day": user_day, "appointment_time": user_time,
                "booking_stage": "collect_contact", "human_approval": False}
    messages.append(AIMessage(content=f" {error_msg}\n\nPlease pick a valid day and time."))
    return {**state, "messages": messages, "human_approval": False}


def _handle_collect_contact(state, messages, last_msg, selected_doctor):
    phone_match = re.search(r'(\d{10})', last_msg)
    email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', last_msg)
    phone = phone_match.group(1) if phone_match else ""
    email = email_match.group(1) if email_match else ""

    errors = []
    if not phone: errors.append("a valid 10-digit phone number")
    if not email: errors.append("a valid email address")
    if errors:
        messages.append(AIMessage(content=f" I couldn't find {' and '.join(errors)}. Please try again."))
        return {**state, "messages": messages, "human_approval": False}

    msg = (f" **Booking Summary**\n\n"
           f" {state.get('name')}\n📱 {phone}\n {email}\n\n"
           f" {selected_doctor.get('Name')}\n {selected_doctor.get('Clinic Name')}\n"
           f" {selected_doctor.get('Address')}, {selected_doctor.get('City')}\n"
           f" {state.get('appointment_day', '').capitalize()} at {state.get('appointment_time', '').upper()}\n"
           f" ₹{selected_doctor.get('Consultation Fee (₹)')}\n\n"
           f"Type **yes** to confirm, or **no** to cancel.")
    messages.append(AIMessage(content=msg))
    return {**state, "messages": messages, "patient_phone": phone, "patient_email": email,
            "booking_stage": "confirm", "human_approval": False}


def _handle_confirm(state, messages, last_msg, selected_doctor):
    if any(word in last_msg for word in ['yes', 'confirm', 'book', 'ok', 'okay', 'done']):
        if not selected_doctor:
            return state
        booking_id = _finalize_booking(state, selected_doctor)
        msg = (f" **Appointment Confirmed!**\nBooking ID: #{booking_id}\n\n"
               f" {selected_doctor.get('Name')}\n🏥 {selected_doctor.get('Clinic Name')}\n"
               f" {selected_doctor.get('Address')}, {selected_doctor.get('City')}\n"
               f" {state.get('appointment_day', '').capitalize()} at {state.get('appointment_time', '').upper()}\n"
               f" ₹{selected_doctor.get('Consultation Fee (₹)')}\n📞 {selected_doctor.get('Phone Number')}\n\n"
               f" Confirmation sent to {state.get('patient_email')}\n"
               f"Please arrive 10 minutes early. Take care! 🩺")
        messages.append(AIMessage(content=msg))
        return {**state, "messages": messages, "human_approval": True, "booking_stage": "done", "booking_complete": True}

    if any(word in last_msg for word in ['no', 'cancel', 'change']):
        messages.append(AIMessage(content="Cancelled. Type a new day and time."))
        return {**state, "messages": messages, "booking_stage": "select_slot", "human_approval": False}
    return state


def human_approval_node(state):
    messages = list(state.get("messages", []))
    last_msg = _get_last_user_msg(messages)
    doctors = state.get("doctors_list", [])
    selected_doctor = state.get("selected_doctor")
    stage = state.get("booking_stage", "select_doctor")


    if stage == "select_doctor":
        return _handle_select_doctor(state, messages, last_msg, doctors)
    if stage == "select_slot" and selected_doctor:
        return _handle_select_slot(state, messages, last_msg, selected_doctor)
    if stage == "collect_contact" and selected_doctor:
        return _handle_collect_contact(state, messages, last_msg, selected_doctor)
    if stage == "confirm" and selected_doctor:
        return _handle_confirm(state, messages, last_msg, selected_doctor)

    
    return {**state, "human_approval": False}



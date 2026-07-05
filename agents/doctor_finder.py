import pandas as pd
import os
from langchain_core.messages import AIMessage

# LOAD EXCEL DATABASE

EXCEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "doctors.xlsx")

def _load_doctors():
    df = pd.read_excel(EXCEL_PATH)
    df.columns = df.columns.str.strip()
    db = {}
    for doc in df.to_dict('records'):
        spec = str(doc.get('Speciality', '')).strip()
        db.setdefault(spec, []).append(doc)
    return db

DOCTORS_DB = _load_doctors()

# SYMPTOM → SPECIALITY

SYMPTOM_MAP = {
    "fever": "General Physician", "cough": "General Physician", "cold": "General Physician",
    "fatigue": "General Physician", "weakness": "General Physician", "weight loss": "General Physician",
    "body pain": "General Physician", "chest pain": "Cardiologist", "heart": "Cardiologist",
    "palpitation": "Cardiologist", "blood pressure": "Cardiologist", "cholesterol": "Cardiologist",
    "skin": "Dermatologist", "rash": "Dermatologist", "acne": "Dermatologist", "hair": "Dermatologist",
    "allergy": "Allergist", "headache": "Neurologist", "migraine": "Neurologist", "seizure": "Neurologist",
    "memory": "Neurologist", "numbness": "Neurologist", "paralysis": "Neurologist", "tremor": "Neurologist",
    "back pain": "Orthopedic Surgeon", "joint pain": "Orthopedic Surgeon", "fracture": "Orthopedic Surgeon",
    "knee": "Orthopedic Surgeon", "shoulder": "Orthopedic Surgeon", "neck pain": "Orthopedic Surgeon",
    "sports injury": "Sports Medicine Specialist", "eye": "Ophthalmologist", "vision": "Ophthalmologist",
    "blurred": "Ophthalmologist", "ear": "ENT Specialist", "hearing": "ENT Specialist",
    "throat": "ENT Specialist", "nose": "ENT Specialist", "sinus": "ENT Specialist", "tonsil": "ENT Specialist",
    "pregnancy": "Gynecologist", "period": "Gynecologist", "menstrual": "Gynecologist",
    "fertility": "Reproductive Medicine Specialist", "child": "Pediatrician", "baby": "Pediatrician",
    "newborn": "Neonatologist", "anxiety": "Psychiatrist", "depression": "Psychiatrist",
    "stress": "Psychiatrist", "sleep": "Psychiatrist", "mood": "Psychiatrist",
    "stomach": "Gastroenterologist", "abdomen": "Gastroenterologist", "digestion": "Gastroenterologist",
    "acidity": "Gastroenterologist", "liver": "Hepatologist", "jaundice": "Hepatologist",
    "urine": "Urologist", "kidney": "Nephrologist", "stone": "Urologist", "breathing": "Pulmonologist",
    "asthma": "Pulmonologist", "lung": "Pulmonologist", "wheezing": "Pulmonologist",
    "cancer": "Oncologist", "tumor": "Oncologist", "radiation": "Radiation Oncologist",
    "thyroid": "Endocrinologist", "diabetes": "Endocrinologist", "hormone": "Endocrinologist",
    "arthritis": "Rheumatologist", "swelling": "Rheumatologist", "anemia": "Hematologist",
    "blood": "Hematologist", "bleeding": "Hematologist", "spine": "Neurosurgeon",
    "brain": "Neurosurgeon", "heart surgery": "Cardiothoracic Surgeon",
    "chronic pain": "Pain Management Specialist", "elderly": "Geriatrician", "old age": "Geriatrician",
    "infection": "Infectious Disease Specialist", "viral": "Infectious Disease Specialist",
    "plastic": "Plastic Surgeon", "vascular": "Vascular Surgeon", "colorectal": "Colorectal Surgeon",
    "nuclear": "Nuclear Medicine Specialist", "critical": "Critical Care Specialist",
}

def _match_speciality(symptoms: str) -> str:
    sym_lower = symptoms.lower()
    for keyword, spec in SYMPTOM_MAP.items():
        if keyword in sym_lower:
            return spec
    return "General Physician"

def _filter_city(doctors, city):
    if not city:
        return doctors
    city_lower = city.strip().lower()
    return [d for d in doctors if city_lower in str(d.get('City', '')).lower()
                                 or city_lower in str(d.get('Area', '')).lower()
                                 or city_lower in str(d.get('Address', '')).lower()]

def find_doctors(symptoms, city=None, max_results=3):
    speciality = _match_speciality(symptoms)
    doctors = DOCTORS_DB.get(speciality, [])
    if not doctors:
        doctors = DOCTORS_DB.get("General Physician", [])
        speciality = "General Physician"

    if city:
        filtered = _filter_city(doctors, city)
        if not filtered:
            # Fall back to General Physician in the same city if not already searching for one
            if speciality != "General Physician":
                general_docs = DOCTORS_DB.get("General Physician", [])
                filtered_general = _filter_city(general_docs, city)
                if filtered_general:
                    return filtered_general[:max_results], "General Physician", False
            return [], speciality, True   # city not found (or no General Physician either)
        doctors = filtered

    return doctors[:max_results], speciality, False



# DOCTOR FINDER AGENT

def doctor_finder_agent(state):
    symptoms = state.get("symptoms", "")
    city = state.get("city", "")
    doctors, speciality, city_not_found = find_doctors(symptoms, city)

    messages = list(state.get("messages", []))
    if city_not_found:
        msg = f"😔 We couldn't find any doctors in **{city}** matching your symptoms.\n\nPlease check Google Maps or contact local hospitals directly to find a doctor near you."
        return {
            **state,
            "messages": messages + [AIMessage(content=msg)],
            "doctors_list": [],
            "selected_doctor": None,
            "booking_complete": True,
            "booking_stage": "done",
            "human_approval": False
        }
    if doctors:
        lines = []
        for i, d in enumerate(doctors, 1):
            lines.append(f"{i}. **{d.get('Name', '')}**\n   🏥 {d.get('Clinic Name', '')}\n   📍 {d.get('Address', '')}, {d.get('City', '')}\n   ⭐ {d.get('Rating', '')} | 💰 ₹{d.get('Consultation Fee (₹)', '')}\n   📞 {d.get('Phone Number', '')}\n")
        msg = f"🏥 Found **{speciality}** {f'in **{city}**' if city else ''}:\n\n{''.join(lines)}Reply with number (1-{len(doctors)}) to select."
        return {**state, "messages": messages + [AIMessage(content=msg)], "doctors_list": doctors,
                "booking_stage": "select_doctor", "selected_doctor": None, "human_approval": False}
    msg = "😔 No doctors found for your symptoms. Please try again."
    return {**state, "messages": messages + [AIMessage(content=msg)], "doctors_list": [],
            "booking_stage": "select_doctor", "human_approval": False}
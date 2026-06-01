import sqlite3
import os
from datetime import datetime

DB_PATH = "/tmp/bookings.db"

def get_db():
    """Create/connect to SQLite database"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create bookings table if not exists"""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT,
            patient_age TEXT,
            patient_city TEXT,
            patient_phone TEXT,
            patient_email TEXT,
            doctor_name TEXT,
            speciality TEXT,
            clinic_name TEXT,
            address TEXT,
            city TEXT,
            day TEXT,
            time TEXT,
            fee TEXT,
            doctor_phone TEXT,
            booked_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_booking(data):
    """Save booking to database"""
    init_db()
    conn = get_db()
    
    conn.execute("""
        INSERT INTO bookings (
            patient_name, patient_age, patient_city,
            patient_phone, patient_email,
            doctor_name, speciality, clinic_name,
            address, city, day, time, fee, doctor_phone, booked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("patient_name", ""),
        data.get("patient_age", ""),
        data.get("patient_city", ""),
        data.get("patient_phone", ""),
        data.get("patient_email", ""),
        data.get("doctor_name", ""),
        data.get("speciality", ""),
        data.get("clinic_name", ""),
        data.get("address", ""),
        data.get("city", ""),
        data.get("day", ""),
        data.get("time", ""),
        data.get("fee", ""),
        data.get("doctor_phone", ""),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    
    booking_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    
    print(f"✅ Booking #{booking_id} saved to database")
    return booking_id




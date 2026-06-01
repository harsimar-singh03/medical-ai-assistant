import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def send_booking_email(patient_name, patient_email, doctor_name, clinic_name, 
                       address, day, time, fee, doctor_phone, booking_id):
    """
    Send booking confirmation email to patient.
    Falls back to mock if email credentials not configured.
    """
    
    sender_email = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    
    if not sender_email or not app_password:
        # Mock mode
        print(f"\n📧 [MOCK EMAIL] To: {patient_email}")
        print(f"   Subject: Appointment Confirmed with {doctor_name}")
        print(f"   Booking ID: #{booking_id}")
        return True
    
    # Create email
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = patient_email
    msg["Subject"] = f"✅ Appointment Confirmed — {doctor_name}"
    
    # Email body
    body = f"""
Hi {patient_name},

Your appointment has been confirmed!

📋 BOOKING DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━
Booking ID: #{booking_id}
Doctor: {doctor_name}
Clinic: {clinic_name}
Address: {address}
Date: {day.capitalize()}
Time: {time.upper()}
Fee: ₹{fee}
Doctor's Phone: {doctor_phone}
━━━━━━━━━━━━━━━━━━━━━━━━

📍 Please arrive 10 minutes before your appointment time.
📞 Need to reschedule? Call the clinic directly.

Take care! 🩺

— Medical AI Assistant
"""
    
    msg.attach(MIMEText(body, "plain"))
    
    try:
        # Connect to Gmail SMTP
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, patient_email, msg.as_string())
        server.quit()
        
        print(f"✅ Email sent to {patient_email}")
        return True
        
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False
import os
import requests
import tempfile
import fitz  # PyMuPDF
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# 🔹 Twilio credentials (set these in Render → Environment Variables)
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")

# 🔹 Hugging Face API endpoint
HF_API = "https://your-hf-endpoint.hf.space/predict"  # <-- replace with yours

def extract_text(pdf_path):
    """Extract text from PDF using PyMuPDF"""
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text.strip()

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.values.get("Body", "").lower().strip()
    media_url = request.values.get("MediaUrl0", "")
    media_type = request.values.get("MediaContentType0", "")

    resp = MessagingResponse()
    msg = resp.message()

    # 🔹 Check if user asked for doc verify AND uploaded a PDF
    if "doc verify" in incoming_msg and "application/pdf" in media_type:
        try:
            # Download PDF from Twilio's temporary URL
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            r = requests.get(media_url, auth=(TWILIO_SID, TWILIO_AUTH))
            tmp.write(r.content)
            tmp.close()

            # Extract text from PDF
            extracted_text = extract_text(tmp.name)

            if not extracted_text:
                msg.body("❌ Could not read any text from the document.")
                return str(resp)

            # Send text to Hugging Face API
            hf_resp = requests.post(HF_API, json={"text": extracted_text})
            prediction = hf_resp.json()

            msg.body(f"📄 Verification result:\n{prediction}")

        except Exception as e:
            msg.body(f"❌ Error processing document: {str(e)}")
    else:
        msg.body("⚠️ Please send a PDF with 'Doc verify' in the message.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

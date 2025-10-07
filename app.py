import os
import requests
import tempfile
import fitz
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Twilio credentials (set these in Render as environment variables)
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")

HF_API = "https://your-hf-endpoint.hf.space/predict"

def extract_text(pdf_path):
    txt = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            txt += page.get_text()
    return txt

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.values.get("Body", "").lower()
    media_url = request.values.get("MediaUrl0", "")

    resp = MessagingResponse()
    msg = resp.message()

    if "doc verify" in incoming_msg and media_url.endswith(".pdf"):
        try:
            # ✅ Download PDF with Twilio auth
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            r = requests.get(media_url, auth=(TWILIO_SID, TWILIO_AUTH))
            tmp.write(r.content)
            tmp.close()

            # ✅ Extract text
            text = extract_text(tmp.name)

            # ✅ Send to Hugging Face API
            hf_resp = requests.post(HF_API, json={"text": text})
            prediction = hf_resp.json()

            msg.body(f"📄 Verification result:\n{prediction}")

        except Exception as e:
            msg.body(f"❌ Error processing document: {str(e)}")

    else:
        msg.body("Please send a PDF with 'Doc verify'.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

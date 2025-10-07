from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import requests
import fitz  # PyMuPDF
import tempfile
import os

app = Flask(__name__)

HF_API = "https://st-thomas-of-aquinas-document-verification.hf.space/predict"

def extract_text_from_pdf(file_path):
    text = ""
    with fitz.open(file_path) as pdf:
        for page in pdf:
            text += page.get_text()
    return text

@app.route("/whatsapp", methods=["POST"])
def whatsapp_bot():
    incoming_msg = request.form.get("Body", "").strip().lower()
    media_url = request.form.get("MediaUrl0")  # WhatsApp attachment
    resp = MessagingResponse()
    msg = resp.message()

    if "doc verify" in incoming_msg and media_url:
        try:
            # Download PDF
            pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf_content = requests.get(media_url).content
            pdf_file.write(pdf_content)
            pdf_file.close()

            # Extract text
            extracted_text = extract_text_from_pdf(pdf_file.name)

            # Send to HF API
            response = requests.post(HF_API, json={"text": extracted_text})
            result = response.json()

            msg.body(f"📄 Doc Verification Result:\n{result}")
            os.unlink(pdf_file.name)

        except Exception as e:
            msg.body(f"❌ Error processing document: {str(e)}")
    else:
        msg.body("Hi 👋 Send 'Doc verify' with a PDF to check the document.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

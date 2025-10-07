import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Replace with your Gradio Space API
HF_SPACE_API_URL = "https://st-thomas-of-aquinas-document-verification.hf.space/predict"

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    num_media = int(request.values.get("NumMedia", 0))
    resp = MessagingResponse()
    reply = resp.message()

    if incoming_msg.lower().startswith("doc verify") and num_media > 0:
        media_url = request.values.get("MediaUrl0")
        media_type = request.values.get("MediaContentType0")

        if media_type == "application/pdf":
            try:
                # Download PDF
                pdf_data = requests.get(media_url).content

                # ⚠️ You'll need to extract text from PDF before sending it
                from PyPDF2 import PdfReader
                with open("/tmp/temp.pdf", "wb") as f:
                    f.write(pdf_data)
                reader = PdfReader("/tmp/temp.pdf")
                text = " ".join([page.extract_text() or "" for page in reader.pages])

                # ✅ Call your Hugging Face Space (GET with params)
                params = {"text": text}
                r = requests.get(HF_SPACE_API_URL, params=params)

                if r.status_code == 200:
                    try:
                        result = r.json()
                        reply.body(f"✅ Prediction: {result}")
                    except Exception:
                        reply.body(f"⚠️ Got non-JSON: {r.text[:200]}")
                else:
                    reply.body(f"❌ API error {r.status_code}: {r.text[:200]}")

            except Exception as e:
                reply.body(f"❌ Error processing document: {e}")
        else:
            reply.body("⚠️ Please send a PDF with 'Doc verify'")
    else:
        reply.body("Send 'Doc verify' followed by a PDF document.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from PyPDF2 import PdfReader

app = Flask(__name__)

# Hugging Face Space API
HF_SPACE_API_URL = "https://st-thomas-of-aquinas-document-verification.hf.space/predict"

# Twilio credentials (set as environment variables in Render/Docker)
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")

twilio_client = Client(TWILIO_SID, TWILIO_AUTH)

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    num_media = int(request.values.get("NumMedia", 0))
    from_number = request.values.get("From")
    to_number = request.values.get("To")

    resp = MessagingResponse()
    reply = resp.message()

    if incoming_msg.lower().startswith("doc verify") and num_media > 0:
        media_url = request.values.get("MediaUrl0")
        media_type = request.values.get("MediaContentType0")

        if media_type == "application/pdf":
            # ✅ First response → tell user it's processing
            reply.body("⏳ Processing your document...")

            try:
                # Download PDF
                pdf_data = requests.get(media_url).content
                with open("/tmp/temp.pdf", "wb") as f:
                    f.write(pdf_data)

                # Extract text
                reader = PdfReader("/tmp/temp.pdf")
                text = " ".join([page.extract_text() or "" for page in reader.pages])

                # Call Hugging Face model (GET with params)
                params = {"text": text}
                r = requests.get(HF_SPACE_API_URL, params=params)

                if r.status_code == 200:
                    try:
                        result = r.json()
                        label = result.get("predicted_label", "Unknown")
                        probs = result.get("class_probabilities", {})
                        confidence = probs.get(label, 0) * 100

                        prediction_text = (
                            f"✅ Prediction Result:\n"
                            f"Label: {label}\n"
                            f"Confidence: {confidence:.2f}%"
                        )
                    except Exception:
                        prediction_text = f"⚠️ Got non-JSON: {r.text[:200]}"
                else:
                    prediction_text = f"❌ API error {r.status_code}: {r.text[:200]}"

                # ✅ Send the final result as a new message
                twilio_client.messages.create(
                    body=prediction_text,
                    from_=to_number,
                    to=from_number
                )

            except Exception as e:
                twilio_client.messages.create(
                    body=f"❌ Error processing document: {e}",
                    from_=to_number,
                    to=from_number
                )
        else:
            reply.body("⚠️ Please send a PDF with 'Doc verify'")
    else:
        reply.body("Send 'Doc verify' followed by a PDF document.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

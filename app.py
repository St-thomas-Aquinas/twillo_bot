import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from PyPDF2 import PdfReader

app = Flask(__name__)

# ✅ Hugging Face Space API endpoint
HF_SPACE_API_URL = "https://st-thomas-of-aquinas-document-verification.hf.space/predict"

# ✅ Twilio credentials (from environment)
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
            # ✅ Immediate response
            reply.body("⏳ Processing your document...")

            try:
                # ✅ Download PDF with Twilio auth
                pdf_data = requests.get(
                    media_url,
                    auth=(TWILIO_SID, TWILIO_AUTH)
                ).content

                # ✅ Save PDF temporarily
                with open("/tmp/temp.pdf", "wb") as f:
                    f.write(pdf_data)

                # ✅ Extract text
                reader = PdfReader("/tmp/temp.pdf")
                text = " ".join([page.extract_text() or "" for page in reader.pages]).strip()

                if not text:
                    twilio_client.messages.create(
                        body="⚠️ Couldn’t extract any text from the PDF.",
                        from_=to_number,
                        to=from_number
                    )
                    return str(resp)

                # ✅ Call Hugging Face API
                r = requests.get(HF_SPACE_API_URL, params={"text": text})

                if r.status_code == 200:
                    try:
                        result = r.json()

                        if isinstance(result, dict) and "class_probabilities" in result:
                            # pick highest
                            probs = result.get("class_probabilities", {})
                            if probs:
                                label, score = max(probs.items(), key=lambda x: x[1])
                                prediction_text = f"The Author of this memo is:\nLabel: {label}"
                            else:
                                prediction_text = f"✅ Prediction: {result.get('predicted_label', 'Unknown')}"
                        else:
                            prediction_text = f"✅ Prediction:\n{str(result)}"

                    except Exception:
                        prediction_text = f"✅ Prediction:\n{r.text.strip()[:500]}"
                else:
                    prediction_text = f"❌ API error {r.status_code}: {r.text[:200]}"

                # ✅ Send follow-up message with result
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
        reply.body("👋 Send 'Doc verify' followed by a PDF document.")

    return str(resp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

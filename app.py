import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text

app = Flask(__name__)

# Hugging Face Space API
HF_SPACE_API_URL = "https://st-thomas-of-aquinas-document-verification.hf.space/predict"

# Twilio credentials from environment variables
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
            reply.body("⏳ Processing your document...")  # instant response

            try:
                # ✅ Download PDF
                pdf_response = requests.get(media_url, stream=True)
                with open("/tmp/temp.pdf", "wb") as f:
                    f.write(pdf_response.content)
                print("💾 Saved incoming PDF to /tmp/temp.pdf")

                # ✅ Try parsing from saved file
                text = ""
                try:
                    reader = PdfReader("/tmp/temp.pdf")
                    text = " ".join([page.extract_text() or "" for page in reader.pages])
                    print("✅ Extracted text with PyPDF2")
                except Exception as e1:
                    print(f"⚠️ PyPDF2 failed: {e1}, trying pdfminer...")
                    try:
                        text = extract_text("/tmp/temp.pdf")
                        print("✅ Extracted text with pdfminer")
                    except Exception as e2:
                        print(f"❌ Both PyPDF2 and pdfminer failed: {e2}")
                        raise Exception("Could not extract text from PDF")

                if not text.strip():
                    twilio_client.messages.create(
                        body="⚠️ Couldn’t extract any text from this PDF.",
                        from_=to_number,
                        to=from_number
                    )
                    return str(resp)

                # ✅ Send to Hugging Face API
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
                    except Exception as e:
                        prediction_text = f"⚠️ Got non-JSON response: {r.text[:200]} | Error: {e}"
                else:
                    prediction_text = f"❌ API error {r.status_code}: {r.text[:200]}"

                # ✅ Send prediction back to user
                twilio_client.messages.create(
                    body=prediction_text,
                    from_=to_number,
                    to=from_number
                )

            except Exception as e:
                error_message = f"❌ Error processing document: {e}"
                print(error_message)
                twilio_client.messages.create(
                    body=error_message,
                    from_=to_number,
                    to=from_number
                )
        else:
            reply.body("⚠️ Please send a PDF with 'Doc verify'")
    else:
        reply.body("Send 'Doc verify' followed by a PDF document.")

    return str(resp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

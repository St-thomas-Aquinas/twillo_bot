import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from PyPDF2 import PdfReader

app = Flask(__name__)

# ✅ Hugging Face Space API endpoint
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
                reply.body("⏳ Processing your document...")

                # ✅ Download PDF from Twilio (with authentication)
                pdf_data = requests.get(
                    media_url,
                    auth=(
                        os.environ.get("TWILIO_ACCOUNT_SID"),
                        os.environ.get("TWILIO_AUTH_TOKEN")
                    )
                ).content

                # ✅ Save PDF temporarily
                with open("/tmp/temp.pdf", "wb") as f:
                    f.write(pdf_data)

                # ✅ Extract text
                reader = PdfReader("/tmp/temp.pdf")
                text = " ".join([page.extract_text() or "" for page in reader.pages]).strip()

                if not text:
                    reply.body("⚠️ Couldn’t extract any text from the PDF.")
                    return str(resp)

                # ✅ Call Hugging Face API
                r = requests.get(HF_SPACE_API_URL, params={"text": text})

                if r.status_code == 200:
                    try:
                        result = r.json()

                        # If it's a classification list with labels & scores
                        if isinstance(result, list) and all("label" in x and "score" in x for x in result):
                            top = max(result, key=lambda x: x["score"])
                            reply.body(f"✅ Highest Prediction:\nLabel: {top['label']}\nScore: {top['score']:.4f}")

                        # If it's a dict with a prediction
                        elif isinstance(result, dict):
                            prediction = result.get("prediction", str(result))
                            reply.body(f"✅ Prediction:\n{prediction}")

                        else:
                            # Fallback
                            reply.body(f"✅ Prediction:\n{str(result)}")

                    except Exception:
                        # If not JSON, just send raw text
                        reply.body(f"✅ Prediction:\n{r.text.strip()[:500]}")
                else:
                    reply.body(f"❌ API error {r.status_code}: {r.text[:200]}")

            except Exception as e:
                reply.body(f"❌ Error processing document: {e}")
        else:
            reply.body("⚠️ Please send a PDF with 'Doc verify'")
    else:
        reply.body("👋 Send 'Doc verify' followed by a PDF document.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

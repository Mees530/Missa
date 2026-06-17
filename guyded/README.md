# Guyded — WhatsApp Webhook

A minimal FastAPI service that connects to the Meta WhatsApp Cloud API. It verifies the webhook handshake and echoes every inbound text message back to the sender.

## Project structure

```
guyded/
├── main.py           # FastAPI app and webhook logic
├── requirements.txt
├── .env.example      # Copy to .env and fill in your values
└── README.md
```

## Prerequisites

- Python 3.11+
- A [Meta Developer](https://developers.facebook.com/) account with a WhatsApp Business app
- [ngrok](https://ngrok.com/) for local testing

## Setup

### 1. Clone and install

```bash
cd guyded
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | Where to find it |
|---|---|
| `WHATSAPP_TOKEN` | Meta Developer Console → App → WhatsApp → API Setup → Temporary / permanent token |
| `PHONE_NUMBER_ID` | Same page — the numeric Phone Number ID |
| `VERIFY_TOKEN` | Any string you choose; you will enter it again in the Meta console |

### 3. Run the server

```bash
uvicorn main:app --reload --port 8000
```

### 4. Expose locally with ngrok

Install ngrok from <https://ngrok.com/download>, then:

```bash
ngrok http 8000
```

ngrok prints a public HTTPS URL such as `https://abc123.ngrok-free.app`. Copy it — you will use it in the next step.

### 5. Register the webhook in Meta Developer Console

1. Go to your app → **WhatsApp** → **Configuration**.
2. Under **Webhook**, click **Edit**.
3. Set **Callback URL** to `https://<your-ngrok-subdomain>.ngrok-free.app/webhook`.
4. Set **Verify token** to the same value you put in `VERIFY_TOKEN`.
5. Click **Verify and save** — Meta sends a GET request; the server returns the challenge.
6. Subscribe to the **messages** field.

### 6. Send a test message

Send any WhatsApp text message to your test number. The server logs the payload and the Cloud API echoes the message back to you.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/webhook` | Webhook verification handshake required by Meta |
| `POST` | `/webhook` | Receives inbound messages and echoes them |

## Notes

- ngrok free tier assigns a new URL on every restart — re-register the webhook each time.
- The permanent token required for production lives under **System Users** in the Meta Business Manager; the temporary token shown in API Setup expires after 24 hours.
- This project intentionally has no database. Persistence can be added later.

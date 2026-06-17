import os
import httpx
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

WHATSAPP_API_URL = "https://graph.facebook.com/v19.0"

app = FastAPI(title="Guyded WhatsApp Webhook")


@app.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return hub_challenge
    raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()

    entry = body.get("entry", [])
    for e in entry:
        for change in e.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            for message in messages:
                if message.get("type") == "text":
                    from_number = message["from"]
                    text = message["text"]["body"]
                    await send_message(from_number, text)

    return {"status": "ok"}


async def send_message(to: str, text: str) -> None:
    url = f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()

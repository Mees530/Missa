import os
from contextlib import asynccontextmanager

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

import database
from prompts import SYSTEM_PROMPT

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-6"

_anthropic_client: anthropic.AsyncAnthropic | None = None


def _get_anthropic() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_pool()
    yield
    await database.close_pool()


app = FastAPI(title="Guyded WhatsApp Webhook", lifespan=lifespan)


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

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                if message.get("type") == "text":
                    await handle_inbound(
                        wa_id=message["from"],
                        text=message["text"]["body"],
                    )

    return {"status": "ok"}


async def handle_inbound(wa_id: str, text: str) -> None:
    user_id = await database.upsert_user(wa_id)
    await database.insert_message(user_id, "inbound", text)

    history = await database.get_recent_messages(user_id)

    # Build Anthropic messages list; merge consecutive same-role turns so the
    # API's strict alternation requirement is always satisfied.
    api_messages: list[dict] = []
    for entry in history:
        role = "user" if entry["direction"] == "inbound" else "assistant"
        if api_messages and api_messages[-1]["role"] == role:
            api_messages[-1]["content"] += "\n" + entry["body"]
        else:
            api_messages.append({"role": role, "content": entry["body"]})

    response = await _get_anthropic().messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=api_messages,
    )

    ai_draft = response.content[0].text
    await database.insert_handler_queue(user_id, ai_draft)

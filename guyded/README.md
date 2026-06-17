# Guyded — WhatsApp Webhook

A FastAPI service that receives WhatsApp messages via the Meta Cloud API, persists them in Supabase (Postgres), and uses the Anthropic API to draft a reply. A Streamlit console lets you review, edit, approve, or reject every draft before anything is sent.

## Project structure

```
guyded/
├── main.py                # FastAPI webhook — inbound pipeline
├── console.py             # Streamlit review console
├── database.py            # asyncpg pool + DB helpers (used by main.py)
├── prompts.py             # Guyded system prompt
├── migrations/
│   └── 001_initial.sql    # Run once in Supabase to create the schema
├── requirements.txt
├── .env.example
└── README.md
```

## Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com/) project (free tier is fine)
- An [Anthropic](https://console.anthropic.com/) API key
- A [Meta Developer](https://developers.facebook.com/) account with a WhatsApp Business app
- [ngrok](https://ngrok.com/) for local testing

## Setup

### 1. Create the Supabase schema

1. Open your Supabase project → **SQL Editor**.
2. Paste the contents of `migrations/001_initial.sql` and click **Run**.

This creates three tables: `users`, `messages`, and `handler_queue`.

### 2. Clone and install

```bash
cd guyded
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | Where to find it |
|---|---|
| `WHATSAPP_TOKEN` | Meta Developer Console → App → WhatsApp → API Setup → token |
| `PHONE_NUMBER_ID` | Same page — the numeric Phone Number ID |
| `VERIFY_TOKEN` | Any string you choose; re-enter it in the Meta console |
| `DATABASE_URL` | Supabase → **Project Settings** → **Database** → **Connection string** → URI (use the direct connection on port 5432, not the pooler) |
| `ANTHROPIC_API_KEY` | Anthropic Console → API Keys |

`DATABASE_URL` format:
```
postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

### 4. Run the webhook server

```bash
uvicorn main:app --reload --port 8000
```

### 4b. Run the review console (separate terminal)

```bash
streamlit run console.py
```

The console opens at `http://localhost:8501`. It auto-refreshes every 30 seconds and shows every `pending` draft alongside the full conversation thread.

### 5. Expose locally with ngrok

Install ngrok from <https://ngrok.com/download>, then:

```bash
ngrok http 8000
```

ngrok prints a public HTTPS URL such as `https://abc123.ngrok-free.app`. Copy it.

### 6. Register the webhook in Meta Developer Console

1. Go to your app → **WhatsApp** → **Configuration**.
2. Under **Webhook**, click **Edit**.
3. Set **Callback URL** to `https://<your-ngrok-subdomain>.ngrok-free.app/webhook`.
4. Set **Verify token** to the value you put in `VERIFY_TOKEN`.
5. Click **Verify and save** — Meta sends a GET; the server returns the challenge.
6. Subscribe to the **messages** field.

### 7. Send a test message

Send any WhatsApp text to your test number. In your Supabase table editor you should see:

- A new row in `users`
- The inbound message in `messages` with `direction = 'inbound'`
- An AI draft in `handler_queue` with `status = 'pending'`

Nothing is sent back to the user at this stage.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/webhook` | Webhook verification handshake required by Meta |
| `POST` | `/webhook` | Receives inbound messages, stores them, generates an AI draft |

## Inbound message pipeline

```
POST /webhook
  └── upsert user (wa_id)
  └── insert message (direction='inbound')
  └── fetch last 20 messages for context
  └── call Anthropic claude-sonnet-4-6 with system prompt + history
  └── insert handler_queue row (status='pending', ai_draft=<response>)
```

The `handler_queue.status` lifecycle:

```
pending  →  sent      (Approve & Send in console)
         →  rejected  (Reject in console)
```

## Console (`console.py`)

```
streamlit run console.py
```

For each pending draft the console shows:

1. **Conversation thread** — last 20 messages rendered as a chat (inbound = user bubble, outbound = assistant bubble).
2. **Editable text area** — pre-filled with the AI draft; edit freely before acting.
3. **Approve & Send** — calls the WhatsApp Cloud API with the (optionally edited) text, marks the queue row `sent`, and inserts an `outbound` row in `messages`.
4. **Reject** — marks the row `rejected`; nothing is sent.

The page auto-refreshes every 30 s so new drafts appear without manual reload.

## Notes

- ngrok free tier assigns a new URL on every restart — re-register the webhook each time.
- Use the **direct** Supabase connection string (port 5432). The transaction-mode pooler (port 6543) breaks asyncpg's prepared-statement cache.
- The permanent WhatsApp token lives under **System Users** in Meta Business Manager; the temporary API Setup token expires after 24 hours.

import os
from contextlib import contextmanager
from typing import Generator

import httpx
import psycopg2
import psycopg2.extras
import streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_API_URL = "https://graph.facebook.com/v19.0"


# ── DB helpers ────────────────────────────────────────────────────────────────

@contextmanager
def _db() -> Generator[psycopg2.extensions.connection, None, None]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_pending() -> list[dict]:
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT hq.id,
                       hq.user_id,
                       hq.ai_draft,
                       hq.created_at,
                       u.wa_id
                FROM   handler_queue hq
                JOIN   users u ON u.id = hq.user_id
                WHERE  hq.status = 'pending'
                ORDER  BY hq.created_at ASC
            """)
            return [dict(r) for r in cur.fetchall()]


def fetch_thread(user_id: int) -> list[dict]:
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT direction, body, created_at
                FROM   messages
                WHERE  user_id = %s
                ORDER  BY created_at DESC
                LIMIT  20
            """, (user_id,))
            # Reverse so the thread reads top-to-bottom chronologically.
            return list(reversed([dict(r) for r in cur.fetchall()]))


def _approve_in_db(queue_id: int, user_id: int, final_text: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE handler_queue SET status = 'sent', final_text = %s WHERE id = %s",
                (final_text, queue_id),
            )
            cur.execute(
                "INSERT INTO messages (user_id, direction, body) VALUES (%s, 'outbound', %s)",
                (user_id, final_text),
            )


def _reject_in_db(queue_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE handler_queue SET status = 'rejected' WHERE id = %s",
                (queue_id,),
            )


# ── WhatsApp ──────────────────────────────────────────────────────────────────

def _send_whatsapp(wa_id: str, text: str) -> None:
    resp = httpx.post(
        f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages",
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
        json={
            "messaging_product": "whatsapp",
            "to": wa_id,
            "type": "text",
            "text": {"body": text},
        },
        timeout=10,
    )
    resp.raise_for_status()


# ── Actions ───────────────────────────────────────────────────────────────────

def do_approve(queue_id: int, user_id: int, wa_id: str, final_text: str) -> None:
    _send_whatsapp(wa_id, final_text)
    _approve_in_db(queue_id, user_id, final_text)


def do_reject(queue_id: int) -> None:
    _reject_in_db(queue_id)


# ── Page ──────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Guyded Console", layout="wide")

# Refresh the page every 30 s so new drafts appear automatically.
st_autorefresh(interval=30_000, key="queue_autorefresh")

st.title("Guyded — Draft Queue")

pending = fetch_pending()

if not pending:
    st.success("Queue is empty — nothing pending.")
    st.stop()

count = len(pending)
st.caption(f"{count} pending draft{'s' if count != 1 else ''}")

for item in pending:
    with st.container(border=True):
        # Header row
        st.markdown(
            f"**{item['wa_id']}** "
            f"<span style='color:grey; font-size:0.85em'>"
            f"{item['created_at'].strftime('%d %b %Y %H:%M')}"
            f"</span>",
            unsafe_allow_html=True,
        )

        # Conversation thread
        thread = fetch_thread(item["user_id"])
        with st.expander("Conversation thread", expanded=True):
            if not thread:
                st.caption("No messages recorded yet.")
            for msg in thread:
                role = "user" if msg["direction"] == "inbound" else "assistant"
                with st.chat_message(role):
                    st.write(msg["body"])

        # Editable draft — session_state retains edits across reruns
        draft_key = f"draft_{item['id']}"
        st.text_area(
            "AI draft — edit before sending",
            value=item["ai_draft"],
            key=draft_key,
            height=130,
        )

        col_approve, col_reject, _ = st.columns([1, 1, 4])

        with col_approve:
            if st.button(
                "Approve & Send",
                key=f"approve_{item['id']}",
                type="primary",
                use_container_width=True,
            ):
                try:
                    do_approve(
                        queue_id=item["id"],
                        user_id=item["user_id"],
                        wa_id=item["wa_id"],
                        final_text=st.session_state[draft_key],
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Send failed: {exc}")

        with col_reject:
            if st.button(
                "Reject",
                key=f"reject_{item['id']}",
                use_container_width=True,
            ):
                try:
                    do_reject(item["id"])
                    st.rerun()
                except Exception as exc:
                    st.error(f"Reject failed: {exc}")

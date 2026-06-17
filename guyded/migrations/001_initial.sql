-- Run this once in your Supabase SQL editor (or psql) before starting the app.

CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL PRIMARY KEY,
    wa_id       TEXT        UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    direction   TEXT        NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    body        TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Speeds up the "last 20 messages per user" query.
CREATE INDEX IF NOT EXISTS messages_user_id_created_at
    ON messages (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS handler_queue (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ai_draft    TEXT        NOT NULL,
    status      TEXT        NOT NULL DEFAULT 'pending',
    final_text  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS handler_queue_user_status
    ON handler_queue (user_id, status);

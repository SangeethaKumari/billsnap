"""
Discord Bot Gateway Service
----------------------------
Sits right behind the API Gateway (Kong/Envoy + WAF). Its only jobs:
  1. Verify the request actually came from Discord.
  2. Map Discord's snowflake IDs to an internal conversation UUID (Redis).
  3. Guard against duplicate/"zombie" events with a short-lived Redis lock.
  4. Push a clean, standardized payload onto the message queue (Kafka).
  5. Immediately ack Discord within the 3-second interaction window.

This service never talks to the LLM. That separation is the whole point:
if the agent is slow, this service is still fast, and Discord never times out.
"""

import json
import os
import time
import uuid

import redis
from fastapi import FastAPI, Header, HTTPException, Request
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from kafka import KafkaProducer

app = FastAPI()

redis_client = redis.Redis(
    host=os.environ["REDIS_HOST"],
    port=int(os.environ.get("REDIS_PORT", 6379)),
    decode_responses=True,
)

producer = KafkaProducer(
    bootstrap_servers=os.environ["KAFKA_BROKERS"].split(","),
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    # A slow producer should never become the bottleneck for ingress traffic.
    acks="all",
    retries=5,
    linger_ms=5,
)

DISCORD_PUBLIC_KEY = os.environ["DISCORD_PUBLIC_KEY"]
JOB_TOPIC = "sales-agent-jobs"
LOCK_TTL_SECONDS = 8  # covers the realistic time a user might double-click


def verify_discord_signature(signature: str, timestamp: str, body: bytes) -> bool:
    """Discord signs every webhook. Reject anything that doesn't check out
    at the edge, before it ever touches business logic."""
    try:
        verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
        return True
    except BadSignatureError:
        return False


def get_or_create_conversation_uuid(discord_thread_id: str) -> str:
    """Map Discord's snowflake to a stable internal UUID. This UUID -- not
    the snowflake -- is the identity used everywhere downstream (Redis keys,
    Kafka payloads, CRM idempotency keys)."""
    mapping_key = f"thread_map:{discord_thread_id}"
    existing = redis_client.get(mapping_key)
    if existing:
        return existing

    new_uuid = str(uuid.uuid4())
    # No expiry: this mapping needs to live as long as the conversation does.
    redis_client.set(mapping_key, new_uuid)
    return new_uuid


def acquire_dedup_lock(user_id: str, thread_id: str) -> bool:
    """Returns True if this is the first request in the window (lock
    acquired), False if a duplicate is already in flight and should be
    dropped. This is what stops the 'zombie message loop' race condition."""
    lock_key = f"lock:{user_id}:{thread_id}"
    # SET ... NX EX is atomic -- no race between check and set.
    acquired = redis_client.set(lock_key, "1", nx=True, ex=LOCK_TTL_SECONDS)
    return bool(acquired)


@app.post("/discord/interactions")
async def handle_interaction(
    request: Request,
    x_signature_ed25519: str = Header(...),
    x_signature_timestamp: str = Header(...),
):
    raw_body = await request.body()

    if not verify_discord_signature(x_signature_ed25519, x_signature_timestamp, raw_body):
        raise HTTPException(status_code=401, detail="invalid request signature")

    payload = json.loads(raw_body)

    # PING for Discord's endpoint verification handshake.
    if payload.get("type") == 1:
        return {"type": 1}

    discord_user_id = payload["member"]["user"]["id"]
    discord_thread_id = payload["channel_id"]
    interaction_token = payload["token"]
    user_text = _extract_user_text(payload)

    if not acquire_dedup_lock(discord_user_id, discord_thread_id):
        # A duplicate arrived while the previous one is still being handled.
        # Silently drop it at the edge -- this is the fix for the "zombie"
        # loop, not a downstream retry policy.
        return {
            "type": 4,
            "data": {"content": "Still working on your last message \u2013 one sec!"},
        }

    conversation_id = get_or_create_conversation_uuid(discord_thread_id)

    job = {
        "conversation_id": conversation_id,
        "discord_user_id": discord_user_id,
        "discord_thread_id": discord_thread_id,
        "interaction_token": interaction_token,
        "user_text": user_text,
        "submitted_at": time.time(),
    }
    producer.send(JOB_TOPIC, value=job)

    # Type 5 = deferred channel message. Discord shows "Thinking..." and the
    # 3-second clock stops. The real reply comes later via PATCH to
    # /webhooks/{application_id}/{interaction_token}/messages/@original
    return {"type": 5}


def _extract_user_text(payload: dict) -> str:
    data = payload.get("data", {})
    if "options" in data:
        return " ".join(str(o.get("value", "")) for o in data["options"])
    return data.get("custom_id", "")
"""
Egress Delivery Worker
-----------------------
The Agent Core never calls Discord's API directly. It drops the finished
reply onto a delivery queue, and this dedicated worker handles the actual
outbound call -- with retries -- so a Discord-side outage (502s, latency
spikes) can never hang the agent's execution thread.
"""

import json
import os
import time

import requests
from kafka import KafkaConsumer

DISCORD_API_BASE = "https://discord.com/api/v10"
APPLICATION_ID = os.environ["DISCORD_APPLICATION_ID"]
MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 1.0

consumer = KafkaConsumer(
    "discord-egress-delivery",
    bootstrap_servers=os.environ["KAFKA_BROKERS"].split(","),
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    group_id="egress-delivery-workers",
)


def deliver(job: dict) -> None:
    url = (
        f"{DISCORD_API_BASE}/webhooks/{APPLICATION_ID}"
        f"/{job['interaction_token']}/messages/@original"
    )
    body = _format_payload(job["final_text"])

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.patch(url, json=body, timeout=5)
            if response.status_code < 500:
                # Any non-5xx is a definitive outcome (success, or a
                # permanent client error like an expired token) -- stop.
                response.raise_for_status()
                return
        except requests.RequestException:
            pass

        backoff = BASE_BACKOFF_SECONDS * (2 ** attempt)
        time.sleep(backoff)

    print(f"[EGRESS FAILED] conversation={job['conversation_id']} after {MAX_RETRIES} attempts")


def _format_payload(text: str) -> dict:
    if len(text) <= 2000:
        return {"content": text}

    # Discord's 2000-char limit: break cleanly on the nearest paragraph
    # boundary rather than mid-sentence.
    cutoff = text.rfind("\n\n", 0, 2000)
    cutoff = cutoff if cutoff > 0 else 2000
    return {
        "content": text[:cutoff],
        "attachments": [{"filename": "full_response.md", "content": text}],
    }


def run_forever() -> None:
    for message in consumer:
        deliver(message.value)


if __name__ == "__main__":
    run_forever()
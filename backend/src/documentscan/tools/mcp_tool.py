"""
MCP / CRM Tool Layer
---------------------
These functions are what get registered as `tools=[...]` on the ADK agent.
Two production concerns live here, both learned the hard way in distributed
systems: schema drift and duplicate writes.

  * Schema Validation (Pydantic): if the CRM's response doesn't match what
    we expect, fail loudly and immediately -- never let a malformed payload
    quietly corrupt the agent's understanding of what happened.
  * Idempotency: every state-changing call carries a key derived from the
    conversation UUID + a stable action fingerprint, so retries (from a
    crashed pod re-reading a Kafka offset, for example) can never create a
    duplicate opportunity or double-update a deal stage.
"""

import hashlib
import json
import os

import redis
from pydantic import BaseModel, ValidationError
import requests

redis_client = redis.Redis(
    host=os.environ["REDIS_HOST"],
    port=int(os.environ.get("REDIS_PORT", 6379)),
    decode_responses=True,
)

CRM_BASE_URL = os.environ["CRM_MCP_ENDPOINT"]
IDEMPOTENCY_TTL_SECONDS = 60 * 60 * 24  # 24h is plenty for a single sales thread


class LeadRecord(BaseModel):
    lead_id: str
    company_name: str
    deal_stage: str
    owner_email: str


class DealStageUpdateResult(BaseModel):
    lead_id: str
    new_stage: str
    updated_at: str


def _idempotency_key(conversation_id: str, action: str, payload: dict) -> str:
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()[:16]
    return f"idem:{conversation_id}:{action}:{fingerprint}"


def search_lead(company_name: str) -> dict:
    """MCP tool: look up a lead by company name."""
    response = requests.get(f"{CRM_BASE_URL}/search_lead", params={"company_name": company_name})
    response.raise_for_status()

    try:
        record = LeadRecord.model_validate(response.json())
    except ValidationError as exc:
        # Fail fast at the boundary instead of letting a bad shape flow
        # into the agent's reasoning as if it were valid.
        raise RuntimeError(f"CRM schema drift detected in search_lead: {exc}") from exc

    return record.model_dump()


def update_deal_stage(conversation_id: str, lead_id: str, new_stage: str) -> dict:
    """MCP tool: write a deal-stage change. Idempotent by construction --
    calling this twice with the same arguments for the same conversation
    performs the write exactly once."""
    payload = {"lead_id": lead_id, "new_stage": new_stage}
    idem_key = _idempotency_key(conversation_id, "update_deal_stage", payload)

    cached_result = redis_client.get(idem_key)
    if cached_result:
        return json.loads(cached_result)

    try:
        response = requests.post(
            f"{CRM_BASE_URL}/update_deal_stage",
            json=payload,
            headers={"Idempotency-Key": idem_key},
        )
        response.raise_for_status()
        result = DealStageUpdateResult.model_validate(response.json()).model_dump()
    except (requests.HTTPError, ValidationError) as exc:
        _send_to_dead_letter_queue(conversation_id, payload, str(exc))
        raise

    redis_client.set(idem_key, json.dumps(result), ex=IDEMPOTENCY_TTL_SECONDS)
    return result


def _send_to_dead_letter_queue(conversation_id: str, payload: dict, error: str) -> None:
    """Permanent CRM failures (e.g. a revoked permission) shouldn't vanish
    silently -- they land in a DLQ and page the platform team."""
    from kafka import KafkaProducer  # local import keeps this a clear side-effect

    producer = KafkaProducer(
        bootstrap_servers=os.environ["KAFKA_BROKERS"].split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    producer.send(
        "crm-updates-dlq",
        value={"conversation_id": conversation_id, "payload": payload, "error": error},
    )
    print(f"[DLQ] conversation={conversation_id} error={error}")
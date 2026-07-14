"""
Agentic Core Worker (Google ADK)
---------------------------------
Runs as an independent consumer (a Kubernetes pod / deployment), completely
decoupled from the Discord-facing ingress path. It:

  1. Pulls one job at a time from Kafka.
  2. Hydrates short-term memory from Redis, with a token-budget guard so
     long B2B threads don't blow out the model's context window.
  3. Runs the ADK agent, which can call the CRM through an MCP-style tool.
  4. Applies a max-loop guard so a confused agent can't spin forever.
  5. Hands the final text off to the egress delivery queue (never calls
     Discord's API directly -- see egress_worker.py for why).
"""

import json
import os
import time
import redis
from kafka import KafkaConsumer, KafkaProducer

from google.adk.agents import Agent
from google.adk.sessions.in_memory_session_service import InMemorySessionService  # swap for a persistent
                                                          # session backend in prod

from documentscan.tools.mcp_tool import search_lead, update_deal_stage

redis_client = redis.Redis(
    host=os.environ["REDIS_HOST"],
    port=int(os.environ.get("REDIS_PORT", 6379)),
    decode_responses=True,
)

consumer = KafkaConsumer(
    "sales-agent-jobs",
    bootstrap_servers=os.environ["KAFKA_BROKERS"].split(","),
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    group_id="agent-core-workers",   # multiple pods share the work
    enable_auto_commit=False,        # commit only after we've safely queued
                                      # the reply -- avoids losing a job if
                                      # the pod dies mid-turn
)

egress_producer = KafkaProducer(
    bootstrap_servers=os.environ["KAFKA_BROKERS"].split(","),
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)

MAX_AGENT_STEPS = 5
TOKEN_BUDGET_TRIGGER = 6000  # ~75% of a typical 8k-context sales prompt budget

sales_agent = Agent(
    name="sales_discovery_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a B2B sales assistant. Use search_lead to look up CRM "
        "context before answering pipeline questions, and update_deal_stage "
        "only when the user explicitly confirms a stage change."
    ),
    tools=[search_lead, update_deal_stage],
)

session_service = InMemorySessionService()


def hydrate_history(conversation_id: str) -> list[dict]:
    """Read recent turns from Redis. If the thread has grown past the
    token budget, collapse it to a summary instead of feeding raw history
    into the model -- this is the fix for context-window OOM crashes."""
    history_key = f"history:{conversation_id}"
    raw_turns = redis_client.lrange(history_key, 0, -1)
    turns = [json.loads(t) for t in raw_turns]

    approx_tokens = sum(len(t.get("text", "")) for t in turns) // 4
    if approx_tokens > TOKEN_BUDGET_TRIGGER:
        turns = _summarize_and_compress(conversation_id, turns)

    return turns


def _summarize_and_compress(conversation_id: str, turns: list[dict]) -> list[dict]:
    """Replace the oldest turns with a single dense summary, keep only the
    last few turns verbatim, and persist the compressed state back."""
    recent = turns[-4:]
    older_text = " ".join(t.get("text", "") for t in turns[:-4])

    summary_agent = Agent(
        name="history_summarizer",
        model="gemini-2.5-flash",
        instruction="Summarize this sales conversation into 3-4 dense sentences.",
    )
    summary = summary_agent.run_sync(older_text).text

    compressed = [{"role": "system", "text": f"[summary] {summary}"}] + recent
    history_key = f"history:{conversation_id}"
    redis_client.delete(history_key)
    for turn in compressed:
        redis_client.rpush(history_key, json.dumps(turn))

    return compressed


def append_turn(conversation_id: str, role: str, text: str) -> None:
    redis_client.rpush(f"history:{conversation_id}", json.dumps({"role": role, "text": text}))


def process_job(job: dict) -> None:
    conversation_id = job["conversation_id"]
    history = hydrate_history(conversation_id)
    append_turn(conversation_id, "user", job["user_text"])

    session = session_service.create_session_sync(
        app_name="sales_agent", user_id=job["discord_user_id"], state={"history": history}
    )

    step_count = 0
    final_text: str | None = None

    # Max-loop guard: if the agent can't converge on a final answer within
    # N steps, fail cleanly instead of burning tokens in a semantic deadlock.
    for event in sales_agent.run(session=session, message=job["user_text"]):
        step_count += 1
        if event.is_final_response():
            final_text = event.text
            break
        if step_count >= MAX_AGENT_STEPS:
            final_text = (
                "I hit a snag pulling that information together -- looping in "
                "a sales rep to help from here."
            )
            _alert_human_handoff(conversation_id, reason="max_loop_exceeded")
            break

    append_turn(conversation_id, "assistant", final_text)

    egress_producer.send(
        "discord-egress-delivery",
        value={
            "interaction_token": job["interaction_token"],
            "conversation_id": conversation_id,
            "final_text": final_text,
        },
    )


def _alert_human_handoff(conversation_id: str, reason: str) -> None:
    # In production this posts to PagerDuty/Slack; kept as a stub here so
    # the flow is visible without pulling in real credentials.
    print(f"[HANDOFF] conversation={conversation_id} reason={reason}")


def run_forever() -> None:
    for message in consumer:
        try:
            process_job(message.value)
            consumer.commit()
        except Exception as exc:  # noqa: BLE001 -- top-level worker guard
            print(f"[ERROR] job failed, will be retried by group: {exc}")
            time.sleep(1)


if __name__ == "__main__":
    run_forever()
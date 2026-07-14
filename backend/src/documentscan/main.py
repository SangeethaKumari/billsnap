import os
import uvicorn
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from google.adk import Runner  # noqa: E402
from google.adk.sessions.in_memory_session_service import InMemorySessionService  # noqa: E402
from documentscan.agent import root_agent  # noqa: E402
from .api.routes import query, ingest, evals  # noqa: E402

if not os.environ.get("GEMINI_API_KEY") and os.environ.get("GOOGLE_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.environ.get("GOOGLE_API_KEY")

if os.environ.get("PHOENIX_COLLECTOR_ENDPOINT") or os.environ.get("ENABLE_PHOENIX_TRACING") == "true":
    try:
        from phoenix.otel import register
        register(
            endpoint=os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces"),
            project_name=os.environ.get("PHOENIX_PROJECT_NAME", "documentscan"),
            protocol="http/protobuf",
            auto_instrument=True,
        )
    except Exception as e:
        print(f"Failed to initialize Arize Phoenix tracing framework: {e}")

app = FastAPI(title="Document Scan API", version="0.1.0")

session_service = InMemorySessionService()
app.state.runner = Runner(
    agent=root_agent,
    session_service=session_service,
    app_name="documentscan",
    auto_create_session=True
)

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

app.include_router(query.router,  prefix="/api/query",  tags=["Query"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["Ingestion"])
app.include_router(evals.router,  prefix="/api/evals",  tags=["Evaluation"])

@app.get("/health")
async def health(): return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

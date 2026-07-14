from typing import Any
def retrieve_documents(query: str) -> list[dict[str, Any]]: return [{"doc_id": "doc-001", "title": "Sample Document", "text": f"Result for: {query}", "metadata": {}, "score": 0.95}]

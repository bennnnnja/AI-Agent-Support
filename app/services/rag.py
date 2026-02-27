import httpx
from app.config import settings


def _get_token() -> str:
    with httpx.Client(timeout=10.0) as client:
        r = client.post(
            f"{settings.rag_api_url}/login",
            data={"username": settings.rag_username, "password": settings.rag_api_key},
        )
        r.raise_for_status()
        return r.json()["access_token"]


def search_knowledge(query: str) -> list[str]:
    token = _get_token()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    body = {
        "query": query,
        "mode": "mix",
        "only_need_context": False,
        "top_k": 5,
        "include_references": True,
        "stream": False,
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                f"{settings.rag_api_url}/query",
                json=body,
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        print(f"RAG request failed: {e}")
        return []

    response_text = data.get("response", "")
    if response_text:
        return [response_text]
    return []
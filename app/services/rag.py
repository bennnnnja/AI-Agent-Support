import logging

import httpx
from app.config import settings

logger = logging.getLogger(__name__)


def _get_token() -> str:
    with httpx.Client(timeout=10.0) as client:
        r = client.post(
            f"{settings.rag_api_url}/login",
            data={"username": settings.rag_username, "password": settings.rag_api_key},
        )
        r.raise_for_status()
        return r.json()["access_token"]


def search_knowledge(query: str) -> list[str]:
    try:
        token = _get_token()
    except Exception as e:
        logger.error(f"RAG login failed: {e}")
        return []

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    body = {
        "query": query,
        "mode": "hybrid",  # Changed from "mix" to "hybrid" for better relevance
        "only_need_context": False,
        "top_k": 10,  # Increased from 5 to 10 to get more results
        "include_references": True,
        "stream": False,
    }

    logger.warning(f"[RAG] Sending query: {query[:100]}")
    logger.debug(f"[RAG] Request body: mode={body['mode']}, top_k={body['top_k']}")

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{settings.rag_api_url}/query",
                json=body,
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
    except httpx.TimeoutException:
        logger.error(f"RAG request timed out (120s) for query: {query[:80]}")
        return []
    except Exception as e:
        logger.error(f"RAG request failed: {e}")
        return []

    response_text = data.get("response", "")
    if response_text:
        logger.info(f"RAG returned {len(response_text)} chars")
        return [response_text]
    logger.warning("RAG returned empty response")
    return []
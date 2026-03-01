import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# Cached token after successful login (cleared on 401 to retry login)
_rag_token: str | None = None


def _get_rag_token() -> str | None:
    """Login via POST /login (application/x-www-form-urlencoded), return Bearer token."""
    global _rag_token
    if not settings.rag_api_key:
        return None
    base = settings.rag_api_url.rstrip("/")
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"{base}/login",
                data={
                    "grant_type": "password",
                    "username": settings.rag_username or "user",
                    "password": settings.rag_api_key,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            # 200 can be plain string (token) or JSON with access_token
            text = response.text.strip()
            if not text:
                return None
            ct = response.headers.get("content-type", "")
            if "json" in ct:
                data = response.json()
                _rag_token = data.get("access_token") or data.get("token") or text
            else:
                _rag_token = text
            return _rag_token
    except Exception as e:
        logger.warning(f"[RAG] Login failed: {e}")
        _rag_token = None
        return None


def search_knowledge(query: str) -> list[str]:
    """
    Search knowledge base via LightRAG API: login (username+password) then POST /query.
    
    Args:
        query: User's question or search term
        
    Returns:
        List of relevant documentation snippets (or single answer from LightRAG)
    """
    global _rag_token
    if not query or not query.strip():
        logger.warning("[RAG] Empty query provided")
        return []

    base = settings.rag_api_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if settings.rag_api_key:
        token = _rag_token or _get_rag_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

    # LightRAG API: POST /query (mode: mix, optional top_k etc.)
    payload = {
        "query": query.strip(),
        "mode": "mix",
        "top_k": 5,
        "include_references": False,
    }

    try:
        logger.debug(f"[RAG] Searching: {query[:100]}...")
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{base}/query",
                json=payload,
                headers=headers,
            )
            if response.status_code == 401:
                _rag_token = None
                token = _get_rag_token()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    response = client.post(f"{base}/query", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        # LightRAG returns {"response": "..."} or similar; some APIs return "results" list
        if isinstance(data.get("results"), list) and data["results"]:
            results = [r if isinstance(r, str) else str(r) for r in data["results"]]
            logger.info(f"[RAG] Found {len(results)} results for query")
            return results
        if isinstance(data.get("response"), str) and data["response"].strip():
            logger.info("[RAG] Got single response from LightRAG")
            return [data["response"].strip()]
        # Fallback: any list of strings
        for key in ("chunks", "documents", "context"):
            if isinstance(data.get(key), list) and data[key]:
                out = [x if isinstance(x, str) else str(x) for x in data[key]]
                if out:
                    return out
        logger.debug("[RAG] No results in response")
        return []

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.error("[RAG] Authentication failed - invalid API key")
        else:
            logger.error(f"[RAG] HTTP error {e.response.status_code}: {e.response.text}")
        return []

    except httpx.TimeoutException:
        logger.error("[RAG] Request timeout (60s)")
        return []

    except Exception as e:
        logger.error(f"[RAG] Search failed: {e}")
        return []
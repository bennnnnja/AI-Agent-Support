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

    # LightRAG API: POST /query
    # Адаптируем payload под удачный пример из Swagger:
    # {
    #   "query": "...",
    #   "mode": "hybrid",
    #   "include_references": true,
    #   "response_type": "Multiple Paragraphs",
    #   "top_k": 10
    # }
    payload = {
        "query": query.strip(),
        "mode": "hybrid",
        "include_references": True,
        "response_type": "Multiple Paragraphs",
        "top_k": 10,
    }

    try:
        logger.debug(f"[RAG] Searching: {query[:100]}...")
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{base}/query", json=payload, headers=headers)
            if response.status_code == 401:
                _rag_token = None
                token = _get_rag_token()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    response = client.post(f"{base}/query", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        # LightRAG returns {"response": "..."} and optionally "results"/"references".
        # Некоторые версии сервера в no-context сценариях возвращают техническую фразу,
        # которую не стоит показывать пользователю как документацию.
        bad_markers = [
            "No relevant context found for the query",
            "no-context",
        ]

        results: list[str] = []

        # 1) Явный список результатов, если сервер его отдаёт
        if isinstance(data.get("results"), list) and data["results"]:
            results.extend(
                r if isinstance(r, str) else str(r) for r in data["results"]
            )

        # 2) Основной текст ответа
        resp_text = data.get("response")
        if isinstance(resp_text, str):
            text = resp_text.strip()
            if text and not any(marker in text for marker in bad_markers):
                results.append(text)
            else:
                logger.info("[RAG] Server response indicates no relevant context, skipping as RAG result")

        if results:
            logger.info(f"[RAG] Found {len(results)} results for query")
            return results

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
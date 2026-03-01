import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


def search_knowledge(query: str) -> list[str]:
    """
    Search knowledge base via RAG API using Bearer token authentication.
    
    Args:
        query: User's question or search term
        
    Returns:
        List of relevant documentation snippets
    """
    if not settings.rag_api_key:
        logger.warning("[RAG] RAG_API_KEY not configured, cannot search knowledge base")
        return []
    
    if not query or not query.strip():
        logger.warning("[RAG] Empty query provided")
        return []

    try:
        headers = {
            "Authorization": f"Bearer {settings.rag_api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "query": query,
            "top_k": 5,
        }
        
        logger.debug(f"[RAG] Searching: {query[:100]}...")
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{settings.rag_api_url}/search",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            
            if results:
                logger.info(f"[RAG] Found {len(results)} results for query")
                return results
            else:
                logger.debug("[RAG] No results found")
                return []

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.error("[RAG] Authentication failed - invalid API key")
        else:
            logger.error(f"[RAG] HTTP error {e.response.status_code}: {e.response.text}")
        return []
        
    except httpx.TimeoutException:
        logger.error("[RAG] Request timeout (30s)")
        return []
        
    except Exception as e:
        logger.error(f"[RAG] Search failed: {e}")
        return []
import logging
import re
import time
from app.state import AgentState
from app.services.rag import search_knowledge
from app.config import settings

logger = logging.getLogger(__name__)


_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _normalize_query(text: str) -> str:
    if not text:
        return ""
    out = text
    out = _CODE_FENCE_RE.sub(" ", out)
    out = _TAG_RE.sub(" ", out)
    out = _WS_RE.sub(" ", out).strip()
    max_chars = getattr(settings, "rag_max_query_chars", 1500)
    if max_chars and len(out) > max_chars:
        out = out[:max_chars].rstrip()
    return out


def _short_query(user_message: str, issue_summary: str) -> str:
    base = (user_message or "").strip()
    if not base:
        base = (issue_summary or "").strip()
    if not base:
        return ""
    # first sentence-ish chunk
    for sep in (".", "!", "?", "\n"):
        if sep in base:
            head = base.split(sep, 1)[0].strip()
            if len(head) >= 10:
                return head
    return base[:400].strip()


def search_knowledge_node(state: AgentState) -> AgentState:
    """Search knowledge base for relevant documentation."""
    user_message = state.get("user_message", "")
    issue_description = state.get("issue_description", "")
    issue_summary = state.get("issue_summary", "")

    # Build search query from user message and/or issue description
    query_parts = []
    if user_message:
        query_parts.append(user_message)
    if issue_description:
        query_parts.append(issue_description)

    query = _normalize_query(" ".join(query_parts))

    if not query:
        logger.warning("No query content for knowledge search")
        return {**state, "rag_results": []}

    try:
        logger.info(f"Searching knowledge base (query len={len(query)})")
        t0 = time.monotonic()
        results = search_knowledge(query) or []

        if not results:
            short_q = _normalize_query(_short_query(user_message, issue_summary))
            if short_q and short_q != query:
                logger.info(f"Retrying knowledge search with short query (len={len(short_q)})")
                results = search_knowledge(short_q) or []

        rag_latency_ms = int((time.monotonic() - t0) * 1000)

        if results:
            logger.info(f"Found {len(results)} RAG results in {rag_latency_ms}ms")
            logger.debug(f"Results preview: {str(results)[:200]}")
        else:
            logger.warning(f"No RAG results found for query ({rag_latency_ms}ms)")

        return {**state, "rag_results": results, "rag_latency_ms": rag_latency_ms}

    except Exception as e:
        logger.error(f"Knowledge search failed: {e}", exc_info=True)
        return {**state, "rag_results": [], "rag_latency_ms": 0}
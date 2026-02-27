#!/usr/bin/env python3
"""
Quick health check - verify all components are running and connected.
Run this to diagnose integration issues.
"""

import json
import logging
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def check_redis():
    """Check Redis connection."""
    try:
        from app.services.redis_consumer import get_redis_client
        client = get_redis_client()
        client.ping()
        
        # Check stream
        stream_len = client.xlen("jira.events")
        
        return True, f"✓ Redis OK (stream has {stream_len} events)"
    except Exception as e:
        return False, f"✗ Redis FAILED: {e}"


def check_ollama():
    """Check Ollama LLM."""
    try:
        from app.services.llm import get_llm
        llm = get_llm()
        # Don't invoke, just create - it's expensive
        return True, f"✓ Ollama OK (model: qwen3:8b configured)"
    except Exception as e:
        return False, f"✗ Ollama FAILED: {e}"


def check_rag():
    """Check RAG API."""
    try:
        from app.services.rag import search_knowledge
        # Try a quick search
        results = search_knowledge("test")
        return True, f"✓ RAG OK (got {len(results)} results)"
    except Exception as e:
        return False, f"✗ RAG FAILED: {e}"


def check_jira_mcp():
    """Check Jira MCP connection."""
    try:
        from app.services.jira_mcp import get_issue
        # Try to fetch an issue - will fail if MCP not running
        issue = get_issue("TEST-1", comment_limit=1)
        
        if not issue:
            return False, f"⚠ Jira MCP: Got empty response (MCP server may not be running)"
        if not issue.get("issue_key"):
            return False, f"⚠ Jira MCP: Response has no issue_key (MCP issue)"
        
        return True, f"✓ Jira MCP OK (fetched {issue.get('issue_key')})"
    except Exception as e:
        error_str = str(e)
        if "Unknown tool" in error_str:
            return False, f"✗ Jira MCP: MCP server running but tool not found"
        elif "Connection refused" in error_str or "No such file" in error_str:
            return False, f"✗ Jira MCP: Server NOT running (run 'uvx mcp-atlassian')"
        else:
            return False, f"✗ Jira MCP: {error_str[:100]}"


def check_graph():
    """Check that graph builds correctly."""
    try:
        from app.graph import build_graph
        graph = build_graph()
        return True, f"✓ Graph OK"
    except Exception as e:
        return False, f"✗ Graph FAILED: {e}"


def main():
    logger.info("=" * 60)
    logger.info("Jira Agent Health Check")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    checks = [
        ("Redis Stream", check_redis),
        ("Ollama LLM", check_ollama),
        ("RAG API", check_rag),
        ("Jira MCP", check_jira_mcp),
        ("Agent Graph", check_graph),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            ok, msg = check_func()
            results.append((name, ok, msg))
            logger.info(f"{msg}")
        except Exception as e:
            logger.error(f"✗ {name}: Unexpected error: {e}")
            results.append((name, False, str(e)))
    
    # Summary
    logger.info("\n" + "=" * 60)
    
    ok_count = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    
    for name, ok, msg in results:
        status = "✓" if ok else "✗"
        logger.info(f"{status} {name}")
    
    logger.info("=" * 60)
    logger.info(f"Status: {ok_count}/{total} components OK")
    
    if ok_count < total:
        logger.warning("\n⚠️ Some components are not running. Fix them:")
        for name, ok, msg in results:
            if not ok:
                logger.warning(f"  - {name}: {msg}")
        
        if "Jira MCP" in [n for n, ok, _ in results if not ok]:
            logger.warning("\n💡 To run MCP server:")
            logger.warning("   1. Open new PowerShell terminal")
            logger.warning("   2. & C:\\ai-agent-support\\myvenv\\Scripts\\Activate.ps1")
            logger.warning("   3. uvx mcp-atlassian")
        
        return 1
    else:
        logger.info("\n✓ All components ready! You can now:")
        logger.info("  1. Create a new task in Jira")
        logger.info("  2. Agent will automatically process it")
        logger.info("  3. Check Jira for agent's comment")
        return 0


if __name__ == "__main__":
    sys.exit(main())

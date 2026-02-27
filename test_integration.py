#!/usr/bin/env python3
"""
Integration test script for Jira agent.
Tests basic connectivity and flow without running the full main loop.
"""

import json
import logging
import sys
from app.config import settings
from app.services.redis_consumer import get_redis_client, ensure_group
from app.services.jira_mcp import get_issue, JiraIssue
from app.services.rag import search_knowledge
from app.services.llm import get_llm

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_redis_connection():
    """Test Redis connection."""
    logger.info("Testing Redis connection...")
    try:
        client = get_redis_client()
        client.ping()
        logger.info("✓ Redis connection OK")
        return True
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        return False


def test_redis_group():
    """Test Redis consumer group."""
    logger.info("Testing Redis consumer group...")
    try:
        client = get_redis_client()
        ensure_group(client)
        logger.info("✓ Redis consumer group OK")
        return True
    except Exception as e:
        logger.error(f"✗ Redis consumer group failed: {e}")
        return False


def test_jira_connection():
    """Test Jira MCP connection with a real issue."""
    logger.info("Testing Jira MCP connection...")
    try:
        # Try to fetch a test issue
        issue = get_issue("TEST-1", comment_limit=5)
        
        if not isinstance(issue, dict):
            logger.error(f"✗ Expected dict, got {type(issue)}")
            return False
        
        # Empty dict means MCP server is not responding properly
        if not issue or not issue.get("issue_key"):
            logger.warning("⚠ MCP server may not be running")
            logger.info("   To test Jira integration, run MCP server in another terminal:")
            logger.info("   uvx mcp-atlassian")
            return False
        
        # Check basic fields
        required_fields = ["issue_key", "summary"]
        missing = [f for f in required_fields if f not in issue]
        
        if missing:
            logger.error(f"✗ Missing fields: {missing}")
            return False
        
        logger.info(f"✓ Jira connection OK - fetched {issue.get('issue_key', 'unknown')}")
        logger.info(f"  Summary: {issue.get('summary', 'N/A')[:60]}")
        return True
    except Exception as e:
        logger.warning(f"⚠ Jira MCP test skipped: {e}")
        logger.info("   To run this test, start MCP server:")
        logger.info("   uvx mcp-atlassian")
        return False


def test_rag_connection():
    """Test RAG API connection."""
    logger.info("Testing RAG API connection...")
    try:
        results = search_knowledge("test")
        logger.info(f"✓ RAG connection OK - got {len(results) if results else 0} result(s)")
        if results:
            logger.info(f"  Sample: {str(results[0])[:100]}")
        return True
    except Exception as e:
        logger.error(f"✗ RAG connection failed: {e}")
        return False


def test_llm_connection():
    """Test LLM (Ollama) connection."""
    logger.info("Testing LLM connection...")
    try:
        llm = get_llm()
        response = llm.invoke("Say 'OK' in Russian")
        
        if hasattr(response, 'content'):
            text = response.content.strip()
        else:
            text = str(response).strip()
        
        logger.info(f"✓ LLM connection OK")
        logger.info(f"  Response: {text[:50]}")
        return True
    except Exception as e:
        logger.error(f"✗ LLM connection failed: {e}")
        return False


def test_event_format():
    """Test JSON event parsing."""
    logger.info("Testing event format parsing...")
    try:
        # Simulate webhook event
        test_event = {
            "issue_key": "TEST-123",
            "event_type": "issue_created",
            "payload": '{"issue_key": "TEST-123", "summary": "Test issue", "description": "Description"}'
        }
        
        # Parse payload like main.py does
        payload = test_event.get("payload", "{}")
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        assert payload.get("issue_key") == "TEST-123"
        logger.info("✓ Event format parsing OK")
        return True
    except Exception as e:
        logger.error(f"✗ Event format parsing failed: {e}")
        return False


def main():
    logger.info("=" * 60)
    logger.info("Jira Agent Integration Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Redis Connection", test_redis_connection),
        ("Redis Consumer Group", test_redis_group),
        ("Event Format Parsing", test_event_format),
        ("LLM (Ollama) Connection", test_llm_connection),
        ("RAG API Connection", test_rag_connection),
        ("Jira MCP Connection", test_jira_connection),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"Test '{name}' crashed: {e}")
            results.append((name, False))
        logger.info("")
    
    # Summary
    logger.info("=" * 60)
    logger.info("Test Summary:")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status:8} | {name}")
    
    logger.info("=" * 60)
    logger.info(f"Result: {passed}/{total} tests passed")
    logger.info("=" * 60)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

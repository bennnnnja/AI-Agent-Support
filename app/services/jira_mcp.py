import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings


def _server_params() -> StdioServerParameters:
    env = {**os.environ, "JIRA_URL": settings.jira_url}
    if settings.jira_token:
        env["JIRA_PERSONAL_TOKEN"] = settings.jira_token
    return StdioServerParameters(command="uvx", args=["mcp-atlassian"], env=env)


async def _call(tool: str, args: dict) -> str:
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            return result.content[0].text if result.content else ""


def get_issue(issue_key: str) -> str:
    return asyncio.run(_call("get_issue", {"issue_key": issue_key, "comment_limit": 0}))


def add_comment(issue_key: str, comment: str) -> None:
    asyncio.run(_call("add_comment", {"issue_key": issue_key, "comment": comment}))
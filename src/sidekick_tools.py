"""
Tools used by the Sidekick agent (browser, search, files, notifications).

Steps (called from sidekick.py at setup):
  1. playwright_tools(): start Playwright, launch Chromium, return browser toolkit tools + browser + playwright handle.
  2. other_tools(): build file, search, Wikipedia, and push tools; return combined list.
  3. Sidekick merges both lists and passes them to the worker LLM and ToolNode.
The LLM chooses which tools to call each step; descriptions below guide that choice.
"""
from playwright.async_api import async_playwright
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from dotenv import load_dotenv
import os
import requests
from langchain_core.tools import StructuredTool
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_experimental.tools import PythonREPLTool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper

# --- Config (Pushover + Serper from .env) ---
load_dotenv(override=True)
pushover_token = os.getenv("PUSHOVER_TOKEN")
pushover_user = os.getenv("PUSHOVER_USER")
pushover_url = "https://api.pushover.net/1/messages.json"
serper = GoogleSerperAPIWrapper()


async def playwright_tools():
    """Start Playwright, launch Chromium; return (browser toolkit tools, browser, playwright) for Sidekick to hold and pass to ToolNode."""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
    return toolkit.get_tools(), browser, playwright


def push(text: str):
    """Send a push notification via Pushover. Used when the agent wants to notify the user (e.g. task done)."""
    requests.post(pushover_url, data={"token": pushover_token, "user": pushover_user, "message": text})
    return "success"


def get_file_tools():
    """Return file read/write/list tools scoped to the sandbox/ directory."""
    toolkit = FileManagementToolkit(root_dir="sandbox")
    return toolkit.get_tools()


async def other_tools():
    """Build and return non-browser tools: file, web search, Wikipedia, push. (Python REPL optional.)"""

    # Push notification tool. Used to send a push notification via Pushover.
    push_tool = StructuredTool.from_function(
        func=push,
        name="send_push_notification",
        description="Use this tool when you want to send a push notification",
    )

    # File tools. Used to read/write/list files under the sandbox/ directory.
    file_tools = get_file_tools()

    # Search tool. Used to get the results of an online web search.
    tool_search = StructuredTool.from_function(
        func=serper.run,
        name="search",
        description="Use this tool when you want to get the results of an online web search",
    )

    # Wikipedia tool. Used to look up encyclopedic facts (definitions, summaries).
    wikipedia = WikipediaAPIWrapper()
    wiki_tool = WikipediaQueryRun(api_wrapper=wikipedia)

    # Python REPL - comment to avoid any unintended execution because its not running in docker container
    # so it might cause some security issues if it is not properly configured and executed locally.
    python_repl = PythonREPLTool()

    return file_tools + [push_tool, tool_search, python_repl, wiki_tool]


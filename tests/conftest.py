"""Pytest fixtures and config for ai-sidekick tests."""
import pytest
from langchain_core.messages import AIMessage, HumanMessage


@pytest.fixture
def state_with_tool_calls():
    """State where last message has tool_calls (worker_router should return 'tools')."""
    return {
        "messages": [
            HumanMessage(content="Search for X"),
            AIMessage(content="", tool_calls=[{"name": "search", "args": {"query": "X"}, "id": "1"}]),
        ],
        "success_criteria": "Find X",
        "feedback_on_work": None,
        "success_criteria_met": False,
        "user_input_needed": False,
    }


@pytest.fixture
def state_without_tool_calls():
    """State where last message has no tool_calls (worker_router should return 'evaluator')."""
    return {
        "messages": [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
        ],
        "success_criteria": "Be helpful",
        "feedback_on_work": None,
        "success_criteria_met": False,
        "user_input_needed": False,
    }


@pytest.fixture
def state_done():
    """State where evaluator said success_criteria_met (route should return END)."""
    return {
        "messages": [],
        "success_criteria": "Done",
        "feedback_on_work": "Good",
        "success_criteria_met": True,
        "user_input_needed": False,
    }


@pytest.fixture
def state_user_input_needed():
    """State where evaluator said user_input_needed (route should return END)."""
    return {
        "messages": [],
        "success_criteria": "Done",
        "feedback_on_work": None,
        "success_criteria_met": False,
        "user_input_needed": True,
    }


@pytest.fixture
def state_retry():
    """State where evaluator said not done and no user input (route should return worker)."""
    return {
        "messages": [],
        "success_criteria": "Do X",
        "feedback_on_work": "You missed Y",
        "success_criteria_met": False,
        "user_input_needed": False,
    }

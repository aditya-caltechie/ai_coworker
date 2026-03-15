"""Unit tests for sidekick.py (routers, format_conversation, schema). No LLM or Playwright."""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from sidekick import Sidekick, EvaluatorOutput, State


class TestWorkerRouter:
    """Tests for worker_router: routes to 'tools' or 'evaluator' based on last message."""

    def test_returns_tools_when_last_message_has_tool_calls(self, state_with_tool_calls):
        sk = Sidekick()
        assert sk.worker_router(state_with_tool_calls) == "tools"

    def test_returns_evaluator_when_last_message_has_no_tool_calls(self, state_without_tool_calls):
        sk = Sidekick()
        assert sk.worker_router(state_without_tool_calls) == "evaluator"

    def test_returns_evaluator_when_last_message_has_empty_tool_calls(self):
        sk = Sidekick()
        state = {
            "messages": [HumanMessage(content="Hi"), AIMessage(content="", tool_calls=[])],
            "success_criteria": "X",
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
        }
        assert sk.worker_router(state) == "evaluator"


class TestRouteBasedOnEvaluation:
    """Tests for route_based_on_evaluation: routes to END or worker (retry)."""

    def test_returns_end_when_success_criteria_met(self, state_done):
        sk = Sidekick()
        assert sk.route_based_on_evaluation(state_done) == "END"

    def test_returns_end_when_user_input_needed(self, state_user_input_needed):
        sk = Sidekick()
        assert sk.route_based_on_evaluation(state_user_input_needed) == "END"

    def test_returns_worker_when_retry_needed(self, state_retry):
        sk = Sidekick()
        assert sk.route_based_on_evaluation(state_retry) == "worker"


class TestFormatConversation:
    """Tests for format_conversation: turns messages into plain text for evaluator."""

    def test_formats_human_and_ai_messages(self):
        sk = Sidekick()
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
        ]
        out = sk.format_conversation(messages)
        assert "User: Hello" in out
        assert "Assistant: Hi there!" in out
        assert out.startswith("Conversation history:")

    def test_ai_message_without_content_shows_tools_use(self):
        sk = Sidekick()
        messages = [HumanMessage(content="Search"), AIMessage(content="")]
        out = sk.format_conversation(messages)
        assert "[Tools use]" in out


class TestEvaluatorOutput:
    """Tests for EvaluatorOutput Pydantic model."""

    def test_parses_valid_output(self):
        out = EvaluatorOutput(
            feedback="Looks good.",
            success_criteria_met=True,
            user_input_needed=False,
        )
        assert out.feedback == "Looks good."
        assert out.success_criteria_met is True
        assert out.user_input_needed is False

    def test_parses_retry_case(self):
        out = EvaluatorOutput(
            feedback="Add more detail.",
            success_criteria_met=False,
            user_input_needed=False,
        )
        assert out.feedback == "Add more detail."
        assert out.success_criteria_met is False
        assert out.user_input_needed is False


class TestState:
    """State is a TypedDict; we only check it accepts expected keys."""

    def test_state_can_be_constructed_with_expected_keys(self):
        state: State = {
            "messages": [],
            "success_criteria": "Be clear",
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
        }
        assert state["success_criteria"] == "Be clear"
        assert state["messages"] == []

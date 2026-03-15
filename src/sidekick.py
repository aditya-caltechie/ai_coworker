"""
Sidekick agent: LangGraph workflow (worker + tools + evaluator + memory + retry).

Code flow / steps:
  1. setup(): Load tools (playwright + other_tools), bind worker LLM to tools, create evaluator LLM with structured output, build_graph() and compile with MemorySaver.
  2. build_graph(): Define State, add nodes (worker, tools, evaluator), add conditional edges (worker_router, route_based_on_evaluation), START→worker, compile with checkpointer.
  3. run_superstep(message, success_criteria, history): Build initial state, graph.ainvoke(state, thread_id); return history + [user, reply, evaluator_feedback] for UI.
  4. Inside the graph: worker runs (optionally calls tools); worker_router sends to tools or evaluator; tools→worker loop until no tool_calls; evaluator runs; route_based_on_evaluation sends to END or back to worker (retry).
"""
from typing import Annotated, List, Any, Optional, Dict
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sidekick_tools import playwright_tools, other_tools
import uuid
import asyncio
from datetime import datetime

load_dotenv(override=True)


# --- Graph state and evaluator output schema ---
class State(TypedDict):
    """Shared state for the graph: messages (with add_messages merge), success_criteria, evaluator feedback and flags."""
    messages: Annotated[List[Any], add_messages]
    success_criteria: str
    feedback_on_work: Optional[str]
    success_criteria_met: bool
    user_input_needed: bool


# Evaluator output schema.
# Its used to parse the output of the evaluator LLM.
# It contains the feedback on the assistant's response, whether the success criteria have been met, and whether more input is needed from the user.
class EvaluatorOutput(BaseModel):
    """Structured output from the evaluator LLM: feedback text and two booleans for routing."""
    feedback: str = Field(description="Feedback on the assistant's response")
    success_criteria_met: bool = Field(description="Whether the success criteria have been met")
    user_input_needed: bool = Field(
        description="True if more input is needed from the user, or clarifications, or the assistant is stuck"
    )


# Sidekick class.
# Its used to hold the tools, worker LLM, evaluator LLM, compiled graph, and memory.
# It also runs one superstep per user message.
class Sidekick:
    """Holds tools, worker LLM, evaluator LLM, compiled graph, and memory; runs one superstep per user message."""

    def __init__(self):
        self.worker_llm_with_tools = None
        self.evaluator_llm_with_output = None
        self.tools = None
        self.llm_with_tools = None
        self.graph = None
        self.sidekick_id = str(uuid.uuid4())
        self.memory = MemorySaver()
        self.browser = None
        self.playwright = None

    async def setup(self):
        """Load tools (playwright + other), bind worker LLM to tools, create evaluator LLM, build and compile graph."""
        self.tools, self.browser, self.playwright = await playwright_tools()
        self.tools += await other_tools()
        worker_llm = ChatOpenAI(model="gpt-4o-mini")
        self.worker_llm_with_tools = worker_llm.bind_tools(self.tools)
        evaluator_llm = ChatOpenAI(model="gpt-4o-mini")
        self.evaluator_llm_with_output = evaluator_llm.with_structured_output(EvaluatorOutput)
        await self.build_graph()

    # Worker node.
    # Its used to build the system prompt, invoke the worker LLM with messages, and return the new messages.
    def worker(self, state: State) -> Dict[str, Any]:
        """Build system prompt (success_criteria + optional feedback_on_work), invoke worker LLM with messages; return new messages."""
        system_message = f"""You are a helpful assistant that can use tools to complete tasks.
    You keep working on a task until either you have a question or clarification for the user, or the success criteria is met.
    You have many tools to help you, including tools to browse the internet, navigating and retrieving web pages.
    You have a tool to run python code, but note that you would need to include a print() statement if you wanted to receive output.
    The current date and time is {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    This is the success criteria:
    {state["success_criteria"]}
    You should reply either with a question for the user about this assignment, or with your final response.
    If you have a question for the user, you need to reply by clearly stating your question. An example might be:

    Question: please clarify whether you want a summary or a detailed answer

    If you've finished, reply with the final answer, and don't ask a question; simply reply with the answer.
    """

        if state.get("feedback_on_work"):
            system_message += f"""
    Previously you thought you completed the assignment, but your reply was rejected because the success criteria was not met.
    Here is the feedback on why this was rejected:
    {state["feedback_on_work"]}
    With this feedback, please continue the assignment, ensuring that you meet the success criteria or have a question for the user."""

        # Ensure system message is in conversation (inject or update)
        found_system_message = False
        messages = state["messages"]
        for message in messages:
            if isinstance(message, SystemMessage):
                message.content = system_message
                found_system_message = True

        if not found_system_message:
            messages = [SystemMessage(content=system_message)] + messages

        response = self.worker_llm_with_tools.invoke(messages)
        return {
            "messages": [response],
        }

    # Worker router.
    # Its used to determine the next node to run.
    # If the last message has tool_calls, then we need to run the tools node.
    # If the last message does not have tool_calls, then we need to run the evaluator node.
    # This is needed to ensure that the worker node is only run if it has not already completed the task.
    def worker_router(self, state: State) -> str:
        """After worker: if last message has tool_calls → 'tools', else → 'evaluator'."""
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "evaluator"

    def format_conversation(self, messages: List[Any]) -> str:
        """Turn message list into a plain-text conversation string for the evaluator prompt."""
        conversation = "Conversation history:\n\n"
        for message in messages:
            if isinstance(message, HumanMessage):
                conversation += f"User: {message.content}\n"
            elif isinstance(message, AIMessage):
                text = message.content or "[Tools use]"
                conversation += f"Assistant: {text}\n"
        return conversation

    # Evaluator node.
    # Its used to evaluate the assistant's response based on the success criteria.
    # It returns the feedback on the assistant's response, whether the success criteria have been met, and whether more input is needed from the user.
    def evaluator(self, state: State) -> State:
        """Run evaluator LLM on last response vs success_criteria; return state update with feedback, success_criteria_met, user_input_needed."""
        last_response = state["messages"][-1].content

        system_message = """You are an evaluator that determines if a task has been completed successfully by an Assistant.
    Assess the Assistant's last response based on the given criteria. Respond with your feedback, and with your decision on whether the success criteria has been met,
    and whether more input is needed from the user."""

        user_message = f"""You are evaluating a conversation between the User and Assistant. You decide what action to take based on the last response from the Assistant.

    The entire conversation with the assistant, with the user's original request and all replies, is:
    {self.format_conversation(state["messages"])}

    The success criteria for this assignment is:
    {state["success_criteria"]}

    And the final response from the Assistant that you are evaluating is:
    {last_response}

    Respond with your feedback, and decide if the success criteria is met by this response.
    Also, decide if more user input is required, either because the assistant has a question, needs clarification, or seems to be stuck and unable to answer without help.

    The Assistant has access to a tool to write files. If the Assistant says they have written a file, then you can assume they have done so.
    Overall you should give the Assistant the benefit of the doubt if they say they've done something. But you should reject if you feel that more work should go into this.

    """
        if state["feedback_on_work"]:
            user_message += f"Also, note that in a prior attempt from the Assistant, you provided this feedback: {state['feedback_on_work']}\n"
            user_message += "If you're seeing the Assistant repeating the same mistakes, then consider responding that user input is required."

        evaluator_messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_message),
        ]

        eval_result = self.evaluator_llm_with_output.invoke(evaluator_messages)
        new_state = {
            "messages": [
                {
                    "role": "assistant",
                    "content": f"Evaluator Feedback on this answer: {eval_result.feedback}",
                }
            ],
            "feedback_on_work": eval_result.feedback,
            "success_criteria_met": eval_result.success_criteria_met,
            "user_input_needed": eval_result.user_input_needed,
        }
        return new_state

    # --- Route based on evaluation ---
    # Its needed to determine the next node to run.
    # If the success criteria are met or the user input is needed, then we need to end the run.
    # If the success criteria are not met and the user input is not needed, then we need to run the worker node again.
    # This is needed to ensure that the run is only ended if the success criteria are met or the user input is needed.
    def route_based_on_evaluation(self, state: State) -> str:
        """After evaluator: if success_criteria_met or user_input_needed → END, else → worker (retry)."""
        if state["success_criteria_met"] or state["user_input_needed"]:
            return "END"
        return "worker"

    # Build the graph.
    # Its used to create the StateGraph, add the nodes, add the edges, and compile the graph with the memory.
    async def build_graph(self):
        """Create StateGraph with worker, tools, evaluator; wire conditional edges and compile with MemorySaver."""
        graph_builder = StateGraph(State)

        # Add nodes
        graph_builder.add_node("worker", self.worker)
        graph_builder.add_node("tools", ToolNode(tools=self.tools))
        graph_builder.add_node("evaluator", self.evaluator)

        # Add edges
        graph_builder.add_conditional_edges(
            "worker", self.worker_router, {"tools": "tools", "evaluator": "evaluator"}
        )
        graph_builder.add_edge("tools", "worker")
        graph_builder.add_conditional_edges(
            "evaluator", self.route_based_on_evaluation, {"worker": "worker", "END": END}
        )
        graph_builder.add_edge(START, "worker")

        # Compile the graph
        self.graph = graph_builder.compile(checkpointer=self.memory)

    # Run the superstep. Its used to invoke the graph with the initial state.
    # It returns the chat history + [user, reply, evaluator_feedback] for the UI.
    async def run_superstep(self, message, success_criteria, history):
        """Run graph.ainvoke with initial state; return chat history + [user, reply, evaluator_feedback] for UI."""
        config = {"configurable": {"thread_id": self.sidekick_id}}

        state = {
            "messages": message,
            "success_criteria": success_criteria or "The answer should be clear and accurate",
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
        }

        # Invoke the graph with the initial state
        result = await self.graph.ainvoke(state, config=config)
        user = {"role": "user", "content": message}
        reply = {"role": "assistant", "content": result["messages"][-2].content}
        feedback = {"role": "assistant", "content": result["messages"][-1].content}
        return history + [user, reply, feedback]

    def cleanup(self):
        """Close browser and playwright (called when Sidekick is removed from UI state)."""
        if self.browser:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.browser.close())
                if self.playwright:
                    loop.create_task(self.playwright.stop())
            except RuntimeError:
                # No event loop (e.g. sync context): run cleanup directly
                asyncio.run(self.browser.close())
                if self.playwright:
                    asyncio.run(self.playwright.stop())

# ai-sidekick

[![CI](https://github.com/aditya-caltechie/ai-sidekick/actions/workflows/ci.yml/badge.svg)](https://github.com/aditya-caltechie/ai-sidekick/actions)

**Sidekick** is an AI-powered “personal co-worker” that takes your request and optional **success criteria**, then works autonomously until it meets those criteria (or needs your input). It pairs a **tool-using worker** model with a separate **evaluator** model that checks results against your criteria, enabling a retry loop that improves answers until they pass.

## Why Sidekick (vs. a chat box)

You provide a **task** and (optionally) **success criteria**. The worker can use real tools (browser, search, files, Python, notifications) in a loop. When the worker produces a final response, the evaluator checks it against your criteria and either:

- **Ends** (criteria met), or
- **Requests input** (missing info / ambiguity), or
- **Retries** (sends the worker back with specific feedback).

## Key capabilities

- **Autonomous tool use**: browsing with Playwright, optional web search, Wikipedia lookups, Python execution, file read/write (scoped), and optional push notifications.
- **Criteria-driven completion**: success criteria are part of the state and enforced by an evaluator, not just “best effort” prompting.
- **Checkpointed runs**: conversation state is persisted per thread via a checkpointer so the graph can loop deterministically within a run.
- **Simple UI**: a Gradio app to run tasks with visible evaluator feedback.

## Quickstart

### Prerequisites

- **Python**: 3.12+
- **Package manager**: [uv](https://docs.astral.sh/uv/)
- **Browser tooling (recommended)**: Playwright (Chromium)

### Install and run

```bash
# from repo root
uv sync --all-groups
uv run playwright install chromium

# required
export OPENAI_API_KEY="..."

uv run src/app.py
```

Open the printed local URL (typically `http://127.0.0.1:7860`).

---

## How it works

```mermaid
flowchart TB
    subgraph UI
        Gradio[Gradio UI\nmessage + success criteria\nReset / Go]
    end
    subgraph Sidekick
        Graph[LangGraph]
        Worker[worker node\nLLM + tools]
        Tools[tools node\nPlaywright, search, file, push, ...]
        Eval[evaluator node\nstructured output]
        Memory[MemorySaver\ncheckpointer]
    end
    Gradio -->|run_superstep| Graph
    Graph --> Worker
    Worker -->|tool_calls| Tools
    Worker -->|no tool_calls| Eval
    Tools --> Worker
    Eval -->|success or user_input_needed| END
    Eval -->|retry| Worker
    Graph --> Memory
```

### Control loop (conceptual)

- **Worker node**: generates actions and may call tools.
- **Tools node**: executes tool calls and returns results to the worker.
- **Evaluator node**: checks the final worker response against success criteria, producing structured feedback.
- **Routing**: the run ends when criteria are met or user input is required; otherwise the worker retries with evaluator feedback.

---

## Tech stack

| Layer | Tech |
|-------|------|
| **Orchestration** | LangGraph (state graph, conditional edges, checkpointer) |
| **LLM** | OpenAI (ChatOpenAI, gpt-4o-mini) via LangChain |
| **Tools** | LangChain (StructuredTool, toolkits), Playwright, Serper API, Pushover, Wikipedia |
| **Memory** | LangGraph MemorySaver (in-process checkpointer) |
| **UI** | Gradio |
| **Observability** | LangSmith (optional tracing) |
| **Package / run** | uv, Python ≥3.12 |

---

## Configuration

| Item | Notes |
|------|--------|
| **OPENAI_API_KEY** | Required. Used by worker and evaluator. |
| **SERPER_API_KEY** | Optional. Enables web search when set; otherwise the search tool is omitted. |
| **PUSHOVER_TOKEN**, **PUSHOVER_USER** | Optional. Enables push notifications when set. |
| **Playwright** | Run `uv run playwright install chromium` after `uv sync` if you use browser tasks. |
| **LangSmith** | Set `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_PROJECT`, `LANGCHAIN_API_KEY` to trace runs. |

---

## Development

### Run tests

Tests are isolated (no real LLM or Playwright); external calls are mocked.

```bash
uv run pytest tests/ -v
```

### Repository map

For a contributor-oriented overview (what lives where, how to run locally, common pitfalls), see `AGENTS.md`.

## Security and safety model

- **Filesystem access is scoped**: file tools are restricted to `sandbox/` (by design).
- **Optional integrations**: search and push notifications are only enabled when their environment variables are present.

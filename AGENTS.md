# AGENTS — Project overview (ai-sidekick)

This document is a **contributor-oriented map** of this repo: where things live, what each module does, and how to run and test.

---

## Repository layout

```
ai-sidekick/
├── README.md
├── AGENTS.md                 # This file
├── .gitignore
├── .python-version
├── pyproject.toml            # Dependencies, pytest config; run uv sync from repo root
├── uv.lock
├── .github/
│   └── workflows/
│       └── ci.yml            # CI: uv sync, pytest
├── docs/
│   ├── BASICS.md            # LangGraph basics, five steps, tools/memory/loop
│   ├── HLD.md               # High-level design: graph, state, tools, evaluator, retry
│   ├── DEMO.md              # Demo 1–4 walkthroughs (CNN, math, Python code, restaurant + traces)
│   ├── OBSERVABILITY.md     # LangSmith tracing, tool usage, how it helps
│   └── demo/                # Screenshots for DEMO.md and OBSERVABILITY.md
├── sandbox/                  # File tools (read/write/list) are scoped here
│   └── dinner.md            # Example output (e.g. Demo 4 restaurant report)
├── src/                     # Application and agent code
│   ├── app.py               # Gradio UI entrypoint; setup Sidekick, process_message, reset
│   ├── sidekick.py          # Sidekick class, LangGraph (worker, tools, evaluator), State, EvaluatorOutput
│   └── sidekick_tools.py    # Tools: playwright_tools, other_tools (search, file, push, wiki, REPL)
└── tests/
    ├── __init__.py
    ├── conftest.py          # Fixtures (state with/without tool_calls)
    ├── test_sidekick.py     # worker_router, route_based_on_evaluation, format_conversation, State, EvaluatorOutput
    └── test_sidekick_tools.py # push, get_file_tools, other_tools (mocked)
```

Notes:

- Run everything from the **repo root**. Use `uv run ...` so the `src` package is on the path (pyproject.toml / pytest set `pythonpath = ["src"]`).
- After `uv sync`, install Playwright for browser tools: `uv run playwright install chromium`.

---

## Key components (where to start reading)

- **Entrypoint (run app)**: `src/app.py`
  - `setup()`: create `Sidekick()`, call `await sidekick.setup()` (load tools, build graph), store in Gradio state.
  - `process_message()`: call `sidekick.run_superstep(message, success_criteria, history)` and append reply + evaluator feedback to chat.
  - `reset()`: new Sidekick, clear inputs and chat. `free_resources()`: cleanup browser/playwright.

- **Agent and graph**: `src/sidekick.py`
  - **Sidekick**: holds tools, worker LLM (with tools), evaluator LLM (structured output), compiled graph, `MemorySaver` (checkpointer), optional browser/playwright.
  - **setup()**: `playwright_tools()` + `other_tools()` → merge tool list; bind worker to tools; evaluator with `EvaluatorOutput`; `build_graph()` and compile with checkpointer.
  - **build_graph()**: `State` (messages, success_criteria, feedback_on_work, success_criteria_met, user_input_needed). Nodes: **worker**, **tools** (ToolNode), **evaluator**. Edges: START→worker; worker→tools or evaluator via **worker_router**; tools→worker; evaluator→END or worker via **route_based_on_evaluation**.
  - **run_superstep()**: build initial state from message + success_criteria + history, `graph.ainvoke(state, thread_id=sidekick_id)`, return history + user message + assistant reply + evaluator feedback.

- **Tools**: `src/sidekick_tools.py`
  - **playwright_tools()**: start Playwright, launch Chromium, return PlayWrightBrowserToolkit tools + browser + playwright (used by Sidekick for cleanup).
  - **other_tools()**: file tools (`FileManagementToolkit`, root_dir=`sandbox`), push (Pushover), search (Serper, only if `SERPER_API_KEY` set), Wikipedia, Python REPL. All returned as one list for the worker.

- **Tests**: `tests/`
  - No LLM or real Playwright in tests; push and HTTP are mocked. Run with `uv run pytest tests/ -v` from repo root.

---

## Configuration & environment variables

Use a `.env` in the repo root (or export). Main keys:

| Variable              | Used by           | Purpose |
|-----------------------|-------------------|--------|
| `OPENAI_API_KEY`      | Worker, evaluator | ChatOpenAI (gpt-4o-mini) |
| `SERPER_API_KEY`      | sidekick_tools    | Web search tool (optional; omit for CI/tests) |
| `PUSHOVER_TOKEN`      | push tool         | Pushover API token |
| `PUSHOVER_USER`       | push tool         | Pushover user key |
| `LANGCHAIN_TRACING_V2`| LangSmith         | Set `true` to trace runs |
| `LANGCHAIN_PROJECT`   | LangSmith         | Project name in LangSmith |
| `LANGCHAIN_API_KEY`   | LangSmith         | LangSmith API key |

---

## Running locally

### Install dependencies

From repo root:

```bash
uv sync --all-groups
uv run playwright install chromium
```

### Run the app

```bash
uv run src/app.py
```

Then open the URL (e.g. http://127.0.0.1:7860).

### Run tests

```bash
uv run pytest tests/ -v
```

---

## Common pitfalls

- **`ModuleNotFoundError` for `sidekick` / `sidekick_tools`**: Run with `uv run` from repo root so `src` is on `PYTHONPATH` (pyproject.toml sets this for pytest; for `uv run src/app.py` the runner adds it).

- **`GoogleSerperAPIWrapper` validation error**: The search tool is only created when `SERPER_API_KEY` is set. For CI or headless runs without search, leave it unset; tests and app still work (search tool is simply omitted).

- **Playwright "Executable doesn't exist"**: After `uv sync`, run `uv run playwright install chromium`. On some Macs only Chromium is reliable; skip WebKit if it fails.

- **Gradio theme / Chatbot `type`**: This project uses Gradio 5.x/6.x; `theme` is passed to `launch()`, and `gr.Chatbot` is used without `type="messages"` to avoid compatibility issues.

- **Lockfile out of date in CI**: If `uv sync --locked --all-groups` fails, run `uv lock` locally (with dev deps) and commit the updated `uv.lock`.
